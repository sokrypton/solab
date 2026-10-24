#!/usr/bin/env python3
"""Layout-aware extraction of a paper PDF into an editable document.

Plain text extraction loses the one thing that tells prose apart from a figure
axis label or a table cell: where on the page it sat. This reads blocks with
their geometry and font sizes instead, classifies each one, crops the figures
out as images, and writes a document per paper:

    .cache/doc/<slug>.json     nodes in reading order, each with a stable id
    assets/papers/<slug>/      figure crops, web-sized

Nodes are never hand-edited. Corrections live in edits/<slug>.json as ops
keyed by node id, applied at build time, so this can be re-run at any point
without losing them (see apply_edits in build_papers.py).

    python3 scripts/extract_pdf.py [--only SUBSTRING] [--limit N] [--dpi 150]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter

import pymupdf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
PDF_DIR = os.path.join(CACHE, 'pdf')
DOC_DIR = os.path.join(CACHE, 'doc')
WEB_DIR = os.path.join(REPO, 'assets', 'papers')

# A caption opens its block and is punctuated like a label — "Figure 1." or
# "Fig. 2 Coevolution in…". The delimiter matters: without it, a sentence that
# happens to break before "table S3; supplementary text" reads as a caption.
LABEL = r'(Figure|Fig|Table|Scheme|Chart|Box)\.?\s*(S?\d{1,2}[A-Za-z]?)'
DELIM = r'(?:\s*[.:|—–-]\s*|\s+(?=[A-Z(]))'
CAPTION = re.compile(r'^\s*' + LABEL + DELIM, re.I)
SUPP_CAPTION = re.compile(r'^\s*(?:Supplementary|Extended\s+Data|Supplemental)\s+'
                          + LABEL + DELIM, re.I)

# a line of a reference list, and the headings that introduce back matter
CITE = re.compile(r'\bet al\b|\(\d{4}[a-z]?\)|\b(19|20)\d{2}[a-z]?[.;)]|'
                  r'\bdoi\b|\bpp\.\s*\d|arxiv|biorxiv', re.I)

# A section heading by name rather than by typography. Cell sets these smaller
# than its body text, so size alone reads them as footnotes.
# Cell's STAR Methods section headers, set in white on a coloured band. The
# band makes them look like figure interior to a geometric test.
STAR_SECTION = re.compile(
    r'^(star\s*\+?\s*methods|key resources table|'
    r'(?:experimental|animal) model[a-z\s]*details|method details|'
    r'quantification and statistical analysis|'
    r'data and (?:software|code) availability|resource availability)\s*$', re.I)

CANON_HEAD = re.compile(
    r'^(?:\d{1,2}[.)]?\s+|[IVX]{1,4}[.)]\s+)?'
    r'(abstract|summary|introduction|background|results and discussion|results|'
    r'discussion|materials and methods|methods and materials|methods|'
    r'experimental procedures|star\s*\+?\s*methods|method details|'
    r'conclusions?|outlook|significance|main)\s*[:.]?$', re.I)

# The front-of-issue furniture publishers wrap around a paper
COVER_HEAD = re.compile(r'^(graphical abstract|highlights|authors?|in brief|'
                        r'correspondence.*|article|research article|keywords?|'
                        r'key words|editor|abstract graphic|one sentence summary)'
                        r'\s*:?$', re.I)
SELF_CITE = re.compile(r'^[A-Z][A-Za-z’\'-]+ et al\.?,?\s*(19|20)\d{2}')

# Science and Nature bind a standalone summary page ahead of the paper: a
# graphical abstract, a structured précis, the byline again. When the publisher
# labels the page as such, the whole page is front matter.
SUMMARY_PAGE = re.compile(r'^(research\s+articles?\s+summary|review\s+summary|'
                          r'research\s+summary|in\s+brief\s+summary)\s*$', re.I)

# labels of that structured précis — "INTRODUCTION:", "RATIONALE:" — which look
# like section headings but sit inside the summary
SUMMARY_LABEL = re.compile(r'^(introduction|rationale|results|conclusions?|'
                           r'background|objective)\s*:$', re.I)
# "1 Department of Systems Biology, Columbia University, New York, NY, USA."
# — the numbered affiliation footnote at the foot of a page
AFFIL_BLOCK = re.compile(r'^\d{1,2}\s+[A-Z][a-z]')
AFFIL = re.compile(r'\b(university|universit[eé]|department|institute|instituto|'
                   r'laborator(?:y|ies)|school of|college|centre|center|hospital|'
                   r'academy|hhmi)\b', re.I)
# "Rochereau1,2", "Rochereau 1,2 †" — extraction may space out the affiliation
# markers and daggers that follow a surname. The leading word must be
# capitalised: without that, ordinary prose ("at least 20 canonical") matches.
BYLINE = re.compile(r'[A-Z][a-z]{2,}\s?[#*†‡]?\s?\d{1,2}(?:\s?,\s?\d{1,2})*'
                    r'\s?[#*†‡]?(?=[,;\s]|$)')
REFS_HEAD = re.compile(r'^(references|bibliography|literature cited|'
                       r'references and notes)\s*[:.]?$', re.I)
APPARATUS_HEAD = re.compile(
    r'^(acknowledge?ments?|author contributions?|competing interests?|'
    r'declarations?(?: of interests?)?|conflicts? of interest|funding|'
    r'data (?:and code )?availability|code availability|'
    r'supplementary information|supplemental information|key resources table|'
    r'additional information|ethics declarations|reporting summary|'
    r'declaration of competing|editor.s summary|about the authors?|'
    r'terms of service|permissions|reprints and permissions)\s*[:.]?$', re.I)

# The publisher's legal block closes the PDF: nothing after it is the paper.
TAIL_BLOCK = re.compile(r'^(use of this article is subject|science \(issn|'
                        r'copyright ©|view the article online|'
                        r'© \d{4} the authors|'
                        # the "cite this article as" line
                        r'(science|nature|cell)\s+\d{2,4}\s*\(\d+\))', re.I)

# the author list that heads that citation panel: names and commas, no sentence
NAME_LIST = re.compile(r'^[A-Z][a-z]+ [A-Z]')

# symbols that only appear in a formula
MATHY = re.compile(r'[∑∏∫√≈≠≤≥≈∝±×÷−–⁄⟨⟩∈∀∃θλμσαβγδΔ∆∇]|=\s|=$|\blog\b|\bsoftmax\b|'
                   r'\barg\s*max\b|[a-z]\s*[{(]\s*[ijkn]\s*[})]')


def panel_label(text):
    """Panel letters and axis keys: "C D", "F G H", "A B G.O.F. phenotype".

    These sit around the artwork rather than inside its drawn area, so geometry
    alone leaves them as headings — and a contents rail full of "I J K" is the
    result. The tell is that most of the tokens are one or two characters.
    """
    tokens = text.split()
    if not 1 <= len(tokens) <= 6:
        return False
    if len(tokens) == 1:               # a lone panel letter
        bare = tokens[0].strip('.,;:()')
        return len(bare) <= 2 and bare.isupper()
    # residue identifiers labelling a structure figure: "L1786 S1787 E1788"
    if sum(1 for t in tokens if re.fullmatch(r'[A-Z]\d{2,4}[`\']?', t)) >= 2:
        return True
    # a sequence or a row of one-letter codes, with no lower-case anywhere:
    # "REALYRG A YDV M R", "I PR Y Q GF M PR Y R GF"
    if len(tokens) >= 3 and not re.search(r'[a-z]', text):
        return True
    short = sum(1 for t in tokens if len(t.strip('.,;:()')) <= 2
                and t.strip('.,;:()').isupper() or t.isdigit())
    return short >= max(2, len(tokens) / 2)

# preprint and publisher stamps that repeat down the side of every page
STAMP = re.compile(r'(which was not certified by peer review|is the author/funder|'
                   r'granted bioRxiv a license|available under a CC-BY|'
                   r'preprint doi|this version posted|no reuse allowed)', re.I)


# Typographic ligatures come straight out of the PDF font: "modiﬁcation",
# "ﬂuorescence". They read fine but break search, copy-paste and any text
# comparison — GROBID normalises them, and so should this.
LIGATURES = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi',
             'ﬄ': 'ffl', 'ﬅ': 'ft', 'ﬆ': 'st'}


# A hyphen at a line break is ambiguous: "bidirec- tional" must close up,
# "high- confidence" must keep its hyphen. Without a dictionary the reliable
# signal is the first element — these words are whole words that form compounds,
# never syllable fragments, so a hyphen after them is the author's.
COMPOUND_HEAD = re.compile(
    r'(?:^|[\s(\[])(?:high|low|well|self|non|semi|multi|cross|single|double|'
    r'triple|long|short|wild|full|half|one|two|three|four|first|second|third|'
    r'large|small|whole|near|mid|pre|post|anti|pro|co|re|sub|super|inter|intra|'
    r'trans|ultra|micro|macro|nano|meta|end|side|top|bottom|left|right|open|'
    r'closed|free|fixed|based|like|specific|dependent|independent|wide|deep|'
    r'state|real|time|N|C|X|3D|2D)$', re.I)


# Invisible characters the typesetter used for line breaking. A soft hyphen is
# why "high-\u00adconfidence" arrived as "highconfidence": it sits between the
# hyphen and the next word and defeats every pattern that looks for one.
INVISIBLE = dict.fromkeys(map(ord, '\u00ad\u200b\u200c\u200d\u2060\ufeff'), None)


# Publisher PDFs lose specific glyphs through extraction. Only substitutions
# that cannot be confused with real text are made here: "DmlaE" for ΔmlaE is
# NOT among them, because the same shape matches tool names like DockQ.
GLYPH_FIXES = (
    (re.compile(r'A\s?˚|˚\s?A'), 'Å'),
    # α-helical, β-sheet: no such thing as an a-sheet or a b-helix
    (re.compile(r'\b([ab])-(?=(?:helic|helix|barrel|sheet|strand|turn))'),
     lambda m: ('α' if m.group(1) == 'a' else 'β') + '-'),
    # β5-β6 strand pairs
    (re.compile(r'\bb(\d{1,2})-b(\d{1,2})\b'), r'β\1-β\2'),
    # "~35%" arrives as "$35%". Currency is left alone: "US$2,000" is real.
    (re.compile(r'(?<!US)(?<!U\.S\.)\$(?=\s?\d)'), '~'),
)


def fix_glyphs(text):
    for pattern, repl in GLYPH_FIXES:
        text = pattern.sub(repl, text)
    return text


def dehyphenate(text):
    """Close up words broken across a line, keeping genuine compounds."""
    text = fix_glyphs(text.translate(INVISIBLE))
    def join(m):
        head, tail = m.group(1), m.group(2)
        # a compound keeps its hyphen but loses the line break
        if COMPOUND_HEAD.search(head):
            return '%s-%s' % (head, tail)
        return head + tail
    return re.sub(r'([A-Za-z]{2,})-\s+([a-z]{2,})', join, text)


def norm(text):
    text = (text or '').translate(str.maketrans(LIGATURES))
    text = re.sub(r'\s+', ' ', text).strip()
    return dehyphenate(text)


def furniture_key(text):
    """Running headers repeat with only their page number changing."""
    return re.sub(r'\d+', '#', norm(text))[:60]


def node_id(page_no, text, bbox):
    """Stable across re-extraction: keyed on content, not on position in file.

    An edit written against a node keeps applying as long as that node's text
    survives; if extraction changes the text, the op stops matching and shows
    up as stale rather than silently landing on the wrong paragraph.
    """
    seed = norm(text)[:200] or ('%.0f,%.0f' % (bbox[0], bbox[1]))
    return 'p%d-%s' % (page_no, hashlib.sha1(seed.encode()).hexdigest()[:6])


def uniquify_ids(doc):
    """Give repeated text distinct ids, keeping the first occurrence's id.

    Identical text on one page — an equation shard, a repeated table cell —
    hashes to one id, and an op against it could only ever reach whichever copy
    the lookup happened to keep. Suffixing later copies leaves every existing
    op pointing where it already pointed, and makes the rest reachable.
    """
    seen = {}
    for node in doc['nodes']:
        base = node['id']
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            node['id'] = '%s-%d' % (base, seen[base])
    return doc


# ---------- page geometry ----------

def block_text(block):
    return norm(' '.join(s['text'] for l in block.get('lines', [])
                         for s in l.get('spans', [])))


def block_size(block):
    """The dominant font size in a block, weighted by how much text uses it."""
    sizes = Counter()
    for line in block.get('lines', []):
        for span in line.get('spans', []):
            sizes[round(span['size'], 1)] += len(span['text'])
    return sizes.most_common(1)[0][0] if sizes else 0


BOLD_NAME = re.compile(r'bold|black|heavy|semib|-b\b', re.I)


def span_bold(span):
    """PyMuPDF's bold flag is often unset; the font name still says so."""
    return bool(span['flags'] & 2 ** 4) or bool(BOLD_NAME.search(span.get('font', '')))


