#!/usr/bin/env python3
"""Generate a reading page per publication.

Structured papers are rendered straight from the cached JATS, walking the body
in document order so figures land where the authors put them. Papers that only
have PDF-derived text fall back to plain prose with the journal furniture
stripped off the front.

    python3 scripts/build_papers.py [--only SUBSTRING] [--limit N]
"""

import argparse
import html
import json
import os
import re
import sys

from lxml import etree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, '.cache')
JATS_DIR = os.path.join(CACHE, 'jats')
OUT_ROOT = os.path.join(REPO, 'papers')
XLINK = '{http://www.w3.org/1999/xlink}href'

# leading journal furniture on PDF-derived text
BOILER = re.compile(
    r'^(contents\s*lists\s*available.*?|.*?journal\s*homepage.*?|'
    r'•?cover\s*article•?.*?|downloaded\s*from.*?)$', re.I)

# stamps repeated on every page of a preprint or publisher PDF
STAMP = re.compile(
    r'(which was not certified by peer review|is the author/funder|'
    r'has granted bioRxiv a license|available under a CC-BY|'
    r'medRxiv preprint doi|bioRxiv preprint doi|this version posted|'
    r'all rights reserved\. no reuse allowed)', re.I)


def slug(rec):
    base = re.sub(r'[^A-Za-z0-9]+', '-', rec['title'])[:70].strip('-').lower()
    return '%s-%s' % (rec.get('year') or 'n-d', base or 'untitled')


def esc(s):
    return html.escape(s or '', quote=True)


# bare URLs sitting in the prose (abstracts and reference lists are full of
# them); run over already-escaped text so tags are never touched
URL_RE = re.compile(r'(https?://[^\s<>"\']+[^\s<>"\'().,;:])')


def linkify(escaped):
    return URL_RE.sub(r'<a href="\1">\1</a>', escaped)


# ---------- lab member linking ----------

def lab_members():
    """{'Ovchinnikov S': 'Sergey_Ovchinnikov'} from the lab page markup."""
    out = {}
    for page in ('lab/index.html', 'lab/alumni/index.html'):
        path = os.path.join(REPO, page)
        if not os.path.exists(path):
            continue
        src = open(path, encoding='utf-8').read()
        for card in re.finditer(
                r'data-authors="([^"]*)"[^>]*>.*?<div class="name">([^<]+)</div>',
                src, re.S):
            keys, name = card.group(1), card.group(2).strip()
            for key in keys.split('|'):
                if key.strip():
                    out[key.strip()] = name.replace(' ', '_')
    return out


def link_authors(byline, members, depth='../../'):
    """Turn 'Kolodziej A, ... and Ovchinnikov S.' into links where we can."""
    if not byline:
        return ''
    parts = re.split(r'(,\s*|\s+and\s+)', byline)
    out = []
    for part in parts:
        key = part.strip().rstrip('.')
        target = members.get(key)
        if target:
            out.append('<a href="%slab/member/?name=%s">%s</a>'
                       % (depth, esc(target), esc(part)))
        else:
            out.append(esc(part))
    return ''.join(out)


# ---------- body rendering ----------

# subtrees that must not bleed into the running text: a <fig> nested inside a
# <p> would otherwise repeat its whole caption mid-paragraph
SKIP_INLINE = {'fig', 'table-wrap', 'supplementary-material', 'graphic', 'media'}

# trailing sections that are publishing apparatus rather than the paper
APPARATUS = {'online content', 'supplementary information', 'source data',
             'additional information', 'supporting information', 'data availability',
             'code availability', 'extended data', 'author contributions',
             'competing interests', 'acknowledgements', 'acknowledgments',
             'reporting summary', 'peer review information', 'about this article',
             'extended data', 'ethics declarations', 'rights and permissions'}


MATHML_NS = 'http://www.w3.org/1998/Math/MathML'
TEX_BODY = re.compile(r'\\begin\{document\}(.*?)\\end\{document\}', re.S)


def render_math(formula):
    """JATS keeps MathML and a whole standalone LaTeX document side by side.

    Use the MathML (browsers render it unaided); fall back to the TeX with its
    preamble stripped, which is the part a reader actually wants to see.
    """
    from copy import deepcopy

    mml = formula.find('.//{%s}math' % MATHML_NS)
    if mml is not None:
        m = deepcopy(mml)
        for pi in m.xpath('//processing-instruction()'):
            pi.getparent().remove(pi)
        for el in m.iter():
            if isinstance(el.tag, str):
                el.tag = etree.QName(el).localname
        etree.cleanup_namespaces(m)
        out = etree.tostring(m, encoding='unicode')
        if 'xmlns' not in out.split('>', 1)[0]:
            out = out.replace('<math', '<math xmlns="%s"' % MATHML_NS, 1)
        return out

    tex = formula.find('.//tex-math')
    if tex is not None:
        raw = ''.join(tex.itertext())
        body = TEX_BODY.search(raw)
        expr = (body.group(1) if body else raw).strip().strip('$').strip()
        if expr:
            return '<span class="paper-tex">%s</span>' % esc(expr)
    return ''


def inline_html(node, in_sup=False, targets=None):
    """A paragraph's markup: citations as superscript links, emphasis kept."""
    parts = []
    if node.text:
        parts.append(linkify(esc(node.text)))
    for child in node:
        tag = etree.QName(child).localname if isinstance(child.tag, str) else ''
        if tag in SKIP_INLINE:
            pass                                    # dropped, tail still kept
        elif tag in ('inline-formula', 'disp-formula'):
            math = render_math(child)
            if math:
                parts.append(math if tag == 'inline-formula'
                             # a span, not a div: display formulae sit inside a
                             # <p>, and a block element there closes it early
                             else '<span class="paper-math">%s</span>' % math)
        elif tag == 'xref' and child.get('ref-type') == 'bibr':
            label = ''.join(child.itertext()).strip()
            rid = child.get('rid') or ''
            # Some publishers ship JATS with citations but no <ref-list>, so the
            # superscripts had nowhere to land. Render those as plain text
            # rather than as links to an anchor that does not exist.
            if targets is not None and rid not in targets:
                parts.append(esc(label) if in_sup else '<sup>%s</sup>' % esc(label))
            else:
                link = '<a href="#%s">%s</a>' % (esc(rid), esc(label))
                # many publishers wrap the xref in <sup>; don't double it
                parts.append(link if in_sup else '<sup>%s</sup>' % link)
        elif tag == 'xref':
            parts.append(esc(''.join(child.itertext())))
        elif tag in ('italic', 'bold', 'sup', 'sub'):
            wrap = {'italic': 'i', 'bold': 'b', 'sup': 'sup', 'sub': 'sub'}[tag]
            parts.append('<%s>%s</%s>'
                         % (wrap, inline_html(child, in_sup=(tag == 'sup'),
                                              targets=targets), wrap))
        elif tag == 'ext-link':
            href = child.get(XLINK) or ''
            parts.append('<a href="%s">%s</a>'
                         % (esc(href), esc(''.join(child.itertext()))))
        else:
            parts.append(inline_html(child, in_sup, targets))
        if child.tail:
            parts.append(linkify(esc(child.tail)))
    out = re.sub(r'\s+', ' ', ''.join(parts)).strip()
    # Nature-style "(ref. 1)" / "(refs. 2,3)" wrapping around a citation: the
    # scaffolding is theirs, the superscript alone reads better here
    out = re.sub(r'\(\s*refs?\.?\s*((?:<sup>.*?</sup>[\s,;&–-]*)+)\)',
                 lambda m: m.group(1).rstrip(' ,;&–-'), out, flags=re.I)
    return out


