#!/usr/bin/env python3
"""Extract papers with GROBID, taking its figure images where it has them.

GROBID is a trained model rather than a pile of regexes: it recovers canonical
section structure, unfragmented paragraphs and — most valuably — a *parsed*
bibliography with author, title, venue and year as fields.

Its asset endpoint also returns the figures' embedded images, linked to each
figure by a <graphic> element, at native resolution. That beats re-rendering a
region at 150 dpi, so those are preferred. It can only return what the PDF
embeds as a bitmap, though, and a figure drawn as vector art yields nothing —
which is exactly what extract_pdf.py's crops are for, so they remain the
fallback.

Output is the same document shape as the other two sources, so the builder,
the edit overlays and the audit work on it unchanged.

    .cache/tei/<slug>.tei.xml     GROBID's TEI, cached
    .cache/figmap/<slug>.json     label -> figure image, harvested from ours
    .cache/doc/<slug>.json        nodes, marked source: grobid

Needs the service running:  cd grobid && ./gradlew run

    python3 scripts/ingest_tei.py [--only SUBSTRING] [--limit N] [--force]
"""

import argparse
import glob
import io
import hashlib
import json
import os
import re
import sys
import zipfile

import requests
from PIL import Image
from lxml import etree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
PDF_DIR = os.path.join(CACHE, 'pdf')
DOC_DIR = os.path.join(CACHE, 'doc')
TEI_DIR = os.path.join(CACHE, 'tei')
ASSET_DIR = os.path.join(CACHE, 'tei_assets')
FIGMAP_DIR = os.path.join(CACHE, 'figmap')
OURS_DIR = os.path.join(CACHE, 'doc_ours')
NO_RESTORE = False
NS = {'t': 'http://www.tei-c.org/ns/1.0'}

BACK_HEAD = re.compile(r'^(references?(?: and notes)?|bibliography|'
                       r'mdar reproducibility|submitted \d|'
                       r'acknowledge?ments?|author contributions?|'
                       r'competing interests?|declarations?|funding|'
                       r'data (and code )?availability|code availability|'
                       r'supplementary|supporting information|'
                       r'conflicts? of interest|ethics|resource availability|'
                       r'key resources)', re.I)
# Supplementary figures and tables are not part of the paper as it reads: the
# publisher link is there for anyone who wants them.
SUPP_LABEL = re.compile(r'^(supplementary|supplemental|extended\s+data|appendix'
                        r'|(?:fig(?:ure)?|table|scheme)\.?\s*s\s*\d)', re.I)

# GROBID occasionally promotes a caption fragment or a page banner to a heading
# only the named divisions of a paper are top-level; everything else is a
# subsection, however short its title
TOP_LEVEL = re.compile(r'^(abstract|summary|introduction|background|results'
                       r'(?: and discussion)?|discussion|conclusions?|'
                       r'materials and methods|methods(?: and materials)?|'
                       r'materials|experimental procedures|star\s*\+?\s*methods|'
                       r'main|significance|outlook)\s*[:.]?$', re.I)

JUNK_HEAD = re.compile(r'^(research \| research article|'
                       r'\(legend continued on next page\)|'
                       r'downloaded from|see also)', re.I)


# Publisher watermarks are printed sideways down the page, so extraction drops
# them into whatever paragraph happens to be alongside — mid-sentence.
STAMP = re.compile(
    # "on July 26" may arrive as "onJuly 26": the watermark is set sideways and
    # extraction loses spaces at the glyph boundaries
    r'Downloaded from \S+ at [^,]{0,120}?\s*on\s*[A-Z][a-z]+\s*\d{1,2},?\s*\d{4}'
    r'|which was not certified by peer review[^.]{0,80}\.'
    r'|The copyright holder for this preprint[^.]{0,120}\.'
    r'|(?:bioRxiv|medRxiv) preprint doi: ?\S+'
    r'|available under a ?CC-BY[^\s]*(?: \d\.\d)?(?: International license)?'
    r'|this version posted \w+ \d{1,2},? \d{4}[^.]{0,40}\.'
    # Nature's running head, which lands mid-sentence and even alone as a
    # heading: "Article https://doi.org/10.1038/s41589-022-01223-z"
    r'|Articles?\s+https?://doi\.org/\S+'
    r'|https?://doi\.org/10\.1038/\S+', re.I)


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

# U+02BC (modifier letter apostrophe) is what Nature's closing quote becomes, and
# extraction drops the space after it: "matrixʼfor", "singletonʼpairs".
MODIFIER_QUOTE = re.compile('\u02bc(?=[A-Za-z0-9])')


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
    text = fix_glyphs(MODIFIER_QUOTE.sub("' ", text).translate(INVISIBLE))
    def join(m):
        head, tail = m.group(1), m.group(2)
        # a compound keeps its hyphen but loses the line break
        if COMPOUND_HEAD.search(head):
            return '%s-%s' % (head, tail)
        return head + tail
    return re.sub(r'([A-Za-z]{2,})-\s+([a-z]{2,})', join, text)


def norm(text):
    # An unmappable glyph reads as a broken page; the audit flags the nodes it
    # touched so the notation can be restored from context later.
    text = (text or '').replace('\ufffd', '')
    # Collapse whitespace *first*: the watermark spans lines in the source, and
    # a newline inside it defeats every pattern below.
    text = re.sub(r'\s+', ' ', text or '').strip()
    return dehyphenate(re.sub(r'\s+', ' ', STAMP.sub(' ', text)).strip())


def node_id(index, text):
    seed = norm(text)[:200] or str(index)
    return 'g%d-%s' % (index, hashlib.sha1(seed.encode()).hexdigest()[:6])


def tei_with_assets(pdf, url, force=False):
    """TEI plus the figures' embedded images, unpacked into a cache directory.

    The asset endpoint answers with a zip: the TEI, and one PNG per embedded
    image, referenced from each <figure> by a <graphic url="…">. That link is
    exact, which is worth more than any label matching.
    """
    slug = os.path.basename(pdf)[:-4]
    out_dir = os.path.join(ASSET_DIR, slug)
    tei_path = os.path.join(out_dir, 'tei.xml')
    if os.path.exists(tei_path) and not force:
        return open(tei_path, encoding='utf-8').read(), out_dir

    with open(pdf, 'rb') as fh:
        r = requests.post(url.rstrip('/') + '/api/processFulltextAssetDocument',
                          files={'input': fh},
                          data={'consolidateHeader': '0',
                                'consolidateCitations': '0',
                                'includeRawCitations': '1'},
                          timeout=1200)
    r.raise_for_status()
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in zf.namelist():
            if name.endswith('/') or '..' in name:
                continue
            target = os.path.join(out_dir, os.path.basename(name))
            with zf.open(name) as src, open(target, 'wb') as dst:
                dst.write(src.read())
    # the TEI arrives named after the PDF; normalise it
    if not os.path.exists(tei_path):
        for name in os.listdir(out_dir):
            if name.endswith('.xml'):
                os.rename(os.path.join(out_dir, name), tei_path)
                break
    # keep a copy where the comparison script looks for it
    os.makedirs(TEI_DIR, exist_ok=True)
    open(os.path.join(TEI_DIR, slug + '.tei.xml'), 'w',
         encoding='utf-8').write(open(tei_path, encoding='utf-8').read())
    return open(tei_path, encoding='utf-8').read(), out_dir


