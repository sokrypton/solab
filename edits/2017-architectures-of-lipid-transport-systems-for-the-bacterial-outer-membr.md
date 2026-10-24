# 2017-architectures-of-lipid-transport-systems-for-the-bacterial-outer-membr

## 2026-07-27 — rewritten for the GROBID pass

The page is now built from GROBID (`.cache/doc/…`, node ids `g*`); figures come
from GROBID's own crops (`gb-01..07.jpg`). All 22 ops that were still live from
the earlier PDF pass (`p*` ids) are now in `retired` — none of them matched.
44 new ops, 0 stale. The older changelog is kept at the bottom: most of the
defects it describes (duplicated bibliography, key-resources table dump, outline
page read as headings) are gone, because GROBID does not emit any of it.

### Fixed with an op — main text

- `g8-92d8f7` / `g9-6fa855` — the Results heading "Mutations in MCE Operons
  Result in OM Defects" is emitted as a heading *and* repeated as the first
  words of the paragraph under it. Stripped from the paragraph.
- `g20-e5b9ef` / `g76-2440d7` — Figure 3's entire panel legend, "(A)
  Co-expression of MlaFEDCB…" through "(H) Hybrid model…", was appended to the
  body paragraph "We next sought to determine the architecture of the MlaFEDB
  complex…", while the figure's own caption stopped at its title. Moved the
  legend out of the paragraph and into the caption.
- `g22-f41141` / `g23-1b3324` — "MlaC Binds Lipid Tails" is a Results
  subsection heading (a separate `heading` node, `p7-1b3324`, in `doc_ours`)
  left inline as the first four words of the paragraph. Heading restored,
  prefix stripped.