def block_bold(block):
    spans = [s for l in block.get('lines', []) for s in l.get('spans', [])]
    return bool(spans) and sum(span_bold(s) for s in spans) > len(spans) / 2


def dominant_font(block):
    fonts = Counter()
    for line in block.get('lines', []):
        for span in line.get('spans', []):
            fonts[span.get('font', '')] += len(span['text'])
    return fonts.most_common(1)[0][0] if fonts else ''


def body_size(doc):
    """Modal font size across the document: the size the prose is set in."""
    sizes = Counter()
    for page in doc:
        for block in page.get_text('dict')['blocks']:
            if block['type'] == 0:
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        sizes[round(span['size'], 1)] += len(span['text'])
    return sizes.most_common(1)[0][0] if sizes else 10.0


def columns(blocks, page_width):
    """One column or two, decided by where block centres fall."""
    wide = [b for b in blocks if b['bbox'][2] - b['bbox'][0] > page_width * 0.55]
    if len(wide) > len(blocks) * 0.4:
        return 1
    left = sum(1 for b in blocks if (b['bbox'][0] + b['bbox'][2]) / 2 < page_width / 2)
    right = len(blocks) - left
    return 2 if min(left, right) >= 2 else 1


def reading_order(blocks, page_width, ncols):
    """Column-major for a two-column page, otherwise top to bottom."""
    if ncols == 1:
        return sorted(blocks, key=lambda b: (round(b['bbox'][1], 1), b['bbox'][0]))
    mid = page_width / 2

    def key(b):
        x0, y0, x1, _ = b['bbox']
        spans_both = x0 < mid < x1 and (x1 - x0) > page_width * 0.5
        col = 0 if spans_both else (0 if (x0 + x1) / 2 < mid else 1)
        # a block spanning both columns belongs above the pair, not inside one
        return (col, round(y0, 1), x0)

    return sorted(blocks, key=key)


