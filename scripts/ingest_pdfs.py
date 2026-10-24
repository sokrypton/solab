#!/usr/bin/env python3
"""Match hand-supplied PDFs to publication entries and file them in the cache.

Filenames from publisher downloads are meaningless, so each PDF is identified
by the DOI printed inside it, falling back to a fuzzy title match against the
first two pages.

    python3 scripts/ingest_pdfs.py missing_papers/
"""

import argparse
import difflib
import json
import os
import re
import shutil
import sys

from pypdf import PdfReader

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
PDF_DIR = os.path.join(CACHE, 'pdf')

DOI_RE = re.compile(r'\b(10\.\d{4,9}/[^\s"<>,;()\[\]]+)', re.I)


def slug(rec):
    base = re.sub(r'[^A-Za-z0-9]+', '-', rec['title'])[:70].strip('-').lower()
    return '%s-%s' % (rec.get('year') or 'n-d', base or 'untitled')


def head_text(path, pages=2):
    try:
        reader = PdfReader(path)
        return '\n'.join((reader.pages[i].extract_text() or '')
                         for i in range(min(pages, len(reader.pages))))
    except Exception:
        # pypdf trips over some publishers' font descriptors; pdfminer doesn't
        try:
            from pdfminer.high_level import extract_text
            return extract_text(path, maxpages=pages) or ''
        except Exception:
            return ''


def norm(s):
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower()).split())


def identify(text, pubs):
    """(record, how) for the entry this PDF belongs to."""
    dois = {d.group(1).rstrip('.').lower() for d in DOI_RE.finditer(text)}
    for rec in pubs:
        rd = (rec.get('doi') or '').lower()
        if rd and any(d.startswith(rd) or rd.startswith(d) for d in dois):
            return rec, 'doi'

    head = norm(text[:1500])
    best, score = None, 0.0
    for rec in pubs:
        t = norm(rec['title'])
        if not t:
            continue
        # how much of the title appears verbatim near the top of the PDF
        m = difflib.SequenceMatcher(None, head, t).find_longest_match(
            0, len(head), 0, len(t))
        ratio = m.size / max(len(t), 1)
        if ratio > score:
            best, score = rec, ratio
    if best and score >= 0.6:
        return best, 'title(%.2f)' % score
    return None, 'unmatched(best=%.2f)' % score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src', help='directory of supplied PDFs')
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs_jats.json'))
    args = ap.parse_args()

    with open(args.pubs) as fh:
        pubs = json.load(fh)
    os.makedirs(PDF_DIR, exist_ok=True)

    files = sorted(f for f in os.listdir(args.src) if f.lower().endswith('.pdf'))
    matched, unmatched = [], []
    for name in files:
        path = os.path.join(args.src, name)
        text = head_text(path)
        if not text.strip():
            unmatched.append((name, 'no extractable text'))
            print('  %-46s -> no text' % name[:46], file=sys.stderr)
            continue
        rec, how = identify(text, pubs)
        if not rec:
            unmatched.append((name, how))
            print('  %-46s -> %s' % (name[:46], how), file=sys.stderr)
            continue
        dest = os.path.join(PDF_DIR, slug(rec) + '.pdf')
        shutil.copyfile(path, dest)
        matched.append((name, rec, how))
        print('  %-46s -> [%-11s] %s' % (name[:46], how, rec['title'][:44]),
              file=sys.stderr)

    print('\nfiled %d/%d' % (len(matched), len(files)), file=sys.stderr)
    if unmatched:
        print('\nnot identified:', file=sys.stderr)
        for name, why in unmatched:
            print('  %s  (%s)' % (name, why), file=sys.stderr)
    print('\nnow run: .venv/bin/python scripts/fetch_fulltext.py', file=sys.stderr)


if __name__ == '__main__':
    main()
