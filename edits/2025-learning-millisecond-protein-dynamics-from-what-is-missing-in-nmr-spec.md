# 2025-learning-millisecond-protein-dynamics-from-what-is-missing-in-nmr-spec

Wayment-Steele et al., Dyna-1 (bioRxiv preprint, 59 pages). 102 ops.

## Fixed with ops

- **Page folios read as headings (59 drops).** This preprint prints the page
  number alone at the bottom of every page, and every one of them became a
  `heading` node: `p1-356a19` "1" through `p59-5a5b0f` "59". They rendered as
  `<h3>` and, worse, each one took a slot in the contents rail, so the rail was
  a list of numbers with "Results", "Discussion" and "Methods" buried in it.
  Dropped all 59. This is the single largest defect on the page and it is not
  specific to this paper — see escalation below.
- **Results subsection headings read as prose (5 retypes).** The five bold
  subsection titles in Results — `p4-09337b` (conservation), `p7-f05b0c`
  (curating labels), `p9-1fbf11` (deep learning can predict), `p12-9c9ffc`
  (assigned residues with exchange), `p16-dbc97c` (exchange not typically
  considered) — were typed `prose`. Three of them are under 60 characters, and
  `render_doc` silently drops prose that short, so they were *missing from the
  page entirely*, not merely mis-styled. Retyped to `heading`; `p4-09337b` and
  `p7-f05b0c` also got `level: 3` because auto-levelling makes anything over 60
  characters an h2. `p7-f05b0c` had a stray space before its final period (the
  bold run ended before the period) — fixed with `set`.
- **Methods subsection headings lost the same way (16 retypes).** "Curating the
  RelaxDB dataset.", "BMRB entries.", "Data from literature.", "Generating
  MSAs.", "Generating structure models.", "Curating data.", "Comparing to
  structure models in PDB", "Complete dispersion data available/unavailable",
  "Data splitting", "Training", "Adjusting logits…", "Uncertainty estimation."
  and three more. All were short `prose` and therefore invisible; Methods was a
  40-paragraph undifferentiated slab. Retyped to `heading` (auto-level 3).
  Three of them — `p35-6c6a67` "Fitting data / assigning labels.", `p38-c0c744`
  "The mBMRB dataset", `p39-f2fb61` "RelaxDB-CPMG curation" — are immediately
  followed by another heading, so `drop_empty_sections` still prunes them. That
  is the builder behaving as designed (a heading with no prose of its own) and I
  left it.