# ---------- figures ----------

def overlaps(rect, obstacles, share=0.35):
    """Does this rectangle swallow a chunk of any block it must not cross?"""
    for ob in obstacles:
        if (rect & ob).get_area() > ob.get_area() * share:
            return True
    return False


def between(a, b):
    """The empty strip separating two rectangles, or None if they touch.

    Merging is decided on what lies *between* two pieces of artwork, not on
    what their union would cover: two panels of one figure have whitespace
    between them, while a panel above and a panel below a column of text have
    the text in between. Testing the union instead refuses both.
    """
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0)
    if dx == 0 and dy == 0:
        return None
    if dx >= dy:
        x0, x1 = min(a.x1, b.x1), max(a.x0, b.x0)
        y0, y1 = max(a.y0, b.y0), min(a.y1, b.y1)
        if y1 <= y0:                       # no vertical overlap to speak of
            y0, y1 = min(a.y0, b.y0), max(a.y1, b.y1)
    else:
        y0, y1 = min(a.y1, b.y1), max(a.y0, b.y0)
        x0, x1 = max(a.x0, b.x0), min(a.x1, b.x1)
        if x1 <= x0:
            x0, x1 = min(a.x0, b.x0), max(a.x1, b.x1)
    return pymupdf.Rect(x0, y0, x1, y1)


def prose_obstacles(blocks, body, captions, rects, min_words=15):
    """Running text that artwork must not be merged across.

    A figure's own legend can be long and set at body size, so anything sitting
    inside the drawn area is excluded — otherwise a figure with a wordy legend
    splits into fragments.
    """
    obstacles = []
    for block in blocks:
        if block in captions:
            continue                       # a caption belongs to its figure
        if block_size(block) < body * 0.9 \
                or len(block_text(block).split()) < min_words:
            continue
        r = pymupdf.Rect(block['bbox'])
        if any((r & art).get_area() > r.get_area() * 0.5 for art in rects):
            continue
        obstacles.append(r)
    return obstacles


