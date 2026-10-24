# 2025-de-novo-design-of-a-peptide-modulator-to-reverse-sodium-channel-dysfun

Mahling et al., *Cell* 188, 6170–6185 (2025). 36-page Cell article with STAR
Methods and eight supplemental figures. 177 ops.

## Fixed with ops

**Cell Press running head (64 drops).** Every page opening carries the Cell
Press "ll" logo glyph plus the word "Article", both set large enough that the
classifier called them headings. `render_doc` dedupes headings by text, so only
the first surviving copy reaches the page — which means dropping one just
promotes the next. All 64 nodes (`p1-4360c2` … `p35-4360c2`, `p2-110c8a` …
`p35-110c8a`, and the merged "ll Article" on `p26-f1a19d` and friends) had to be
dropped together.

**Figure interiors read as headings (~80 drops).** Panel letters ("A B",
"J K L", "E"), residue labels from the Figure S1 structure panels
("L1786 S1787 E1788 F1791 …", `p26-da00dc`, which rendered as an *h2*), and
sequence-logo letters from Figure S2 ("P H REALYR A P R REALYR G",
`p28-454ca7`) were all classified `heading` rather than `figure-text`. Same
promotion problem as the running head: `drop_empty_sections` was hiding all but
the last of each chain, so each drop exposed the next one and they had to go as
a set.

**Truncated run-in headings (16 sets + 3 levels).** The most damaging defect.
Cell sets these subsection headings with the current name in italic small-caps
("*I*~NaL~"), and extraction broke each heading at that boundary: the heading
node kept the roman part and the italic tail was glued onto the front of the
following paragraph. Seven headings and seven paragraphs were wrong:

| heading node | was | now |
|---|---|---|
| `p4-ae7103` | "A rational approach to developing an" | "… an I NaL inhibitor" |
| `p5-8306d2` | "ELIXIR decreases" | "… I NaL of a channelopathic Na V 1.5 variant" |
| `p5-738374` | "ELIXIR is a general inhibitor of NaV1.5" | "… NaV1.5 I NaL" |
| `p5-e2e888` | "ELIXIR preferentially tunes pathological" | "… pathological I NaL" |
| `p9-686cfc` | "ELIXIR reduces" | "… I NaL and APD 90 of CaMKII δ C,OE ventricular myocytes" |
| `p9-ef386a` | "ELIXIR inhibits" | "… I NaL in LQT3 patient-derived iPSC-CMs" |
| `p24-6a1306` | "Enzymatic isolation of ventricular CaMKII" | "… CaMKII δ C,OE cardiomyocytes" |

