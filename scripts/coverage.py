#!/usr/bin/env python3
"""Find body text our own pass read but GROBID's document does not contain.

GROBID loses prose silently, most often where a paragraph runs across a page
turn: the page ends mid-sentence and the continuation never appears. On one
refined paper that cost a full printed page of Methods. Nothing flagged it — the
sections were all present, so the page looked complete.

Our layout pass has that text. The two documents cannot be compared page by
page, because GROBID's nodes carry no page number, so this compares by content
instead: every sentence our pass read is looked for in GROBID's text, and the
misses are reported against the page they came from. Sentences are matched on a
normalised word shingle, so the two passes' differing hyphenation, spacing and
glyph repairs do not register as absences.

    python3 scripts/coverage.py                  every GROBID-built paper
    python3 scripts/coverage.py --slug SUBSTRING
    python3 scripts/coverage.py --json

Only prose and captions are compared. Our furniture, figure interiors, rotated
stamps and running heads are text GROBID is *right* to omit.
"""

import argparse
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')

# A sentence shorter than this says nothing about coverage: fragments, stray
# labels and axis ticks match by accident.
MIN_WORDS = 9
SHINGLE = 7


# Text GROBID is right to leave out of the body, which our pass did not label
# as furniture: journal boilerplate, data-availability and licence notices,
# citation lines, and the consortium author lists that some papers print in the
# middle of the document rather than on the cover.
FURNITURE = re.compile(
    r'creative commons|is licensed under|permits use, sharing|springernature|'
    r'^\s*citation\b|supplementary (information|material)|'
    r'competing interests|correspondence and requests|reprints and permission|'
    r'publisher.s note|all claims expressed|solely those of the authors|'
    r'^\s*doi:|\bdoi\.org/|\bdoi:10\.|available online at|'
    r'author contributions|data curation|writing-original draft|'
    r'received:|accepted:|published:|copyright ©|\bet al\.\s*$',
    re.I)


def looks_like_names(sentence):
    """A run of author names and superscript affiliation markers."""
    initials = len(re.findall(r'\b[A-Z]\.', sentence))
    commas = sentence.count(',')
    digits = len(re.findall(r'\d', sentence))
    tokens = re.findall(r'[A-Za-z]+', sentence)
    lower = sum(1 for t in tokens if t.islower() and len(t) > 3)
    return ((initials >= 3 or commas >= 6) and lower <= len(tokens) * 0.25
            and (digits >= 3 or initials >= 3))


def furniture(sentence):
    return bool(FURNITURE.search(sentence)) or looks_like_names(sentence)


def words(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def shingles(tokens, n=SHINGLE):
    return {' '.join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def sentences(text):
    """Rough sentence split — good enough to localise a gap to a paragraph."""
    parts = re.split(r'(?<=[.;:])\s+(?=[A-Z(\[]|\d)', text)
    return [p.strip() for p in parts if p.strip()]


def compared_nodes(doc):
    """Our nodes whose text GROBID is expected to carry."""
    out = []
    for node in doc['nodes']:
        if node['type'] not in ('prose', 'caption'):
            continue
        if node.get('role') in ('front', 'back', 'references'):
            continue
        out.append(node)
    return out


def check(slug):
    ours_path = os.path.join(CACHE, 'doc_ours', slug + '.json')
    theirs_path = os.path.join(CACHE, 'doc', slug + '.json')
    if not (os.path.exists(ours_path) and os.path.exists(theirs_path)):
        return None
    theirs = json.load(open(theirs_path, encoding='utf-8'))
    if theirs.get('source') == 'biorxiv':
        return None                      # publisher's own text; not ours to check
    ours = json.load(open(ours_path, encoding='utf-8'))

    # Compare against the rendered page, not against GROBID's document. The
    # question is whether text reaches the reader, and a page draws on more than
    # one source: an abstract GROBID truncated is printed in full from the
    # record, and comparing documents reported it as lost when it was not.
    page = os.path.join(REPO, 'papers', slug, 'index.html')
    if not os.path.exists(page):
        return None
    html = open(page, encoding='utf-8').read()
    have = shingles(words(re.sub(r'<[^>]+>', ' ', html)))

    # Score every comparable node, then judge in context. A node GROBID omits
    # entirely is usually one it files elsewhere — the author list, the
    # affiliations, the bibliography — and the run of those sits at the start or
    # the end. A dropout looks different: a *hole*, either inside a paragraph
    # that is otherwise present, or a whole paragraph with covered prose on both
    # sides of it.
    scored = []
    for node in compared_nodes(ours):
        parts = []
        for sentence in sentences(node['text']):
            tokens = words(sentence)
            if len(tokens) < MIN_WORDS or furniture(sentence):
                continue
            mine = shingles(tokens)
            if mine:
                parts.append((len(mine & have) / len(mine), sentence))
        if parts:
            covered = sum(1 for hit, _ in parts if hit >= 0.2) / len(parts)
            scored.append((node, covered, parts))

    gaps = []
    for i, (node, covered, parts) in enumerate(scored):
        before = any(c > 0.5 for _, c, _ in scored[:i])
        after = any(c > 0.5 for _, c, _ in scored[i + 1:])
        if not (before and after):
            continue                      # leading or trailing run: front/back matter
        if covered >= 0.9:
            continue
        # A wholly absent paragraph is only interesting if it is substantial;
        # a partly absent one is the page-turn signature at any length.
        missing = [s for hit, s in parts if hit < 0.2]
        if covered == 0 and sum(len(s) for s in missing) < 180:
            continue
        gaps.append({'page': node.get('page'), 'node': node['id'],
                     'kind': 'hole' if covered else 'paragraph',
                     'chars': sum(len(s) for s in missing), 'text': missing[0]})
    return {'slug': slug, 'gaps': gaps,
            'chars': sum(g['chars'] for g in gaps),
            'pages': sorted({g['page'] for g in gaps if g['page']})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', help='substring; default is every GROBID paper')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--min-chars', type=int, default=200,
                    help='only report papers missing at least this much')
    args = ap.parse_args()

    slugs = [os.path.basename(p)[:-5]
             for p in sorted(glob.glob(os.path.join(CACHE, 'doc_ours', '*.json')))]
    if args.slug:
        slugs = [s for s in slugs if args.slug.lower() in s.lower()]

    reports = [r for r in (check(s) for s in slugs) if r]
    if args.json:
        print(json.dumps(reports, indent=1, ensure_ascii=False))
        return 0

    loud = [r for r in reports if r['chars'] >= args.min_chars]
    print('%d GROBID papers checked, %d missing %d+ characters of body text'
          % (len(reports), len(loud), args.min_chars))
    for r in sorted(loud, key=lambda r: -r['chars']):
        print('\n%s' % r['slug'])
        print('  %d sentences, %d chars, pages %s'
              % (len(r['gaps']), r['chars'],
                 ', '.join(str(p) for p in r['pages'])))
        for gap in r['gaps'][:3]:
            print('    p%-3s %s' % (gap['page'], gap['text'][:120]))
    total = sum(r['chars'] for r in reports)
    print('\n%d characters across the corpus' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
