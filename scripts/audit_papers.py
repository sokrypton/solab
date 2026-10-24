#!/usr/bin/env python3
"""Find what extraction probably got wrong, per paper.

This is the work list for the refinement pass. Rather than reading 48 papers
end to end, each is scanned for the failure shapes extraction is known to have,
and only the suspect nodes are reported — with their ids, so a fix can be
written straight into edits/<slug>.json.

    python3 scripts/audit_papers.py                 every paper, worst first
    python3 scripts/audit_papers.py --slug SUBSTR   one paper, every flag
    python3 scripts/audit_papers.py --json          machine-readable

Flags are suspicions, not verdicts: a short paragraph may be a real aside, and
a heading of 90 characters may genuinely be that long.
"""

import argparse
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_DIR = os.path.join(REPO, '.cache', 'doc')
EDIT_DIR = os.path.join(REPO, 'edits')

COVER_WORD = re.compile(r'^(graphical abstract|highlights|authors?|in brief|'
                        r'correspondence|article|keywords?|editor)\b', re.I)
FIG_REF = re.compile(r'^\(?[A-H]\)|^(Fig|Figure|Table)\b', re.I)


def flags_for(node, doc):
    """Every suspicion about one node, as (code, note) pairs."""
    out = []
    text = node['text']
    words = text.split()
    kind = node['type']

    if kind == 'heading':
        if COVER_WORD.match(text):
            out.append(('cover-heading', 'issue furniture read as a heading'))
        if len(text) > 95:
            out.append(('long-heading', '%d characters' % len(text)))
        if text[:1].islower():
            out.append(('lowercase-heading', 'starts mid-sentence'))
    if kind == 'caption':
        out.append(('orphan-caption', 'caption with no artwork matched'))
    if kind == 'prose' and not node.get('role'):
        # A digit count alone cannot tell a table from a Methods paragraph:
        # buffer recipes, concentrations and instrument settings are numbers in
        # sentences. Every reviewer of these flags rejected them as real prose.
        # What a table lacks is sentences — so require that too.
        # A digit count alone cannot tell a table from a Methods paragraph:
        # buffer recipes, concentrations and instrument settings are numbers in
        # sentences, and at 18% digits this flagged 21 nodes of which one was
        # really a table. What a table lacks is sentences, so require both — no
        # sentence break at all across 40+ words, and numbers throughout.
        digits = sum(1 for w in words if any(c.isdigit() for c in w))
        if (len(words) > 40 and digits > len(words) * 0.22
                and not re.search(r'[.;:]\s+[A-Za-z(]', text)):
            out.append(('table-dump', '%d%% of words carry digits, no sentence '
                        'break' % (100 * digits / len(words))))
        if len(words) >= 25 and FIG_REF.match(text):
            out.append(('caption-as-prose', 'opens like a figure caption'))
        if 60 < len(text) < 140 and text.count('. ') == 0:
            out.append(('fragment', 'no sentence break; may be a stray line'))
        if re.search(r'/C\d{2}', text) or '\ufffd' in text:
            out.append(('glyph-artifact', 'unmapped PDF glyph'))
        if re.search(r'\{\s*i\s*\}|\bx \{', text):
            out.append(('lost-notation', 'subscript notation may have lost a '
                                         'glyph — check against the PDF'))
    if kind == 'figure':
        w, h = node.get('image_size', (0, 0))
        if w and h:
            if w < 240 or h < 180:
                out.append(('small-figure', '%dx%d px — may be cropped short'
                            % (w, h)))
            if h > w * 3.5:
                out.append(('tall-figure', '%dx%d px — may span two figures'
                            % (w, h)))
    return out


# nodes the builder does not render: flagging them would pad the work list with
# things no reader will ever see
HIDDEN = {'stamp', 'furniture', 'figure-text', 'rotated', 'small', 'empty',
          'refs-head', 'apparatus-head', 'dropped'}


def audit(doc):
    rows = []
    for node in doc['nodes']:
        if node.get('role') or node['type'] in HIDDEN:
            continue
        for code, note in flags_for(node, doc):
            rows.append({'id': node['id'], 'page': node.get('page'),
                         'type': node['type'], 'code': code, 'note': note,
                         'text': node['text'][:120]})
    return rows


def from_doc(slug):
    """Is this paper's page actually rendered from its extracted doc?

    The builder prefers JATS where a publisher provides it. Those pages carry no
    data-node attributes, which is the tell.
    """
    for page in glob.glob(os.path.join(REPO, 'papers', '*', 'index.html')):
        if os.path.basename(os.path.dirname(page)) == slug:
            return 'data-node' in open(page, encoding='utf-8').read()
    return True                    # not built yet: audit it rather than hide it


def edited_ids(slug):
    path = os.path.join(EDIT_DIR, slug + '.json')
    if not os.path.exists(path):
        return set()
    spec = json.load(open(path, encoding='utf-8'))
    return {op.get('id') for op in spec.get('ops', [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', help='only papers matching this substring')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--code', help='only this flag')
    args = ap.parse_args()

    docs = sorted(glob.glob(os.path.join(DOC_DIR, '*.json')))
    if args.slug:
        docs = [d for d in docs if args.slug.lower() in os.path.basename(d).lower()]
    # A paper whose page is built from JATS ignores its extracted doc entirely;
    # auditing it sends someone to fix nodes no reader will ever see.
    docs = [d for d in docs if from_doc(os.path.basename(d)[:-5])]

    report = []
    for path in docs:
        doc = json.load(open(path, encoding='utf-8'))
        done = edited_ids(doc['slug'])
        rows = [r for r in audit(doc) if r['id'] not in done]
        if args.code:
            rows = [r for r in rows if r['code'] == args.code]
        if rows:
            report.append({'slug': doc['slug'], 'flags': rows})

    if args.json:
        json.dump(report, sys.stdout, indent=1, ensure_ascii=False)
        return 0

    report.sort(key=lambda r: -len(r['flags']))
    counts = {}
    for paper in report:
        for row in paper['flags']:
            counts[row['code']] = counts.get(row['code'], 0) + 1
    if args.slug:
        for paper in report:
            print('\n%s' % paper['slug'])
            for row in paper['flags']:
                print('  %-17s %-9s p%-3s %s' % (row['code'], row['id'],
                                                 row['page'], row['text'][:74]))
    else:
        for paper in report:
            top = ', '.join(sorted({r['code'] for r in paper['flags']}))
            print('  %3d  %-58s %s' % (len(paper['flags']), paper['slug'][:58], top))
    print('\n%d papers flagged, %d flags total' %
          (len(report), sum(len(p['flags']) for p in report)))
    for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print('   %-18s %d' % (code, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