- `g31-a9aaec` / `g32-53ffb5` — paragraph split across a column break at
  "…likely lipids or other hy-" + "drophobic molecules) across the intervening,
  aqueous periplasm.", with a stray cross-reference fragment " S4 ." dropped in
  between. Fragment removed, halves merged. (The audit's `fragment` flag.)

### Fixed with an op — STAR Methods

- `g45-54359b` carried `role: back`, and the builder skips `role in
  ('back','front')`, so the page jumped from the end of the Discussion straight
  into an unheaded "TEM of E. coli outer membrane". `role → body` restores
  STAR+METHODS as an h2 and gives the methods subsections a parent in the rail.
- `g48-292b1c`, `g49-a7ebce`, `g50-d7eda2` had the same `role: back` and were
  **not rendered at all** — the lipid-extraction and TLC methods were simply
  absent from the page. Rescued. (`g46-5e4153`, the "Detailed methods are
  provided in the online version" lead, and `g47-9f320d`, the printed outline
  with the whole key-resources table run into it, are correctly suppressed by
  that same role and were left alone.)
- Nine subsection headings were inlined into the paragraph below them; each got
  a heading inserted and the prefix stripped: Ethidium bromide uptake assays;
  Expression and purification of MlaD; Crystallization and structure
  determination of MlaD; Model building and refinement for PqiB; Identification
  of inter-subunit restraints in MlaFEDB complex using co-evolving residue
  pairs; Expression and purification of MlaC; Crystallization and structure
  determination of MlaC; Expression and purification of MlaA-OmpF complex;
  Protein-protein interactions by biolayer interferometry. All are separate
  `heading` nodes in `doc_ours` and all but one appear verbatim in the paper's
  own printed methods outline (inside `g47-9f320d`).
- Three STAR section headers exist in *neither* extraction and were inserted as
  h3: EXPERIMENTAL MODEL AND SUBJECT DETAILS, QUANTIFICATION AND STATISTICAL
  ANALYSIS, DATA AND SOFTWARE AVAILABILITY. Without the last two, the ANOVA
  paragraph reads as part of the biolayer-interferometry protocol and the
  accession-number list reads as a stray table dump.
- Content GROBID lost outright, restored from `doc_ours`:
  - `g56-039cfa` broke off mid-list at "(Leu42Met, Leu52Met, Leu73Met," and was
    then glued directly to the *YebT* purification paragraph from a page later.
    Completed with `p18-039cfa` + `p19-8b5148` (Met scan, MAD phasing).
  - Inserted after it: the complete-MlaD-periplasmic-domain crystallization
    paragraph (`p19-ba4b67`); "Purification of the MlaFEDB complex" +
    `p19-cc8d72`; "Expression and purification of PqiB" + `p19-70bf19`;
    "Expression and purification of YebT" + `p20-942eb5`. A full printed page of
    METHOD DETAILS that was missing from the page entirely.
  - `p17-74e421` (model organism, strains, complementation) and `p17-304525`
    (first paragraph of the lipid binding assay: cloning, expression, IMAC).
- `g81-15ae7f` — dropped. Tail of the Figure S1 legend from a supplemental
  page; it rendered as an orphan caption after the accession numbers,
  describing panels (H)-(J) of artwork this page deliberately does not show.

### Figures

All seven rendered figures were opened and checked against their captions.
`gb-01.jpg` … `gb-07.jpg` are complete: correct artwork, no clipped panels, no
transparency mask or background layer, multi-panel figures (2, 3, 6) include
every panel through H/I. No figure ops needed. No display equations.

### Flags rejected

- `table-dump g73-6e3706` — the real DATA AND SOFTWARE AVAILABILITY paragraph
  (PDB/EMDB accessions). It only looked like a dump because its section header
  was missing; the node itself is correct.
- (`fragment g32-53ffb5` and `orphan-caption g81-15ae7f` were both genuine and
  are fixed. The audit still reports them because it reads `doc/` directly,
  not the overlay.)

### Deliberately left alone

- `g58-c363e9` and `g60-330cd6` still open "Negative stain EM data …" and bury
  further run-in labels ("Cryo EM of MlaFEDB", "Cryo EM of PqiB", "Cryo EM
  processing of PqiB") mid-paragraph. One level below the headings fixed above,
  and `doc_ours` also merges these into the parent heading ("Electron
  microscopy data collection Negative stain EM data"), so there is no reliable
  text to split on. They read as run-in labels and mislead nobody.
- `g63-066ec2` lost a leading run-in label "Needle" (`doc_ours` has "Needle .
  While the positions…"). One word; not worth an op.
- The key-resources table renders nowhere. It is a ~40-row three-column table
  flattened into `g47-9f320d` together with the methods outline. Nothing an
  overlay can rebuild.
- "CONTACT FOR REAGENT AND RESOURCE SHARING" (lead-contact email) is missing
  from GROBID. Left out: administrative, not scientific.
- Glyph damage is left throughout: `~` renders as `$` ("a $10 A ˚resolution
  map"), `Å` as `A ˚`, Greek romanised (`b5-b6`, `a-helical`, `DmlaE`,
  `$230 A ˚long`). Dozens of occurrences; a per-node `set` for each is the
  wrong tool. See below.

### Needs the extractor changed

1. **`role: back` swallows STAR Methods.** The back-matter classifier in the
   GROBID ingest tagged `STAR+METHODS` and the four nodes after it `back`, and
   `build_papers.py` skips `back` outright, so a section heading and three real
   methods paragraphs never reached the page. The trigger is almost certainly
   the literal "STAR+METHODS" or the "Detailed methods are provided in the
   online version" boilerplate. Every Cell Press paper in the corpus hits this.
   Suspect `scripts/ingest_tei.py`.
2. **Run-in headings (highest volume).** GROBID inlines bold run-in subsection
   titles into the following paragraph. Nine in this paper, all in STAR
   Methods. `doc_ours` has every one of them as a separate `heading` node — so
   this is fixable mechanically by matching the head of a GROBID paragraph
   against the heading texts of the layout pass, with no per-paper judgement.
3. **Cell's STAR section headers are lost by both passes.** `doc_ours` types
   METHOD DETAILS / EXPERIMENTAL MODEL AND SUBJECT DETAILS / QUANTIFICATION AND
   STATISTICAL ANALYSIS / DATA AND SOFTWARE AVAILABILITY as `figure-text` —
   they are reversed out of a coloured band, so they look like text inside
   artwork — and GROBID emits them not at all. The `figure-text` test in
   `extract_pdf.py` should not consign a short all-caps line matching a known
   STAR section name to figure interior.
4. **GROBID drops text at page turns, silently and mid-sentence.** A full
   printed page of METHOD DETAILS (`p19-8b5148`, `p19-ba4b67`,
   `p19-0875f1`+`p19-cc8d72`, `p19-600d58`+`p19-70bf19`) never reaches `doc/`,
   and `g56-039cfa` was spliced to a paragraph two pages later in the middle of
   a list. `doc_ours` has all of it. Comparing character count per printed page
   between the two passes would flag this without a human reading the paper.
5. **Figure panel legends leak into body prose.** Figure 3's whole "(A)…(H)"
   legend landed on `g20-e5b9ef` while `g76-2440d7`'s caption stopped at its
   title. Detectable pattern: a figure caption with a title but no "(A)" while
   the adjacent paragraph *ends* in a run of "(X) …" sentences.
6. **Heading repeated as the first words of its own paragraph** (`g8`/`g9`).
   Trivial to detect and strip in the builder.
7. **Inserted nodes get colliding ids.** `after` names new nodes
   `<anchor>-ins`, so seven inserts on one anchor produce seven elements with
   the same `data-node`, and `apply_edits` builds `by_id` before running the
   inserts — a later op aimed at one would silently hit all of them. Suggest
   `-ins1`, `-ins2`, … in `build_papers.py`.
8. **`after` inserts land in reverse order.** Multiple `after` ops on the same
   anchor each insert at `index(anchor)+1`, so reading order is the reverse of
   op order. The `g56-039cfa` and `g47-9f320d` groups in this overlay are
   deliberately written backwards to compensate. Either apply same-anchor
   inserts in op order, or let `after` accept a list of nodes.
9. **Glyph mapping.** GROBID renders `~`→`$`, `Å`→`A ˚`, and romanises Greek
   (`b5-b6`, `DmlaE`) throughout Cell PDFs. A post-processing table in the
   ingest, not an overlay.

---

## Earlier record — written against the PDF (`p*`) extraction, now retired

Cell, `.cache/pdf/2017-architectures-…pdf`, 31 pages: graphical-abstract cover,
body, references, STAR Methods with a three-page key-resources table, then seven
supplemental figures. 111 ops, all of them in four families.

### Duplicated bibliography in the body (40 drops)

The largest defect. `mark_back_matter` in `extract_pdf.py` walks the reference
list with `state = 'refs'` and clears that state on the first block that fails
`looks_like_refs`/`looks_like_entry`. On p13 the entry `Gioffre´ , A., Infante,
E., …` fails `ENTRY_OPEN` — the combining acute plus the space before the comma
breaks `^[A-Z][\w’'-]{1,24},` — and **every one of the 48 entries after it loses
`role: references`**. They then render as body paragraphs sitting between
DISCUSSION and STAR + METHODS. Dropped the 40 of them that were long enough to
render (`p13-4d5c46` … `p14-042bd2`); they are duplicates, because the page's
References section is built from the line-level path (`render_text_refs`), which
recovers all 64 entries correctly.

**Needs the extractor changed, not an overlay.** One malformed entry should not
end the bibliography: `state` should survive a non-matching block (or only be
cleared by a heading/figure, as it already is). Expect this on any paper whose
reference list contains an accented surname; it will recur.

### Key-resources table dump (43 drops)

`p15-e552c2` is the table's column header (`REAGENT or RESOURCE SOURCE
IDENTIFIER`) read as a section heading, and 42 table rows render as one-line
paragraphs with their three columns run together (`Expression construct for
MlaD(32-140), Leu99Met mutant This work pBE1173`). Worse, the builder's 60-char
prose floor admits only the longer rows, so the reader was shown a random ~40%
of the table. Dropped the header and all 42 rendered rows; the `KEY RESOURCES
TABLE` heading itself is already `apparatus-head`/back and never rendered.
A real fix would need table-aware extraction — worth considering, since STAR
Methods papers all carry one of these.

### STAR Methods outline page (8 drops)

p12 prints the outline of the online methods: a `STAR + METHODS` heading, the
lead-in "Detailed methods are provided in the online version of this paper and
include the following:", six `d …` bullets and a set of `B …` sub-bullets. The
bullets came through as headings (`p12-f8a2ba`, `-1b4a39`, `-9bb534`, `-bacb34`,
`-c77343`, `-d51036`) with the bullet glyph attached. Dropped all six plus the
lead-in. Also dropped the p12 `STAR + METHODS` heading (`p12-aa2891`): the
builder's heading dedupe kept the first copy and suppressed `p15-aa2891`, which
is the one that actually opens the methods, so the outline page was holding the
section title hostage.

### Structure and split paragraphs

- Two run-in headings were absorbed into the paragraph below them. Inserted
  `Architecture of the MlaFEDB Transporter Complex` (after `p5-e61f75`) and
  `TEM of E. coli outer membrane` (after `p18-106ed8`), and `set` the two
  paragraphs to start at their real first word. Both are named sections in the
  paper's own outline.
- `p21-51a8cd` is a heading cut after its first word: the extractor kept
  `18-stranded` and gave the rest of the title, `b -barrel lining interior of
  PqiB barrel .`, to the following paragraph. Repaired both halves with `set`.
- Five paragraphs were split mid-sentence by a column or page turn — the
  continuation opened with `and 3.0 A ˚ with E. coli MlaC…`, `to MlaC, as well
  as…`, `long, in good agreement…`, `Met141, Leu143…`, `MlaD and the dimeric
  permease assemblies…`. Rejoined each into the preceding node with `set` and
  dropped the orphan half: `p4-0f0970`+`p5-e8595e`, `p6-c0ab0d`+`p7-5c52e4`,
  `p7-063a9f`+`p7-b8fec1`, `p8-18dca3`+`p8-1bda40`, `p10-a16788`+`p10-5f7eb4`.
- `p25-8eeb81` is the tail of the Figure S1 legend (the page before ends with
  "(legend continued on next page)"), starting at panel `(H)`. Retyped to
  `caption` so it reads as a legend rather than body prose. It cannot be folded
  into the figure it belongs to — that would need the extractor to join a
  caption across a page break.
- Three heading levels forced: `p8-b486d8` and `p21-1f52f5` are subsections that
  came out as level 2 purely because their titles exceed the 60-character rule
  in `heading_level`; `p24-e0ae32` ("Supplemental Figures") was nested under
  QUANTIFICATION AND STATISTICAL ANALYSIS and is now level 2.

### Left alone deliberately

- The cover page (graphical abstract, Highlights bullets, In Brief, authors,
  self-citation) is correctly marked `role: front` and never rendered. No op
  needed — `mark_front_matter` handles Cell's issue-front page well.
- `audit_papers.py` flags 42 "fragment" nodes; most are key-resources rows
  (dropped above), but `p6-1a0fdc` and `p7-5c52e4` are flagged for shortness
  alone. `p6-1a0fdc` ("We next sought to determine the architecture of the
  MlaFEDB complex by single-particle cryoelectron microscopy (cryo-EM).") is a
  genuine one-sentence paragraph — left as is.
- `p23-464e0f`, flagged `table-dump`, is the DATA AND SOFTWARE AVAILABILITY
  paragraph listing PDB/EMDB accessions. It is prose and it is real content —
  the flag is wrong. Left as is.
- `p21-90ea4f` opens `Needle . While the positions…` — another bold run-in
  label, like the `18-stranded` one, but here the label never became a heading
  and the paragraph still reads. Left as is rather than inventing a heading at a
  level (2 or 3) that would misrepresent its depth.
- All 14 figure crops are correct and every caption matched its artwork.

### 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 22 still change the page and were kept; 70 now target nodes the classifier already hides, and 19 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 41 still change the page and were kept; 0 now target nodes the classifier already hides, and 3 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 39 still change the page and were kept; 0 now target nodes the classifier already hides, and 2 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 35 still change the page and were kept; 4 now target nodes the classifier already hides, and 0 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.

## 2026-07-27 — one op added, most of the rest made redundant

The extractor learned two things this paper needed. Prose GROBID dropped is now
taken back from our own layout pass, and paragraphs it split at a column break
are rejoined — which is why four hand-typed Methods paragraphs and two run-in
headings could be retired: the page now gets them without help.

One op was added. `g32-53ffb5` is a stray duplicate: GROBID emitted the clause
"…hydrophobic molecules) across the intervening, aqueous periplasm." twice, once
inside the paragraph where it belongs and again as a loose fragment with the
first two letters gone. Only two other nodes in the whole corpus look like this,
and one of those is real prose, so it is not worth a rule — it is dropped here
by hand.