def render_refs(root):
    """The bibliography, anchored so the inline superscripts land on it."""
    refs = root.findall('.//back//ref')
    if not refs:
        return ''
    items = []
    for ref in refs:
        def first(*paths):
            for p in paths:
                el = ref.find('.//' + p)
                if el is not None and ''.join(el.itertext()).strip():
                    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()
            return ''

        names = []
        for nm in ref.findall('.//name')[:6]:
            surname = nm.find('surname')
            given = nm.find('given-names')
            if surname is not None and surname.text:
                initials = given.text if given is not None and given.text else ''
                names.append(('%s %s' % (surname.text, initials)).strip())
        if ref.findall('.//etal'):
            names.append('et al.')
        title = first('article-title', 'chapter-title')
        source = first('source')
        year = first('year')
        doi = ''
        for pid in ref.findall('.//pub-id'):
            if pid.get('pub-id-type') == 'doi':
                doi = ''.join(pid.itertext()).strip()
        bits = []
        if names:
            bits.append('<span class="ref-authors">%s</span>' % esc(', '.join(names)))
        if title:
            bits.append(esc(title))
        tail = ' '.join(x for x in (source, year) if x)
        if tail:
            bits.append('<span class="ref-src">%s</span>' % esc(tail))
        raw_ref = re.sub(r'^\s*\d{1,3}[.)]\s*', '',
                         re.sub(r'\s+', ' ', ''.join(ref.itertext())).strip())
        body = ' '.join(bits) or linkify(esc(raw_ref[:300]))
        if doi:
            body += ' <a class="ref-doi" href="https://doi.org/%s">doi</a>' % esc(doi)
        items.append('        <li id="%s">%s</li>' % (esc(ref.get('id') or ''), body))
    return ('      <section class="paper-refs" id="references">\n        <h2>References</h2>\n'
            '        <ol>\n%s\n        </ol>\n      </section>' % '\n'.join(items))


def render_jats(rec, name):
    """Walk the article body, emitting sections and figures in place."""
    path = os.path.join(JATS_DIR,
                        re.sub(r'[^A-Za-z0-9]+', '-', rec['title'])[:70] + '.xml')
    if not os.path.exists(path):
        return None
    root = etree.parse(path).getroot()
    # ids the bibliography will actually carry, so a citation to an entry this
    # JATS does not contain renders as plain text instead of a dead link
    ref_targets = {r.get('id') for r in root.findall('.//back//ref') if r.get('id')}
    body = root.find('.//body')
    if body is None:
        return None

    images = {f.get('graphic'): f.get('image')
              for f in rec['jats']['figures'] if f.get('image')}
    html_out = []
    toc = []

    def text_of(el):
        return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()

    def emit_fig(fig):
        graphic = fig.find('.//graphic')
        href = graphic.get(XLINK) if graphic is not None else None
        src = images.get(href)
        if not src:                      # tolerate a missing extension
            stem = os.path.splitext(href or '')[0]
            src = next((v for k, v in images.items()
                        if os.path.splitext(k or '')[0] == stem), None)
        label = text_of(fig.find('label')) if fig.find('label') is not None else ''
        caption = text_of(fig.find('caption')) if fig.find('caption') is not None else ''
        html_out.append('<figure class="paper-fig">')
        if src:
            html_out.append('  <img loading="lazy" src="../../%s" alt="%s">'
                            % (esc(src), esc(label or 'Figure')))
        html_out.append('  <figcaption><b>%s</b> %s</figcaption>'
                        % (esc(label), linkify(esc(caption))))
        html_out.append('</figure>')

    # Figures are stored at section boundaries, not where they are discussed,
    # so anchor each one to the first paragraph that cites it. Anything never
    # cited keeps its document position.
    figs_by_id = {f.get('id'): f for f in body.iter('fig') if f.get('id')}
    placed = set()

    def place(fig_id):
        if fig_id in figs_by_id and fig_id not in placed:
            placed.add(fig_id)
            emit_fig(figs_by_id[fig_id])

    def walk(el, level=2):
        for child in el:
            tag = etree.QName(child).localname if isinstance(child.tag, str) else ''
            if tag == 'sec':
                title = child.find('title')
                head = text_of(title) if title is not None else ''
                if head.lower().strip(' .:') in APPARATUS:
                    continue
                if title is not None and text_of(title):
                    head_text = text_of(title)
                    hid = 'sec-%d-%s' % (len(toc) + 1,
                                         re.sub(r'[^a-z0-9]+', '-',
                                                head_text.lower())[:40].strip('-'))
                    toc.append({'level': level, 'id': hid, 'text': head_text})
                    html_out.append('<h%d id="%s">%s</h%d>'
                                    % (level, esc(hid), esc(head_text), level))
                walk(child, min(level + 1, 4))
            elif tag == 'p':
                markup = inline_html(child, targets=ref_targets)
                if len(re.sub(r'<[^>]+>', '', markup)) > 40:
                    html_out.append('<p>%s</p>' % markup)
                    for x in child.iter('xref'):
                        if x.get('ref-type') == 'fig':
                            place(x.get('rid'))
            elif tag == 'fig':
                place(child.get('id'))

    walk(body)
    refs_html = render_refs(root)
    # any figure the walk did not reach (sits outside the body flow)
    seen = set(re.findall(r'src="\.\./\.\./([^"]+)"', '\n'.join(html_out)))
    trailing = [f for f in rec['jats']['figures']
                if f.get('image') and f['image'] not in seen]
    for f in trailing:
        html_out.append(
            '<figure class="paper-fig">\n'
            '  <img loading="lazy" src="../../%s" alt="%s">\n'
            '  <figcaption><b>%s</b> %s</figcaption>\n</figure>'
            % (esc(f['image']), esc(f.get('label') or 'Figure'),
               esc(f.get('label') or ''), esc(f.get('caption') or '')))
    return '\n'.join(html_out), refs_html, toc


# A section heading in extracted PDF text: a canonical name alone on its line,
# optionally numbered. Deliberately conservative — inventing structure a paper
# does not have would misrepresent it, and Science reports genuinely have none.
HEAD_CANON = re.compile(
    r'^(?:\d{1,2}[.)]?\s+|[IVX]{1,4}[.)]\s+)?'
    r'(abstract|introduction|background|results and discussion|results|discussion|'
    r'materials and methods|methods and materials|methods|experimental procedures|'
    r'model and methods|conclusions?|summary|outlook|significance)'
    r'\s*[:.]?$', re.I)

# numbered subsection: "2.1 Sequence search". Must be followed by a capitalised
# word, or table rows like "0.64 0.64" get promoted to headings.
HEAD_SUB = re.compile(r'^\d{1,2}\.\d{1,2}\.?\s+[A-Z][A-Za-z].{2,78}$')

# Start of the back matter. Deliberately narrow: phrases like "Supplementary
# Data" appear as pointers in the middle of Nature papers, and cutting there
# throws away the Methods.
TAIL = re.compile(
    r'^(?:\d{1,2}[.)]?\s+)?(references|bibliography|literature cited|'
    r'references and notes|acknowledge?ments?|author contributions?|'
    r'competing interests?|declaration of competing|conflicts? of interest)'
    r'\s*[:.]?$', re.I)

# Everything that isn't the paper: the bibliography plus the apparatus a
# journal appends around it. Skipping runs from any of these to the next real
# heading, so a mid-document reference list doesn't take the Methods with it.
BACK = re.compile(
    r'^(?:\d{1,2}[.)]?\s+)?(references|bibliography|literature cited|'
    r'references and notes|acknowledge?ments?|author contributions?|'
    r'competing interests?|declaration of competing|conflicts? of interest|'
    r'declarations?(?: of interests?)?|data (?:and code )?availability|'
    r'code availability|supplementary information|supplemental information|'
    r'key resources table|additional information|ethics declarations|'
    r'reporting summary|funding)\s*[:.]?$', re.I)