def mean_luma(path):
    from PIL import ImageStat
    try:
        return ImageStat.Stat(Image.open(path).convert('L')).mean[0]
    except Exception:                                   # noqa: BLE001
        return 255.0


def resolve_asset(path):
    """Given the image GROBID linked, return the one a reader should see.

    pdfalto dumps every embedded object of a figure separately, so a masked
    graphic arrives as a *pair*: the artwork and its transparency stencil, at
    identical dimensions. GROBID may link either one, and linking the stencil
    renders a white silhouette on black — which is how this was noticed. Given
    a pair, the lighter member is the artwork.
    """
    try:
        target = Image.open(path)
    except Exception:                                   # noqa: BLE001
        return None
    size, here = target.size, mean_luma(path)
    siblings = [p for p in glob.glob(os.path.join(os.path.dirname(path), '*.png'))
                if p != path]
    lighter = [(mean_luma(p), p) for p in siblings
               if Image.open(p).size == size]
    lighter = [(m, p) for m, p in lighter if m > here + 60]
    if lighter:
        return max(lighter)[1]
    # an unpaired stencil: two-tone, and dark overall
    small = target.convert('L').resize((64, 64))
    pixels = list(small.getdata())
    extreme = sum(1 for p in pixels if p < 12 or p > 243)
    if here < 40 and extreme > len(pixels) * 0.7:
        return None
    return path


def is_flat(img):
    """Almost nothing drawn: a background wash or an empty layer.

    pdfalto splits a composited figure into its layers, so GROBID can end up
    linking the gradient behind the artwork rather than the artwork. Edge
    density separates the two cleanly — real figures score 19-24 here, empty
    layers 2-7.
    """
    from PIL import ImageFilter, ImageStat
    grey = img.convert('L')
    edges = ImageStat.Stat(grey.filter(ImageFilter.FIND_EDGES)).mean[0]
    return edges < 8 or ImageStat.Stat(grey).stddev[0] < 15


def flatten(img):
    """Composite transparency onto white; never let alpha become black."""
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P'
                                      and 'transparency' in img.info):
        img = img.convert('RGBA')
        canvas = Image.new('RGB', img.size, (255, 255, 255))
        canvas.paste(img, mask=img.split()[-1])
        return canvas
    return img.convert('RGB') if img.mode not in ('RGB', 'L') else img


def web_image(src, slug, seq, max_width=1300):
    """Web-size one of GROBID's extracted images alongside our own crops."""
    from PIL import Image
    out_dir = os.path.join(REPO, 'assets', 'papers', slug)
    os.makedirs(out_dir, exist_ok=True)
    try:
        img = flatten(Image.open(src))
        if is_flat(img):
            return None                    # an empty layer, not the figure
        if img.width > max_width:
            img = img.resize((max_width, round(img.height * max_width / img.width)),
                             Image.LANCZOS)
        if img.width < 120 or img.height < 90:
            return None                    # an icon or a rule, not a figure
        name = 'gb-%02d.jpg' % seq
        img.save(os.path.join(out_dir, name), 'JPEG', quality=84, optimize=True,
                 progressive=True)
        return os.path.join('assets', 'papers', slug, name)
    except Exception:                                   # noqa: BLE001
        return None


def crop_index(slug):
    """{1: 'assets/papers/<slug>/fig-01.jpg', …} straight from disk.

    More durable than a label map: the crops keep their numbering whatever
    happens to the document that produced them, and a figure's number is the
    one part of GROBID's label that is reliably parseable.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(REPO, 'assets', 'papers', slug,
                                              'fig-*.*'))):
        m = re.search(r'fig-(\d+)\.', os.path.basename(path))
        if m:
            out[int(m.group(1))] = os.path.relpath(path, REPO)
    return out


def label_number(label):
    """The figure number in a GROBID label: "Fig. 1 ." -> 1. None if unclear."""
    if not label or not re.match(r'\s*(figure|fig|table|scheme)\b', label, re.I):
        return None
    m = re.search(r'(\d{1,2})', label)
    return int(m.group(1)) if m else None


def figure_map(slug):
    """{'Figure 1': 'assets/papers/…/fig-01.jpg'} from our own extraction.

    Harvested before GROBID's document replaces ours, and cached, so the crops
    survive any number of re-ingests.
    """
    os.makedirs(FIGMAP_DIR, exist_ok=True)
    path = os.path.join(FIGMAP_DIR, slug + '.json')
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    mapping = {}
    doc_path = os.path.join(DOC_DIR, slug + '.json')
    if os.path.exists(doc_path):
        doc = json.load(open(doc_path, encoding='utf-8'))
        if doc.get('source') != 'biorxiv':
            for node in doc['nodes']:
                if node['type'] == 'figure' and node.get('label'):
                    key = re.sub(r'\s+', ' ', node['label']).strip(' .:')
                    mapping.setdefault(key.lower(), node['image'])
    if mapping:
        json.dump(mapping, open(path, 'w', encoding='utf-8'), indent=1)
    return mapping


def our_furniture(slug):
    """Text our own geometric extraction judged to be *inside* a figure.

    GROBID reads the page as a stream and has no notion of a figure's area, so
    panel labels, axis titles and legend fragments arrive as paragraphs — one
    became an <h2> reading "Masked Sequence". Our extractor does know, having
    clustered the artwork, so its verdict is used here as a filter. This is the
    one thing the geometric pass does that a text model cannot.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return set()
    keys = set()
    for node in json.load(open(path, encoding='utf-8'))['nodes']:
        if node['type'] in ('figure-text', 'small', 'rotated', 'furniture',
                            'math'):
            key = re.sub(r'[^a-z0-9]', '', node['text'].lower())
            if len(key) >= 12:
                keys.add(key)
    return keys


def is_figure_furniture(text, keys):
    """Does our extraction place this text inside a figure?"""
    key = re.sub(r'[^a-z0-9]', '', text.lower())
    if len(key) < 12:
        return False
    if key in keys:
        return True
    # GROBID merges several label fragments into one paragraph, and our
    # extractor split them differently, so exact matching is not enough:
    # measure how much of this paragraph our figure text accounts for.
    if len(key) < 1400:
        covered = sum(len(k) for k in keys if len(k) >= 6 and k in key)
        # a short fragment is label soup at a lower bar than a long paragraph,
        # which may be figure text merged with real prose
        bar = 0.35 if len(key) < 300 else 0.5
        if covered > len(key) * bar:
            return True
    return False


EQUATION_OP = re.compile(r'[=≥≤<>≠±×÷∑∏∫√]|\b(log|exp|softmax|arg\s*max|arg\s*min|'
                         r'max|min|sum|mean)\b', re.I)


