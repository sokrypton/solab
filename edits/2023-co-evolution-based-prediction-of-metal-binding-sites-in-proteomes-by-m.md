# 2023-co-evolution-based-prediction-of-metal-binding-sites-in-proteomes-by-m

Nature Chemical Biology 19, 548–555. Two-column, 13 pages plus 10 Extended Data
figure pages. GROBID's TEI is the render source; `.cache/doc_ours` was used as
the repair source throughout — it has the printed reading order and the words
GROBID lost at column and page breaks.

## What was wrong

**Reading order (the worst defect).** GROBID emitted page 2's right column
before its left column, so the page read: abstract, Introduction ¶1–2, then
*"The results suggested that we could in principle incorporate the co-evolution
information…"* — a Results paragraph with no antecedent — then Figure 1, then
the whole "Assembling co-evolved metal-binding pairs into network" subsection,
and only *then* Introduction ¶3–5, the `Results` heading and the first Results
subsection. Fixed by dropping `g11 g12 g13 g14 g15 g16 g17` and re-inserting
them after `g3` in printed order (7 drops + 7 `after` inserts). Everything else
then falls into place because `g4 g5 fig1 g6 g7 g8 …` were already in order
among themselves.

**Sentences spliced across the wrong boundary.** Five paragraphs were cut at a
column/page foot and had unrelated text welded on. Each pair was repaired from
`doc_ours`:

| node | broke off at | what was welded on instead | where the real tail was |
|---|---|---|---|
| `g3` | "researchers have" | the running head | tail of `g10` |
| `g10` | "it should be possible to compare" | `g3`'s lost tail (ICP-MS / ABPP / metal isotope autography) | `g18` |
| `g23` | "MetalNet found 1,603 network clusters and" | Fig. 1 panel c/d caption | head of `g24` |
| `g27` | "the overall distribution of" | Fig. 2 caption tail | head of `g29` |
| `g107` | "containing 20% (vol/vol) glycerol" | nothing — page 12 was simply dropped | `doc_ours` p11 |

`g10` is the one worth flagging: the splice produced a sentence the authors
never wrote — that co-evolution architecture makes it "possible to compare
explored metal-binding proteins directly in proteomes using ICP-MS…". A reader
would take that as a claim of the paper.

