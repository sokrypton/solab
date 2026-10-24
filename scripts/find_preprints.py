#!/usr/bin/env python3
"""Find bioRxiv preprints of papers we are currently reading from a PDF.

Our records carry each paper's *published* DOI, so `fetch_biorxiv.py` only ever
tried papers whose venue was bioRxiv itself. A journal article usually also has
a preprint, under a different DOI, and bioRxiv's vendor conversion of that
preprint is far better structured than anything reconstructed from the PDF.

Crossref indexes preprints as type `posted-content`, so they can be looked up by
title. A title match is not proof of identity — several papers here have
near-identical titles to other groups' work — so matches are scored and the
weak ones are reported separately rather than acted on.

    python3 scripts/find_preprints.py            look, report, cache
    python3 scripts/find_preprints.py --json

Writes .cache/preprints.json: {slug -> {doi, title, score}}.
Nothing is fetched here. Deciding to *use* a preprint in place of the published
text is an editorial call, not a mechanical one: the versions differ.
"""

import argparse
import difflib
import glob
import json
import os
import re
import sys
import time

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
OUT = os.path.join(CACHE, 'preprints.json')
UA = {'User-Agent': 'solab-site/1.0 (mailto:so3@mit.edu)'}
PREPRINT_HOST = re.compile(r'^10\.(1101|64898)/')


def norm(title):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', (title or '').lower())).strip()


def pdf_papers():
    """Papers whose page is built from a PDF we read ourselves."""
    out = {}
    recs = json.load(open(os.path.join(CACHE, 'pubs_text.json'), encoding='utf-8'))
    for rec in recs:
        if not rec.get('text_file'):
            continue
        slug = os.path.basename(rec['text_file'])[:-4]
        doc = os.path.join(CACHE, 'doc', slug + '.json')
        if not os.path.exists(doc):
            continue
        if json.load(open(doc, encoding='utf-8')).get('source') == 'biorxiv':
            continue
        out[slug] = rec
    return out


def search(title, tries=4):
    for attempt in range(tries):
        try:
            r = requests.get('https://api.crossref.org/works',
                             params={'query.bibliographic': title,
                                     'filter': 'type:posted-content',
                                     'rows': 5},
                             headers=UA, timeout=60)
            if r.status_code == 200:
                return r.json()['message']['items']
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(4 * (attempt + 1))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--min-score', type=float, default=0.85)
    args = ap.parse_args()

    papers = pdf_papers()
    if args.only:
        papers = {s: r for s, r in papers.items() if args.only.lower() in s.lower()}
    found, weak = {}, {}
    for slug, rec in sorted(papers.items()):
        title = rec.get('title') or ''
        best = None
        for item in search(title):
            doi = item.get('DOI', '')
            if not PREPRINT_HOST.match(doi):
                continue               # a preprint, but not on bioRxiv/medRxiv
            other = re.sub(r'<[^>]+>', ' ', (item.get('title') or [''])[0])
            score = difflib.SequenceMatcher(None, norm(title), norm(other)).ratio()
            if best is None or score > best['score']:
                best = {'doi': doi, 'title': other.strip(), 'score': round(score, 3)}
        if best and best['score'] >= args.min_score:
            found[slug] = best
        elif best:
            weak[slug] = best
        time.sleep(1.5)                # Crossref asks for politeness, not speed

    if args.json:
        print(json.dumps({'found': found, 'weak': weak}, indent=1))
    else:
        print('%d papers read from PDF; %d have a preprint, %d uncertain\n'
              % (len(papers), len(found), len(weak)))
        for slug, hit in found.items():
            print('  %-52s %s' % (slug[:52], hit['doi']))
        if weak:
            print('\nuncertain — title differs, check before using:')
            for slug, hit in weak.items():
                print('  %-40s %.2f %s' % (slug[:40], hit['score'], hit['doi']))
                print('      %s' % hit['title'][:96])
    json.dump(found, open(OUT, 'w', encoding='utf-8'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
