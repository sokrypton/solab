#!/usr/bin/env python3
"""Fetch structured full text (JATS XML) from Europe PMC.

Better source than the PDFs: real section headings, paragraphs, figure
captions and figure image references, which is what a formatted per-paper
page needs.

The lab holds the rights to repost these articles, so everything fetched here
is fair game for the per-paper pages.

    python3 scripts/fetch_jats.py [--limit N]
"""

import argparse
import json
import os
import re
import sys
import time

import requests
from lxml import etree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
XML_DIR = os.path.join(CACHE, 'jats')
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
UA = 'solab-site-builder/0.1 (https://solab.org; mailto:kingsergey@gmail.com)'


def search(session, rec):
    """Locate the article in Europe PMC by DOI, then by title."""
    queries = []
    if rec.get('doi'):
        queries.append('DOI:"%s"' % rec['doi'])
    if rec.get('title'):
        queries.append('TITLE:"%s"' % re.sub(r'["\\]', '', rec['title'])[:180])
    for q in queries:
        r = session.get(EPMC + '/search', timeout=45, params={
            'query': q, 'format': 'json', 'resultType': 'core', 'pageSize': 3})
        if r.status_code != 200:
            continue
        for hit in r.json().get('resultList', {}).get('result', []):
            if hit.get('hasTextMinedTerms') or hit.get('fullTextIdList') or \
               hit.get('isOpenAccess') == 'Y':
                return hit
        time.sleep(0.2)
    return None


def full_text_xml(session, hit):
    """The JATS document, when Europe PMC is allowed to serve it."""
    # the endpoint keys off the PMC/preprint id alone — no source segment
    ids = [hit.get('pmcid')]
    ids += (hit.get('fullTextIdList') or {}).get('fullTextId', [])
    if (hit.get('source') or '').upper() == 'PPR':
        ids.append(hit.get('id'))
    for key in [i for i in ids if i]:
        url = '%s/%s/fullTextXML' % (EPMC, key)
        r = session.get(url, timeout=60)
        if r.status_code == 200 and r.content.lstrip().startswith(b'<'):
            return r.content, url
        time.sleep(0.2)
    return None, None


def parse_jats(xml):
    """JATS -> {abstract, sections, figures} in plain structures."""
    root = etree.fromstring(xml)

    def txt(el):
        return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip() if el is not None else ''

    meta = root.find('.//article-meta')

    sections = []
    for sec in root.findall('.//body//sec'):
        if sec.getparent().tag == 'sec':          # only top-level sections
            continue
        head = txt(sec.find('title'))
        paras = [txt(p) for p in sec.findall('.//p')]
        paras = [p for p in paras if len(p) > 40]
        if head or paras:
            sections.append({'heading': head, 'paragraphs': paras})

    figures = []
    for fig in root.findall('.//fig'):
        graphic = fig.find('.//graphic')
        href = graphic.get('{http://www.w3.org/1999/xlink}href') if graphic is not None else None
        figures.append({
            'id': fig.get('id'),
            'label': txt(fig.find('label')),
            'caption': txt(fig.find('caption')),
            'graphic': href,
        })

    return {
        'abstract': txt(meta.find('abstract')) if meta is not None else '',
        'sections': sections,
        'figures': figures,
        'body_words': sum(len(p.split()) for s in sections for p in s['paragraphs']),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs_text.json'))
    ap.add_argument('--out', default=os.path.join(CACHE, 'pubs_jats.json'))
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    with open(args.pubs) as fh:
        pubs = json.load(fh)
    os.makedirs(XML_DIR, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = UA

    todo = [p for p in pubs if p.get('openalex')]
    if args.limit:
        todo = todo[:args.limit]

    stats = {'xml': 0, 'figs': 0, 'secs': 0}
    for i, rec in enumerate(todo, 1):
        label = rec['title'][:52]
        path = os.path.join(XML_DIR, re.sub(r'[^A-Za-z0-9]+', '-', rec['title'])[:70] + '.xml')
        xml = None
        if os.path.exists(path):
            xml = open(path, 'rb').read()
        else:
            hit = search(session, rec)
            if hit:
                rec['pmcid'] = hit.get('pmcid')
                rec['epmc_id'] = '%s:%s' % (hit.get('source'), hit.get('id'))
                xml, url = full_text_xml(session, hit)
                if xml:
                    open(path, 'wb').write(xml)
                time.sleep(0.3)
        if not xml:
            print('  [%2d/%d] --   no xml            %s' % (i, len(todo), label), file=sys.stderr)
            continue
        try:
            doc = parse_jats(xml)
        except etree.XMLSyntaxError as err:
            print('  [%2d/%d] --   bad xml           %s' % (i, len(todo), label), file=sys.stderr)
            continue

        rec['jats'] = doc
        stats['xml'] += 1
        stats['figs'] += len(doc['figures'])
        stats['secs'] += len(doc['sections'])
        print('  [%2d/%d] ok   %5dw %2dsec %2dfig  %s' % (
            i, len(todo), doc['body_words'], len(doc['sections']),
            len(doc['figures']), label), file=sys.stderr)

    with open(args.out, 'w') as fh:
        json.dump(pubs, fh, indent=1)
    print('\n--- summary ---', file=sys.stderr)
    print('structured full text : %d' % stats['xml'], file=sys.stderr)
    print('figures with captions: %d' % stats['figs'], file=sys.stderr)
    print('sections             : %d' % stats['secs'], file=sys.stderr)
    print('wrote %s' % args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