def artwork_rects(page):
    """Everything drawn on the page that could be part of a figure."""
    page_area = page.rect.get_area()
    rects = []
    for block in page.get_text('dict')['blocks']:
        if block['type'] != 1:
            continue
        r = pymupdf.Rect(block['bbox'])
        # publisher PDFs carry full-height slivers as column masks; they are
        # not artwork and they stretch any cluster to the whole page
        if min(r.width, r.height) > 6 and max(r.width, r.height) / max(
                min(r.width, r.height), 1) < 25:
            rects.append(r)
    edge = 2
    for draw in page.get_drawings():
        r = pymupdf.Rect(draw['rect'])
        # hairlines are column rules and table borders; a page-sized box is a
        # background wash. Neither is a figure.
        if not (r.width > 20 and r.height > 20 and r.get_area() < page_area * 0.9):
            continue
        # trim and registration marks sit in the page corners and would drag a
        # cluster out to the paper edge
        touches_edge = (r.x0 <= page.rect.x0 + edge or r.y0 <= page.rect.y0 + edge
                        or r.x1 >= page.rect.x1 - edge or r.y1 >= page.rect.y1 - edge)
        if touches_edge and max(r.width, r.height) < 90:
            continue
        rects.append(r)
    return rects


def artwork_clusters(page, blocks, body, captions, gap=60):
    """Artwork on the page, grouped into figures.

    Captions may sit above, below or beside their figure, so nothing here
    reasons from the caption's position: pieces of artwork are merged whenever
    the space between them is empty. The distance allowed is generous, because
    panels of one figure can be well separated; what stops a merge is finding
    running text in the gap, not the size of the gap.
    """
    rects = artwork_rects(page)
    obstacles = prose_obstacles(blocks, body, captions, rects)
    pieces = [pymupdf.Rect(r) for r in rects]
    merged = True
    while merged:
        merged = False
        for i, a in enumerate(pieces):
            for b in pieces[i + 1:]:
                if not (a + (-gap, -gap, gap, gap)).intersects(b):
                    continue
                strip = between(a, b)
                if strip is not None and overlaps(strip, obstacles, share=0.05):
                    continue
                pieces.remove(a)
                pieces.remove(b)
                pieces.append(a | b)
                merged = True
                break
            if merged:
                break
    return [p & page.rect for p in pieces
            if p.width > 55 and p.height > 55
            and not overlaps(p, obstacles, share=0.6)]


def rect_gap(a, b):
    """How far apart two rectangles are, 0 if they touch or overlap."""
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0)
    return (dx * dx + dy * dy) ** 0.5


def margin_blocks(blocks, page, share=0.055):
    """Running heads and folios: in the margin band, and short."""
    band = page.rect.height * share
    return [pymupdf.Rect(b['bbox']) for b in blocks
            if (b['bbox'][3] < page.rect.y0 + band
                or b['bbox'][1] > page.rect.y1 - band)
            and len(block_text(b)) < 200]


def grow_region(rect, blocks, obstacles, captions, page, pad=18, margin=11):
    """Extend a region over the figure's own text: panel letters, axis titles.

    Those sit outside the drawn artwork, so a region built from drawings alone
    clips them. Anything nearby that is not running prose and not another
    figure's caption belongs to this figure; growth repeats so a chain of
    labels is picked up, and stops at prose.
    """
    # a running head is not prose, so nothing above stops the region reaching
    # it; it has to be named explicitly
    keep_out = (list(obstacles) + [pymupdf.Rect(c['bbox']) for c in captions]
                + margin_blocks(blocks, page)
                # Science prints "Downloaded from …" sideways *inside* the text
                # frame, so the margin test never sees it and the region grows
                # right over it. Only the stamp is excluded, not sideways text
                # in general: a figure's own axis titles are rotated too, and
                # keeping them out pins the region and clips the panel letters.
                + [pymupdf.Rect(b['bbox']) for b in blocks
                   if STAMP.search(block_text(b))])
    rect = pymupdf.Rect(rect)
    changed = True
    while changed:
        changed = False
        for block in blocks:
            r = pymupdf.Rect(block['bbox'])
            if r.is_empty or rect.contains(r) or rect_gap(rect, r) > pad:
                continue
            if any(r.intersects(k) and (r & k).get_area() > r.get_area() * 0.5
                   for k in keep_out):
                continue
            candidate = rect | r
            if overlaps(candidate, keep_out, share=0.25):
                continue
            rect, changed = candidate, True
    # Panel letters sit right on the region's edge, so a thin margin clips
    # them. Widen generously, then give ground back if that would start eating
    # a neighbouring block.
    grown = (rect + (-margin, -margin, margin, margin)) & page.rect
    if overlaps(grown, keep_out, share=0.12):
        grown = (rect + (-4, -4, 4, 4)) & page.rect
    return grown


def match_captions(captions, clusters, max_gap=140):
    """Pair each caption with its artwork, nearest first, one cluster each."""
    pairs, taken = [], []
    scored = sorted(
        ((rect_gap(pymupdf.Rect(cap['bbox']), cl), i, j)
         for i, cap in enumerate(captions) for j, cl in enumerate(clusters)),
        key=lambda t: t[0])
    used_caps = set()
    for dist, i, j in scored:
        if dist > max_gap or i in used_caps or j in taken:
            continue
        used_caps.add(i)
        taken.append(j)
        pairs.append((captions[i], clusters[j]))
    return pairs


