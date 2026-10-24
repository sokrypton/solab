#!/usr/bin/env python3
"""Re-render every paper with the current code, and say what changed.

The refinement loop alternates between fixing one paper by hand and fixing the
extractor for all of them. That only works if each code change is pushed back
through the papers already done — and if a regression is visible when it
happens. This re-runs the pipeline and compares the result against the last
recorded state: audit flags per paper, overlay ops that have gone stale, and
the whole-site checks.

    python3 scripts/refresh.py              re-render, compare, report
    python3 scripts/refresh.py --baseline   record the current state as the
                                            thing future runs compare against

A paper whose flags go *up*, or whose overlay ops go stale, is the signal to
look before moving on to the next paper.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, '.venv', 'bin', 'python')
CACHE = os.path.join(REPO, '.cache')
BASELINE = os.path.join(CACHE, 'refresh_baseline.json')

sys.path.insert(0, os.path.join(REPO, 'scripts'))


def script(name, *args, stream=False):
    """Run a pipeline step. Streaming matters: a whole-corpus pass takes minutes,
    and buffering its output meant a kill left nothing to show."""
    if stream:
        print('    $ %s %s' % (name, ' '.join(args)), flush=True)
        return subprocess.run([PY, os.path.join(REPO, 'scripts', name), *args],
                              text=True, cwd=REPO)
    return subprocess.run([PY, os.path.join(REPO, 'scripts', name), *args],
                          capture_output=True, text=True, cwd=REPO)


def grobid_slugs():
    """Papers whose page is built from a PDF we extracted ourselves."""
    out = []
    for path in sorted(glob.glob(os.path.join(CACHE, 'doc', '*.json'))):
        try:
            doc = json.load(open(path, encoding='utf-8'))
        except Exception:                               # noqa: BLE001
            continue
        if doc.get('source') != 'biorxiv':
            out.append(doc['slug'])
    return out


def audit_counts():
    out = script('audit_papers.py', '--json')
    try:
        report = json.loads(out.stdout or '[]')
    except json.JSONDecodeError:
        return {}
    return {p['slug']: len(p['flags']) for p in report}


def stale_counts():
    """Overlay ops that no longer match a node, per paper."""
    counts = {}
    for path in sorted(glob.glob(os.path.join(REPO, 'edits', '*.json'))):
        slug = os.path.basename(path)[:-5]
        doc_path = os.path.join(CACHE, 'doc', slug + '.json')
        if not os.path.exists(doc_path):
            continue
        ids = {n['id'] for n in json.load(open(doc_path, encoding='utf-8'))['nodes']}
        ops = json.load(open(path, encoding='utf-8')).get('ops', [])
        stale = sum(1 for op in ops if op.get('id') not in ids)
        if stale:
            counts[slug] = stale
    return counts


def wrong_tier():
    """Preprints being read from a PDF when the publisher offers full text.

    A paper on the wrong tier looks perfectly fine — the page renders, nothing
    is missing, the audit is quiet — so this has to be asserted rather than
    noticed. Two papers sat on GROBID for months because the fetcher tested
    `'10.1101' in doi` and bioRxiv had started issuing 10.64898 DOIs.
    """
    path = os.path.join(CACHE, 'pubs_text.json')
    if not os.path.exists(path):
        return []
    out = []
    for rec in json.load(open(path, encoding='utf-8')):
        if not rec.get('text_file'):
            continue
        slug = os.path.basename(rec['text_file'])[:-4]
        doc = os.path.join(CACHE, 'doc', slug + '.json')
        if not os.path.exists(doc):
            continue
        source = json.load(open(doc, encoding='utf-8')).get('source')
        venue = '%s %s' % (rec.get('venue') or '', rec.get('url') or '')
        if source != 'biorxiv' and re.search(r'biorxiv|medrxiv', venue, re.I):
            out.append(slug)
    return out


def site_checks():
    from lxml import etree
    parser = etree.HTMLParser(recover=False)
    bad = missing = dangling = 0
    for page in glob.glob(os.path.join(REPO, 'papers', '*', 'index.html')):
        html = open(page, encoding='utf-8').read()
        try:
            etree.fromstring(html.encode(), parser)
        except Exception:                               # noqa: BLE001
            bad += 1
        for src in re.findall(r'<img[^>]+src="\.\./\.\./([^"]+)"', html):
            if not os.path.exists(os.path.join(REPO, src)):
                missing += 1
        ids = set(re.findall(r'id="([^"]+)"', html))
        dangling += sum(1 for h in re.findall(r'href="#([^"]+)"', html)
                        if h not in ids)
    return {'html_errors': bad, 'broken_images': missing,
            'dangling_links': dangling}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', action='store_true',
                    help='record the current state instead of comparing')
    ap.add_argument('--skip-extract', action='store_true',
                    help='rebuild pages only, do not re-read the PDFs')
    args = ap.parse_args()

    slugs = grobid_slugs()
    print('re-rendering %d papers with the current code' % len(slugs))
    if not args.skip_extract:
        # Our layout pass first: the GROBID ingest reads its output for figures,
        # figure-interior text, reading order and column-break repairs. One pass
        # writes both the documents and the figure crops.
        script('extract_pdf.py', '--doc-dir', os.path.join(CACHE, 'doc_ours'),
               stream=True)
        script('ingest_tei.py', stream=True)
    print('  pages    %s' % script('build_papers.py'
                                   ).stderr.strip().splitlines()[-1])

    now = {'audit': audit_counts(), 'stale': stale_counts(),
           'site': site_checks()}
    print('\nsite: %s' % ', '.join('%s %d' % (k, v) for k, v in now['site'].items()))
    print('flags: %d across %d papers'
          % (sum(now['audit'].values()), len(now['audit'])))
    if now['stale']:
        print('overlay ops gone stale: %s'
              % ', '.join('%s(%d)' % (s[:34], n) for s, n in now['stale'].items()))
    astray = wrong_tier()
    if astray:
        print('READ FROM PDF THOUGH THE PUBLISHER HAS FULL TEXT: %s'
              % ', '.join(s[:40] for s in astray))

    if args.baseline or not os.path.exists(BASELINE):
        json.dump(now, open(BASELINE, 'w', encoding='utf-8'), indent=1)
        print('\nrecorded as the baseline for future runs')
        return 0

    was = json.load(open(BASELINE, encoding='utf-8'))
    worse = [(s, was['audit'].get(s, 0), n) for s, n in now['audit'].items()
             if n > was['audit'].get(s, 0)]
    better = sum(max(0, was['audit'].get(s, 0) - now['audit'].get(s, 0))
                 for s in set(was['audit']) | set(now['audit']))
    print('\ncompared with the last run: %d flags cleared' % better)
    for slug, before, after in sorted(worse, key=lambda r: r[2] - r[1],
                                      reverse=True):
        print('  REGRESSED %-52s %d -> %d' % (slug[:52], before, after))
    for key, value in now['site'].items():
        if value > was['site'].get(key, 0):
            print('  REGRESSED %-52s %d -> %d'
                  % (key, was['site'].get(key, 0), value))
    if not worse:
        print('  no paper got worse')
    json.dump(now, open(BASELINE, 'w', encoding='utf-8'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