- **Figure 1's caption title, split three ways.** The bold title ran across
  `p22-e9ebcf` (the figure node, "…demonstrates"), `p22-a4b0e8` ("residues with
  ps-ns motion are less conserved…", promoted to an **h2** because it is set in
  the caption's bold face) and the head of `p22-5e005d` ("conserved. (a) Many
  biological…"). Set the figure caption to the whole sentence, dropped
  `p22-a4b0e8`, and trimmed the leading "conserved. " off `p22-5e005d` so the
  panel list starts at (a).
- **"Aeolicus" as a section heading.** `p17-fc9dbf` is the italic species word
  from the middle of "Adenylate Kinase from Aquifex aeolicus". Dropped it and
  appended the word to `p17-67b712` so the sentence reads through into
  "49 , Biliverdin reductase B 50 , …".
- **Body prose mis-typed as orphan captions (4 retypes).** `p5-0a7fb1`,
  `p11-b2a5c6`, `p13-c6fb24`, `p13-3b0ce1` all begin "Fig. Nx depicts…" /
  "Extended Data Fig. 5 ." and were typed `caption`, so they rendered in the
  orphan-caption style in the middle of Results. Each is ordinary body text that
  continues into the next paragraph. Retyped to `prose`. The two genuine orphan
  captions on the figure-only pages (`p25-034772` Fig. 3, `p27-f319d8` Fig. 4)
  are correct and were left alone.
- **Equation shards promoted to headings (8 drops).** `p34-f41a42` "!' [J(0) +",
  `p45-5714ac` "K(K1*G*AN|+)OK(JBGGBAL|+) =", `p34-32be0d`, `p34-6e1f13`,
  `p36-cc9019`, `p45-0fe46a`, `p45-522c24`, `p36-14fb53`. The display equations
  in Methods come out of the PDF as a dozen unordered scraps with substituted
  glyphs; several were classified `heading`. Nothing readable can be recovered
  from them, so they go. Note that some of these only became *visible* once the
  real Methods headings were restored — `drop_empty_sections` had been hiding
  them because they had no prose beneath them.
- **`p41-484151`** read "Identifying unsuppressed R 2,e$". The "eff" subscript is
  mangled; the same subscript appears as "e1" a dozen times in this section
  ("R 2,e1 vs ν CPMG"). Set to "Identifying unsuppressed R 2,eff" — the heading
  only, because the body occurrences are too numerous to patch by hand.

## Deliberately left

- **34 of the 37 `fragment` flags are not defects to fix here.** Nearly every
  paragraph in this paper is split at a line-wrap boundary: `p4-e2e0a6` ends
  "we could only ﬁnd fewer than 10 sets of complete" and `p4-7b504b` starts
  "CPMG dispersion data…". The audit flags the short leading/trailing pieces.
  Stitching them would mean a `set` per paragraph across 45 pages, and the
  correct fix is in the extractor (below). The text is all present and in order,
  so a reader loses paragraph boundaries, not content.
- **`p34-01a402`** "√( . 𝜇 $ is the permeability of free space, h is Planck's
  constant, 𝛾 9 is where d=" — real content in scrambled order, mixed with an
  equation fragment. Any reconstruction would be a guess. Left.
- **The 4 `table-dump` flags (`p30-4fa32d`, `p31-f05649`, `p32-8e5a1a`,
  `p33-80139d`)** are the bibliography, pages 30-33. They are real content and
  must not be dropped. They are, however, mis-*rendered* — see below.
- The `ﬁ`/`ﬀ` ligature loss ("diference", "ofset", "cutof", "sufficient" →
  "suficient") is everywhere in this PDF. Not patchable per node; it is a font
  mapping problem in extraction.

## Needs `extract_pdf.py` changed, not an overlay

1. **Bottom-of-page folios are classified `heading`, not `furniture`.** 59 of
   them here. This is systemic: a scan of `.cache/doc/*.json` for heading nodes
   whose text is a bare 1-3 digit number finds 139 across 5 papers —
   `2023-genomic-language-model…` (34), `2024-computational-design-of-soluble…`
   (23), `2025-designing-novel-solenoid-proteins…` (21),
   `2021-de-novo-protein-design-by-deep-network-hallucination` (2), this one
   (59). A node whose whole text is a bare number, sitting at the top or bottom
   of a page, should be `furniture` unconditionally. That one rule retires 139
   drop ops.
2. **The `references` role does not carry past the first page of the
   bibliography.** `p29-c1ef3b` has `role: references` and is correctly rendered
   into the reference list; `p30-4fa32d`, `p31-f05649`, `p32-8e5a1a`,
   `p33-80139d` are the *continuation* of the same numbered list, have no role,
   and render as four 2-3 kB `<p>` blobs of run-together citations. Once a
   bibliography starts, subsequent pages' nodes should inherit `references`
   until a real heading intervenes. No op can express this (there is no
   `role` op).
3. **Bold subsection titles are not recognised as headings when they sit flush
   with the paragraph they introduce.** 21 headings in this paper (5 in Results,
   16 in Methods) came out as `prose`. Because `render_doc` drops prose shorter
   than 60 characters, a heading missed this way disappears from the page
   without a trace — the failure is silent and lossy, which makes it worse than
   a mis-styled heading. Worth using the font weight the extractor already sees
   for the caption-title case.
4. **Caption classification triggers on any line starting "Fig."** — four body
   paragraphs in the middle of Results were typed `caption` purely because the
   sentence opens "Fig. 3e depicts…". Requiring proximity to a located figure
   region (or to the page's artwork cluster) would fix this class.
5. **Caption bold titles that wrap are emitted as separate `heading` nodes.**
   Fig. 1's title became an h2 (`p22-a4b0e8`); the Extended Data Fig. 2 colour
   key became another (`p50-ed6847` "ps-ns motion no labelled motion µs-ms
   motion missing assignment"). A bold run inside a caption block should stay
   part of the caption.
6. **Duplicate node ids make some nodes unaddressable.** Equation shards repeat
   verbatim on a page, so several ids occur 2-3 times (`p36-14fb53` ×3,
   `p34-d08f88` ×2, `p34-28ed3a` ×2). `apply_ops` builds `by_id` as a dict, so a
   `drop` lands on the last occurrence only — `p36-14fb53` "$ /𝑅 !" still
   renders as an h3 in Methods and there is no way to point at it. Ids should be
   made unique (e.g. an occurrence suffix), or `apply_ops` should apply an op to
   every node sharing the id.

## 2026-07-27 — corrections pruned

This paper now renders from bioRxiv's own full-text conversion rather than from its PDF, so every op below was written against nodes that no longer exist. They described PDF extraction artefacts — page furniture, fragmented paragraphs, figure labels — which the publisher's conversion does not have.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.