# Back matter over, paper resumes: the section names journals use for the full
# Methods when it is printed after the references.
RESUME = re.compile(
    r'^(star\s*\+?\s*methods|(?:experimental|animal) model[a-z\s]*details|'
    r'method details|methods? and materials|quantification and statistical '
    r'analysis|supplementary methods)\s*[:.]?$', re.I)


# Science runs its structured-abstract labels straight into the text:
# "INTRODUCTION:Protein-protein interactions play a central role..."
HEAD_RUNIN = re.compile(
    r'^(INTRODUCTION|RATIONALE|RESULTS|CONCLUSIONS?|DISCUSSION|BACKGROUND|'
    r'SIGNIFICANCE|SUMMARY)\s*:\s*(.*)$')

# repository copies (eScholarship, OSTI) arrive with a cover sheet in front
COVER = ('permalink', 'escholarship.org', 'lbl publications', 'peer reviewed',
         'publication date', 'osti.gov', 'escholarship')

# a table-of-contents line: title followed by a page number
TOC_LINE = re.compile(r'^.{4,58}?\s+\d{1,3}$')


GUTTER = re.compile(r'^(.*?)\s(\d{1,4})\s*$')

AFFIL = re.compile(r'\b(university|universit[eé]|department|departamento|institute|'
                   r'instituto|laborator(?:y|ies)|school of|college|centre|center|'
                   r'hospital|academy|hhmi|inc\.)\b', re.I)


# "Jin Su1," / "Vorobieva#1,2" — superscript markers extraction glued to names
BYLINE = re.compile(r'[A-Za-z]{3,}[#*†‡]?\d{1,2}(?=[,\s]|$)')


def is_affiliations(para):
    """A cover-page byline and affiliation list rather than prose.

    Judged on how the paragraph *opens*, since extraction often glues the cover
    block onto the text that follows it. Prose can accumulate the same signals
    over hundreds of words — numeric citations look like author markers — so a
    long paragraph only qualifies when they are dense throughout.
    """
    head = ' '.join(para.split()[:60])
    if len(BYLINE.findall(head)) < 3 and len(AFFIL.findall(head)) < 2 \
            and '@' not in head:
        return False
    words = len(para.split())
    if words < 200:
        return True
    return len(BYLINE.findall(para)) + len(AFFIL.findall(para)) >= words / 25


def strip_line_numbers(lines):
    """Remove a line-number gutter that extraction merged into the text.

    Line-numbered manuscripts come out as "Introduction 29" — enough to stop
    every heading from being recognised. Only strip when the trailing numbers
    really do count up across the document, so page numbers and values at the
    end of a sentence are left alone.
    """
    matched = [(i, m) for i, l in enumerate(lines) if (m := GUTTER.match(l))]
    # judge the pattern on prose lines only: a table of numbers would otherwise
    # look like a gutter to us
    prose = [(i, m) for i, m in matched if not lines[i].strip()[0:1].isdigit()]
    if len(prose) < 20:
        return lines
    runs = sum(1 for (_, a), (_, b) in zip(prose, prose[1:])
               if 0 < int(b.group(2)) - int(a.group(2)) <= 2)
    if runs < 0.7 * len(prose):
        return lines
    out = list(lines)
    for i, m in matched:       # once established, strip the whole column
        out[i] = m.group(1)
    return out


# a line out of a reference list: "Pettersen, E.F. et al. (2004) ... doi:..."
CITE = re.compile(r'\bet al\b|\(\d{4}[a-z]?\)|\b(19|20)\d{2}[a-z]?[.;)]|'
                  r'\bdoi\b|\bpp\.\s*\d|\bvol\.\s*\d|arxiv|biorxiv', re.I)


ACK_CUE = re.compile(r'\bwe (?:thank|are grateful|acknowledge)|supported (?:in part )?by|'
                     r'\bgrants?\s+(?:no\.?|number|from)?|funded by|fellowship', re.I)


def body_prose_ahead(lines, i, width=6):
    """Does the paper resume here, in the middle of back matter?

    Extraction gives us no paragraph breaks to lean on, so this reads the next
    few lines: running prose has sentences and no citations, while a reference
    list, a resources table and a one-line funding note each fail on one of
    those counts.
    """
    win = [l.strip() for l in lines[i:i + width] if l.strip()]
    if any(BACK.match(l) for l in win):
        win = win[:next(j for j, l in enumerate(win) if BACK.match(l))]
    text = ' '.join(win)
    words = text.split()
    if len(words) < 60 or text.count('. ') < 2 or CITE.search(text):
        return False
    if ACK_CUE.search(text):        # the acknowledgments themselves
        return False
    # resources tables read as sentences once the row breaks are lost, but
    # they are packed with catalogue numbers and accessions
    return sum(1 for w in words if any(c.isdigit() for c in w)) < 0.12 * len(words)


NUM_REF = re.compile(r'^\d{1,3}\.\s+[A-Z]')


def reference_run_starts(lines):
    """Where a numbered bibliography begins without a heading above it.

    Nature PDFs often lose the "References" line in extraction, leaving the
    list itself — "1. Xu, J. Distance-based protein folding…" — sitting under
    whatever section came before. Enumerated lists in prose look similar, so
    require several consecutive entries and citation markers around them.
    """
    starts, prev_entry = set(), -2
    for i, line in enumerate(lines):
        if not NUM_REF.match(line.strip()):
            continue
        was_run, prev_entry = prev_entry == i - 1, i
        if was_run:                 # mark only where the list begins
            continue
        window = lines[i:i + 60]
        entries = [l.strip() for l in window if NUM_REF.match(l.strip())]
        nums = [int(l.split('.')[0]) for l in entries]
        # count citation markers over the whole window: entries wrap, so the
        # year often sits on the continuation line
        if (len(entries) >= 5 and nums == sorted(nums)
                and len(CITE.findall(' '.join(window))) >= 4):
            starts.add(i)
    return starts


# the back-matter markers that introduce a bibliography rather than apparatus
REFS_HEAD = re.compile(r'^(?:\d{1,2}[.)]?\s+)?(references|bibliography|'
                       r'literature cited|references and notes)\s*[:.]?$', re.I)

# where one entry ends and the next begins: "12. Xu, J." or "Adams, P.D., …"
# numbering is unambiguous: it can only be the start of an entry
NUMBERED = re.compile(r'^(?:\[\d{1,3}\]|\d{1,3}[.)])\s+\S'
                      # or with no punctuation after it: "1 Hoch, J. C. et al."
                      r'|^\d{1,3}\s+[A-Z][\w’\'-]{1,24}[,\s]')

# A name at the head of a line, either surname-first ("Adams, P.D.,", with or
# without the spaces the extractor may have eaten) or given-name-first ("Badri
# Adhikari and Jianlin Cheng."). Ambiguous on its own — an author list that
# wraps puts one of these mid-entry — so it counts only after a line that
# closed off a sentence.
# the character class keeps the stray combining marks extraction leaves behind
# ("Gioffre´ , A."), which would otherwise break the surname match
NAME_CH = r'\w’\'´`¨ˆ~-'
NAME_START = re.compile(
    r'^[A-Z][' + NAME_CH + r']{1,24}\s?,\s*(?:[A-Z]\.|[A-Z][a-z]+[,\s]|et ?al)'
    r'|^(?:[A-Z][' + NAME_CH + r']*\.?\s+){1,4}(?:and\s+)?[A-Z]')

# an entry's last line ends a sentence; a wrapped one usually doesn't. A page
# footer landing mid-list ("Cell 169, 273–285, April 6, 2017 283") also counts,
# since the entry it interrupted did end above it.
ENDS_ENTRY = re.compile(r'(?:19|20)\d{2}\s+\d{1,4}\s*$|'
                        r'(?<![A-Z])(?<!\bNat)(?<!\bSci)(?<!\bProc)(?<!\bNatl)'
                        r'(?<!\bAcad)(?<!\bBiol)(?<!\bChem)(?<!\bRes)(?<!\bMol)'
                        r'(?<!\bStruct)(?<!\bBiophys)(?<!\bComput)(?<!\bEng)'
                        r'[.)]\s*$')

