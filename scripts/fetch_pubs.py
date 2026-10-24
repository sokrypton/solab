#!/usr/bin/env python3
"""Resolve the publications page against OpenAlex and cache the metadata.

Stage 1 of the publications graph: read publications/index.html, match every
entry to an OpenAlex work, and write a metadata file with topics, citation
edges and open-access locations.

Metadata only — no article text is downloaded here (see fetch_fulltext.py),
and nothing copyrighted lands in the repo.

    python3 scripts/fetch_pubs.py [--out assets/data/pubs.json]
"""

import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.parse

import requests
from lxml import html

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS_HTML = os.path.join(REPO, 'publications', 'index.html')
API = 'https://api.openalex.org/works'
MAILTO = 'kingsergey@gmail.com'          # OpenAlex polite pool
CACHE = os.environ.get('PUBS_CACHE', os.path.join(REPO, '.cache', 'openalex'))


def parse_page():
    """Every <li class="pub"> on the publications page, in document order."""
    doc = html.parse(PUBS_HTML).getroot()
    out = []
    for cat in doc.cssselect('section.pub-cat'):
        theme = cat.get('id') or ''
        heading = cat.cssselect('h2.section-title')
        theme_name = heading[0].text_content().strip() if heading else theme
        for li in cat.cssselect('li.pub'):
            title_el = li.cssselect('a.pub-title')
            title = title_el[0].text_content().strip() if title_el else ''
            out.append({
                'title': title.rstrip('.'),
                'url': title_el[0].get('href') if title_el else None,
                'year': _text(li, 'span.pub-year'),
                'authors_short': _text(li, 'span.pub-auth'),
                'venue': _text(li, 'span.pub-venue'),
                'authors_full': li.get('data-authors') or '',
                'theme': theme,
                'theme_name': theme_name,
            })
    return out


def _text(el, sel):
    hit = el.cssselect(sel)
    return hit[0].text_content().strip() if hit else ''


def doi_from_url(url):
    """Publisher links that carry a DOI outright (biorxiv, doi.org, PLOS...)."""
    if not url:
        return None
    m = re.search(r'(10\.\d{4,9}/[^\s"?#]+)', urllib.parse.unquote(url))
    if not m:
        return None
    doi = m.group(1).rstrip('.').rstrip('/')
    doi = re.sub(r'v\d+$', '', doi)          # biorxiv version suffix
    return doi.lower()


def api_get(params, key):
    """GET with an on-disk cache so reruns cost nothing."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r'[^A-Za-z0-9._-]', '_', key)[:180] + '.json')
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    params = dict(params, mailto=MAILTO)
    r = requests.get(API, params=params, timeout=45)
    r.raise_for_status()
    data = r.json()
    with open(path, 'w') as fh:
        json.dump(data, fh)
    time.sleep(0.15)                          # be a good citizen
    return data


def norm(s):
    return re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower()).split()


def resolve(entry):
    """Find the OpenAlex work for one page entry: DOI first, then title."""
    doi = doi_from_url(entry['url'])
    if doi:
        data = api_get({'filter': 'doi:' + doi, 'per-page': 1}, 'doi_' + doi)
        if data.get('results'):
            return data['results'][0], 'doi'

    title = entry['title']
    if not title:
        return None, 'no-title'
    query = re.sub(r'[^A-Za-z0-9 ]', ' ', title)[:200]
    data = api_get({'filter': 'title.search:' + query, 'per-page': 5},
                   'title_' + query)
    best, best_score = None, 0.0
    for w in data.get('results', []):
        score = difflib.SequenceMatcher(
            None, ' '.join(norm(title)), ' '.join(norm(w.get('title')))).ratio()
        if score > best_score:
            best, best_score = w, score
    if best and best_score >= 0.85:
        return best, 'title(%.2f)' % best_score
    return None, 'unmatched(best=%.2f)' % best_score if best else 'unmatched'


def abstract_of(work):
    """OpenAlex ships abstracts as an inverted index; put it back together."""
    inv = work.get('abstract_inverted_index')
    if not inv:
        return ''
    spots = [(pos, word) for word, places in inv.items() for pos in places]
    spots.sort()
    return ' '.join(word for _, word in spots)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, '.cache', 'pubs.json'))
    args = ap.parse_args()

    entries = parse_page()
    print('parsed %d publications from the page' % len(entries), file=sys.stderr)

    resolved, misses = [], []
    for i, e in enumerate(entries, 1):
        try:
            work, how = resolve(e)
        except requests.RequestException as err:
            work, how = None, 'error: %s' % err
        rec = dict(e, matched_by=how)
        if work:
            oa = work.get('open_access') or {}
            loc = work.get('best_oa_location') or {}
            rec.update({
                'openalex': work['id'],
                'doi': (work.get('doi') or '').replace('https://doi.org/', ''),
                'oa_year': work.get('publication_year'),
                'cited_by': work.get('cited_by_count'),
                'is_oa': bool(oa.get('is_oa')),
                'oa_status': oa.get('oa_status'),
                'oa_url': oa.get('oa_url'),
                'pdf_url': loc.get('pdf_url'),
                'landing_url': loc.get('landing_page_url'),
                'topics': [{'name': t['display_name'], 'score': t.get('score')}
                           for t in work.get('topics', [])],
                'concepts': [c['display_name'] for c in work.get('concepts', [])[:8]],
                'referenced_works': work.get('referenced_works', []),
                'abstract': abstract_of(work),
            })
            resolved.append(rec)
        else:
            misses.append(rec)
            resolved.append(rec)
        print('  [%2d/%d] %-12s %s' % (i, len(entries), how, e['title'][:64]),
              file=sys.stderr)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as fh:
        json.dump(resolved, fh, indent=1)

    ok = [r for r in resolved if r.get('openalex')]
    oa = [r for r in ok if r.get('is_oa')]
    pdf = [r for r in ok if r.get('pdf_url')]
    ids = {r['openalex'] for r in ok}
    internal = sum(len(ids & set(r.get('referenced_works', []))) for r in ok)
    print('\n--- summary ---', file=sys.stderr)
    print('resolved   %d/%d' % (len(ok), len(entries)), file=sys.stderr)
    print('open access %d   with a PDF url %d' % (len(oa), len(pdf)), file=sys.stderr)
    print('internal citation edges (lab paper -> lab paper): %d' % internal,
          file=sys.stderr)
    print('abstracts  %d' % sum(1 for r in ok if r.get('abstract')), file=sys.stderr)
    if misses:
        print('\nunresolved (%d):' % len(misses), file=sys.stderr)
        for m in misses:
            print('  - [%s] %s' % (m['matched_by'], m['title'][:70]), file=sys.stderr)
    print('\nwrote %s' % args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
