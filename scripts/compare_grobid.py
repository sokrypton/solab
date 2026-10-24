#!/usr/bin/env python3
"""Compare our PDF extraction against GROBID, on the same measures.

GROBID is the ML-based scholarly PDF parser that Semantic Scholar and others
use, and it is benchmarked against exactly the vendor JATS that bioRxiv, PMC
and eLife publish. This asks whether it beats the heuristics in extract_pdf.py
for structure — sections, prose, references, front matter — on our own papers.

Needs a GROBID service running (default http://localhost:8070).

    python3 scripts/compare_grobid.py --slug SUBSTRING [--url http://…]
"""

import argparse
import glob
import json
import os
import re
import sys

import requests
from lxml import etree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(REPO, '.cache', 'pdf')
DOC_DIR = os.path.join(REPO, '.cache', 'doc')
TEI_DIR = os.path.join(REPO, '.cache', 'tei')
TEI_NS = {'t': 'http://www.tei-c.org/ns/1.0'}


def grobid_tei(pdf, url, force=False):
    """Full-text TEI for one PDF, cached — a call takes 10-40 seconds."""
    os.makedirs(TEI_DIR, exist_ok=True)
    out = os.path.join(TEI_DIR, os.path.basename(pdf)[:-4] + '.tei.xml')
    if os.path.exists(out) and not force:
        return open(out, encoding='utf-8').read()
    with open(pdf, 'rb') as fh:
        r = requests.post(
            url.rstrip('/') + '/api/processFulltextDocument',
            files={'input': fh},
            data={'consolidateHeader': '0', 'consolidateCitations': '0',
                  'includeRawCitations': '1', 'segmentSentences': '0'},
            timeout=600)
    r.raise_for_status()
    open(out, 'w', encoding='utf-8').write(r.text)
    return r.text


def measure_tei(xml):
    """Sections, paragraphs, references and figures as GROBID sees them."""
    root = etree.fromstring(xml.encode())
    body = root.find('.//t:text/t:body', TEI_NS)
    heads, paras, words = [], 0, 0
    if body is not None:
        for div in body.findall('.//t:div', TEI_NS):
            head = div.find('t:head', TEI_NS)
            if head is not None and (head.text or '').strip():
                heads.append(' '.join(head.itertext()).strip())
        for p in body.findall('.//t:p', TEI_NS):
            text = ' '.join(p.itertext()).strip()
            if text:
                paras += 1
                words += len(text.split())
    refs = root.findall('.//t:listBibl/t:biblStruct', TEI_NS)
    figs = root.findall('.//t:figure', TEI_NS)
    abstract = root.find('.//t:profileDesc/t:abstract', TEI_NS)
    authors = root.findall('.//t:sourceDesc//t:author', TEI_NS)
    return {'headings': heads, 'paragraphs': paras, 'words': words,
            'references': len(refs), 'figures': len(figs),
            'has_abstract': abstract is not None and bool(
                ' '.join(abstract.itertext()).strip()),
            'authors': len(authors)}


def measure_ours(slug):
    """The same measures over our own extracted document."""
    path = os.path.join(DOC_DIR, slug + '.json')
    if not os.path.exists(path):
        return None
    doc = json.load(open(path, encoding='utf-8'))
    heads, paras, words, refs, figs = [], 0, 0, 0, 0
    for n in doc['nodes']:
        role, kind = n.get('role'), n['type']
        if role == 'references':
            refs += 1
            continue
        if role or kind in ('stamp', 'furniture', 'figure-text', 'rotated',
                            'small', 'empty', 'math'):
            continue
        if kind == 'heading':
            heads.append(n['text'])
        elif kind == 'prose':
            paras += 1
            words += len(n['text'].split())
        elif kind == 'figure':
            figs += 1
    return {'headings': heads, 'paragraphs': paras, 'words': words,
            'references': refs, 'figures': figs}


JUNK = re.compile(r'^(graphical abstract|highlights|authors?|in brief|article|'
                  r'[A-Z]( [A-Z])+|\d+|[^A-Za-z]*)$', re.I)


def junk_headings(heads):
    """Headings a reader would not accept: panel letters, folios, furniture."""
    return [h for h in heads if JUNK.match(h.strip()) or len(h) > 95]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', help='only PDFs matching this substring')
    ap.add_argument('--url', default='http://localhost:8070')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, '*.pdf')))
    if args.slug:
        pdfs = [p for p in pdfs if args.slug.lower() in os.path.basename(p).lower()]
    if args.limit:
        pdfs = pdfs[:args.limit]

    for pdf in pdfs:
        slug = os.path.basename(pdf)[:-4]
        try:
            tei = measure_tei(grobid_tei(pdf, args.url, args.force))
        except Exception as exc:                        # noqa: BLE001
            print('  !!   %s: %s' % (slug[:50], exc))
            continue
        ours = measure_ours(slug) or {}
        print('\n%s' % slug)
        print('  %-14s %-28s %s' % ('', 'GROBID', 'ours'))
        for key in ('paragraphs', 'words', 'references', 'figures'):
            print('  %-14s %-28s %s' % (key, tei[key], ours.get(key, '-')))
        print('  %-14s %-28s %s' % ('headings', len(tei['headings']),
                                    len(ours.get('headings', []))))
        print('  %-14s %-28s %s' % ('junk headings',
                                    len(junk_headings(tei['headings'])),
                                    len(junk_headings(ours.get('headings', [])))))
        print('  GROBID headings: %s' % '; '.join(tei['headings'][:12]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