def crop_figure(page, rect, out_path, dpi, max_width=1100, png_limit=140_000,
                jpeg_limit=280_000):
    """Render the region to an image, choosing the format by what's in it.

    Line art and diagrams stay PNG, where they are small and stay crisp. A
    micrograph or a rendered structure makes a huge PNG, so anything over the
    limit is re-saved as JPEG — 5-10x smaller with no visible cost on
    photographic content.
    """
    scale = dpi / 72.0
    if rect.width * scale > max_width:
        scale = max_width / rect.width
    pix = page.get_pixmap(clip=rect, matrix=pymupdf.Matrix(scale, scale))
    if pix.width < 80 or pix.height < 60:
        return None
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pix.save(out_path)
    if os.path.getsize(out_path) > png_limit:
        from PIL import Image
        jpg = re.sub(r'\.png$', '.jpg', out_path)
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        img.save(jpg, 'JPEG', quality=80, optimize=True, progressive=True)
        # a very tall composite still lands over a quarter of a megabyte
        if os.path.getsize(jpg) > jpeg_limit:
            img.save(jpg, 'JPEG', quality=70, optimize=True, progressive=True)
        if os.path.getsize(jpg) < os.path.getsize(out_path):
            os.remove(out_path)
            out_path = jpg
        else:
            os.remove(jpg)
    return {'width': pix.width, 'height': pix.height, 'path': out_path,
            'bytes': os.path.getsize(out_path)}


# ---------- classification ----------

def classify(block, page, body, ncols, in_figure, seen_counts):
    """What this block is: prose, a heading, a caption, or page furniture."""
    text = block_text(block)
    if not text:
        return 'empty'
    size = block_size(block)
    page_rect = page.rect
    x0, y0, x1, y1 = block['bbox']

    # Geometry says this sits inside a figure, but body-size running text of
    # any length is prose that the artwork was laid out around. Typography is
    # the more reliable witness, so it wins.
    if STAR_SECTION.match(text):
        return 'heading'                   # never figure interior, however set
    if in_figure and not (size >= body * 0.95 and len(text.split()) >= 25):
        return 'figure-text'
    # A folio or a running head, wherever on the page it sits. Position alone
    # misses them: publishers set folios inside the text frame, and Cell's "ll"
    # logotype and "Article" label are large enough to read as headings.
    if re.fullmatch(r'[\divxlcIVXLC]{1,6}', text) \
            or (len(text) < 60 and seen_counts[furniture_key(text)] >= 3):
        return 'furniture'
    if STAMP.search(text):
        return 'stamp'
    # a running header or footer: in the margin band, short, and repeated
    margin = (y1 < page_rect.y0 + page_rect.height * 0.055
              or y0 > page_rect.y1 - page_rect.height * 0.055)
    if margin and len(text) < 200 and seen_counts[furniture_key(text)] >= 3:
        return 'furniture'
    if margin and re.fullmatch(r'[\divxlc\s|/–—-]{1,12}', text, re.I):
        return 'furniture'
    # sideways text is a preprint stamp or a rotated table, never prose
    if block.get('lines') and abs(block['lines'][0].get('dir', (1, 0))[1]) > 0.5:
        return 'rotated'
    if CAPTION.match(text) or SUPP_CAPTION.match(text):
        return 'caption'
    if REFS_HEAD.match(text):
        return 'refs-head'
    if APPARATUS_HEAD.match(text):
        return 'apparatus-head'
    words = text.split()
    # Equation debris: a displayed formula arrives as fragments that mean
    # nothing on their own ("i = 1 log P"). Typing them as maths keeps them out
    # of the prose and out of the contents rail, where they read as sections.
    if len(words) <= 12 and MATHY.search(text) \
            and not re.search(r'\b[a-z]{5,}\b', text.lower()):
        return 'math'
    # by name, whatever size it is set at
    if CANON_HEAD.match(text):
        return 'heading'
    letters = [c for c in text if c.isalpha()]
    all_caps = letters and sum(c.isupper() for c in letters) > len(letters) * 0.85
    if (size > body * 1.06 or block_bold(block) or all_caps) \
            and len(words) <= 14 and not text.endswith(('.', ';', ',')):
        # …unless it is a row of panel letters, which is figure furniture
        return 'figure-text' if panel_label(text) else 'heading'
    if size < body * 0.86 and len(words) < 25:
        return 'small'          # axis labels, panel keys, footnotes
    return 'prose'


def split_run_in(block, body):
    """Separate a bold run-in heading from the paragraph it opens.

    Cell and Nature start a section with a bold phrase on the same line as the
    text: "MlaD Forms a Hexameric Ring… As MCE proteins are…". Kept together it
    is neither a usable heading nor a clean paragraph.
    """
    spans = [(i, s) for i, line in enumerate(block.get('lines', []))
             for s in line.get('spans', [])]
    if len(spans) < 2:
        return None
    # The head is set apart from the paragraph either by weight or, as in Cell,
    # simply by being a different font. It must be one unbroken run of that
    # font: prose is full of italic species names, which are also "different".
    main = dominant_font(block)
    lead_font = spans[0][1].get('font')
    if not (span_bold(spans[0][1]) or (main and lead_font != main)):
        return None
    parts, taken, line_at = [], 0, spans[0][0]
    for line_i, span in spans:
        # any font other than the paragraph's continues the heading: Cell sets
        # the closing term of a subsection title in italic, and stopping at the
        # first font change cuts the heading in half
        if span.get('font') == main or abs(span['size'] - body) >= body * 0.35:
            break
        if line_i != line_at and parts and not parts[-1].endswith((' ', '-')):
            parts.append(' ')              # the head wrapped to the next line
        line_at = line_i
        parts.append(span['text'])
        taken += 1
    head = norm(''.join(parts))
    rest = norm(' '.join(s['text'] for _, s in spans[taken:]))
    if not (8 <= len(head) <= 95 and len(rest.split()) >= 20):
        return None
    if head.endswith(('.', ';')) or head[:1].islower():
        return None
    return head, rest


