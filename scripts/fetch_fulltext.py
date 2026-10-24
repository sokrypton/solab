#!/usr/bin/env python3
"""Download and parse the open-access full text of the lab's papers.

Reads the metadata from fetch_pubs.py and, for every entry with a legitimate
open-access copy (bioRxiv, arXiv, PMC, publisher OA), fetches the PDF and
extracts its text. Paywalled entries are skipped and listed at the end so they
can be supplied by hand.

Everything lands in .cache/ (gitignored): article PDFs are copyrighted and do
not belong in the repo.

    python3 scripts/fetch_fulltext.py [--limit N]
"""

import argparse
import io
import json
import os
import re
import sys
import time

import requests
from pypdf import PdfReader

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
PDF_DIR = os.path.join(CACHE, 'pdf')
TXT_DIR = os.path.join(CACHE, 'text')
UA = 'solab-site-builder/0.1 (https://solab.org; mailto:kingsergey@gmail.com)'

# hosts that serve open-access PDFs directly and are happy to be fetched
OA_HOSTS = ('osti.gov', 'ipd.uw.edu', 'escholarship.org', 'infoscience.epfl.ch',
            'biorxiv.org', 'arxiv.org', 'ncbi.nlm.nih.gov', 'europepmc.org',
            'nature.com', 'science.org', 'plos.org', 'pnas.org', 'elifesciences.org',
            'mdpi.com', 'frontiersin.org', 'oup.com', 'aps.org', 'acs.org',
            'wiley.com', 'springer.com', 'cell.com', 'mlsb.io', 'neurips.cc',
            'openreview.net', 'proceedings.mlr.press')


# Repository copies that the generic resolution misses: OpenAlex points at a
# publisher landing page, but an institutional or lab-hosted PDF exists.
KNOWN_PDF = {
    '10.1038/s41586-018-0509-0':
        'https://www.osti.gov/servlets/purl/1601813',          # OSTI
    '10.1126/science.abn2100':
        'https://www.ipd.uw.edu/wp-content/uploads/2022/07/science.abn2100.pdf',
}


def slug(rec):
    base = re.sub(r'[^A-Za-z0-9]+', '-', rec['title'])[:70].strip('-').lower()
    return '%s-%s' % (rec.get('year') or 'n-d', base or 'untitled')


def pdf_candidates(rec):
    """Ordered list of URLs worth trying for a full-text PDF."""
    urls = []
    known = KNOWN_PDF.get((rec.get('doi') or '').lower())
    if known:
        urls.append(known)
    # rec['url'] is the link on the publications page itself, which for
    # workshop papers is often the PDF outright
    for u in (rec.get('pdf_url'), rec.get('oa_url'), rec.get('landing_url'),
              rec.get('url')):
        if u and u not in urls:
            urls.append(u)
    # bioRxiv landing pages have a predictable .full.pdf sibling
    doi = rec.get('doi') or ''
    if doi.startswith('10.1101/'):
        urls.append('https://www.biorxiv.org/content/%s v1.full.pdf'.replace(' ', '') % doi)
    return [u for u in urls if any(h in u for h in OA_HOSTS)]


def fetch_pdf(rec, session):
    """Return (path, note). Only stores things that are actually PDFs."""
    path = os.path.join(PDF_DIR, slug(rec) + '.pdf')
    if os.path.exists(path) and os.path.getsize(path) > 20000:
        return path, 'cached'

    for url in pdf_candidates(rec):
        try:
            r = session.get(url, timeout=60, allow_redirects=True,
                            headers={'Accept': 'application/pdf,*/*'})
        except requests.RequestException as err:
            note = 'error %s' % type(err).__name__
            continue
        ctype = r.headers.get('content-type', '')
        if r.status_code == 200 and (r.content[:5] == b'%PDF-' or 'pdf' in ctype):
            with open(path, 'wb') as fh:
                fh.write(r.content)
            time.sleep(0.4)
            return path, 'downloaded'
        note = 'http %d %s' % (r.status_code, ctype.split(';')[0] or '?')
        time.sleep(0.3)
    return None, locals().get('note', 'no open-access url')


def extract(path, rec):
    """PDF -> plain text, lightly de-hyphenated. Returns (path, words)."""
    out = os.path.join(TXT_DIR, slug(rec) + '.txt')
    if os.path.exists(out):
        with open(out) as fh:
            return out, len(fh.read().split())
    try:
        reader = PdfReader(path)
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)
    except Exception as err:                       # malformed/encrypted pdf
        # pypdf chokes on some publishers' font descriptors; pdfminer copes
        try:
            from pdfminer.high_level import extract_text as miner
            text = miner(path) or ''
        except Exception:
            return None, 'parse failed: %s' % type(err).__name__
    text = re.sub(r'-\n(\w)', r'\1', text)         # join hyphenated line breaks
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if len(text.split()) < 200:                    # scanned or image-only
        return None, 'too little text (%d words)' % len(text.split())
    with open(out, 'w') as fh:
        fh.write(text)
    return out, len(text.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs.json'))
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    with open(args.pubs) as fh:
        pubs = json.load(fh)
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(TXT_DIR, exist_ok=True)

    session = requests.Session()
    session.headers['User-Agent'] = UA

    # unresolved entries still count if the page links a PDF directly
    todo = [p for p in pubs if p.get('openalex') or (p.get('url') or '').endswith('.pdf')]
    if args.limit:
        todo = todo[:args.limit]

    got, failed = [], []
    for i, rec in enumerate(todo, 1):
        label = rec['title'][:56]
        # a hand-supplied PDF in the cache wins over anything else, including
        # for paywalled papers where there is nothing to download
        cached = os.path.join(PDF_DIR, slug(rec) + '.pdf')
        if os.path.exists(cached) and os.path.getsize(cached) > 20000:
            path, note = cached, 'supplied'
        elif not rec.get('is_oa') and not pdf_candidates(rec):
            failed.append((rec, 'not open access'))
            print('  [%2d/%d] skip     %s' % (i, len(todo), label), file=sys.stderr)
            continue
        else:
            path, note = fetch_pdf(rec, session)
        if not path:
            failed.append((rec, note))
            print('  [%2d/%d] miss %-14s %s' % (i, len(todo), note[:14], label),
                  file=sys.stderr)
            continue
        txt, words = extract(path, rec)
        if not txt:
            failed.append((rec, str(words)))
            print('  [%2d/%d] bad  %-14s %s' % (i, len(todo), str(words)[:14], label),
                  file=sys.stderr)
            continue
        rec['text_file'] = os.path.relpath(txt, REPO)
        rec['text_words'] = words
        got.append(rec)
        print('  [%2d/%d] ok %7d words  %s' % (i, len(todo), words, label),
              file=sys.stderr)

    with open(os.path.join(CACHE, 'pubs_text.json'), 'w') as fh:
        json.dump(pubs, fh, indent=1)

    print('\n--- summary ---', file=sys.stderr)
    print('full text extracted: %d/%d' % (len(got), len(todo)), file=sys.stderr)
    print('total words: %s' % f'{sum(r["text_words"] for r in got):,}', file=sys.stderr)
    if failed:
        print('\nneeds a hand (%d):' % len(failed), file=sys.stderr)
        for rec, why in failed:
            print('  - [%-22s] %s' % (why[:22], rec['title'][:60]), file=sys.stderr)
            print('      %s' % (rec.get('landing_url') or rec.get('url') or ''),
                  file=sys.stderr)


if __name__ == '__main__':
    main()
