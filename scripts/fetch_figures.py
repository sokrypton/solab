#!/usr/bin/env python3
"""Download the figure images for papers that have structured full text.

JATS gives figure captions and the graphic filename; the images themselves
come from the PMC open-access package. Downloaded images are cached at full
size, then written into assets/papers/<slug>/ web-sized so the repo stays
reasonable.

    python3 scripts/fetch_figures.py [--limit N] [--width 1400]
"""

import argparse
import json
import os
import re
import sys
import time

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
FIG_CACHE = os.path.join(CACHE, 'figures')
WEB_DIR = os.path.join(REPO, 'assets', 'papers')
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
UA = 'solab-site-builder/0.1 (https://solab.org; mailto:kingsergey@gmail.com)'
IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff')


def slug(rec):
    base = re.sub(r'[^A-Za-z0-9]+', '-', rec['title'])[:70].strip('-').lower()
    return '%s-%s' % (rec.get('year') or 'n-d', base or 'untitled')


def pmcid_for(session, rec):
    """Ask Europe PMC for the PMC id, by DOI then title."""
    for q in [q for q in ('DOI:"%s"' % rec['doi'] if rec.get('doi') else None,
                          'TITLE:"%s"' % re.sub(r'["\\]', '', rec['title'])[:180]) if q]:
        r = session.get(EPMC + '/search', timeout=45, params={
            'query': q, 'format': 'json', 'resultType': 'core', 'pageSize': 3})
        if r.status_code != 200:
            continue
        for hit in r.json().get('resultList', {}).get('result', []):
            if hit.get('pmcid'):
                return hit['pmcid']
        time.sleep(0.2)
    return None


def fetch_image(session, pmcid, graphic, dest_dir):
    """One figure image, from the PMC article instance store.

    The OA tarballs that used to live on the FTP mirror now 404; the per-file
    `instance/<numeric id>/bin/<name>` route is what still serves them.
    """
    num = re.sub(r'\D', '', pmcid or '')
    if not num or not graphic:
        return None
    stem, ext = os.path.splitext(graphic)
    names = [graphic] if ext else []
    names += [stem + e for e in ('.jpg', '.png', '.gif')]
    os.makedirs(dest_dir, exist_ok=True)
    for name in names:
        out = os.path.join(dest_dir, name)
        if os.path.exists(out) and os.path.getsize(out) > 2000:
            return out
        url = 'https://www.ncbi.nlm.nih.gov/pmc/articles/instance/%s/bin/%s' % (num, name)
        try:
            r = session.get(url, timeout=90)
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.headers.get('content-type', '').startswith('image/'):
            with open(out, 'wb') as fh:
                fh.write(r.content)
            time.sleep(0.25)
            return out
        time.sleep(0.15)
    return None


def web_copy(src, dest, width):
    """Resize into assets/ for the site; skip if it is already small enough."""
    try:
        from PIL import Image
    except ImportError:
        return None
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        return dest
    try:
        im = Image.open(src)
        im.load()
    except Exception:
        return None
    if im.mode in ('RGBA', 'P', 'LA'):
        im = im.convert('RGB')
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)),
                       Image.LANCZOS)
    im.save(dest, 'JPEG', quality=82, optimize=True, progressive=True)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs_jats.json'))
    ap.add_argument('--width', type=int, default=1400)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    with open(args.pubs) as fh:
        pubs = json.load(fh)
    session = requests.Session()
    session.headers['User-Agent'] = UA

    todo = [r for r in pubs if r.get('jats') and r['jats'].get('figures')]
    if args.limit:
        todo = todo[:args.limit]

    total_imgs = total_bytes = 0
    for i, rec in enumerate(todo, 1):
        name = slug(rec)
        figs = rec['jats']['figures']
        cache_dir = os.path.join(FIG_CACHE, name)
        label = rec['title'][:46]

        pmcid = rec.get('pmcid') or pmcid_for(session, rec)
        rec['pmcid'] = pmcid
        if not pmcid:
            print('  [%2d/%d] --   no pmcid        %s' % (i, len(todo), label),
                  file=sys.stderr)
            continue

        placed = 0
        for fig in figs:
            src = fetch_image(session, pmcid, fig.get('graphic'), cache_dir)
            if not src:
                continue
            out = os.path.join(WEB_DIR, name, os.path.splitext(os.path.basename(src))[0] + '.jpg')
            web = web_copy(src, out, args.width)
            if web:
                fig['image'] = os.path.relpath(web, REPO)
                total_bytes += os.path.getsize(web)
                placed += 1
        total_imgs += placed
        print('  [%2d/%d] ok   %2d/%-2d figures   %s' % (
            i, len(todo), placed, len(figs), label), file=sys.stderr)

    with open(args.pubs, 'w') as fh:
        json.dump(pubs, fh, indent=1)
    print('\n--- summary ---', file=sys.stderr)
    print('figure images placed: %d' % total_imgs, file=sys.stderr)
    print('assets/papers size  : %.1f MB' % (total_bytes / 1e6), file=sys.stderr)


if __name__ == '__main__':
    main()