def looks_like_equation(text):
    """A formula, not a row of sequence labels.

    GROBID tags both as <formula>: "PLL(x) = ∑ L i=1 logP…" alongside
    "R I G R … MV -- … T V V …", which is a figure's alignment strip. An
    equation states a relation, so it contains one.
    """
    return bool(EQUATION_OP.search(text))


def label_soup(text):
    """A row of panel letters or axis ticks: tokens, not words.

    "A T S E M L N K D H R F Y P W G C Amino Acid" is an axis; counting words
    calls it nineteen and lets it through, so count what the tokens *are*.
    """
    tokens = text.split()
    if not tokens:
        return True
    singles = sum(1 for t in tokens if len(t.strip('.,;:()[]')) <= 1)
    words = len(re.findall(r'[a-z]{4,}', text))
    return singles >= len(tokens) * 0.4 or words < 3


# A cell is a number, a yes/no, or a *single* character. Two-character tokens
# were counted too, which makes "of", "in", "as" cells and any English sentence
# a table row — it silently ate the opening sentence of this paper.
TABLE_TOKEN = re.compile(r'^(yes|no|n/?a|[-+]?\d+[\d.,%]*|\S)$', re.I)


def table_row(sentence):
    """A row of a figure's table rather than a sentence.

    "refactoring No refactoring 0.77 Yes No Yes No Individual Combined Rel.
    fitness…" is Figure 5's table, and it arrives welded to the front of a real
    Discussion paragraph. Yes/No/number/one-letter tokens are the giveaway.
    """
    tokens = sentence.split()
    if len(tokens) < 5:
        return False
    cells = sum(1 for t in tokens if TABLE_TOKEN.match(t.strip('.,;:()')))
    # and a sentence has a verb-bearing shape: several ordinary words in a row
    prose_words = len(re.findall(r'\b[a-z]{4,}\b', sentence))
    return cells >= len(tokens) * 0.3 and prose_words < len(tokens) * 0.35


def trim_leading_junk(text):
    """Drop table rows and label runs from the head of a paragraph."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    while len(parts) > 1 and (table_row(parts[0]) or label_soup(parts[0])):
        parts = parts[1:]
    kept = ' '.join(parts).strip()
    return kept if len(kept) >= 120 else text


def strip_figure_prefix(text, keys):
    """Remove a figure label that GROBID glued to the front of a paragraph.

    "Protein Language Models time, from the beginning of the sequence…" opens
    with a panel title and continues into the body text. Dropping the whole
    paragraph would lose real prose, so only the known label is cut.
    """
    stripped = text
    for _ in range(4):                     # labels can stack
        key = re.sub(r'[^a-z0-9]', '', stripped.lower())
        best = ''
        for k in keys:
            if len(k) < 8:
                continue
            # the label our extractor found may be longer than the fragment
            # GROBID glued on, so compare their shared opening run
            shared = 0
            for a, b in zip(key, k):
                if a != b:
                    break
                shared += 1
            if shared >= 12 and shared > len(best):
                best = key[:shared]
        if not best:
            break
        # walk forward through the original text until that many alphanumerics
        # have been consumed
        seen, cut = 0, 0
        for i, ch in enumerate(stripped):
            if ch.isalnum():
                seen += 1
            if seen >= len(best):
                cut = i + 1
                break
        stripped = stripped[cut:].lstrip(' ,.;:)-')
    return stripped if len(stripped) >= 40 else text


def ref_text(bibl):
    """One bibliography entry, assembled from GROBID's parsed fields."""
    names = []
    for author in bibl.findall('.//t:author', NS):
        surname = author.find('.//t:surname', NS)
        first = author.find('.//t:forename', NS)
        if surname is not None and surname.text:
            initial = (first.text or '')[:1] if first is not None else ''
            names.append('%s %s' % (surname.text, initial) if initial
                         else surname.text)
    title = bibl.find('.//t:title[@level="a"]', NS)
    journal = bibl.find('.//t:title[@level="j"]', NS)
    date = bibl.find('.//t:date', NS)
    year = (date.get('when') or '')[:4] if date is not None else ''
    doi = bibl.find('.//t:idno[@type="DOI"]', NS)
    bits = []
    if names:
        bits.append(', '.join(names[:8]) + (' et al.' if len(names) > 8 else ''))
    if title is not None and title.text:
        bits.append(norm(' '.join(title.itertext())))
    tail = ' '.join(x for x in (
        norm(' '.join(journal.itertext())) if journal is not None else '',
        year) if x)
    if tail:
        bits.append(tail)
    text = '. '.join(b.rstrip('.') for b in bits if b)
    if doi is not None and doi.text:
        text += '. doi:%s' % doi.text.strip()
    return text.strip()


CITES_FIG = re.compile(r'\b(?:fig(?:ure)?s?\.?|table)\s*(\d{1,2})', re.I)


def add_missing_figures(nodes, slug, crops):
    """Add figures GROBID did not find at all, from our own extraction.

    GROBID missed Figure 3 of this paper outright — no <figure> element, no
    caption. Our geometric pass had it, so the two sources are unioned rather
    than one being trusted wholesale.
    """
    def key_of(label):
        kind = 'ed' if re.search(r'extended|supplementary', label or '', re.I) \
            else 'fig'
        m = re.search(r'(\d{1,2})', label or '')
        return (kind, int(m.group(1))) if m else None

    have = set()
    for node in nodes:
        if node['type'] in ('figure', 'caption'):
            key = key_of(node.get('label'))
            if key:
                have.add(key)
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes
    for node in json.load(open(path, encoding='utf-8'))['nodes']:
        if node['type'] != 'figure':
            continue
        key = key_of(node.get('label'))
        if not key or key in have:
            continue
        kind, number = key
        image = node.get('image') or crops.get(number)
        if not image or not os.path.exists(os.path.join(REPO, image)):
            continue
        have.add(key)
        nodes.append({'id': node_id(900 + number, node['text']), 'type': 'figure',
                      'anchor': ('figure-ed%d' if kind == 'ed' else 'figure-%d')
                                % number,
                      'text': node['text'], 'label': node.get('label', ''),
                      'image': image, 'lines': [node['text']],
                      'from_ours': True})
    return nodes


# a paragraph that ends mid-sentence, and one that starts mid-sentence
OPEN_END = re.compile(r'[^.!?"”\'’)]$|[a-z0-9,;:\-–(\[]$|\b[A-Z]\.$')
OPEN_START = re.compile(r'^[a-z0-9(\[]')
FOOTNOTE_OPEN = re.compile(r'^\d{1,2}\s+[A-Z][a-z]')


