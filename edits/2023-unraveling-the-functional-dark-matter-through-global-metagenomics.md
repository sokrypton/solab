# 2023-unraveling-the-functional-dark-matter-through-global-metagenomics

## Read this first: the overlay is currently inert

`build_papers.py` prefers JATS over the extracted document
(`build()` tries `render_jats` first and only falls back to `load_doc` when
JATS produced no body). This paper has JATS, so `--only "functional dark
matter"` prints `ok jats`, **not** `doc (56 edits)` — the overlay is never
applied to the page a reader sees. The 56 ops below were verified by calling
`apply_edits` + `render_doc` directly: 56 applied, 0 stale. They are correct
and will take effect the moment this paper loses JATS or the precedence
changes; they are also the record of what the extractor got wrong.

The JATS page itself is clean (Abstract, Main, the six named sections,
Discussion, Methods with six subsections, References). The only thing it
loses relative to the PDF is the second half of Methods — "Protein fold
prediction", "Data availability", "Code availability" are absent — which is
a JATS-coverage matter, not an extraction one.

## What was wrong in the extracted document, and what the ops do

- **Cover furniture read as headings and body text (9 drops).** The title
  came out as `Article Unraveling the functional dark matter…`; the leading
  "Article" label defeats `render_doc`'s running-title filter (it compares
  with `startswith(title_key[:30])`), so the title was re-emitted as an `h2`
  and as the first contents entry. The DOI, the received / accepted /
  published-online dates, "Open access" and "Check for updates" each became
  their own heading. The byline split into a heading (`p1-461e90`, the first
  author) and a paragraph starting with the corresponding-author envelope
  glyph (`p1-440601`).

- **A paragraph broken across the Fig. 1 caption, with caption text spliced
  in (1 set).** `p2-0fddd6` ended "…we first discarded **visualization and
  comparison of cluster components per cluster for the number of sequences
  (c) and the number of genome or ED samples (d).**" — that tail is the end
  of the Fig. 1 caption. The real continuation was extracted separately as
  `p2-5369af`, which carries `role=front` and is therefore never rendered, so
  the sentence had no ending at all on the page. Set `p2-0fddd6` to the
  correct joined text (checked against the JATS full text).

- **Table 1 came out as fourteen one-line headings (2 sets, 2 retypes,
  12 drops).** One heading per cell row, with the row-group labels
  ("Environmental dataset", "Reference genomes"), the "Cluster size" column
  header and the numbers all separated — and two indistinguishable
  "Proteins …" rows. Not dropped: these numbers appear nowhere else on the
  page. Instead the environmental-dataset half is collapsed into
  `p3-d8536f` and the reference-genome half into `p3-a3e472`, each as one
  labelled prose block that keeps the column meaning; the twelve rows they
  absorb are dropped. The real caption (`p3-fd9fcf`) was already typed
  `caption` and is left alone.

- **Figure caption second halves read as body prose (6 retypes).**
  `p4-13e2ac` (Fig. 2 b,c), `p14-584e07`, `p19-672690`, `p20-d72974`,
  `p21-08b39c`, `p22-e3f474` (Extended Data Figs. 1, 6, 7, 8, 9) each begin
  mid-caption and were rendered as paragraphs of running text. Retyped to
  `caption`.

- **A Discussion sentence cut at a column break (1 set + 1 drop).**
  `p7-3dd7c1` ends "…we observed that the majority of" and `p7-e9c60a`
  starts "NMPFs (60%) comprised…". Rejoined into `p7-3dd7c1`; also closed up
  the line-break hyphen in "avail - able".

- **Licence, consortium and affiliation dumps on pp. 8–9 (22 drops).**
  Publisher's note, the "Open Access" label (as a heading) and the Creative
  Commons text; the Novel Metagenome Protein Families Consortium byline plus
  two member names lifted into headings and two long member lists as
  paragraphs; and fourteen blocks of numbered author affiliations. The
  builder's `is_affiliations` guard only fires *before the first heading*, so
  affiliation blocks printed at the back of the article are always rendered.

## Deliberately left alone

- `p3-fd9fcf` (flagged `orphan-caption`) is a genuine table caption. Correct
  as extracted.
- `p1-be66e0` is the abstract; `render_doc` already suppresses it when it
  matches the abstract box, and it is real content either way.
- Run-in headings that were not lifted out of their paragraph —
  `p12-d8d3ec` "Reporting summary …", `p13-cb1e13` "Competing interests …",
  and the Methods subsection labels (`p10-bb1d24` "Data collection and
  filtering …", `p10-e3b85a`, `p10-56a237`, `p10-3fc0aa`, `p11-60dbc2`,
  `p11-7fd8b8`, `p11-eeb9ab`). Each would need an `after`-inserted heading
  *plus* a `set` to strip the label from the paragraph — nine paired ops to
  paper over one extractor rule. Left for the extractor (see below).
