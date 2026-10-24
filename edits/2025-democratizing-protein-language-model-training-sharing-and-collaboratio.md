# 2025-democratizing-protein-language-model-training-sharing-and-collaboratio

The PDF is the bioRxiv preprint ("SaprotHub: Making Protein Modeling Accessible
to All Biologists"); the record's title and abstract are the Nature
Biotechnology version ("Democratizing protein language model training, sharing
and collaboration"). Nothing in the build notices the mismatch, so the cover
block and the preprint abstract both survived the usual dedup. It is also a
Springer/LaTeX manuscript with a hanging-indent bibliography and seven
supplementary tables, which is where the rest of the damage came from.

130 ops: 121 `drop`, 5 `set`, 4 `retype`.

## Fixed with ops

- **The bibliography was rendered twice.** 87 numbered reference lines were
  emitted as body paragraphs — 39 of them wedged between the conclusion and
  Methods, 46 more between "Code and Service availability" and "Be an OPMC
  member" — while the `References` section below already listed all 50 entries
  correctly. Dropped all 87 (`p6-fdd11c` … `p17-882c7f`). Root cause is in the
  extractor, see below; the overlay only papers over it.
- **Cover block.** `p1-3955ad` / `p1-01bc04` (the two lines of the preprint
  title, read as headings), `p1-e5db6f` + `p1-192c7f` (author list, the tail of
  it promoted to a heading), `p1-d8a966` (affiliations). Dropped.
- **Second abstract.** `p1-d79da3` ("Abstract") + `p1-d61fdf` (the preprint
  abstract). `drop_abstract_section` judges overlap against the *published*
  abstract and the manuscript wording is different enough to survive, so the
  reader got two abstracts in a row. Dropped both.
- **Three paragraphs split across page breaks with the folio welded into the
  continuation.** Rejoined with `set` + `drop`:
  - `p1-697839` ("… and ProtGPT2 [ 4 ],") + `p1-356a19` ("1 each demonstrating…")
  - `p4-629b49` ("… are updated, resulting") + `p4-1b6453` ("4 in nearly identical…")
  - `p11-70f6f4` + `p12-9642b5`. This one also had equation (1) and the folio
    dumped inside the sentence: "…Both ProteinGym and 11 t | x \ T ) − logP ( x
    t = s wt t | x \ T )] (1)". Truncated at "Both ProteinGym and " and
    completed from `p12-9642b5`.
- **Table rows and in-figure labels promoted to headings** — they were filling
  the contents rail with entries like "Saprot 0.457 0.574 0.909", "RMSD 2.28
  2.07", "Spearman's", "AAV", "3EFE-A". Dropped 18: `p19-5892ff`, `p19-1334d9`,
  `p19-6e8bd8`, `p19-1d03af`, `p19-c8d11d`, `p19-2f0fdb`, `p19-fdb918`,
  `p19-6bc7c6`, `p19-4b555d`, `p19-50eae4` (Supplementary Table 1),
  `p20-0274bf` (Table 2), `p21-70ed0e`, `p21-bdb9fc` (Table 3), `p22-9d2f11`,
  `p22-54e60f` (Table 4), and `p25-21d9fe`, `p25-3c6d03`, `p25-925744`,
  `p25-f6115b`, `p25-233896`, `p25-e82cce`, `p25-25527b`, `p25-e4080a`,
  `p25-ee996d` (PDB ids printed inside Supplementary Fig. 3). These have to be
  dropped as a group: `drop_empty_sections` was already hiding most of them, so
  removing the last one in a run just promotes the one before it.