The matching paragraph in each case now starts at its real first word ("Fast
inactivation of Na V channels is…", "Thus affirmed, we sought…", etc.). Two of
the repaired headings crossed the 60-character cutoff in `heading_level` and
needed an explicit `level: 3`; `p9-fd0462` needed the same for the same reason.

**Two headings absorbed whole (2 afters + 2 sets).** "CaMKII δ C,OE mice"
(`p19-722221`) and "CaMKII δ C,OE cardiomyocyte electrophysiology"
(`p24-ae10ca`) had no heading node at all — the heading text was the first
words of the paragraph. Reinstated with `after` on the preceding node and
trimmed off the front of the paragraph.

**Key resources table (19 drops).** `p18-e552c2` … `p19-60480d`: the Cell key
resources table, flattened cell-by-cell into paragraphs ("pEGFP C1-Venus Koushik
et al. 90 Addgene: Cat#27794; RRID:Addgene_27794 pEGFP C1-Cerulean …"). Two
pages of catalogue numbers with the columns gone. The header row
("REAGENT or RESOURCE SOURCE IDENTIFIER") and the "Continued" banner were
rendering as headings.

**Figure captions rendered as prose (6 retypes).** Figures 4 and 6 and
supplemental Figures S1, S6 and S7 have captions whose artwork was not located,
so the caption arrived as `prose` and sat in the reading flow as if it were
argument. `p32-c3f1e0` is the panels H–K tail of the Figure S5 caption, split
across a column break. All six retyped to `caption`.

**Equations mistaken for structure (1 retype + 5 drops).** The fluorescence
anisotropy equation (`p21-ea5f3d`) was a heading; retyped to `caption` so it
still prints above its "where I VV and I VH are…" paragraph but leaves the
contents rail. Five equation stubs that carry nothing readable were dropped:
"STV =", "RR 100", "QT C = QT", "1 − E D", "∆ G". `p23-5f3bca` was a bare run
of ~70 combining-macron characters — the overbar of a displayed FRET equation.

**Three other drops.** `p14-11b8b1` was two bullets of Cell's STAR Methods
outline rendered as an h2 (the real headings follow it); dropping it let the
genuine "STAR★METHODS" heading `p14-38d179` through, which needed
`level: 2`. `p14-200c4a` is the tail of the funding paragraph, opening mid grant
number ("HL151969), S.O.M. (R01 HL160089…"), which lost its `back` role while
the head of the same block (`p13-837d27`) kept it.

## Deliberately left alone

- **Eight `table-dump` flags are false positives.** `p20-a9cb3d`, `p20-7814b6`,
  `p23-bfddf4`, `p24-98145f`, `p24-ae10ca`, `p25-6a2356`, `p16-3fa3ae` and
  `p24-34c6af` are ordinary Methods prose and reference entries — kept as text
  (two of them had a separate heading defect, fixed above). They trip the
  flag because they are dense with identifiers, residue lists and buffer
  concentrations — exactly the surface statistics of a table.
- **Most `fragment` flags are real equations or their explanations**
  (`p21-17ec91`, `p21-267a62`, `p23-55e3fc`, `p23-6ba9fb`, `p23-0754a1`,
  `p25-4ae01b`). Reduced to linearized text they read poorly, but the content is
  the paper's and nothing better can be reconstructed by hand.
- `p1-047657` (title fragment) and `p18-cb8186` are already suppressed by the
  builder; no op needed.

## Needs `extract_pdf.py` changed, not an overlay

1. **Cell Press furniture is not recognized.** The "ll" logotype and "Article"
   run above every page opening in a Cell paper and are typeset large, so the
   size-based classifier promotes them to headings instead of `furniture`. 64
   drop ops on one paper, and it will recur identically on every Cell/Neuron/
   Molecular Cell PDF in the collection. The extractor already detects repeated
   running heads for the plain-text path (`build_papers.py` counts lines
   appearing ≥3 times); the node path needs the same repeat test — a heading
   whose text repeats on more than a few pages is furniture, whatever its size.

2. **Panel letters and in-figure labels leak into `heading`.** ~80 nodes here.
   Single capitals, short capital runs, and residue labels sitting inside a
   figure's bounding region should classify as `figure-text` regardless of size;
   they are typeset boldly precisely because they are panel keys. The current
   region test evidently does not cover the label band above/beside artwork.

3. **Italic run-in heading tails are cut off and reattached to the body.** Seven
   occurrences on this paper, all with the same shape: heading breaks at a font
   change, tail becomes the first words of the next paragraph. This is a
   general Cell/*Neuron* house style (subsection headings ending in an
   italicized current or gene name), so expect it on every Cell paper. A
   heading and the following prose should not be split at a font change on the
   same text line.

4. **Node ids are not unique, so two nodes survive that were dropped.**
   `p26-3a4217` ("F1879") and `p28-e0184a` ("E") each occur *twice* on their
   page with identical text, so both copies get the same id. `apply_edits`
   builds `by_id` as a dict, keeping one node; the drop lands on that one and
   the twin still renders. Those are the only two junk entries left in the
   contents rail ("F1879", "E") and they cannot be removed by any op. The id
   scheme needs a disambiguator (occurrence index, or block coordinates) when
   the same text appears twice on a page.

5. **The bibliography loses its `references` role partway through.** Only
   references 1–17 (`p14-19dfd2` … `p14-bf9f9d`) plus a stray 50
   (`p16-90d2ce`) carry `role: references` and render in the reference list;
   entries 19–100 on pages 15–17 carry no role and render as ~55 body
   paragraphs wedged between STAR★METHODS and the Methods text. There is no
   `role` op, so this is not fixable by an overlay — and dropping them would
   throw away four fifths of the bibliography, so they are left in place. The
   role detector appears to stop at the first page break in the reference
   block; it needs to continue while entries keep matching the numbered-citation
   shape.

6. **Minor:** `RESOURCE AVAILABILITY` (`p13-87db6e`) and `Supplemental figures`
   (`p26-550e72`) are legitimate headings that `drop_empty_sections` removes
   because their only children are further headings. Arguably a builder
   heuristic to soften rather than an extraction bug; left alone.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 49 still change the page and were kept; 114 now target nodes the classifier already hides, and 14 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 0 still change the page and were kept; 0 now target nodes the classifier already hides, and 49 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.