def lift_run_in_headings(nodes, slug):
    """Split out subsection titles GROBID inlined into the following paragraph.

    Cell and Nature set a subsection title as bold text at the head of its first
    paragraph. GROBID reports the paragraph whole, so the title is buried; our
    layout pass detects the font change and has each one as its own heading.
    Matching a paragraph's opening against those headings recovers the structure
    without judgement — on the lipid paper this was nine headings and roughly
    half the hand-written corrections.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes
    ours = json.load(open(path, encoding='utf-8'))['nodes']
    heads = {}
    for node in ours:
        if node['type'] == 'heading' and node.get('run_in'):
            key = re.sub(r'[^a-z0-9]', '', node['text'].lower())
            if 8 <= len(key) <= 120:
                heads[key] = re.sub(r'\s+', ' ', node['text']).strip()
    if not heads:
        return nodes

    out = []
    for node in nodes:
        if node['type'] != 'prose' or node.get('role'):
            out.append(node)
            continue
        flat = re.sub(r'[^a-z0-9]', '', node['text'].lower())
        hit = next((heads[k] for k in heads if flat.startswith(k)), None)
        if not hit:
            out.append(node)
            continue
        # walk to the same point in the original text, then past the punctuation
        want = len(re.sub(r'[^a-z0-9]', '', hit.lower()))
        seen = cut = 0
        for i, ch in enumerate(node['text']):
            if seen == want:
                cut = i
                break
            if ch.isalnum():
                seen += 1
        while cut < len(node['text']) and not node['text'][cut].isalnum():
            cut += 1
        rest = node['text'][cut:].strip()
        if len(rest) < 40:
            out.append(node)
            continue
        out.append({'id': node_id(0, hit), 'type': 'heading', 'text': hit,
                    'lines': [hit], 'run_in': True, 'level': 3})
        shift = len(node['text']) - len(rest)
        links = [dict(l, a=l['a'] - shift, b=l['b'] - shift)
                 for l in (node.get('links') or []) if l['a'] >= shift]
        out.append(dict(node, text=rest, lines=[rest],
                        **({'links': links} if links else {})))
    return out


SECTION_HEAD = re.compile(
    r'^(star\s*\+?\s*methods|key resources table|'
    r'(?:experimental|animal) model[a-z\s]*details|method details|'
    r'quantification and statistical analysis|'
    r'data and (?:software|code) availability|resource availability|'
    r'materials and methods|methods)\s*$', re.I)


def split_section_headings(nodes):
    """Separate a named section from a subsection title glued onto it.

    "QUANTIFICATION AND STATISTICAL ANALYSIS Ethidium bromide uptake assay" is
    two headings set on one line.
    """
    out = []
    for node in nodes:
        if node['type'] == 'heading':
            parts = re.split(r'(?<=[A-Z])\s+(?=[A-Z][a-z])|(?<=[a-z])\s+(?=[A-Z])',
                             node['text'], maxsplit=1)
            if len(parts) == 2 and SECTION_HEAD.match(parts[0]) \
                    and len(parts[1].split()) >= 2:
                out.append(dict(node, text=parts[0], lines=[parts[0]], level=2,
                                id=node_id(0, parts[0])))
                out.append(dict(node, text=parts[1], lines=[parts[1]], level=3,
                                id=node_id(0, parts[1])))
                continue
        out.append(node)
    return out


def reading_order(nodes, slug):
    """Restore printed order where GROBID scrambled the columns.

    On one paper GROBID emitted page 2's right column before its left, so the
    Introduction was interleaved with Results and a paragraph from the middle of
    the page appeared with no antecedent. Our layout pass reads columns in the
    right order and — because both sides hash the same normalised text — its
    nodes can be matched to GROBID's by that hash. Nodes with no match keep
    their position relative to the last matched one, so nothing is lost if the
    alignment is partial.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes, 0
    place = {}
    for i, node in enumerate(json.load(open(path, encoding='utf-8'))['nodes']):
        h = node['id'].split('-', 1)[-1]
        place.setdefault(h, (node.get('page', 0), i))

    keyed, last, matched = [], (0, 0), 0
    for i, node in enumerate(nodes):
        h = node['id'].split('-', 1)[-1]
        where = place.get(h)
        if where and node['type'] in ('prose', 'heading'):
            last = where
            matched += 1
            keyed.append((where, 0, i, node))
        else:
            # unmatched: sits just after whatever preceded it
            keyed.append((last, 1, i, node))
    if matched < 8:
        return nodes, 0                    # too little overlap to trust
    ordered = [n for *_, n in sorted(keyed, key=lambda t: (t[0], t[1], t[2]))]
    moved = sum(1 for a, b in zip(nodes, ordered) if a is not b)
    return ordered, moved


def insert_missing_sections(nodes, slug):
    """Add section headers GROBID omitted altogether.

    Cell reverses its STAR headers out of a coloured band and GROBID reports
    none of them, so the methods arrive as an unlabelled run of subsections. Our
    layout pass has them; each is placed by matching the paragraph that follows
    it there to the same paragraph here.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes
    ours = json.load(open(path, encoding='utf-8'))['nodes']
    have = {re.sub(r'[^a-z0-9]', '', n['text'].lower())
            for n in nodes if n['type'] == 'heading'}

    wanted = []
    for i, node in enumerate(ours):
        if node['type'] != 'heading' or not SECTION_HEAD.match(node['text']):
            continue
        if re.sub(r'[^a-z0-9]', '', node['text'].lower()) in have:
            continue
        follower = next((n for n in ours[i + 1:]
                         if n['type'] in ('prose', 'heading')
                         and len(n['text']) > 60), None)
        if follower:
            wanted.append((re.sub(r'[^a-z0-9]', '',
                                  follower['text'].lower())[:40],
                           re.sub(r'\s+', ' ', node['text']).strip()))

    if not wanted:
        return nodes
    out = []
    for node in nodes:
        flat = re.sub(r'[^a-z0-9]', '', node['text'].lower())
        for key, head in list(wanted):
            if key and flat.startswith(key[:30]):
                out.append({'id': node_id(0, head), 'type': 'heading',
                            'text': head, 'lines': [head], 'level': 2,
                            'from_ours': True})
                wanted.remove((key, head))
                break
        out.append(node)
    return out


def strip_repeated_heading(nodes):
    """Drop a heading's text when the paragraph under it repeats it.

    GROBID emits both the run-in heading and the paragraph that still carries
    it, so the title reads twice.
    """
    for i, node in enumerate(nodes[:-1]):
        if node['type'] != 'heading':
            continue
        nxt = nodes[i + 1]
        if nxt['type'] != 'prose' or nxt.get('role'):
            continue
        head = re.sub(r'\s+', ' ', node['text']).strip()
        if len(head) > 8 and nxt['text'].startswith(head):
            rest = nxt['text'][len(head):].lstrip(' .:;—-')
            if len(rest) >= 40:
                nxt['text'] = rest
    return nodes


def repair_compounds(nodes, slug):
    """Restore hyphens in compounds the other extractor kept.

    GROBID lost one "high-confidence" to a soft hyphen and rendered it
    "highconfidence". Our extraction of the same page has the hyphen, so the
    mashed form is corrected from it — only for long words, and only where our
    text actually contains the hyphenated version.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes
    hyphenated = {}
    for node in json.load(open(path, encoding='utf-8'))['nodes']:
        for word in re.findall(r'[A-Za-z]{3,}-[A-Za-z]{3,}', node['text']):
            hyphenated.setdefault(word.replace('-', '').lower(), word)
    if not hyphenated:
        return nodes
    for node in nodes:
        if node['type'] not in ('prose', 'caption', 'heading'):
            continue

        def restore(m):
            fixed = hyphenated.get(m.group(0).lower())
            return fixed if fixed else m.group(0)

        node['text'] = re.sub(r'[A-Za-z]{12,}', restore, node['text'])
    return nodes