YEAR = re.compile(r'\b(?:19|20)\d{2}[a-z]?\b')

# a running footer swept up at the end of an entry: "… Cell 169, 273–285,
# April 6, 2017 283". The bare page number at the end is what marks it as
# furniture rather than part of the citation.
FOOTER_TAIL = re.compile(r'\s+[A-Z][A-Za-z.]+\s+\d{1,4},\s*\d+[–-]\d+,\s*'
                         r'[A-Z][a-z]+\s+\d{1,2},\s*(?:19|20)\d{2}\s+\d{1,4}$')


def parse_references(lines):
    """Group the collected bibliography lines into one string per entry.

    Entries wrap across lines and the extraction keeps no record of where they
    break, so the only signal is how a line *starts* — numbering, or a name
    once the line before it has closed off a sentence.
    """
    entries, prev = [], ''
    for line in lines:
        s = re.sub(r'\s+', ' ', line.strip())
        if not s:
            continue
        boundary = (NUMBERED.match(s)
                    or (NAME_START.match(s) and ENDS_ENTRY.search(prev)))
        if boundary or not entries:
            entries.append(s)
        else:
            entries[-1] += ' ' + s
        prev = s
    out = []
    for e in entries:
        e = re.sub(r'^(?:\[\d{1,3}\]|\d{1,3}[.)]|\d{1,3}(?=\s+[A-Z]))\s*', '', e).strip()
        e = FOOTER_TAIL.sub('', e).strip()
        if len(e) >= 40 and YEAR.search(e):
            out.append(e)
    return out


def well_formed(entry):
    """One reference, not two merged or half of one.

    A page whose entries mostly fail this has had its bibliography mangled
    beyond what the text can support, and gets no reference list at all.
    """
    return (45 <= len(entry) <= 420 and YEAR.search(entry)
            and re.match(r'[A-Z\[]', entry))


def render_entries(entries):
    """A bibliography that arrived already parsed, one entry per item."""
    entries = [(a, t, n) for a, t, n in entries if len(t) >= 25]
    if len(entries) < 3:
        return ''
    # value= sets the displayed number, so it matches what the text cites even
    # where the parsed list skipped an entry
    items = ['        <li%s%s>%s</li>'
             % ((' id="%s"' % esc(a)) if a else '',
                (' value="%d"' % n) if n else '', linkify(esc(t)))
             for a, t, n in entries]
    return ('      <section class="paper-refs" id="references">\n'
            '        <h2>References</h2>\n'
            '        <ol>\n%s\n        </ol>\n      </section>' % '\n'.join(items))


def render_text_refs(lines):
    """A plain bibliography for a PDF-derived page.

    No ids: the inline markers in PDF text are bare characters with nothing to
    link from, so this is a list to read, not a target to jump to.
    """
    entries = parse_references(lines)
    if len(entries) < 3:
        return ''
    good = sum(1 for e in entries if well_formed(e))
    if good < 0.6 * len(entries):
        return ''
    items = ['        <li>%s</li>' % linkify(esc(e)) for e in entries]
    return ('      <section class="paper-refs" id="references">\n'
            '        <h2>References</h2>\n'
            '        <ol>\n%s\n        </ol>\n      </section>' % '\n'.join(items))


def drop_back_matter(lines, repeated=frozenset()):
    """Remove the bibliography and the apparatus printed around it.

    Where back matter *ends* can't be read off a heading: Cell prints the full
    Methods after the references, Nature does the same, ML preprints follow
    with an appendix, and a repository PDF can put author contributions in the
    front matter ahead of the whole paper. So each skip runs only until the
    next real heading, or until the prose picks up again.
    """
    starts = reference_run_starts(lines)
    kept, refs, skipping = [], [], False
    for i, line in enumerate(lines):
        s = line.strip()
        if i in starts or BACK.match(s):
            # remember which kind of back matter this is: the bibliography is
            # kept aside to be rendered, the apparatus is thrown away
            skipping = 'refs' if (i in starts or REFS_HEAD.match(s)) else 'apparatus'
            continue
        if skipping:
            if HEAD_CANON.match(s) or RESUME.match(s) or body_prose_ahead(lines, i):
                skipping = False
            else:
                if skipping == 'refs' and not (STAMP.search(s) or s in repeated):
                    refs.append(line)
                continue
        kept.append(line)
    return kept, refs


def render_text(rec):
    """PDF-derived prose, with whatever section structure the paper really has."""
    path = os.path.join(REPO, rec['text_file'])
    if not os.path.exists(path):
        return None, [], ''
    # non-breaking spaces come out of publisher PDFs everywhere ("et\xa0al.")
    # and quietly defeat every \b-anchored pattern below
    raw = open(path, encoding='utf-8', errors='ignore').read().replace('\xa0', ' ')
    # Cell's PDFs name a few glyphs instead of encoding them: "37/C14C" is
    # 37°C and "/C244hr" is ~4hr. Only the two unambiguous ones are mapped —
    # the rest stay as they are rather than be guessed at.
    raw = re.sub(r'/C14(?=C\b)', '°', raw)
    raw = re.sub(r'/C24(?=\d)', '~', raw)
    lines = raw.split('\n')

    # drop a repository cover sheet: everything up to the last of its markers
    head = [i for i, l in enumerate(lines[:70])
            if any(m in l.lower() for m in COVER)]
    if len(head) >= 2:
        lines = lines[head[-1] + 1:]

    lines = strip_line_numbers(lines)

    # drop a leading table of contents (its entries end in page numbers)
    front = lines[:int(len(lines) * 0.15)]
    toc_rows = [i for i, l in enumerate(front) if TOC_LINE.match(l.strip())]
    if len(toc_rows) >= 4:
        lines = lines[:toc_rows[0]] + lines[toc_rows[-1] + 1:]

    # running headers and footers repeat on every page; drop the repeats
    counts = {}
    for line in lines:
        s = line.strip()
        if 4 < len(s) < 220:
            counts[s] = counts.get(s, 0) + 1
    repeated = {s for s, n in counts.items() if n >= 3}

    lines, ref_lines = drop_back_matter(lines, repeated)

    out, toc, buf = [], [], []

    def key_of(text):
        return re.sub(r'[^a-z0-9]', '', (text or '').lower())

    # the PDF repeats what the page already shows: the abstract above the body,
    # and a title/affiliation block on the cover
    abstract_key = key_of(rec.get('abstract'))[:90]
    title_key = key_of(rec.get('title'))[:45]
    seen = set()

    def flush():
        if not buf:
            return
        para = re.sub(r'\s+', ' ', ' '.join(buf)).strip()
        del buf[:]
        if len(para) < 60 or BOILER.match(para):
            return
        k = key_of(para)
        # fingerprint the whole paragraph: a prefix collides whenever two
        # paragraphs happen to start with the same page furniture
        if k in seen:
            return
        # figure-axis text and table fragments: no sentence structure
        if '. ' not in para and len(para.split()) < 40:
            return
        if abstract_key and k[:90] == abstract_key:
            return
        if title_key and k.startswith(title_key):  # cover block
            return
        # the byline and affiliation block, on a paper whose preprint title
        # differs from the published one so the check above can't see it
        if not any(el.startswith('<h') for el in out) and is_affiliations(para):
            return
        seen.add(k)
        out.append('<p>%s</p>' % linkify(esc(para)))

    for line in lines:
        s = line.strip()
        if (not s or s in repeated or STAMP.search(s)
                or re.fullmatch(r'[\d\s|/-]{1,12}', s)):
            flush()
            continue
        runin = HEAD_RUNIN.match(s)
        if runin:                       # Science structured-abstract label
            flush()
            text = runin.group(1).title()
            hid = 'sec-%d-%s' % (len(toc) + 1, text.lower())
            toc.append({'level': 2, 'id': hid, 'text': text})
            out.append('<h2 id="%s">%s</h2>' % (esc(hid), esc(text)))
            if runin.group(2).strip():
                buf.append(runin.group(2).strip())
            continue

        canon = HEAD_CANON.match(s) or RESUME.match(s)
        sub = HEAD_SUB.match(s) if not canon else None
        if canon or sub:
            flush()
            level = 2 if canon else 3
            text = (canon.group(1).title() if canon else s)
            hid = 'sec-%d-%s' % (len(toc) + 1,
                                 re.sub(r'[^a-z0-9]+', '-', text.lower())[:40].strip('-'))
            toc.append({'level': level, 'id': hid, 'text': text})
            out.append('<h%d id="%s">%s</h%d>' % (level, esc(hid), esc(text), level))
            continue
        buf.append(s)
    flush()
    if rec.get('abstract'):
        out, toc = drop_abstract_section(rec, out, toc)
    out, toc = drop_empty_sections(out, toc)

    return ('\n'.join(out) if out else None), toc, render_text_refs(ref_lines)