# one bibliography entry as its own block: opens on a number or a name, and
# carries a year somewhere
# the character class carries the stray combining marks extraction leaves
# behind ("Gioffre´ , A."), and the comma may be preceded by a space
ENTRY_CH = r'\w’\'´`¨ˆ~-'
ENTRY_OPEN = re.compile(r'^(?:\[\d{1,3}\]|\d{1,3}[.)]\s'
                        r'|[A-Z][' + ENTRY_CH + r']{1,24}\s?,\s*[A-Z]'
                        r'|(?:[A-Z][' + ENTRY_CH + r']*\.?\s+){1,3}[A-Z])')


def looks_like_entry(text):
    words = len(text.split())
    return (12 <= words <= 120 and ENTRY_OPEN.match(text)
            and re.search(r'\b(?:19|20)\d{2}[a-z]?\b', text))


# a numbered bibliography entry: "12. Gao W, Mahajan SP, … 2020"
NUMBERED_ENTRY = re.compile(r'^(?:\[\d{1,3}\]|\d{1,3}[.)])\s+[A-Z]')


def looks_like_body(text):
    """Running prose: the positive signal that a bibliography has ended.

    Absence of entry shape is not that signal — a wrapped entry, a bare DOI, a
    fragment beginning "Biol. 328, 921–926 (2003)" all look like nothing in
    particular, and treating each as the end of the list strands everything
    after it. Body text is long, sentence-rich and sparsely cited.
    """
    words = text.split()
    if len(words) < 60 or text.count('. ') < 3:
        return False
    # a bibliography entry always opens on a name or a number, however long and
    # sentence-like the rest of it reads
    if ENTRY_OPEN.match(text):
        return False
    return len(CITE.findall(text)) < len(words) / 60


def looks_like_refs(text):
    """Citation density high enough that the block can only be a bibliography.

    Judged per word, not per line: a block of body prose in an author-year
    field can hold half a dozen citations and still be prose, while a
    bibliography carries one every twenty words or so.
    """
    words = len(text.split())
    if words < 20:
        return False
    cites = len(CITE.findall(text))
    years = len(re.findall(r'\b(?:19|20)\d{2}[a-z]?\b', text))
    return cites >= max(3, words / 35) and years >= 3


# ---------- extraction ----------

def extract(pdf_path, slug, dpi=150, figures=True):
    doc = pymupdf.open(pdf_path)
    body = body_size(doc)

    counts = Counter()
    for page in doc:
        for block in page.get_text('dict')['blocks']:
            if block['type'] == 0:
                counts[furniture_key(block_text(block))] += 1

    nodes, figs, fig_n = [], [], 0
    for pno, page in enumerate(doc, start=1):
        blocks = [b for b in page.get_text('dict')['blocks']
                  if b['type'] == 0 and block_text(b)]
        images = [b for b in page.get_text('dict')['blocks'] if b['type'] == 1]
        ncols = columns(blocks, page.rect.width)

        # figure regions first: everything inside one is artwork, not prose
        caption_blocks = [b for b in blocks
                          if CAPTION.match(block_text(b))
                          or SUPP_CAPTION.match(block_text(b))]
        rects = artwork_rects(page)
        obstacles = prose_obstacles(blocks, body, caption_blocks, rects)
        clusters = artwork_clusters(page, blocks, body, caption_blocks)
        regions = [(cap, grow_region(rect, blocks, obstacles, caption_blocks, page))
                   for cap, rect in match_captions(caption_blocks, clusters)]
        captions = {id(b) for b, _ in regions}
        for block in reading_order(blocks, page.rect.width, ncols):
            r = pymupdf.Rect(block['bbox'])
            covered = any((rect & r).get_area() > r.get_area() * 0.65
                          for cap, rect in regions if cap is not block)
            kind = classify(block, page, body, ncols, covered, counts)
            text = block_text(block)
            node = {'id': node_id(pno, text, block['bbox']), 'type': kind,
                    'text': text, 'page': pno,
                    'size': block_size(block), 'bold': block_bold(block),
                    'bbox': [round(v, 1) for v in block['bbox']],
                    # the original line breaks: a bibliography can only be
                    # split into entries with them, and they give an editing
                    # pass the same view of the page the PDF had
                    'lines': [norm(' '.join(s['text'] for s in l.get('spans', [])))
                              for l in block.get('lines', [])]}

            if kind == 'caption' and id(block) in captions:
                rect = next(rc for cap, rc in regions if cap is block)
                fig_n += 1
                name = 'fig-%02d.png' % fig_n
                out = os.path.join(WEB_DIR, slug, name)
                meta = crop_figure(page, rect, out, dpi) if figures else None
                if meta:
                    label = CAPTION.match(text) or SUPP_CAPTION.match(text)
                    rel = os.path.relpath(meta['path'], REPO)
                    node.update({'type': 'figure',
                                 'label': norm(label.group(0)) if label else '',
                                 'image': rel,
                                 'image_size': [meta['width'], meta['height']],
                                 'region': [round(v, 1) for v in rect]})
                    figs.append(rel)
            nodes.append(node)

            # a bold phrase opening a paragraph is a section heading; emit it
            # as one and leave the paragraph without it
            if kind == 'prose':
                split = split_run_in(block, body)
                if split:
                    head, rest = split
                    # "ACKNOWLEDGMENTS We thank…" is back matter, not a section:
                    # once lifted out, the head has to be classified again
                    kind = ('refs-head' if REFS_HEAD.match(head) else
                            'apparatus-head' if APPARATUS_HEAD.match(head)
                            else 'heading')
                    node.update({'type': kind, 'text': head,
                                 'lines': [head], 'run_in': True})
                    nodes.append({'id': node_id(pno, rest, block['bbox']),
                                  'type': 'prose', 'text': rest, 'page': pno,
                                  'size': node['size'], 'bold': False,
                                  'bbox': node['bbox'], 'lines': [rest]})

    doc.close()
    return {'slug': slug, 'source': os.path.relpath(pdf_path, REPO),
            'body_size': body, 'nodes': nodes, 'figures': figs}


