#!/usr/bin/env python3
"""Assemble everything a refinement pass needs for one paper.

A PDF that no publisher gives us as structured text is read two ways, because
each sees what the other misses: GROBID for sections, citations and a parsed
bibliography, and our own layout pass for figures, for knowing which text sits
*inside* a figure, and for words GROBID drops at column breaks.

This runs both, crops the figures and the equations, builds the page and lists
what still looks wrong — so a reader (human or agent) starts from evidence
rather than from the PDF.

    python3 scripts/prepare_paper.py --slug SUBSTRING

Leaves behind:
    .cache/doc_ours/<slug>.json        our layout-aware extraction
    .cache/doc/<slug>.json             GROBID's, with our figures merged in
    assets/papers/<slug>/              figure images
    .cache/equation_crops/<slug>/      one image per display equation
    papers/<slug>/index.html           the page as a reader sees it
"""

import argparse
import glob
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, '.venv', 'bin', 'python')
CACHE = os.path.join(REPO, '.cache')


def run(script, *args):
    out = subprocess.run([PY, os.path.join(REPO, 'scripts', script), *args],
                         capture_output=True, text=True, cwd=REPO)
    lines = [l for l in (out.stdout + out.stderr).splitlines()
             if l.startswith(('  ok', '  --', '  !!', '  ..'))]
    return lines[-1] if lines else (out.stderr.strip().splitlines() or [''])[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', required=True)
    ap.add_argument('--title', help='title substring for the builder (defaults '
                                    'to the slug)')
    args = ap.parse_args()

    pdfs = [p for p in sorted(glob.glob(os.path.join(CACHE, 'pdf', '*.pdf')))
            if args.slug.lower() in os.path.basename(p).lower()]
    if not pdfs:
        print('no PDF matches %r' % args.slug)
        return 1
    slug = os.path.basename(pdfs[0])[:-4]

    doc_path = os.path.join(CACHE, 'doc', slug + '.json')
    if os.path.exists(doc_path):
        source = json.load(open(doc_path, encoding='utf-8')).get('source')
        if source == 'biorxiv':
            print('%s already has the publisher\'s own full text — nothing to '
                  'refine here.' % slug)
            return 0

    print('paper: %s\n' % slug)
    print('  ours     %s' % run('extract_pdf.py', '--only', args.slug,
                                '--doc-dir', os.path.join(CACHE, 'doc_ours')))
    print('  figures  %s' % run('extract_pdf.py', '--only', args.slug,
                                '--figures-only'))
    print('  grobid   %s' % run('ingest_tei.py', '--only', args.slug))
    print('  page     %s' % run('build_papers.py', '--only',
                                args.title or args.slug.replace('-', ' ')))

    # equation crops: the OCR models are unreliable on these, but the images are
    # exactly what a reader needs to transcribe from
    try:
        sys.path.insert(0, os.path.join(REPO, 'scripts'))
        import equations as E
        entries = [e for e in E.formulas_with_coords(pdfs[0],
                                                     'http://localhost:8070')
                   if E.looks_like_equation(e['text'])]
        E.crop(pdfs[0], slug, entries, dpi=300)
        print('  maths    %d display equations cropped' % len(entries))
    except Exception as exc:                            # noqa: BLE001
        print('  maths    could not crop (%s)' % str(exc)[:60])

    print('\n--- what still looks wrong ---')
    out = subprocess.run([PY, os.path.join(REPO, 'scripts', 'audit_papers.py'),
                          '--slug', slug], capture_output=True, text=True,
                         cwd=REPO)
    print(out.stdout.strip() or '  (no flags)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