def drop_abstract_section(rec, out, toc):
    """Drop the PDF's own Abstract heading — the box above already shows it.

    The heading always goes: either it repeats the box, or the word turned up
    mid-page and was never a heading to begin with. Its paragraphs go only when
    they restate the abstract, which is judged on word overlap because the
    published wording rarely matches the manuscript's exactly.
    """
    words = lambda s: set(re.findall(r'[a-z]{4,}', s.lower()))
    abstract = words(re.sub(r'<[^>]+>', '', rec['abstract']))
    start = next((i for i, el in enumerate(out)
                  if re.match(r'<h2 id="[^"]*"[^>]*>Abstract</h2>', el)), None)
    if start is None or len(abstract) < 20:
        return out, toc
    end = start + 1
    while end < len(out) and out[end].startswith('<p>'):
        w = words(re.sub(r'<[^>]+>', '', out[end]))
        if not w or len(w & abstract) < 0.5 * len(w):
            break
        end += 1
    dropped = {m.group(1) for el in out[start:end]
               if (m := re.search(r'<h[23] id="([^"]+)"', el))}
    return (out[:start] + out[end:],
            [t for t in toc if t['id'] not in dropped])


def drop_empty_sections(out, toc):
    """Remove headings whose section holds no prose.

    Mostly this is the PDF's own "Abstract" heading, left behind once its text
    was deduped against the abstract box above. A parent heading survives if
    any of its subsections has text.
    """
    levels = [int(m.group(1)) if (m := re.match(r'<h([23])', el)) else None
              for el in out]
    keep = []
    for i, el in enumerate(out):
        if levels[i] is None:
            keep.append(el)
            continue
        has_text = False
        for j in range(i + 1, len(out)):
            if levels[j] is not None and levels[j] <= levels[i]:
                break
            if levels[j] is None:
                has_text = True
                break
        if has_text:
            keep.append(el)
    kept_ids = {m.group(1) for el in keep
                if (m := re.search(r'<h[23] id="([^"]+)"', el))}
    return keep, [t for t in toc if t['id'] in kept_ids]


# ---------- documents extracted from PDFs, plus their edit overlays ----------

DOC_DIR = os.path.join(CACHE, 'doc')
EDIT_DIR = os.path.join(REPO, 'edits')
EQN_DIR = os.path.join(CACHE, 'equations')

# node types that never reach the page: page furniture, figure interiors, and
# whatever the classifier judged to be set too small to be running text
DOC_HIDDEN = {'stamp', 'furniture', 'figure-text', 'rotated', 'small', 'empty',
              'math'}


def load_doc(slug):
    path = os.path.join(DOC_DIR, slug + '.json')
    if not os.path.exists(path):
        return None
    return json.load(open(path, encoding='utf-8'))


def apply_edits(doc, slug):
    """Overlay the hand-written corrections for this paper onto its nodes.

    Extraction output is never edited in place. Corrections live in
    edits/<slug>.json as ops against node ids, so re-extracting a paper keeps
    every fix that still has something to attach to. An op whose id no longer
    exists is reported rather than dropped quietly — that means extraction
    changed underneath it and a human should look.

        {"ops": [{"op": "drop",   "id": "p12-9f2a", "why": "table dump"},
                 {"op": "set",    "id": "p6-44ab",  "text": "…"},
                 {"op": "retype", "id": "p4-1c7d",  "to": "caption"},
                 {"op": "level",  "id": "p2-aa11",  "to": 3},
                 {"op": "after",  "id": "p3-cc33",  "node": {...}}]}
    """
    path = os.path.join(EDIT_DIR, slug + '.json')
    if not os.path.exists(path):
        return doc, 0, []
    spec = json.load(open(path, encoding='utf-8'))
    return apply_ops(doc, spec, path)


def fingerprint(node):
    """What an op remembers about its target besides the id.

    Node ids are content hashes, so any later repair to a paragraph's text —
    a mended hyphen, a rejoined column break — changes its id and quietly
    unmoors every op pointing at it. That is how Figure 4 lost its image: the
    op replacing the wrong crop still matched, the op inserting the right one
    did not. A fingerprint lets the op find its target again.
    """
    words = re.findall(r'[a-z0-9]+', (node.get('text') or '').lower())
    return ' '.join(words[:12])


def shingles(text, n=6):
    words = re.findall(r'[a-z0-9]+', (text or '').lower())
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def most_like(text, nodes):
    """The one node that is recognisably the same paragraph, or nothing.

    A `set` op usually rewrites the *opening* of a paragraph — that is the
    defect it exists to fix — so a prefix match cannot find its target once
    extraction repairs the same opening. The body of the paragraph is what
    stays put, so score on shared word runs and insist the winner be clear.
    """
    want = shingles(text)
    if len(want) < 4:
        return None
    scored = []
    for node in nodes:
        have = shingles(node.get('text'))
        if have:
            scored.append((len(want & have) / len(want | have), node))
    scored.sort(key=lambda s: -s[0])
    if scored and scored[0][0] >= 0.4 and (len(scored) == 1
                                           or scored[1][0] < scored[0][0] * 0.6):
        return scored[0][1]
    return None


def already_present(op, nodes):
    """Is this insert's text now on the page without it?

    An agent that types a lost paragraph back in is fixing a defect in
    extraction, and the fix is meant to be temporary: when the extractor learns
    to recover that paragraph itself, the op becomes a second copy. That is
    exactly what happened on the lipid-transport paper — the restore pass and an
    older overlay each supplied the same Methods text.
    """
    if op.get('op') != 'after':
        return False
    payload = op.get('node') or {}
    # Prose only. A figure insert carries its caption as text, and the wrong
    # image it replaces carries the same caption — reading that as "already
    # present" skipped the replacement and left two figures unreferenced.
    if payload.get('type') != 'prose':
        return False
    want = shingles(payload.get('text') or '')
    if len(want) < 8:
        return False
    return any(len(want & shingles(n.get('text'))) > len(want) * 0.6
               for n in nodes if n.get('type') != 'dropped')


def resolve(op, by_id, by_fp, remap, nodes):
    """The nodes an op applies to: by id, by the text it remembered, by how
    much of a paragraph it still recognises, or by an id a sibling op already
    re-found."""
    ident = op.get('id')
    if by_id.get(ident):
        return by_id[ident], None
    if ident in remap:
        return (by_id.get(remap[ident]) or []), remap[ident]
    for key in (op.get('at'), fingerprint({'text': op.get('text', '')})):
        if key and len(by_fp.get(key) or []) == 1:
            found = by_fp[key][0]
            remap[ident] = found['id']
            return [found], found['id']
    found = most_like(op.get('text') or op.get('at'), nodes)
    if found is not None:
        remap[ident] = found['id']
        return [found], found['id']
    return [], None