- **Captions with table/figure debris on the front.** `p21-78593d` opened with
  the last row of Supplementary Table 3 ("ρ 0.813 0.783 - - 0.829") before the
  caption; `p25-c5b9a6` opened with an in-figure label ("Sequence recovery:
  37.71%"). Trimmed with `set` and retyped to `caption`.
- **Type mix-ups.** `p4-58bcd9` is body prose discussing Fig. 1c but was typed
  `caption` (Fig. 1 already has its own caption on p3) — retyped to `prose`.
  `p26-b5a230` is the panel (a) legend of Supplementary Fig. 4 typed as prose —
  retyped to `caption`.

## Deliberately left alone

- `p11-621d5e` "ProteinGym" and `p11-96b4ee` "Mega-scale" are real run-in
  subheadings; the paragraphs after them therefore open "[ 15 ] is an extensive
  set…" and "[ 20 ] uses cDNA display…". Awkward, but faithful, and inventing
  text to smooth it over is not an extraction fix.
- The four `Supplementary Table 1–4` captions (`p19-11a284`, `p20-4a2ece`,
  `p21-78593d`, `p22-066f5b`) stay as orphan captions. The tables themselves
  cannot be rendered, but the captions are the only remaining description of
  what was measured.
- The footnotes `p1-98ccae` ("conference extended version of our Saprot paper")
  and `p4-d8ae4f` (Hugging Face release date, ProteinGym leaderboard) read as
  stray one-liners in the flow but are real, cited content. Kept.
- `p18-b334cb` / `p18-30f9e9` are the OPMC membership bullet lists, run
  together into single paragraphs with `•` separators. Content is intact and
  legible; splitting bullets is a renderer feature, not an op.
- The `fragment` flags on every reference line were all genuine — but genuine
  as "this is a reference, not prose", not as "this text is broken".

## Needs `extract_pdf.py` changed, not an overlay

1. **`mark_back_matter` abandons the bibliography at the first hanging-indent
   block.** In `state == 'refs'`, a block that is neither `looks_like_refs` nor
   `looks_like_entry` sets `state = None` permanently. This manuscript's
   reference blocks are split by the hanging indent: entry [2] arrives as
   "[2] Ethan C Alley, … AlQuraishi, and" (no terminating citation, fails
   `looks_like_entry`) followed by "George M Church. Unified rational…". So
   `role: references` is set on entry [1] only and the other 49 leak into the
   body — and the second bibliography (p15–17) never enters the refs state at
   all. It should not be a one-strike exit: skip a block that *opens* like a
   continuation (lowercase / no `[n]`, same font size, same left margin as the
   previous entry's runover) and keep the state alive, or re-enter the state
   whenever a block opens on `[n] Capital`. Evidence that this is not one
   paper's problem: 9 papers in `.cache/doc` currently carry prose nodes
   starting `[n] ` with a role other than `references` — 72 of them in
   `2022-language-models-generalize-beyond-natural-proteins`, 45 in
   `2025-protein-diffusion-models-as-statistical-potentials`, 35 in
   `2025-cirpin-…`. That is ~250 bibliography paragraphs across the site, all
   fixable once here instead of with ~250 drop ops.
2. **Node ids collide, and the overlay then cannot address the node.** The id
   is a hash of the first 200 characters plus the page, so short repeated text
   on one page produces duplicates: `p11-c032ad` ("X", the summation sign, four
   times) and `p26-654d91` ("ESM-2", once as a heading and twice as
   figure-text). `apply_edits` builds `by_id` as a dict comprehension, so only
   the *last* node with a given id is reachable; `render_doc` renders the
   *first*. I verified this — a `drop` on `p11-c032ad` marks the fourth copy and
   the rendered `<h3>X</h3>` survives. Two junk headings therefore remain on
   this page, "X" (an orphaned Σ from the zero-shot formula) and "ESM-2" (a
   t-SNE panel label), and no op can remove them. Fix is either a positional
   suffix on collision (`p11-c032ad`, `p11-c032ad-2`, …) or letting ops apply
   to every node sharing an id.
3. **Line-break hyphenation is never undone.** Every page carries "biological
   pro- cesses", "bidirec- tional", "chal- lenge", "parame- ter efficient" —
   including inside figure captions. Not worth per-node `set` ops; it is one
   join rule (`(\w)- (\p{Ll})` when the fragment is not a real compound) in the
   extractor's line stitching.
4. **Paragraphs that continue across a page break are not stitched, and the
   folio is welded onto the continuation** ("1 each demonstrating…", "4 in
   nearly identical accuracy…"). Three instances on this paper alone; the folio
   is already recognised as furniture when it stands alone, so the same test
   should run on the first token of a block.
5. **Tables are emitted as pseudo-prose rows, and bold rows become headings.**
   `heading` should not be assigned to a block whose `lines` are short
   column-shaped cells (Supplementary Table 1 arrives as
   `lines: ["Thermostability [ 25 ]", "Spearman's ρ", "5310", "706", "706"]` —
   the cell structure is right there and is being flattened into a sentence).
   Most rows are then invisible only because `render_doc` drops prose under 60
   characters; the bold ones become sections. A `table` node type (dropped, or
   rendered as a table) would remove this whole class of flag.

## 2026-07-27 — corrections pruned

This paper now renders from bioRxiv's own full-text conversion rather than from its PDF, so every op below was written against nodes that no longer exist. They described PDF extraction artefacts — page furniture, fragmented paragraphs, figure labels — which the publisher's conversion does not have.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.
