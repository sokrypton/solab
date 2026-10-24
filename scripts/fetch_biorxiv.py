#!/usr/bin/env python3
"""Take the publisher's own full text for bioRxiv and medRxiv preprints.

bioRxiv posts the PDF immediately and then sends it to a vendor for conversion
to JATS XML, which is what its "full text" view renders. That conversion is
better than anything reconstructed from the PDF here — it has the real section
titles, unfragmented paragraphs and a parsed bibliography — so where it exists
we read it instead of guessing.

Output is deliberately the same document shape extract_pdf.py writes, so the
builder, the edit overlays and the audit all work on it unchanged:

    .cache/biorxiv/<slug>.html      the fetched page, cached
    .cache/doc/<slug>.json          nodes, marked source: biorxiv
    assets/papers/<slug>/           figure images, web-sized

    python3 scripts/fetch_biorxiv.py [--only SUBSTRING] [--limit N] [--force]
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time

import requests
from lxml import etree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
PREPRINT_MAP = os.path.join(CACHE, 'preprints.json')
HTML_DIR = os.path.join(CACHE, 'biorxiv')
DOC_DIR = os.path.join(CACHE, 'doc')
WEB_DIR = os.path.join(REPO, 'assets', 'papers')

UA = ('solab-site-builder/0.1 (+https://solab.org; mailto:so3@mit.edu) '
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120 Safari/537.36')

# sections that are apparatus rather than the paper
BACK_HEAD = re.compile(r'^(acknowledge?ments?|competing interests?|'
                       r'author contributions?|data availability|'
                       r'code availability|funding|declarations?|'
                       r'supplementary material|supporting information|'
                       r'conflicts? of interest|ethics)', re.I)
REFS_HEAD = re.compile(r'^(references|bibliography|literature cited)', re.I)
# supplementary figures and tables: left to the publisher's copy
SUPP_LABEL = re.compile(r'^(supplementary|supplemental|extended\s+data|appendix'
                        r'|(?:fig(?:ure)?|table|scheme)\.?\s*s\s*\d)', re.I)
ABSTRACT_HEAD = re.compile(r'^abstract', re.I)


def norm(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def node_id(index, text):
    """Same contract as the PDF path: content-hashed, so edits survive."""
    seed = norm(text)[:200] or str(index)
    return 'b%d-%s' % (index, hashlib.sha1(seed.encode()).hexdigest()[:6])


def session():
    s = requests.Session()
    s.headers['User-Agent'] = UA
    return s


def latest_version(s, doi):
    """Ask bioRxiv which version is current; fall back to v1."""
    server = 'medrxiv' if 'medrxiv' in doi.lower() else 'biorxiv'
    for server in (server, 'medrxiv' if server == 'biorxiv' else 'biorxiv'):
        try:
            r = s.get('https://api.biorxiv.org/details/%s/%s' % (server, doi),
                      timeout=45)
            items = r.json().get('collection') or []
            if items:
                return server, max(int(i.get('version', 1)) for i in items)
        except Exception:                               # noqa: BLE001
            continue
    return 'biorxiv', 1


def polite_get(s, url, tries=6, pause=8.0):
    """Fetch with backoff, and never mistake throttling for absence.

    Hitting bioRxiv briskly earns 403s and read timeouts. Treating those as
    "this preprint has no full text" silently skipped papers that do, so the
    status is returned for the caller to report.
    """
    last = None
    for attempt in range(tries):
        try:
            r = s.get(url, timeout=90)
            if r.status_code == 200:
                return r, None
            last = 'HTTP %d' % r.status_code
            if r.status_code == 404:
                return None, last          # genuinely absent, don't retry
        except Exception as exc:                        # noqa: BLE001
            last = type(exc).__name__
        time.sleep(pause * (attempt + 1))               # 4s, 8s, 12s
    return None, last


def fetch_full(s, doi, force=False):
    """The rendered vendor conversion for one preprint, cached on disk."""
    os.makedirs(HTML_DIR, exist_ok=True)
    key = re.sub(r'[^A-Za-z0-9.]+', '_', doi)
    path = os.path.join(HTML_DIR, key + '.html')
    if os.path.exists(path) and not force:
        return open(path, encoding='utf-8', errors='ignore').read(), 'cached'
    server, version = latest_version(s, doi)
    host = 'https://www.%s.org' % server
    # walk versions down from the latest: the newest may not be converted yet
    why = None
    for v in range(version, 0, -1):
        r, why = polite_get(s, '%s/content/%sv%d.full' % (host, doi, v))
        if r is not None and 'fulltext-view' in r.text:
            open(path, 'w', encoding='utf-8').write(r.text)
            return r.text, 'v%d' % v
        time.sleep(3)
    return None, why or 'no full-text view'


# ---------- parsing ----------

def text_of(el):
    return norm(' '.join(el.itertext()))


def figure_nodes(fig, slug, s, seq):
    """A figure's caption and its image, downloaded at the large size."""
    caption = ''
    for cap in fig.xpath('.//div[contains(@class,"fig-caption")]'
                         '|.//figcaption|.//div[contains(@class,"caption")]'):
        caption = text_of(cap)
        if caption:
            break
    href = None
    for a in fig.xpath('.//a[contains(@href,".large.")]/@href'):
        href = a
        break
    if not href:
        for src in fig.xpath('.//img/@src'):
            href = re.sub(r'\.(medium|small)\.(gif|jpg|png)$', '.large.jpg', src)
            break
    image = None
    if href:
        if href.startswith('/'):
            href = 'https://www.biorxiv.org' + href
        image = download_image(s, href, slug, seq)
    label = ''
    m = re.match(r'^\s*((?:Figure|Fig\.?|Table)\s*S?\d{1,2}[A-Za-z]?)', caption)
    if m:
        label = m.group(1)
    return label, caption, image