def apply_ops(doc, spec, path=None):
    # every node sharing an id, not just one of them: extraction suffixes
    # repeats now, but a doc built before that still has collisions and an op
    # must not silently reach only one copy
    by_id, by_fp = {}, {}
    for n in doc['nodes']:
        by_id.setdefault(n['id'], []).append(n)
        by_fp.setdefault(fingerprint(n), []).append(n)
    applied, stale, inserts = 0, [], []
    remap, restamped = {}, False
    for op in spec.get('ops', []):
        if already_present(op, doc['nodes']):
            continue                     # extraction now recovers this itself
        targets, found_id = resolve(op, by_id, by_fp, remap, doc['nodes'])
        if not targets:
            stale.append(op)
            continue
        # Record where this op landed, so the next text repair upstream can be
        # followed rather than silently breaking the op.
        stamp = fingerprint(targets[0])
        if found_id and found_id != op.get('id'):
            op['was'], op['id'], restamped = op.get('id'), found_id, True
        if stamp and op.get('at') != stamp:
            op['at'], restamped = stamp, True
        kind = op.get('op')
        for node in targets:
            if kind == 'drop':
                node['type'] = 'dropped'
            elif kind == 'set':
                node['text'] = op['text']
            elif kind == 'retype':
                node['type'] = op['to']
            elif kind == 'level':
                node['level'] = op['to']
            elif kind == 'role':
                # 'body' rescues a node the classifier wrongly consigned to the
                # cover or the back matter
                node['role'] = None if op['to'] == 'body' else op['to']
            elif kind == 'merge':
                inserts.append(('merge', node, op))
            elif kind == 'after':
                inserts.append(('after', node, op['node']))
            else:
                stale.append(op)
                break
            node['edited'] = op.get('why') or kind
        else:
            applied += 1
    # Several inserts on one anchor each went in at anchor+1, so they came out
    # in reverse, and every one carried the same id. Number them and keep the
    # order they were written in.
    seq = {}
    for kind, anchor, payload in inserts:
        if kind == 'after':
            new = dict(payload)
            seq[anchor['id']] = seq.get(anchor['id'], 0) + 1
            new.setdefault('id', '%s-ins%d' % (anchor['id'], seq[anchor['id']]))
            new.setdefault('page', anchor.get('page'))
            new['edited'] = 'inserted'
            doc['nodes'].insert(doc['nodes'].index(anchor) + seq[anchor['id']],
                                new)
            continue
        # merge: fold the named nodes into this one, in the order given, and
        # drop them — a paragraph split by a column break needs no retyping
        for other_id in payload.get('with', []):
            for other in by_id.get(other_id, []):
                joiner = '' if anchor['text'].endswith('-') else ' '
                anchor['text'] = anchor['text'].rstrip('-') + joiner + other['text']
                other['type'] = 'dropped'
    if restamped and path:
        json.dump(spec, open(path, 'w', encoding='utf-8'), indent=1,
                  ensure_ascii=False)
    return doc, applied, stale


FIG_LABEL = re.compile(r'^\s*((?:Figure|Fig|Table|Scheme|Box)\.?\s*S?\d{1,2}'
                       r'[A-Za-z]?)\s*[.:|—–-]*\s*', re.I)


def split_caption(label, text):
    """A figure's label and its caption, with the label appearing once."""
    body = text
    match = FIG_LABEL.match(body)
    if match:                              # caption carries its own label
        label = label or match.group(1)
        body = body[match.end():]
        again = FIG_LABEL.match(body)      # …and sometimes carries it twice
        if again:
            body = body[again.end():]
    elif label and body.lower().startswith(label.lower()):
        body = body[len(label):]
    label = re.sub(r'\s+', ' ', label).strip(' .:—–-')
    return label, body.strip(' .:—–-')


INTRO_NAME = re.compile(r'^(introduction|main|background|abstract|summary)\b', re.I)

# The named divisions that end a run of Results subsections. Anything else in
# that run is a finding, however it is titled.
AFTER_RESULTS = re.compile(r'^(discussion|conclusions?|materials and methods|'
                           r'methods(?: and materials)?|materials|'
                           r'experimental procedures|star\s*\+?\s*methods|'
                           r'method details|references?|acknowledge?ments?|'
                           r'outlook|limitations)\b', re.I)


def needs_intro(doc):
    """Does this document open with unlabelled prose?

    True only when at least two paragraphs precede the first heading and no
    heading names the opening section, so nothing is invented where the authors
    did label it.
    """
    paragraphs = 0
    for node in doc['nodes']:
        if node.get('role') or node['type'] in DOC_HIDDEN:
            continue
        if node['type'] == 'heading':
            return paragraphs >= 2 and not INTRO_NAME.match(node['text'])
        if node['type'] == 'prose' and len(node['text']) > 200:
            paragraphs += 1
    return False


def heading_level(node):
    if 'level' in node:
        return int(node['level'])
    text = node['text']
    if HEAD_CANON.match(text) or RESUME.match(text):
        return 2
    return 3 if HEAD_SUB.match(text) or len(text) < 60 else 2


def with_links(text, links):
    """Escape the text and splice in the spans GROBID marked as links.

    Offsets index the plain text, so escaping has to happen per segment or the
    entities would shift them.
    """
    if not links:
        return linkify(esc(text))
    out, at = [], 0
    for link in sorted(links, key=lambda l: l['a']):
        if link['a'] < at:
            continue                       # overlapping spans: keep the first
        out.append(linkify(esc(text[at:link['a']])))
        out.append('<a class="paper-cite" href="%s">%s</a>'
                   % (esc(link['href']), esc(text[link['a']:link['b']])))
        at = link['b']
    out.append(linkify(esc(text[at:])))
    return ''.join(out)


def equation_latex(slug):
    """Transcribed LaTeX for this paper's display equations, if any.

    Keyed by the plain text GROBID extracted, so a node can be matched without
    depending on node ids surviving re-extraction.
    """
    path = os.path.join(EQN_DIR, slug + '.json')
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding='utf-8'))
    return {re.sub(r'\s+', ' ', k).strip(): v for k, v in raw.items()
            if not k.startswith('_') and v.get('latex')}


LATEX_LEAK = re.compile(r'\\[a-zA-Z]+|(?<![a-zA-Z])&(?![a-zA-Z#])|aligned')


def to_mathml(latex):
    """MathML for one formula, or None if the conversion is not trustworthy.

    "It parsed" is not enough: an unsupported environment converts happily and
    leaves the alignment markers and command names sitting in the output. So the
    result is checked for leaked LaTeX after the entities are set aside.
    """
    try:
        import latex2mathml.converter
        mathml = latex2mathml.converter.convert(latex)
    except Exception:                                   # noqa: BLE001
        return None
    if LATEX_LEAK.search(re.sub(r'&#x[0-9A-Fa-f]+;', '', mathml)):
        return None
    return mathml


def render_equation(text, latex):
    """MathML where every part converts, the extracted text where it does not.

    The plain text is never discarded: it is what a reader falls back to and
    what search indexes. All-or-nothing per formula — half a rendered equation
    beside half a plain one would read as a mistake.
    """
    parts = latex if isinstance(latex, list) else ([latex] if latex else [])
    rendered = [to_mathml(p) for p in parts]
    if parts and all(rendered):
        # one line per display: several <math> in a row would otherwise sit
        # side by side and read as a single garbled expression
        lines = ''.join('<div class="paper-eqline">%s</div>' % m for m in rendered)
        return ('<div class="paper-equation paper-equation--math" '
                'data-transcribed="1" title="%s">%s</div>'
                % (esc(text[:120]), lines))
    return '<div class="paper-equation">%s</div>' % esc(text)