def word_runs(text, n=6):
    words = re.findall(r'[a-z0-9]+', (text or '').lower())
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def body_prose(text):
    """Does this read as a paragraph of the paper, rather than furniture?

    Used to decide what may be *inserted*: text GROBID never emitted is only
    worth restoring if it is prose. Two numbered citations in a row is a
    bibliography it parsed into fields, and a line of Yes/No/number tokens is a
    table it read as a table.
    """
    if len(NUMBERED_ENTRY_TEXT.findall(text)) >= 2:
        return False
    if label_soup(text) or table_row(text):
        return False
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', text) if len(s) > 40]
    if not sentences:
        return False
    # A paragraph is mostly words. Methods are dense with numbers, so this only
    # rejects the extreme case: a grid of measurements read as one line.
    digits = len(re.findall(r'\d', text))
    return digits <= len(text) * 0.2


def restore_dropped_text(nodes, slug):
    """Take back sentences GROBID lost from the middle of a paragraph.

    GROBID drops prose silently, most often at a page turn: the paragraph is
    present, reads cleanly, and is missing a clause or two from where the column
    ended. `repair_openings` catches the case where the *start* is missing,
    because a paragraph beginning "coli ribosome is…" is self-evidently broken.
    A hole in the middle looks like nothing at all — on one paper it cost a
    printed page of Methods, and on another two paragraphs survived an agent's
    read of the page.

    Our layout pass has the full paragraph. Where its version of the same
    paragraph contains substantially all of GROBID's words and more of them,
    prefer ours. Citation links survive because they carry their span text and
    are re-anchored after this runs.

    The hazard is duplication, and it is not hypothetical: taking our version
    wholesale first time round printed 500 repeated word-runs on one paper,
    because our pass sometimes reads as one paragraph what GROBID split into two
    — so replacing the first copied text the second still held. Nothing is
    written unless the words it *adds* are absent from every other node.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes, 0, 0, 0
    mine = [n for n in json.load(open(path, encoding='utf-8'))['nodes']
            if n['type'] == 'prose' and not n.get('role')
            and len(n['text']) >= 120]
    runs = [(word_runs(n['text']), n) for n in mine]

    # How many nodes each word run appears in, so "is this text already on the
    # page somewhere other than here?" is a lookup rather than a scan.
    here = {id(n): word_runs(n['text']) for n in nodes}
    seen = {}
    for node_runs in here.values():
        for run in node_runs:
            seen[run] = seen.get(run, 0) + 1

    def elsewhere(new_runs, exclude=()):
        """The share of new_runs already printed by some other node."""
        if not new_runs:
            return 1.0
        own = set()
        for node in exclude:
            own |= here.get(id(node), set())
        hits = sum(1 for r in new_runs
                   if seen.get(r, 0) - (1 if r in own else 0) > 0)
        return hits / len(new_runs)

    def account(node, text):
        """Update the running tally after a node's text changes."""
        for run in here.get(id(node), set()):
            seen[run] = seen.get(run, 1) - 1
        here[id(node)] = word_runs(text)
        for run in here[id(node)]:
            seen[run] = seen.get(run, 0) + 1

    taken, matched, restored, rejoined = set(), {}, 0, 0
    for node in nodes:
        if node['type'] != 'prose' or node.get('role') or node.get('entry'):
            continue
        theirs = word_runs(node['text'])
        if len(theirs) < 8:
            continue
        best, score = None, 0.0
        for i, (ours, candidate) in enumerate(runs):
            if i in taken or not ours:
                continue
            hit = len(theirs & ours) / len(theirs)
            if hit > score:
                best, score = i, hit
        if best is None or score < 0.85:
            continue                 # not confidently the same paragraph
        candidate = runs[best][1]
        # A confident match is worth recording even when the text needs no
        # change: it anchors the paragraphs that follow it.
        taken.add(best)
        matched[best] = node
        gain = len(candidate['text']) - len(node['text'])
        # Whatever our paragraph holds that GROBID's node does not, the nodes
        # right after it may already print — GROBID breaks a paragraph at a
        # column and files the tail on its own ("drophobic molecules) across the
        # intervening, aqueous periplasm."). Ours is the whole paragraph, so
        # those become duplicates and have to go. A short tail is easy to miss:
        # four word-runs out of two hundred cleared every proportional check
        # while still printing a stray line on the page.
        at = nodes.index(node)
        absorbed = [n for n in nodes[at + 1:at + 3]
                    if n['type'] == 'prose' and not n.get('role')
                    and not n.get('entry') and here[id(n)]
                    and len(here[id(n)] - runs[best][0])
                    <= len(here[id(n)]) * 0.3]
        # A real dropout adds a clause or more. Small differences are the two
        # passes disagreeing about a hyphen or a reference marker, and taking
        # ours there would churn ids for no gain — but a split still has to be
        # rejoined even when the text itself needs no change.
        if gain < 60 and not absorbed:
            continue
        # Only the words this would add matter. If some *other* node prints
        # them, our paragraph spans a split we have not accounted for, and
        # taking it would duplicate the other half.
        added = runs[best][0] - theirs
        if elsewhere(added, exclude=(node, *absorbed)) > 0.1:
            continue
        for n in absorbed:
            n['type'] = 'dropped'
            n['edited'] = 'joined into the paragraph it was split from'
            account(n, '')
        rejoined += len(absorbed)
        node['text'] = candidate['text']
        node['lines'] = candidate.get('lines') or [candidate['text']]
        node['restored'] = gain
        account(node, node['text'])
        matched[best] = node
        restored += 1

    # Second class: a paragraph GROBID never emitted at all. Whole Methods
    # sections go this way, and nothing downstream notices because the
    # surrounding sections are intact. Our pass has the paragraph and knows what
    # preceded it, so it can be placed after whichever of GROBID's nodes that
    # neighbour matched — the same anchoring `insert_missing_sections` uses.
    inserted = 0
    for i, (ours, candidate) in enumerate(runs):
        if i in taken or len(ours) < 24:
            continue                     # short paragraphs are too easy to mistake
        if elsewhere(ours) > 0.1:
            continue                     # already on the page somewhere
        # Absent from GROBID's document is not the same as missing from the
        # paper. It parses the bibliography into fields and reads tables as
        # tables, so a run of numbered citations or a column of numbers is
        # absent by design; putting it back as a paragraph made pages worse.
        if not body_prose(candidate['text']):
            continue
        anchor = next((matched[j] for j in range(i - 1, -1, -1)
                       if j in matched), None)
        if anchor is None or anchor not in nodes:
            continue
        new = dict(candidate)
        new['inserted'] = 'restored from our own pass'
        nodes.insert(nodes.index(anchor) + 1, new)
        account(new, new['text'])
        matched[i] = new
        inserted += 1
    return nodes, restored, inserted, rejoined


