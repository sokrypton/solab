#!/usr/bin/env python3
"""Point the publications list at the local reading pages.

For every entry that has a generated page under papers/, the title links to
that page and the original publisher link is kept as a pill beside the venue.
Idempotent: entries already pointing at papers/ are left alone.

    python3 scripts/link_papers.py [--dry-run]
"""

import argparse
import html
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS = os.path.join(REPO, 'publications', 'index.html')

PUB_LI = re.compile(r'<li class="pub"[^>]*>.*?</li>', re.S)
TITLE_A = re.compile(r'<a class="pub-title" href="([^"]*)">(.*?)</a>', re.S)
YEAR = re.compile(r'<span class="pub-year">([^<]*)</span>')
VENUE = re.compile(r'(<span class="pub-venue">)(.*?)(</span>)', re.S)


def slug_for(title, year):
    base = re.sub(r'[^A-Za-z0-9]+', '-', title)[:70].strip('-').lower()
    return '%s-%s' % (year or 'n-d', base or 'untitled')


def host_of(url):
    m = re.match(r'https?://(?:www\.)?([^/]+)', url or '')
    return m.group(1) if m else 'Publisher'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    src = open(PUBS, encoding='utf-8').read()
    linked = missing = already = 0

    def fix(block):
        nonlocal linked, missing, already
        m = TITLE_A.search(block.group(0))
        if not m:
            return block.group(0)
        href, title_html = m.group(1), m.group(2)
        if href.startswith('../papers/'):
            already += 1
            return block.group(0)

        title = html.unescape(re.sub(r'<[^>]+>', '', title_html)).strip().rstrip('.')
        ym = YEAR.search(block.group(0))
        year = ym.group(1).strip() if ym else ''
        name = slug_for(title, year)
        if not os.path.isdir(os.path.join(REPO, 'papers', name)):
            missing += 1
            return block.group(0)

        out = block.group(0)
        # title now opens the local reading page
        out = out.replace(m.group(0),
                          '<a class="pub-title" href="../papers/%s/">%s</a>'
                          % (name, title_html), 1)
        # keep the publisher within reach, alongside any existing pills
        if href and 'class="pill"' not in out.split('pub-venue')[-1][:400]:
            pill = ' <a class="pill" href="%s">%s</a>' % (href, host_of(href))
            out = VENUE.sub(lambda v: v.group(1) + v.group(2) + pill + v.group(3),
                            out, count=1)
        elif href:
            pill = ' <a class="pill" href="%s">%s</a>' % (href, host_of(href))
            out = VENUE.sub(lambda v: v.group(1) + v.group(2) + pill + v.group(3),
                            out, count=1)
        linked += 1
        return out

    updated = PUB_LI.sub(fix, src)

    print('linked to local pages : %d' % linked, file=sys.stderr)
    print('already linked        : %d' % already, file=sys.stderr)
    print('no page built         : %d' % missing, file=sys.stderr)
    if args.dry_run:
        print('(dry run — nothing written)', file=sys.stderr)
        return
    if updated != src:
        with open(PUBS, 'w', encoding='utf-8') as fh:
            fh.write(updated)
        print('wrote %s' % os.path.relpath(PUBS, REPO), file=sys.stderr)


if __name__ == '__main__':
    main()