def render_doc(rec, doc):
    """Build the page body from extracted nodes: prose, headings, figures.

    Every rendered element carries its node id, so a later pass — human or
    agent — can point an edit at exactly the block it is looking at.
    """
    out, toc, ref_lines, ref_entries = [], [], [], []
    # Papers that label neither their introduction nor Results (Science does
    # this routinely) leave their opening paragraphs with no heading, so the
    # contents rail cannot offer the top of the article. Supply one — marked
    # data-synthetic, because it is our word and not the authors'.
    want_intro = needs_intro(doc)
    # A paper that labels no introduction labels no Results either, so its
    # findings arrive as a run of untitled-parent subsections. Give them a
    # marked parent so the rail nests them instead of listing seven peers.
    want_results, results_open, results_done = want_intro, False, False
    # Only link to anchors this page will actually contain: GROBID cites a
    # bibliography entry it never emitted (b24 here), and a dead link is worse
    # than plain text.
    # Only anchors that will actually render: a bibliography entry too short to
    # be shown takes its anchor with it, and a citation to it would dangle.
    targets = {n['anchor'] for n in doc['nodes'] if n.get('anchor')
               and (n.get('role') != 'references' or len(n['text']) >= 25)
               and (n['type'] != 'caption')}
    equations = equation_latex(doc['slug'])
    leading_run = True
    abstract_key = re.sub(r'[^a-z0-9]', '', (rec.get('abstract') or '').lower())[:90]
    title_key = re.sub(r'[^a-z0-9]', '', rec['title'].lower())[:45]
    seen = set()

    for node in doc['nodes']:
        kind, text = node['type'], node['text']
        if kind == 'dropped':
            continue                       # must precede the references branch,
                                           # or a drop on an entry does nothing
        if node.get('role') == 'references':
            # GROBID and bioRxiv hand over one parsed entry per node; only the
            # PDF path needs the line-level splitting heuristics
            if node.get('entry') or doc.get('source') in ('grobid', 'biorxiv'):
                ref_entries.append((node.get('anchor'), text,
                                    node.get('number')))
            else:
                ref_lines.extend(node.get('lines') or [text])
            continue
        if node.get('role') in ('back', 'front') or kind in DOC_HIDDEN \
                or kind == 'dropped':
            continue
        nid = ' data-node="%s"' % esc(node['id'])

        if kind == 'figure':
            # Sources disagree about whether the caption repeats its own label:
            # GROBID gives label "Fig. 1 ." and a caption that also opens
            # "Fig. 1. Building a cell…", which rendered the number twice.
            # Take the label from whichever carries it and strip it once.
            label, caption = split_caption(node.get('label') or '', text)
            anchor = (' id="%s"' % esc(node['anchor'])) if node.get('anchor') else ''
            out.append('<figure class="paper-fig"%s%s>' % (anchor, nid))
            out.append('  <img loading="lazy" src="../../%s" alt="%s">'
                       % (esc(node['image']), esc(label or 'Figure')))
            out.append('  <figcaption><b>%s</b> %s</figcaption>'
                       % (esc(label), linkify(esc(caption))))
            out.append('</figure>')
        elif kind == 'equation':
            entry = equations.get(re.sub(r'\s+', ' ', text).strip())
            html_eq = render_equation(text, (entry or {}).get('latex'))
            out.append(html_eq.replace('<div class="paper-equation',
                                       '<div%s class="paper-equation' % nid, 1))
        elif kind == 'caption':
            # the artwork could not be located, but the caption still carries
            # what the figure showed
            out.append('<p class="paper-orphan-caption"%s>%s</p>'
                       % (nid, linkify(esc(text))))
        elif kind == 'heading':
            key = re.sub(r'[^a-z0-9]', '', text.lower())
            # The running title reappears as a heading on every page opening,
            # sometimes behind a section label ("SYNTHETIC BIOLOGY Toward life
            # with…"), so look for it anywhere in the heading rather than only
            # at the start. A repeated heading also clutters the contents rail.
            if title_key and title_key[:30] in key:
                continue
            if key in seen:
                continue
            seen.add(key)
            level = heading_level(node)
            if want_results and not results_done:
                if AFTER_RESULTS.match(text):
                    results_open, results_done = False, True
                elif not results_open and any(e.startswith('<h') for e in out):
                    hid = 'sec-0-results'
                    toc.append({'level': 2, 'id': hid, 'text': 'Results'})
                    out.append('<h2 id="%s" data-synthetic="1">Results</h2>'
                               % esc(hid))
                    results_open = True
            if results_open:
                level = 3                  # a finding under the new parent
                leading_run = False
            # Subsections with no section above them have nothing to fold into,
            # and the rail then opens and closes them at random. Science papers
            # often label neither the introduction nor Results, so the whole
            # leading run is promoted — they are siblings, not children of
            # whichever one happened to come first.
            if level > 2 and leading_run:
                level = 2
            elif level <= 2:
                leading_run = False
            hid = 'sec-%d-%s' % (len(toc) + 1,
                                 re.sub(r'[^a-z0-9]+', '-', text.lower())[:40].strip('-'))
            toc.append({'level': level, 'id': hid, 'text': text})
            out.append('<h%d id="%s"%s>%s</h%d>' % (level, esc(hid), nid,
                                                    esc(text), level))
        elif kind == 'prose':
            key = re.sub(r'[^a-z0-9]', '', text.lower())
            # A 60-character floor silently swallowed misclassified headings and
            # genuinely short paragraphs alike. Keep anything with the shape of
            # a sentence; the audit flags what looks wrong instead of hiding it.
            if key in seen or len(text.split()) < 4 or not re.search(r'[a-z]{3}', text):
                continue
            if abstract_key and key[:90] == abstract_key:
                continue            # the abstract box above already shows it
            # The title inside a paragraph means the cover block, or the
            # publisher's "cite this article as" panel — never body prose.
            if title_key and (key.startswith(title_key) or title_key[:40] in key):
                continue
            if is_affiliations(text) and not any(e.startswith('<h') for e in out):
                continue
            if want_intro and not any(e.startswith('<h') for e in out):
                hid = 'sec-0-introduction'
                toc.append({'level': 2, 'id': hid, 'text': 'Introduction'})
                out.append('<h2 id="%s" data-synthetic="1">Introduction</h2>'
                           % esc(hid))
            seen.add(key)
            out.append('<p%s>%s</p>'
                       % (nid, with_links(text, [
                           l for l in (node.get('links') or [])
                           if l['href'].lstrip('#') in targets])))

    out, toc = drop_empty_sections(out, toc)
    refs = (render_entries(ref_entries) if ref_entries
            else render_text_refs(ref_lines))
    return ('\n'.join(out) if out else None), toc, refs


# ---------- page assembly ----------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_short} — solab</title>
  <meta name="description" content="{summary}">
  <link rel="stylesheet" href="../../assets/css/style.css">
  <link rel="stylesheet" href="../../assets/css/paper.css">
  <link rel="icon" type="image/svg+xml" href="../../assets/favicon.svg">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="solab — Ovchinnikov Lab">
  <meta property="og:title" content="{title_short} — solab">
  <meta property="og:description" content="{summary}">