def download_image(s, url, slug, seq):
    """Web-size the publisher's figure the same way the PDF crops are sized."""
    from PIL import Image
    out_dir = os.path.join(WEB_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    r, _ = polite_get(s, url, tries=3, pause=3.0)
    if r is None or len(r.content) < 2000:
        return None
    try:
        img = Image.open(io.BytesIO(r.content))
        img = img.convert('RGB')
        if img.width > 1100:
            img = img.resize((1100, round(img.height * 1100 / img.width)),
                             Image.LANCZOS)
        name = 'bx-%02d.jpg' % seq
        img.save(os.path.join(out_dir, name), 'JPEG', quality=82, optimize=True,
                 progressive=True)
        return os.path.join('assets', 'papers', slug, name)
    except Exception:                                   # noqa: BLE001
        return None


def parse_full(html, slug, s, want_figures=True):
    """Turn the rendered conversion into the node list the builder consumes."""
    root = etree.fromstring(html.encode(), etree.HTMLParser())
    holder = root.xpath('//div[contains(@class,"fulltext-view")]')
    if not holder:
        return None
    view = holder[0]

    nodes, seq, fig_seq, role = [], 0, 0, None
    seen = set()
    for el in view.iter():
        tag = etree.QName(el).localname if isinstance(el.tag, str) else ''
        if tag in ('h1', 'h2', 'h3', 'h4'):
            text = text_of(el)
            if not text:
                continue
            role = ('back' if BACK_HEAD.match(text) else
                    'references' if REFS_HEAD.match(text) else
                    'front' if ABSTRACT_HEAD.match(text) else None)
            seq += 1
            node = {'id': node_id(seq, text), 'type': 'heading',
                    'text': text, 'level': 2 if tag in ('h1', 'h2') else 3,
                    'lines': [text]}
            if role:
                node['role'] = 'back' if role != 'front' else 'front'
            nodes.append(node)
            continue
        if tag == 'p':
            # a caption's paragraphs live inside the figure block; skip them
            if el.xpath('ancestor::div[contains(@class,"fig")]'
                        '|ancestor::div[contains(@class,"table-wrap")]'
                        '|ancestor::figure|ancestor::li'):
                continue
            text = text_of(el)
            if len(text) < 40 or text in seen:
                continue
            seen.add(text)
            seq += 1
            node = {'id': node_id(seq, text), 'type': 'prose', 'text': text,
                    'lines': [text]}
            if role:
                node['role'] = role
            nodes.append(node)
            continue
        if tag in ('div', 'figure') and re.search(
                r'\bfig\b|\bfigure\b', el.get('class') or ''):
            if el.xpath('ancestor::div[contains(@class,"fig")]'):
                continue                       # nested wrapper
            fig_seq += 1
            label, caption, image = figure_nodes(
                el, slug, s, fig_seq) if want_figures else ('', text_of(el), None)
            if not caption or SUPP_LABEL.match(caption) or SUPP_LABEL.match(label):
                continue
            seq += 1
            node = {'id': node_id(seq, caption),
                    'type': 'figure' if image else 'caption',
                    'text': caption, 'label': label, 'lines': [caption]}
            if image:
                node['image'] = image
            if role:
                node['role'] = role
            nodes.append(node)
            continue
        if tag == 'li' and el.xpath('ancestor::ol[contains(@class,"cit-list")]'
                                    '|ancestor::div[contains(@class,"ref-list")]'):
            text = text_of(el)
            if len(text) < 30:
                continue
            seq += 1
            nodes.append({'id': node_id(seq, text), 'type': 'prose',
                          'text': text, 'role': 'references', 'lines': [text]})
    return nodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs_text.json'))
    ap.add_argument('--only')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--no-figures', action='store_true')
    ap.add_argument('--use-preprints', action='store_true',
                    help='also take papers whose bioRxiv preprint was found by '
                         'find_preprints.py, using the preprint DOI')
    ap.add_argument('--rounds', type=int, default=8,
                    help='how many times to come back to failures')
    args = ap.parse_args()

    recs = json.load(open(args.pubs, encoding='utf-8'))
    # A published paper's record carries its *journal* DOI, so this tier never
    # saw it even when a bioRxiv preprint of the same work exists.
    # scripts/find_preprints.py finds those; the mapping is opt-in because the
    # preprint is a different version of the paper, not merely a cleaner copy.
    preprints = {}
    if args.use_preprints and os.path.exists(PREPRINT_MAP):
        preprints = {k: v['doi'] for k, v
                     in json.load(open(PREPRINT_MAP, encoding='utf-8')).items()}
    todo = []
    for r in recs:
        doi = (r.get('doi') or '').replace('https://doi.org/', '')
        slug = os.path.basename(r['text_file'])[:-4] if r.get('text_file') else ''
        if slug in preprints:
            doi = preprints[slug]
        # Ask "is this a bioRxiv preprint?", not "does the DOI start 10.1101?".
        # bioRxiv issues 10.64898 DOIs now, and testing the old prefix quietly
        # excluded those papers from this tier altogether — they fell through to
        # GROBID, which is a worse source, with nothing reported.
        venue = '%s %s' % (r.get('venue') or '', r.get('url') or '')
        preprint = re.search(r'biorxiv|medrxiv', venue, re.I) or doi.startswith(
            ('10.1101/', '10.64898/'))
        if not r.get('text_file') or not preprint:
            continue
        if args.only and args.only.lower() not in r['title'].lower():
            continue
        todo.append((os.path.basename(r['text_file'])[:-4], doi, r['title']))
    if args.limit:
        todo = todo[:args.limit]

    s = session()
    os.makedirs(DOC_DIR, exist_ok=True)
    done = set()
    pending, rounds = list(todo), 0
    while pending and rounds < args.rounds:
        rounds += 1
        if rounds > 1:
            wait = 30 * rounds
            print('\n--- round %d: %d still unresolved, waiting %ds ---'
                  % (rounds, len(pending), wait))
            time.sleep(wait)
        again = []
        # count papers, not attempts: a paper retried for its images used to be
        # counted once per round, and the tally read "45 of 34"
        done |= run_round(s, pending, again, args)
        pending = again
    for slug, doi, title in pending:
        print('  --   %-46s gave up after %d rounds' % (title[:46], rounds))
    print('\n%d of %d preprints taken from the publisher'
          % (len(done), len(todo)))
    return 0


def run_round(s, todo, again, args):
    """One pass over the outstanding preprints; unresolved ones go to `again`.

    Returns the slugs that now have a document, so retries do not inflate the
    count.
    """
    ok = set()
    for slug, doi, title in todo:
        html, why = fetch_full(s, doi, args.force)
        if not html:
            # never silently: a 403 or a timeout means we were throttled, not
            # that the publisher has no full text. Only an outright 404 on
            # every version is a real absence.
            print('  ..   %-46s %s' % (title[:46], why))
            if why != 'HTTP 404':
                again.append((slug, doi, title))
            continue
        nodes = parse_full(html, slug, s, want_figures=not args.no_figures)
        heads = [n for n in (nodes or []) if n['type'] == 'heading']
        prose = [n for n in (nodes or []) if n['type'] == 'prose'
                 and not n.get('role')]
        # Only take over from the PDF path when the conversion is substantial:
        # a stub page would otherwise replace a working document with nothing.
        if not nodes or len(prose) < 8 or len(heads) < 3:
            print('  --   %-46s conversion too thin (%d prose, %d heads)'
                  % (title[:46], len(prose), len(heads)))
            continue
        if want_more_figures(nodes):
            again.append((slug, doi, title))   # images throttled; retry later
        figs = [n['image'] for n in nodes if n.get('image')]
        # A retry exists to collect the images an earlier round was throttled out
        # of, so it must never *lose* them. Retrying one paper this way replaced
        # 14 figures with 11 and left three captions orphaned on the page.
        path = os.path.join(DOC_DIR, slug + '.json')
        if os.path.exists(path):
            before = json.load(open(path, encoding='utf-8'))
            if (before.get('source') == 'biorxiv'
                    and len(before.get('figures') or []) > len(figs)):
                print('  ..   %-46s kept the earlier fetch (%d figs, not %d)'
                      % (title[:46], len(before['figures']), len(figs)))
                again.append((slug, doi, title))
                continue
        doc = {'slug': slug, 'source': 'biorxiv', 'doi': doi,
               'nodes': nodes, 'figures': figs}
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
        refs = sum(1 for n in nodes if n.get('role') == 'references')
        ok.add(slug)
        print('  ok   %-46s %3d heads %3d prose %2d figs %3d refs'
              % (title[:46], len(heads), len(prose), len(figs), refs))
        time.sleep(4)                          # be a good citizen

    return ok


def want_more_figures(nodes):
    """Captions with no image mean the image fetches were throttled."""
    captions = [n for n in nodes if n['type'] in ('figure', 'caption')]
    return bool(captions) and any(n['type'] == 'caption' for n in captions)


if __name__ == '__main__':
    sys.exit(main())
