# 2024-scalable-protein-design-using-optimization-in-a-relaxed-sequence-space

Science, `.cache/pdf/2024-scalable-protein-design-…pdf`, 8 pages.

- Science closes the article with an **"Editor's summary"** panel. It is set as
  a heading followed by a paragraph, so extraction reads it as a final section
  of the paper. Dropped `p8-c9bc3d` (the heading) and `p8-c2b952` (its text).
- The same page carries a **"View the article online / Permissions"** footer,
  which came through as prose. Dropped `p8-3b3308`.
- Worth fixing in the extractor rather than per paper if it recurs: an
  editor's-summary panel is a *back*-matter pattern the way acknowledgments
  are, and `APPARATUS_HEAD` in `extract_pdf.py` could name it. Seen on one
  paper so far — a second occurrence should promote it from an op to a rule.

## 2026-07-27 — corrections pruned

Extraction improved underneath these ops. 0 still change the page and were kept; 3 now target nodes the classifier already hides, and 0 no longer match any node.

Retired ops are kept in the `retired` list in the JSON, with their original reasons, so the defects they describe stay on record.