def repair_openings(nodes, slug):
    """Restore a sentence start that GROBID lost at a column break.

    "The E." and "We constructed MSAs for all E." vanished, leaving paragraphs
    that open "coli ribosome is the largest…". Our own extraction of the same
    page still has those words, so they are taken from there rather than
    guessed. A lead-in carrying a mathematical relation is left alone: that is
    an equation, already rendered as its own block, and prepending it would
    duplicate it.
    """
    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes
    mine = [n['text'] for n in json.load(open(path, encoding='utf-8'))['nodes']
            if n['type'] == 'prose']
    flat = [(re.sub(r'[^a-z0-9]', '', t.lower()), t) for t in mine]
    for node in nodes:
        if node['type'] != 'prose' or node.get('role'):
            continue
        words = node['text'].split()
        if not words or not (words[0].islower() and words[0].isalpha()):
            continue
        key = re.sub(r'[^a-z0-9]', '', node['text'][:60].lower())[:40]
        if len(key) < 20:
            continue
        for flatkey, text in flat:
            at = flatkey.find(key)
            if at <= 0:
                continue
            # walk to the same point in the original, un-normalised text
            count, cut = 0, None
            for i, ch in enumerate(text):
                if count == at:
                    cut = i
                    break
                if ch.isalnum():
                    count += 1
            # cut lands just after the last counted character, before any
            # punctuation and spacing that follow it — "The E" not "The E. "
            while cut is not None and cut < len(text) and not text[cut].isalnum():
                cut += 1
            lead = text[:cut].strip() if cut else ''
            if not lead or len(lead) > 100 or EQUATION_OP.search(lead):
                break
            node['text'] = lead + ' ' + node['text']
            node['repaired'] = lead
            for link in node.get('links') or []:   # offsets shift with the text
                link['a'] += len(lead) + 1
                link['b'] += len(lead) + 1
            break
    return nodes


def number_references(nodes):
    """Label each reference with the number the paper cites it by.

    GROBID's ids run b0, b1, b2… in the order it parsed the list, which is not
    the paper's numbering: here b1 is cited as "(3)". A single offset does not
    work either, because GROBID merges or misses entries at several points, so
    the offset changes down the list. The citations are ground truth wherever
    they exist, so the known points are interpolated between — which keeps the
    numbering monotonic and leaves an honest gap where an entry is missing,
    rather than shifting everything after it.
    """
    refs = [n for n in nodes if n.get('role') == 'references'
            and (n.get('anchor') or '').startswith('ref-b')]
    if not refs:
        return nodes

    cited = {}
    for node in nodes:
        for link in node.get('links') or []:
            target = link['href'].lstrip('#')
            if not target.startswith('ref-b'):
                continue
            m = re.search(r'(\d{1,3})', node['text'][link['a']:link['b']])
            if m:
                cited.setdefault(target, int(m.group(1)))

    known = [(i, cited[r['anchor']]) for i, r in enumerate(refs)
             if r['anchor'] in cited]
    # numbers must rise with position; a label that breaks that is a bad span
    monotonic, last = [], 0
    for i, number in known:
        if number > last:
            monotonic.append((i, number))
            last = number
    known = monotonic
    for i, node in enumerate(refs):
        if node['anchor'] in cited:
            node['number'] = cited[node['anchor']]
            continue
        before = [(j, n) for j, n in known if j < i]
        after = [(j, n) for j, n in known if j > i]
        if before:
            j, n = before[-1]
            node['number'] = n + (i - j)
        elif after:
            j, n = after[0]
            node['number'] = max(1, n - (j - i))
        else:
            node['number'] = i + 1
    return nodes


NUMBERED_ENTRY_TEXT = re.compile(
    r'(?:(?<=\s)|^)(\d{1,3})\.\s+([A-Z][^;]{30,400}?\((?:19|20)\d{2}\))')


def relocate_links(nodes):
    """Re-anchor every link by finding its span in the final text.

    Half a dozen passes rewrite a node's text after the links were recorded —
    trimming a figure label, stripping a repeated heading, closing a hyphen —
    and each one moved offsets that nothing updated. A link that cannot be
    found again is dropped rather than left pointing at the wrong words.
    """
    for node in nodes:
        links = node.get('links')
        if not links:
            continue
        text, kept, at = node['text'], [], 0
        for link in sorted(links, key=lambda l: l['a']):
            span = link.get('span')
            if not span:
                continue
            where = text.find(span, at)
            if where < 0:
                where = text.find(span)     # text may have been re-ordered
            if where < 0:
                continue
            kept.append({'a': where, 'b': where + len(span),
                         'href': link['href'], 'span': span})
            at = where + len(span)
        if kept:
            node['links'] = kept
        else:
            node.pop('links', None)
    return nodes


def fill_missing_references(nodes, slug):
    """Add bibliography entries GROBID never parsed.

    Its list can skip an entry outright — reference 1 of this paper, and two in
    the middle — which leaves a gap in the numbering and a citation pointing at
    nothing. Our own extraction still has the numbered list as text, so the
    gaps are filled from there and the entries re-sorted by number.
    """
    refs = [n for n in nodes if n.get('role') == 'references' and n.get('number')]
    if not refs:
        return nodes
    present = {n['number'] for n in refs}
    gaps = [n for n in range(1, max(present) + 1) if n not in present]
    if not gaps:
        return nodes

    path = os.path.join(OURS_DIR, slug + '.json')
    if not os.path.exists(path):
        return nodes
    whole = ' '.join(n['text'] for n in
                     json.load(open(path, encoding='utf-8'))['nodes'])
    found = {}
    for number, text in NUMBERED_ENTRY_TEXT.findall(whole):
        found.setdefault(int(number), norm(text))

    added = []
    for number in gaps:
        text = found.get(number)
        if not text or len(text) < 40:
            continue
        added.append({'id': node_id(800 + number, text), 'type': 'prose',
                      'text': text, 'role': 'references', 'entry': True,
                      'lines': [text], 'number': number,
                      'anchor': 'ref-fill%d' % number, 'from_ours': True})
    if not added:
        return nodes

    # rebuild the bibliography in number order, in place of the first entry
    everything = sorted(refs + added, key=lambda n: n['number'])
    out, done = [], False
    for node in nodes:
        if node.get('role') == 'references' and node.get('number'):
            if not done:
                out.extend(everything)
                done = True
            continue
        out.append(node)
    if not done:
        out.extend(everything)
    return out