# a block that ends mid-sentence, and one that starts mid-sentence
OPEN_END = re.compile(r'[a-z0-9,;:\-–(\[]$')
OPEN_START = re.compile(r'^[a-z0-9(\[]')
# "1 Department of…" opens a footnote, not the rest of a sentence
FOOTNOTE_OPEN = re.compile(r'^\d{1,2}\s+[A-Z][a-z]')

SKIPPABLE = {'small', 'figure-text', 'furniture', 'stamp', 'rotated', 'empty',
             'figure', 'caption'}


def stitch_prose(doc):
    """Rejoin paragraphs that a column or page break cut in half.

    A PDF has no paragraphs, only blocks: text flowing from the foot of one
    column to the head of the next arrives as two. They are rejoined when the
    first ends mid-sentence and the second starts mid-sentence, which is the
    same test a reader applies. Figures and page furniture in between are
    stepped over, since artwork interrupts the flow without ending it.
    """
    nodes = doc['nodes']
    keep, merged = [], 0
    for node in nodes:
        prev = next((n for n in reversed(keep)
                     if n['type'] not in SKIPPABLE), None)
        if (node['type'] == 'prose' and prev is not None
                and prev['type'] == 'prose'
                and not node.get('role') and not prev.get('role')
                and OPEN_END.search(prev['text'])
                and OPEN_START.match(node['text'])
                and not FOOTNOTE_OPEN.match(node['text'])
                and not AFFIL_BLOCK.match(node['text'])
                and node['page'] - prev['page'] <= 1):
            joiner = '' if prev['text'].endswith(('-', '–')) else ' '
            if joiner == '':
                prev['text'] = prev['text'][:-1]        # drop the hyphen
            prev['text'] = prev['text'] + joiner + node['text']
            prev['lines'] = prev.get('lines', []) + node.get('lines', [])
            prev.setdefault('stitched', []).append(node['id'])
            merged += 1
            continue
        keep.append(node)
    doc['nodes'] = keep
    doc['stitched'] = merged
    return doc


def split_glued_headings(doc):
    """Separate a named section from the subsection glued onto it.

    "Materials and methods Strains and plasmids" is two headings set on one
    line. This runs over the finished node list rather than inside the loop,
    because such a heading can arrive either from the classifier or from the
    run-in splitter, and only one of those was being caught.
    """
    out = []
    for node in doc['nodes']:
        if node['type'] == 'heading':
            # split on the case change, and also where an all-caps STAR header
            # runs straight into its first subsection title
            parts = re.split(r'(?<=[a-z])\s+(?=[A-Z])|(?<=[A-Z])\s+(?=[A-Z][a-z])',
                             node['text'], maxsplit=1)
            if len(parts) == 2 and (CANON_HEAD.match(parts[0])
                                    or STAR_SECTION.match(parts[0])) \
                    and len(parts[1].split()) >= 2:
                lead = dict(node, text=parts[0], lines=[parts[0]],
                            id=node_id(node.get('page', 0), parts[0], node['bbox']))
                rest = dict(node, text=parts[1], lines=[parts[1]],
                            id=node_id(node.get('page', 0), parts[1], node['bbox']))
                out.extend([lead, rest])
                continue
        out.append(node)
    doc['nodes'] = out
    return doc


def mark_front_matter(doc, pages=2):
    """Flag the cover: byline, affiliations, highlights, journal self-citation.

    Publishers put a whole issue-front page ahead of the paper — Cell's is a
    graphical abstract, a highlights list and an "In Brief" blurb — and it is
    not part of the text. Only the opening pages are considered, and the search
    stops at the first named section heading, so nothing in the body is touched.
    """
    # a publisher-labelled summary page is front matter in its entirety,
    # graphical abstract included
    summary_pages = {n['page'] for n in doc['nodes'] if SUMMARY_PAGE.match(n['text'])}
    if summary_pages:
        for node in doc['nodes']:
            if node['page'] in summary_pages:
                node['role'] = 'front'

    on_cover = False
    for node in doc['nodes']:
        if node['page'] > pages:
            break
        if node.get('role') == 'front':
            continue
        text = node['text']
        if node['type'] == 'heading' and CANON_HEAD.match(text) \
                and not SUMMARY_LABEL.match(text):
            break                          # the paper proper starts here
        # Artwork is never cover furniture, and once a figure appears the cover
        # is over: the run would otherwise swallow the section headings and the
        # first figure of a paper whose body starts on page one.
        if node['type'] in ('figure', 'caption'):
            on_cover = False
            continue
        # A byline and an affiliation block are *lists*: comma-dense, almost no
        # full stops. Without that qualifier, protein nomenclature carries the
        # same shape as an author marker — "Ile 74", "RpsJ 30S" look exactly
        # like "Rochereau 1,2" — and body paragraphs read as cover furniture.
        words = text.split()
        listy = (text.count(',') >= 6 and text.count('. ') <= 2
                 and len(words) < 140)
        cover_signal = (COVER_HEAD.match(text) or SELF_CITE.match(text)
                        or (AFFIL_BLOCK.match(text) and len(AFFIL.findall(text)) >= 2)
                        or (listy and (len(BYLINE.findall(text)) >= 3
                                       or len(AFFIL.findall(text)) >= 2)))
        # Body text ends the run — but a byline is long and full of stops from
        # its affiliation abbreviations, so its own signal has to be read first
        # or a 57-word author list reads as the start of the paper.
        if not cover_signal and len(words) >= 45 and text.count('. ') >= 1:
            on_cover = False
            continue
        # Once a cover signal appears, what follows is cover too: the bullets
        # under Highlights and the blurb under In Brief are separate blocks and
        # carry no signal of their own. A long paragraph is exempted — that is
        # body text, or an abstract, not issue furniture.
        if cover_signal or (on_cover and len(text.split()) < 120):
            node['role'] = 'front'
            on_cover = True
    return doc


