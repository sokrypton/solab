#!/usr/bin/env python3
"""Turn a paper's display equations into LaTeX, then into MathML.

GROBID marks each <formula> and, asked for coordinates, says exactly where it
sits on the page. That removes the hard half of the problem: no detection, and
no risk of running an OCR model over prose. Each formula is cropped at print
resolution, read by Texify, and converted to MathML at build time so browsers
render it natively — the same vocabulary the JATS path already uses.

The plain text is always kept. A wrong formula is worse than a plain one, so
the LaTeX is only used when it parses.

    python3 scripts/equations.py --slug SUBSTRING [--dpi 300] [--write]

Writes .cache/equations/<slug>.json:  {formula text -> {latex, mathml}}
"""

import argparse
import glob
import json
import os
import re
import sys

import pymupdf
import requests
from lxml import etree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
PDF_DIR = os.path.join(CACHE, 'pdf')
OUT_DIR = os.path.join(CACHE, 'equations')
CROP_DIR = os.path.join(CACHE, 'equation_crops')
NS = {'t': 'http://www.tei-c.org/ns/1.0'}

sys.path.insert(0, os.path.join(REPO, 'scripts'))
from ingest_tei import looks_like_equation, norm            # noqa: E402


def formulas_with_coords(pdf, url):
    """Every <formula> GROBID finds, with its page rectangle."""
    with open(pdf, 'rb') as fh:
        r = requests.post(url.rstrip('/') + '/api/processFulltextDocument',
                          files={'input': fh},
                          data={'consolidateHeader': '0',
                                'teiCoordinates': 'formula'},
                          timeout=900)
    r.raise_for_status()
    root = etree.fromstring(r.content)
    out = []
    for formula in root.findall('.//t:formula', NS):
        text = norm(' '.join(formula.itertext()))
        coords = formula.get('coords') or ''
        if not text or not coords:
            continue
        # coords lists one box per line. Unioning them was wrong: GROBID
        # sometimes files several equations under one <formula>, and the union
        # then spans two columns and most of a page — unreadable to any OCR.
        # Group instead into runs of adjacent lines within a column.
        boxes = []
        for part in coords.split(';'):
            bits = part.split(',')
            if len(bits) != 5:
                continue
            page, x, y, w, h = int(bits[0]), *map(float, bits[1:])
            boxes.append((page, pymupdf.Rect(x, y, x + w, y + h)))
        for page, group in group_lines(boxes):
            out.append({'text': text, 'page': page, 'rect': list(group)})
    return out


def group_lines(boxes, gap=14):
    """Runs of adjacent line boxes in the same column, as separate regions."""
    groups = []
    for page, rect in sorted(boxes, key=lambda b: (b[0], b[1].y0, b[1].x0)):
        merged = False
        for i, (gpage, grect) in enumerate(groups):
            overlap = min(grect.x1, rect.x1) - max(grect.x0, rect.x0)
            if (gpage == page and overlap > min(grect.width, rect.width) * 0.3
                    and rect.y0 - grect.y1 < gap):
                groups[i] = (gpage, grect | rect)
                merged = True
                break
        if not merged:
            groups.append((page, pymupdf.Rect(rect)))
    return [(p, r) for p, r in groups if r.width > 20 and r.height > 6]


def crop(pdf_path, slug, entries, dpi=300, pad=6):
    """Render each formula's region at OCR resolution."""
    os.makedirs(os.path.join(CROP_DIR, slug), exist_ok=True)
    doc = pymupdf.open(pdf_path)
    for i, entry in enumerate(entries, 1):
        page = doc[entry['page'] - 1]
        rect = (pymupdf.Rect(entry['rect']) + (-pad, -pad, pad, pad)) & page.rect
        pix = page.get_pixmap(clip=rect, matrix=pymupdf.Matrix(dpi / 72, dpi / 72))
        path = os.path.join(CROP_DIR, slug, 'eq-%02d.png' % i)
        pix.save(path)
        entry['crop'] = path
    doc.close()
    return entries


def to_mathml(latex):
    """LaTeX to MathML, or None if it will not parse.

    Rendering happens at build time so the page needs no JavaScript, and an
    unparseable formula falls back to the plain text rather than shipping
    something broken.
    """
    try:
        import latex2mathml.converter
        return latex2mathml.converter.convert(latex)
    except Exception:                                   # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', required=True)
    ap.add_argument('--url', default='http://localhost:8070')
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--write', action='store_true',
                    help='save the LaTeX for the builder to use')
    args = ap.parse_args()

    pdfs = [p for p in sorted(glob.glob(os.path.join(PDF_DIR, '*.pdf')))
            if args.slug.lower() in os.path.basename(p).lower()]
    if not pdfs:
        print('no PDF matches %r' % args.slug)
        return 1
    pdf = pdfs[0]
    slug = os.path.basename(pdf)[:-4]

    entries = formulas_with_coords(pdf, args.url)
    real = [e for e in entries if looks_like_equation(e['text'])]
    print('%d formulas, %d that state a relation (the rest are figure strips)'
          % (len(entries), len(real)))
    real = crop(pdf, slug, real, args.dpi)

    # pix2tex rather than texify: texify 0.2.1 predates transformers 4.57 and
    # its config repr crashes, and pinning transformers down for one tool would
    # constrain everything else in the venv.
    from pix2tex.cli import LatexOCR
    from PIL import Image

    reader = LatexOCR()
    results = []
    for entry in real:
        try:
            results.append(reader(Image.open(entry['crop'])))
        except Exception as exc:                        # noqa: BLE001
            print('  !! %s: %s' % (os.path.basename(entry['crop']), exc))
            results.append('')

    out = {}
    for entry, latex in zip(real, results):
        latex = (latex or '').strip()
        mathml = to_mathml(latex) if latex else None
        out[entry['text']] = {'latex': latex, 'mathml': mathml,
                              'page': entry['page']}
        print('\n  plain : %s' % entry['text'][:90])
        print('  latex : %s' % latex[:90])
        print('  mathml: %s' % ('parsed' if mathml else 'FAILED — plain text kept'))

    if args.write:
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump(out, open(os.path.join(OUT_DIR, slug + '.json'), 'w',
                            encoding='utf-8'), indent=1, ensure_ascii=False)
        print('\nwrote %s.json' % slug)
    return 0


if __name__ == '__main__':
    sys.exit(main())