def stitch(nodes):
    """Rejoin paragraphs split by a column or page break.

    GROBID reports what the PDF's text stream gives it, so a paragraph flowing
    from the foot of one column to the head of the next arrives as two — the
    second opening mid-sentence ("time, from the beginning of the sequence…").
    The test is the one a reader applies: the first ends unfinished and the
    second starts unfinished. Headings and figures break the chain, so nothing
    is joined across a section boundary.
    """
    out, merged = [], 0
    for node in nodes:
        prev = out[-1] if out else None
        if (node['type'] == 'prose' and prev is not None
                and prev['type'] == 'prose'
                and not node.get('role') and not prev.get('role')
                and OPEN_END.search(prev['text'])
                and OPEN_START.match(node['text'])
                and not FOOTNOTE_OPEN.match(node['text'])):
            joiner = '' if prev['text'].endswith(('-', '–')) else ' '
            if joiner == '':
                prev['text'] = prev['text'][:-1]
            prev['text'] += joiner + node['text']
            prev.setdefault('stitched', []).append(node['id'])
            merged += 1
            continue
        out.append(node)
    return out, merged


def unique_anchors(nodes):
    """One anchor per id. Two figures read as "Figure 1" would otherwise emit
    the same element id, which is invalid HTML and breaks the citation jump."""
    taken = set()
    for node in nodes:
        anchor = node.get('anchor')
        if not anchor:
            continue
        if anchor in taken:
            node['anchor'] = None
        else:
            taken.add(anchor)
    return nodes


def place_figures(nodes):
    """Move each figure to the paragraph that first mentions it.

    TEI collects figures at the end of the body, so rendering them in document
    order puts every figure after the Methods. A reader wants Figure 2 where
    Figure 2 is discussed, which is also what the JATS path does.
    """
    figures, body = [], []
    for node in nodes:
        (figures if node['type'] in ('figure', 'caption') else body).append(node)
    numbered = {}
    for fig in figures:
        m = re.search(r'(\d{1,2})', fig.get('label') or '')
        if m and int(m.group(1)) not in numbered:
            numbered[int(m.group(1))] = fig

    out, placed = [], set()
    for node in body:
        out.append(node)
        if node['type'] != 'prose' or node.get('role'):
            continue
        for number in sorted({int(n) for n in CITES_FIG.findall(node['text'])}):
            fig = numbered.get(number)
            if fig is not None and number not in placed:
                placed.add(number)
                out.append(fig)
    # anything never cited keeps its place at the end, in number order
    out.extend(f for n, f in sorted(numbered.items()) if n not in placed)
    out.extend(f for f in figures if f not in numbered.values())
    return out


XML_ID = '{http://www.w3.org/XML/1998/namespace}id'


def inline_text(el):
    """A paragraph's text plus the spans GROBID marked as links.

    Citations and figure mentions are tagged in the TEI and were being thrown
    away by flattening with itertext(), leaving "(23, 37, 38)" as dead text.
    Offsets are recorded as the text is assembled so the renderer can splice
    links in without re-parsing.
    """
    parts, links = [], []
    pos = 0

    def add(text, href=None):
        nonlocal pos
        # The text has to be assembled in its final form as we go: collapsing
        # whitespace afterwards moved every offset recorded before it, which
        # turned a link on "(36)" into a link on "t (3".
        chunk = STAMP.sub(' ', (text or '').replace('\ufffd', ''))
        chunk = re.sub(r'\s+', ' ', chunk)
        if not chunk:
            return
        if not parts:
            chunk = chunk.lstrip(' ')
        elif parts[-1].endswith(' '):
            chunk = chunk.lstrip(' ')
        if not chunk:
            return
        parts.append(chunk)
        if href:
            # the span text travels with the link: later passes rewrite this
            # node's text, and absolute offsets do not survive that
            links.append({'a': pos, 'b': pos + len(chunk), 'href': href,
                          'span': chunk})
        pos += len(chunk)

    def walk(node):
        add(node.text)
        for child in node:
            tag = etree.QName(child).localname if isinstance(child.tag, str) else ''
            text = ' '.join(child.itertext())
            if tag == 'ref' and child.get('type') == 'bibr' and child.get('target'):
                add(text, '#ref-' + child.get('target').lstrip('#'))
            elif tag == 'ref' and child.get('type') == 'figure':
                # GROBID's figure targets are unreliable here — every one points
                # at the same element — so link by the number it actually cites
                m = re.match(r'\s*S?(\d{1,2})', text)
                supp = re.match(r'\s*S\d', text)
                add(text, '#figure-%s' % m.group(1) if m and not supp else None)
            else:
                walk(child)
            add(child.tail)

    walk(el)
    out = ''.join(parts)
    trailing = len(out) - len(out.rstrip())
    out = out.rstrip()
    # A citation span must still read like a citation. If it does not, the
    # offsets have drifted and the link is dropped rather than pointing at the
    # wrong entry — this is how "t (3" was caught.
    kept = []
    for link in links:
        if not (0 <= link['a'] < link['b'] <= len(out)):
            continue
        span = out[link['a']:link['b']]
        if span != span.strip():
            continue
        if link['href'].startswith('#ref-') and not re.fullmatch(
                r'[\[(]?\s*\d{1,3}\s*(?:[,;–-]\s*\d{1,3}\s*)*[\])]?', span):
            continue
        kept.append(link)
    return out, kept