def mark_back_matter(doc):
    """Flag the bibliography and the apparatus, block by block.

    With geometry there is no need for the line-level guessing the plain-text
    path had to do: back matter starts at its heading and ends at the next
    block that is unmistakably prose again.
    """
    state, misses = None, 0
    for node in doc['nodes']:
        if node['type'] == 'refs-head':
            state, misses = 'refs', 0
            node['role'] = 'back'
            continue
        if node['type'] == 'apparatus-head':
            state, misses = 'apparatus', 0
            node['role'] = 'back'
            # Nature's Reporting Summary is a blank eight-page form at the very
            # end; nothing after it is ever part of the paper
            if re.match(r'reporting summary', node['text'], re.I):
                state = 'tail'
            continue
        if TAIL_BLOCK.match(node['text']):
            state = 'tail'                 # the publisher's closing legal block
            # the citation panel opens with the author list, one node earlier
            prev = doc['nodes'][doc['nodes'].index(node) - 1]
            if prev.get('role') is None and NAME_LIST.match(prev['text']) \
                    and prev['text'].count(',') >= 4 and prev['text'].count('. ') <= 1:
                prev['role'] = 'back'
        if state == 'tail':
            node['role'] = 'back'
            continue
        if state and node['type'] in ('heading', 'figure', 'caption'):
            state = None
        if state == 'refs' and node['type'] in ('prose', 'small'):
            # Under a References heading a block is an entry either by being
            # citation-dense (the whole list in one block) or by being shaped
            # like one entry. A few blocks in a row will match neither — a
            # hanging-indent continuation, an entry opening on an accented
            # surname — and ending the list there strands every entry after it,
            # so it takes a run of misses to conclude the list is over.
            if not looks_like_body(node['text']):
                node['role'] = 'references'
                continue
            state = None
        if state == 'apparatus' and node['type'] in ('prose', 'small'):
            node['role'] = 'back'
            continue
        # An unheaded bibliography: some PDFs lose the heading in extraction, or
        # never had one. A single numbered paragraph proves nothing, so this
        # needs a run of them — consecutive entries, each with a year.
        if state is None and node['type'] in ('prose', 'small') \
                and NUMBERED_ENTRY.match(node['text']):
            i = doc['nodes'].index(node)
            near = [n for n in doc['nodes'][i:i + 5]
                    if n['type'] in ('prose', 'small')]
            if sum(1 for n in near if NUMBERED_ENTRY.match(n['text'])) >= 3:
                state = 'refs'
                node['role'] = 'references'
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs_text.json'))
    ap.add_argument('--only', help='build just the papers matching this substring')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--no-figures', action='store_true')
    ap.add_argument('--force', action='store_true',
                    help='re-extract even where a document already exists')
    ap.add_argument('--figures-only', action='store_true',
                    help='regenerate the figure crops, leave documents alone')
    ap.add_argument('--doc-dir', default=DOC_DIR,
                    help='where to write documents (use .cache/doc_ours to keep '
                         'this extraction alongside another source rather than '
                         'replacing it)')
    ap.add_argument('--override-publisher', action='store_true',
                    help="replace a publisher's own conversion (rarely right)")
    args = ap.parse_args()

    recs = json.load(open(args.pubs, encoding='utf-8'))
    todo = [r for r in recs if r.get('text_file')]
    if args.only:
        todo = [r for r in todo if args.only.lower() in r['title'].lower()
                or args.only.lower() in r['text_file'].lower()]
    if args.limit:
        todo = todo[:args.limit]

    os.makedirs(DOC_DIR, exist_ok=True)
    n_fig = 0
    for rec in todo:
        slug = os.path.basename(rec['text_file'])[:-4]
        # A publisher's own conversion outranks anything reconstructed here, so
        # never overwrite one: both writers target .cache/doc/.
        existing = os.path.join(args.doc_dir, slug + '.json')
        if os.path.exists(existing) and not args.override_publisher \
                and not args.figures_only:
            try:
                if json.load(open(existing, encoding='utf-8')).get('source') \
                        == 'biorxiv':
                    print('  ..   %-58s publisher full text, left alone'
                          % slug[:58])
                    continue
            except Exception:                           # noqa: BLE001
                pass
        pdf = os.path.join(PDF_DIR, slug + '.pdf')
        if not os.path.exists(pdf):
            print('  --   no pdf  %s' % slug)
            continue
        try:
            doc = uniquify_ids(mark_back_matter(stitch_prose(mark_front_matter(
                split_glued_headings(
                    extract(pdf, slug, args.dpi,
                            figures=not args.no_figures))))))
        except Exception as exc:                        # noqa: BLE001
            print('  !!   %s: %s' % (slug, exc))
            continue
        if not args.figures_only:
            os.makedirs(args.doc_dir, exist_ok=True)
            with open(os.path.join(args.doc_dir, slug + '.json'), 'w',
                      encoding='utf-8') as fh:
                json.dump(doc, fh, indent=1, ensure_ascii=False)
        kinds = Counter(n['type'] for n in doc['nodes'])
        n_fig += len(doc['figures'])
        print('  ok   %-58s %3d prose %2d fig %3d dropped'
              % (slug[:58], kinds['prose'], len(doc['figures']),
                 sum(v for k, v in kinds.items()
                     if k in ('figure-text', 'furniture', 'stamp', 'small', 'rotated'))))
    print('\n%d documents, %d figures' % (len(todo), n_fig))


if __name__ == '__main__':
    sys.exit(main())