- `p13-3ef9d0` "Additional information Supplementary information" — two
  labels merged into one heading. Cosmetic; not confident which half Nature
  intends as the section.
- The mid-paragraph hyphenation left by the two-column layout
  ("metagen- omes", "corre- sponding", "predic- tions", "sup - ported") is
  everywhere in this document. It is a systematic extractor issue, not
  something to fix paragraph by paragraph.
- Acknowledgements / Author contributions on pp. 12–13 are real content and
  read fine.
- All of the `fragment` flags on pp. 23–30 — see below, they are one problem,
  not fifty.

## Needs `extract_pdf.py` changed, not an overlay

1. **The Nature Portfolio Reporting Summary is extracted as body text.**
   Pages 23–30 of this PDF are the blank Reporting Summary form. 200 nodes
   survive the type/role filters, 81 of them as headings, so the contents
   rail fills up with "ChIP-seq", "Flow Cytometry", "MRI-based neuroimaging",
   "Dual use research of concern", "n/a Involved in the study",
   "Any other potentially harmful combination of experiments and agents" …
   and the body gains ~120 paragraphs of empty form prompts ("Describe the
   gating strategy used for all relevant experiments…"). This is
   unfixable by overlay: it would take ~200 `drop` ops for one paper, and
   *every* Nature/Nature-family PDF carries this appendix. It is reliably
   detectable — the first page carries "nature portfolio | reporting summary"
   with "Corresponding author(s):" and "Last updated by author(s):" — and
   everything from there to the end of the document should be dropped
   (`role=back` at minimum, `furniture` ideally). This is the single highest
   value change here. Note the extractor already gets *part* of it right:
   `p23-b23d84` "Reporting Summary" is typed `apparatus-head` with
   `role=back`, so the detection is half built; the role just is not
   propagated to the following 200 nodes.

2. **`role=front` leaks past the cover and eats real content.** On pages 1–2
   the following carry `role=front` and are therefore never rendered:
   `p1-4f1cba` (the "two major approaches" paragraph), `p2-d50c6a`
   ("Here we present a scalable computational approach…"), `p2-5369af`
   (the end of the first Results paragraph), the Fig. 1 figure node
   `p2-00671a`, **and both of the first two section headings** —
   `p2-c01be7` "The novel protein sequence space" and `p2-f82e5b`
   "Novel protein families". The doc-rendered page therefore silently loses
   two sections' worth of structure and three paragraphs. No op can fix this:
   there is no op that changes a node's `role`. Either the front-matter
   region needs to stop at the first section heading, or `role` needs to be
   overridable from `edits/*.json`.

3. **Duplicate node ids make some nodes unaddressable.** 33 ids in this
   document appear twice (mostly `figure-text`, but `p3-1aeee9`, the
   "Cluster size ≥3 members…" column header of Table 1, is one of them).
   `apply_edits` builds `by_id = {n['id']: n for n in doc['nodes']}`, so only
   the *last* node with a given id can be targeted, while `render_doc`
   iterates in document order and renders the *first*. The result: the drop
   of `p3-1aeee9` lands on the wrong copy and the heading survives on the
   page. Fix either end — apply an op to every node matching the id, or make
   ids unique (append an occurrence index).

4. **Two-column paragraph flow.** Paragraphs that cross a column break or a
   figure are emitted as two nodes (`p2-0fddd6`/`p2-5369af`,
   `p3-9a6ecd`, `p3-e93987`, `p5-8dc0b2`, `p6-6a65af`, `p7-3dd7c1`/
   `p7-e9c60a`), and in the `p2` case a figure caption's tail was spliced
   into the body paragraph. Three of the six `fragment` flags on the main
   article are this. Worth a merge pass in the extractor; there is also no
   `merge` op, which is why fixing each one costs a `set` plus a `drop`.

5. **Nature's run-in Methods headings are never lifted.** The extractor sets
   `run_in: true` for `p8-6d138d`, `p12-b72ae2`, `p13-8a1a2b` etc., but the
   Methods subsection labels on pp. 10–12 ("Data collection and filtering",
   "Sequence clustering and analysis", "Verification of protein family
   novelty", "Ecosystem and taxonomic annotation of protein clusters",
   "Sequence quality control", "Protein cluster co-occurrence with Pfams",
   "Protein fold prediction.") stay glued to the front of their paragraph, so
   Methods renders as one flat run of eight paragraphs with no structure.
   These are bold run-in headings in the PDF and are the same shape as the
   ones the extractor does catch.

6. **Back-page affiliation blocks.** Related to op group 6 above: whether it
   is fixed in `extract_pdf.py` (mark them `furniture`/`role=back`) or in
   `render_doc` (drop the "before the first heading" condition on
   `is_affiliations`), a Nature paper with a 100-author consortium should not
   need 22 hand-written drops.

## 2026-07-27 — corrections pruned

This paper renders from the publisher's JATS XML, which the builder prefers over the extracted PDF document, so no op here could ever reach the page. The defects described below are real but live in a document nothing reads.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.