</head>
<body>
  <header class="site-header">
    <nav class="nav">
      <a class="brand" href="../../">solab</a>
      <button class="nav-toggle" aria-label="Toggle navigation" onclick="document.getElementById('navlinks').classList.toggle('open')">&#9776;</button>
      <ul class="nav-links" id="navlinks">
        <li><a href="../../">Home</a></li>
        <li><a href="../../lab/">Lab</a></li>
        <li><a href="../../research/">Research</a></li>
        <li><a href="../../publications/" class="active">Publications</a></li>
        <li><a href="../../tools/">Tools</a></li>
        <li><a href="../../resources/">Resources</a></li>
        <li><a href="../../contact/">Contact</a></li>
      </ul>
    </nav>
  </header>

  <main>
    <div class="paper-layout{layout_class}">
{toc}
    <article class="paper">
      <p class="paper-eyebrow"><a href="../../publications/#{theme}">{theme_name}</a></p>
      <h1 class="paper-title">{title}</h1>
      <p class="paper-authors">{authors}</p>
      <p class="paper-meta">{venue}</p>
      <p class="paper-links">{links}</p>
{abstract}
      <div class="paper-body{body_class}">
{body}
      </div>
{related}
    </article>
    </div>
  </main>

  <footer class="site-footer">
    <div class="footer-inner">
      <span><a href="https://web.mit.edu/">Massachusetts Institute of Technology</a></span>
      <span><a href="https://biology.mit.edu/">MIT Biology</a></span>
    </div>
  </footer>
  <script defer src="../../assets/js/msa.js"></script>
  <script defer src="../../assets/js/paper.js"></script>
</body>
</html>
"""


def related_block(rec, by_id, slugs):
    """Papers of the lab's own that this one cites."""
    refs = [by_id[r] for r in rec.get('referenced_works', []) if r in by_id]
    if not refs:
        return ''
    items = []
    for r in sorted(refs, key=lambda x: -int(x.get('year') or 0)):
        items.append('        <li><a href="../%s/">%s</a> <span class="yr">%s</span></li>'
                     % (esc(slugs[r['openalex']]), esc(r['title']), esc(str(r.get('year') or ''))))
    return ('      <nav class="paper-related">\n'
            '        <h2>Earlier work from the lab cited here</h2>\n'
            '        <ul>\n%s\n        </ul>\n      </nav>' % '\n'.join(items))


def build(rec, members, by_id, slugs):
    name = slugs[rec.get('openalex') or rec['title']]
    refs_html, toc = '', []
    body, kind, notes = None, None, ''
    if rec.get('jats'):
        rendered = render_jats(rec, name)
        if rendered:
            body, refs_html, toc = rendered
            kind = 'jats'
    # A paper with JATS renders from it, so an overlay written against its
    # extracted doc would never reach the page. Say so rather than let the work
    # disappear: 13 papers have both.
    if kind == 'jats' and rec.get('text_file'):
        stray = os.path.join(EDIT_DIR, os.path.basename(rec['text_file'])[:-4] + '.json')
        if os.path.exists(stray):
            notes = ' (edits IGNORED — page comes from JATS)'
    if not body and rec.get('text_file'):
        # the layout-aware document, with its edit overlay, is preferred: it
        # has figures and knows what was artwork. Plain text is the fallback
        # for papers that have not been extracted yet.
        doc = load_doc(os.path.basename(rec['text_file'])[:-4])
        if doc:
            doc, applied, stale = apply_edits(doc, doc['slug'])
            body, toc, refs_html = render_doc(rec, doc)
            kind = 'doc'
            # Entries wrap mid-line, so the line-level view of the same PDF
            # splits a bibliography more reliably than blocks do. Take whichever
            # recovers more of the list.
            from_text = render_text(rec)[2]
            # count the tag, not "<li>": parsed entries carry an id attribute,
            # so matching the literal string scored them zero and the
            # line-derived list won even when it was worse
            if from_text.count('<li') > refs_html.count('<li'):
                refs_html = from_text
                if 'id="ref-' not in refs_html:
                    # that list has no per-entry ids, so citation links would
                    # dangle: render them as plain text instead
                    body = re.sub(r'<a class="paper-cite" href="#ref-[^"]*">'
                                  r'(.*?)</a>', r'\1', body)
            if applied or stale:
                notes = ' (%d edits%s)' % (applied,
                                           ', %d STALE' % len(stale) if stale else '')
    if not body:
        body, toc, refs_html = render_text(rec)
        kind = 'text'
    if not body:
        return None, 'no text'
    body_class = '' if kind == 'jats' else ' paper-body--plain'

    jats = rec.get('jats') or {}
    abstract = jats.get('abstract') or rec.get('abstract') or ''
    abstract_html = ('      <section class="paper-abstract"><h2>Abstract</h2><p>%s</p></section>'
                     % linkify(esc(abstract))) if abstract else ''

    links = []
    if rec.get('doi'):
        links.append('<a class="pill" href="https://doi.org/%s">DOI</a>' % esc(rec['doi']))
    if rec.get('url'):
        links.append('<a class="pill" href="%s">Publisher</a>' % esc(rec['url']))
    if rec.get('pmcid'):
        links.append('<a class="pill" href="https://europepmc.org/article/PMC/%s">Europe PMC</a>'
                     % esc(rec['pmcid']))

    # a contents rail only earns its keep on a paper with real structure
    toc_html = ''
    if len(toc) >= 4:
        entries, parent = [], ''
        for t in toc:
            if t['level'] <= 2:
                parent = t['id']
                attr = ' data-section="%s"' % esc(parent)
            else:
                attr = ' data-parent="%s"' % esc(parent)
            entries.append('          <li class="lvl%d"%s><a href="#%s">%s</a></li>'
                           % (t['level'], attr, esc(t['id']), esc(t['text'])))
        if refs_html:
            entries.append('          <li class="lvl2"><a href="#references">References</a></li>')
        toc_html = ('      <nav class="paper-toc" aria-label="Contents">\n'
                    '        <p class="paper-toc-head">Contents</p>\n'
                    '        <ul>\n%s\n        </ul>\n      </nav>' % '\n'.join(entries))

    venue = re.sub(r'\s+', ' ', rec.get('venue') or '').strip()
    page = PAGE.format(
        title=esc(rec['title']),
        title_short=esc(rec['title'][:60]),
        summary=esc((abstract or rec['title'])[:180]),
        theme=esc(rec.get('theme') or ''),
        theme_name=esc(rec.get('theme_name') or 'Publications'),
        authors=link_authors(rec.get('authors_short'), members),
        venue=esc('%s · %s' % (rec.get('year') or '', venue) if venue else str(rec.get('year') or '')),
        links=' '.join(links),
        abstract=abstract_html,
        body=body,
        body_class=body_class,
        toc=toc_html,
        layout_class=' paper--with-toc' if toc_html else '',
        related=refs_html + '\n' + related_block(rec, by_id, slugs),
    )
    out_dir = os.path.join(OUT_ROOT, name)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(page)
    return os.path.join('papers', name, 'index.html'), kind + notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pubs', default=os.path.join(CACHE, 'pubs_jats.json'))
    ap.add_argument('--only', help='build just the papers matching this substring')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    with open(args.pubs) as fh:
        pubs = json.load(fh)
    # the text-only fields live in the other file
    text_by_title = {r['title']: r for r in json.load(open(os.path.join(CACHE, 'pubs_text.json')))}
    for r in pubs:
        t = text_by_title.get(r['title'], {})
        r.setdefault('text_file', t.get('text_file'))
        r.setdefault('text_words', t.get('text_words'))

    members = lab_members()
    slugs = {(r.get('openalex') or r['title']): slug(r) for r in pubs}
    by_id = {r['openalex']: r for r in pubs if r.get('openalex')}

    todo = pubs
    if args.only:
        todo = [r for r in pubs if args.only.lower() in r['title'].lower()]
    if args.limit:
        todo = todo[:args.limit]

    built = {'jats': 0, 'doc': 0, 'text': 0}
    for rec in todo:
        path, kind = build(rec, members, by_id, slugs)
        if not path:
            print('  --   %-5s %s' % (kind, rec['title'][:56]), file=sys.stderr)
            continue
        built[kind.split()[0]] += 1
        print('  ok   %-22s %s' % (kind, path), file=sys.stderr)

    print('\nbuilt %d pages (%d from JATS, %d from extracted PDFs, %d plain text)'
          % (sum(built.values()), built['jats'], built['doc'], built['text']),
          file=sys.stderr)


if __name__ == '__main__':
    main()