def convert(xml, slug, figures, crops, asset_dir=None):
    """TEI to our node list."""
    root = etree.fromstring(xml.encode())
    nodes, seq = [], 0
    used_images = set()

    abstract = root.find('.//t:profileDesc/t:abstract', NS)
    if abstract is not None:
        for p in abstract.findall('.//t:p', NS):
            text = norm(' '.join(p.itertext()))
            if len(text) > 40:
                seq += 1
                nodes.append({'id': node_id(seq, text), 'type': 'prose',
                              'text': text, 'role': 'front', 'lines': [text]})

    furniture = our_furniture(slug)
    body = root.find('.//t:text/t:body', NS)
    role = None
    if body is not None:
        for div in body.findall('t:div', NS):
            head = div.find('t:head', NS)
            if head is not None:
                text = norm(' '.join(head.itertext()))
                if text and not JUNK_HEAD.match(text) \
                        and not is_figure_furniture(text, furniture):
                    role = 'back' if BACK_HEAD.match(text) else None
                    seq += 1
                    node = {'id': node_id(seq, text), 'type': 'heading',
                            'text': text, 'lines': [text],
                            'level': 2 if TOP_LEVEL.match(text) else 3}
                    if role:
                        node['role'] = role
                    nodes.append(node)
            for formula in div.findall('t:formula', NS):
                text = norm(' '.join(formula.itertext()))
                if len(text) < 3 or is_figure_furniture(text, furniture) \
                        or not looks_like_equation(text):
                    continue
                seq += 1
                nodes.append({'id': node_id(seq, text), 'type': 'equation',
                              'text': text, 'lines': [text]})
            for p in div.findall('t:p', NS):
                text, links = inline_text(p)
                # A sentence start can arrive as its own tiny paragraph ("The
                # E." before a column break). Dropping short prose here deleted
                # those, so keep them for stitching and prune afterwards.
                # "The E." is six characters and is the start of a sentence, so
                # the floor has to admit anything that ends unfinished
                if (len(text) < 12 and not OPEN_END.search(text)) \
                        or is_figure_furniture(text, furniture):
                    continue
                text = trim_leading_junk(strip_figure_prefix(text, furniture))
                seq += 1
                node = {'id': node_id(seq, text), 'type': 'prose',
                        'text': text, 'lines': [text]}
                if links:
                    node['links'] = links
                if role:
                    node['role'] = role
                nodes.append(node)

    # figures: GROBID finds them and captions them, our crops supply the image
    for fig in root.findall('.//t:figure', NS):
        if fig.get('type') == 'table':
            continue
        label = norm(' '.join(
            (fig.find('t:head', NS) if fig.find('t:head', NS) is not None
             else etree.Element('x')).itertext()))
        desc = fig.find('t:figDesc', NS)
        caption = norm(' '.join(desc.itertext())) if desc is not None else ''
        if not caption and not label:
            continue
        if SUPP_LABEL.match(label) or SUPP_LABEL.match(caption):
            continue                       # supplementary figure, not the paper
        bare = caption.lstrip(' ;:,.-')
        if BACK_HEAD.match(bare) or BACK_HEAD.match(label):
            continue                       # back matter read as a caption
        if is_figure_furniture(caption, furniture):
            continue                       # panel labels, no caption at all
        if not label and label_soup(caption):
            continue                       # axis ticks or a legend key
        if not label and re.match(r'[a-z]', caption):
            continue                       # the tail of a caption, stranded
        key = re.sub(r'^(figure|fig\.?)\s*', 'figure ', label.lower()).strip(' .:')
        number = label_number(label)
        # GROBID's own image is linked to this figure explicitly and is at the
        # resolution the PDF embeds; our crop is the fallback for vector art
        image = None
        graphic = fig.find('t:graphic', NS)
        if graphic is not None and asset_dir and graphic.get('url'):
            src = os.path.join(asset_dir, os.path.basename(graphic.get('url')))
            src = resolve_asset(src) if os.path.exists(src) else None
            if src:
                fig_seq = len(used_images) + 1
                image = web_image(src, slug, fig_seq)
        if not image:
            image = (figures.get(key) or figures.get(label.lower().strip(' .:'))
                     or (crops.get(number) if number else None))
        # a garbled label ("acKNOWleDGMeNts") is not a figure at all
        if not label_number(label) and not caption:
            continue
        # a caption with no artwork and no sentence is label soup, not a figure
        if not image and caption.count('. ') == 0 and len(caption.split()) < 12:
            continue
        seq += 1
        anchor = label_number(label)
        node = {'id': node_id(seq, caption or label),
                'anchor': 'figure-%d' % anchor if anchor else None,
                'type': 'figure' if image else 'caption',
                'text': ('%s. %s' % (label, caption)).strip('. '),
                'label': label, 'lines': [caption]}
        if image:
            node['image'] = image
            used_images.add(image)
        nodes.append(node)

    nodes, stitched = stitch(nodes)
    nodes = [n for n in nodes
             if n['type'] != 'prose' or n.get('role') or len(n['text']) >= 40]
    nodes = add_missing_figures(nodes, slug, crops)
    nodes = place_figures(nodes)

    for bibl in root.findall('.//t:listBibl/t:biblStruct', NS):
        text = ref_text(bibl)
        if len(text) < 25:
            continue
        seq += 1
        nodes.append({'id': node_id(seq, text), 'type': 'prose', 'text': text,
                      'role': 'references', 'entry': True, 'lines': [text],
                      'anchor': 'ref-%s' % bibl.get(XML_ID)
                                if bibl.get(XML_ID) else None})
    nodes, moved = reading_order(nodes, slug)
    if moved:
        print('  ..   %-56s %d nodes re-ordered to printed order'
              % (slug[:56], moved))
    nodes, restored, inserted, rejoined = ((nodes, 0, 0, 0) if NO_RESTORE
                                          else restore_dropped_text(nodes, slug))
    if restored or inserted or rejoined:
        print('  ..   %-56s %d paragraphs completed, %d restored whole, '
              '%d splits rejoined' % (slug[:56], restored, inserted, rejoined))
    nodes = strip_repeated_heading(split_section_headings(
        insert_missing_sections(lift_run_in_headings(
        repair_compounds(repair_openings(nodes, slug), slug), slug), slug)))
    # after the bibliography exists: the numbering is read off the citations
    nodes = relocate_links(nodes)
    nodes = fill_missing_references(number_references(nodes), slug)
    # last: figures added from our own pass can collide with GROBID's numbering,
    # and a duplicate element id is invalid HTML
    nodes = unique_anchors(nodes)
    return nodes, sorted(used_images)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://localhost:8070')
    ap.add_argument('--only')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--force', action='store_true',
                    help='re-ask GROBID rather than using the cached TEI')
    ap.add_argument('--override-publisher', action='store_true',
                    help="replace a publisher's own conversion (rarely right)")
    ap.add_argument('--no-restore', action='store_true',
                    help='skip taking dropped prose back from our own pass, to '
                         'measure what that pass is doing')
    args = ap.parse_args()
    globals()['NO_RESTORE'] = args.no_restore

    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, '*.pdf')))
    if args.only:
        pdfs = [p for p in pdfs if args.only.lower() in os.path.basename(p).lower()]
    if args.limit:
        pdfs = pdfs[:args.limit]

    done = 0
    for pdf in pdfs:
        slug = os.path.basename(pdf)[:-4]
        doc_path = os.path.join(DOC_DIR, slug + '.json')
        # Tier precedence is separate from cache freshness: --force means
        # "re-ask GROBID", never "overwrite the publisher's own conversion".
        # Conflating the two silently replaced 14 vendor documents once.
        if os.path.exists(doc_path) and not args.override_publisher:
            try:
                if json.load(open(doc_path, encoding='utf-8')).get('source') \
                        == 'biorxiv':
                    print('  ..   %-56s publisher full text, left alone'
                          % slug[:56])
                    continue
            except Exception:                           # noqa: BLE001
                pass
        figures = figure_map(slug)          # harvest before we overwrite
        try:
            xml, asset_dir = tei_with_assets(pdf, args.url, args.force)
            nodes, images = convert(xml, slug, figures, crop_index(slug),
                                    asset_dir)
        except Exception as exc:                        # noqa: BLE001
            print('  !!   %-56s %s' % (slug[:56], str(exc)[:40]))
            continue
        heads = [n for n in nodes if n['type'] == 'heading']
        prose = [n for n in nodes if n['type'] == 'prose' and not n.get('role')]
        refs = [n for n in nodes if n.get('role') == 'references']
        if len(prose) < 5:
            print('  --   %-56s too thin (%d prose)' % (slug[:56], len(prose)))
            continue
        json.dump({'slug': slug, 'source': 'grobid', 'nodes': nodes,
                   'figures': images},
                  open(doc_path, 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
        done += 1
        print('  ok   %-56s %3d heads %3d prose %2d figs %3d refs'
              % (slug[:56], len(heads), len(prose), len(images), len(refs)))
    print('\n%d documents from GROBID' % done)
    return 0


if __name__ == '__main__':
    sys.exit(main())