**Captions cut, their tails rendered as prose.** Fig. 1, Fig. 2, ED Fig. 5 and
ED Fig. 7 all stopped mid-caption; the missing halves surfaced as body text
(`g23`, `g27`) or as two junk "orphan captions" after the Methods (`g113`
concatenated ED Fig. 4's tail + all of ED Fig. 5 + all of ED Fig. 7). Each half
was put back on its own figure and `g113` dropped.

**Wrong figure artwork — every figure below Fig. 2.** Figures 3 and 4 rendered
GROBID's embedded rasters `gb-03.jpg` and `gb-04.jpg`, each of which is a
*single sub-panel* (one protein cartoon; one zinc-site zoom) standing in for a
five- and an eight-panel figure. Our own page crops `fig-03.jpg`/`fig-04.jpg`
are complete and correct. Separately, all six Extended Data figures showed
artwork from four figures earlier — "Extended Data Fig. 5 | Overall workflow of
MetalNet" was illustrated by ED Fig. 1's metal-count bar chart. The crop set is
numbered sequentially over all 14 figures (`fig-05` = ED Fig. 1 … `fig-14` =
ED Fig. 10); the ingest picked the crop whose number matches the *label*
number. Extended Data Figs 1–4 were not rendered at all. Fixed by dropping the
six ED figure nodes and Figs 3–4 and re-inserting nine figure nodes with the
right image, plus four new nodes for ED Figs 1–4 (crops and captions both
already existed).

**Smaller items.** `g28` — the running head "Article" read as a section heading
and appeared in the contents rail between two Results subsections; dropped.
`g111` — PDB codes and e-values printed *inside* Figure 3's panels, rendered as
an orphan caption; dropped (the same information is in the caption).
`g131` — bibliography entry 18 was the article's own DOI; `g49` — "The key
parameters are shown as follows:" with the parameters missing; missing Methods
heading "Direct structural evidence for MetalNet predictions"; the whole
"Molecular dynamics" Methods section (the only citation site for refs 56–59);
a running head pasted inside a sentence in `g30`; and the U+02BC quote glue
(`matrixʼfor`, `singletonʼpairs`) in `g5`/`g8`.

55 ops total: 19 drop, 19 set, 17 after.

## Left alone deliberately

- **Six remaining `table-dump` flags** (`g50 g78 g89 g91 g94 g105`) are not
  tables. Five are real Methods prose that happens to be dense with buffer
  concentrations and temperatures ("25 mM Tris, pH 8.5, 1.0 M NaCl and 1 mM
  PMSF…"). `g50` is the AutoGluon predictor metadata and `g78` the list of
  spliceosome zinc sites — both printed as running text in the Methods and both
  real content. Kept.
- **Two remaining `fragment` flags** (`g51`, `g69`) are one-sentence paragraphs
  that are one sentence long in the PDF too.
- **`Extended Data Fig. N` citations link to the wrong figure.** In the text,
  "Extended Data Fig. 1" links to `#figure-1`, which is main Figure 1. Not
  fixable with an op — the anchor is minted by the link pass, not by a node. I
  gave the four restored ED figures no anchor rather than mint a duplicate
  `figure-1` id. See below.
- **Reference 57 is missing** from the bibliography (Parrinello–Rahman) and refs
  3, 23, 24, 47, 50 lost their titles in GROBID's parse. `value=` numbering is
  correct, so citations still point at the right entries; not worth hand-typing.
- Cosmetic breakage inside URLs (`https:// www.biorxiv.org`,
  `https://ebi10.uni- prot.org`) and hyphen debris (`co-omassie`, `detec tion`)
  left as is — GROBID's own line-join artefacts, not worth 10 more `set` ops.
- No display equations in this paper; `.cache/equations/` untouched.

## For the extractor, not for the next overlay

Ranked by how much hand work they cost here.

1. **Extended Data figure crops are matched to the label number instead of
   carried through from our own layout pass.** `scripts/ingest_tei.py`. The six
   ED nodes are stamped `from_ours: true` and their ids even preserve our text
   hash (`g905-c6e742` ↔ `p18-c6e742`), so the node *came from* `doc_ours` —
   where it already had `image: fig-09.jpg` — and then the image was re-derived
   from "Extended Data Fig. **5**" as `fig-05.png`. Keep the image that came
   with the node. This alone accounts for 12 of my 55 ops.
2. **Extended Data Figs 1–4 are dropped on anchor collision.** Same script.
   `doc_ours` has them (`p14-b9df2c`, `p15-209114`, `p16-677a3b`, `p17-3268fc`)
   with crops and captions; they would want anchors `figure-1`…`figure-4`, which
   GROBID's main Figs 1–4 already hold, and they vanish. Extended Data needs its
   own anchor namespace (`figure-ed1`), which also fixes the mis-targeted
   "Extended Data Fig. N" citation links in `build_papers.py`'s link pass.
   4 more ops.
3. **GROBID's embedded rasters are preferred over our page crops even when they
   are a fragment of the figure.** `scripts/ingest_tei.py`. `gb-03.jpg` /
   `gb-04.jpg` are one panel each; `fig-03.jpg` / `fig-04.jpg` are the whole
   figure. A `gb-*` image whose area or aspect is wildly unlike the caption's
   page region should lose to the crop — or, more simply, prefer the crop
   whenever one exists for that figure. 4 more ops.
4. **Yes to both defects the previous paper reported.** Text *is* dropped at page
   turns: `g107` loses everything after the page-11 foot, taking the second half
   of "X-ray data collection" and all of "Molecular dynamics" (refs 56–59 are
   cited nowhere else on the page). And glyphs *are* mangled, though this is
   Nature rather than Cell: the closing single quote arrives as U+02BC and eats
   the following space (`matrixʼfor`, `singletonʼpairs`, `E.coli`). A
   normalisation step in `ingest_tei.py` — U+02BC → `'` plus a space when the
   next character is alphanumeric — would clear the whole class.
5. **Column-order scramble is not detected.** `scripts/ingest_tei.py`. GROBID
   put page 2's right column before its left; 14 of my ops are a manual
   re-sort. `doc_ours` has the right order and shares text hashes with the TEI
   nodes, so the two node lists can be aligned by id and the TEI list reordered
   to match `doc_ours` wherever the sets agree. This would fix the single most
   confusing thing on the page for free, and it is the same alignment already
   being used to import figures.
6. **Caption/prose cross-contamination at column boundaries.** `ingest_tei.py`.
   Five paragraphs here ended mid-clause with a caption fragment or a running
   head welded on. In every case `doc_ours` had the intact paragraph and marked
   the caption text as figure furniture. Same alignment as (5) makes these
   repairable automatically; they were 10 `set` ops by hand.
7. **Running heads leak into prose and into headings.** `ingest_tei.py`.
   "Article https://doi.org/10.1038/s41589-022-01223-z" appears mid-sentence in
   `g30`, at the head of `g29`, at the tail of `g3`, and on its own as a level-3
   heading (`g28`) that reached the contents rail. The string is constant across
   all 13 pages — strip it before node assembly.
8. **`drop` cannot reach a reference node.** `scripts/build_papers.py` ~line
   1078: the `role == 'references'` branch `continue`s before the
   `kind == 'dropped'` check, so a `drop` op on a bibliography entry applies and
   is counted but changes nothing. I had to `set` `g131`'s text to `"."` so that
   `render_entries`' 25-character floor would swallow it. Move the `dropped`
   test above the references branch.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 49 still change the page and were kept; 1 now target nodes the classifier already hides, and 5 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 43 still change the page and were kept; 6 now target nodes the classifier already hides, and 0 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.
