# Reading pages: where this stands

State note written 2026-07-27, before a context compaction. Nothing here is
inferable from the code alone — it is the loop's position and the open list.

## The pipeline, in tier order

A paper's page comes from the best source available:

1. **Publisher JATS** (`.cache/jats/`) — 21 papers. `render_jats` in
   `scripts/build_papers.py`. Best quality; not touched by the refinement loop.
2. **bioRxiv's own full text** (`scripts/fetch_biorxiv.py`) — 19 papers. bioRxiv
   posts the PDF immediately, then a *vendor* converts it to JATS over ~48h;
   that conversion is what its `.full` page renders, and it beats anything
   reconstructed here. Fetch is slow and throttles: only an outright 404 on
   every version means "no full text".
3. **GROBID + our own layout pass** — 42 papers, the loop's queue.
   `scripts/ingest_tei.py` merges them: GROBID for sections, citation links and
   a parsed bibliography; `scripts/extract_pdf.py` (PyMuPDF) for figure images,
   for knowing which text sits *inside* a figure, for reading order, and for
   words GROBID drops at column breaks.

All three emit the same node schema, so the builder, the `edits/` overlays and
`scripts/audit_papers.py` work unchanged across them.

**Tier precedence is enforced in code**: `--force` refreshes a cache,
`--override-publisher` is the only way to displace a publisher's conversion.
Conflating those two once replaced 14 vendor documents with GROBID output.

## The loop

For each PDF-only paper: `prepare_paper.py` → subagent reads the page and the
figure crops → writes overlay ops + a changelog → reports **systemic** defects →
those get fixed in code → `refresh.py` re-renders everything and reports
regressions → next paper.

- **Done:** 2 of 42 — `2017-architectures-of-lipid-transport…`,
  `2023-co-evolution-based-prediction-of-metal-binding…`
- **Also refined by hand:** `2026-toward-life-with-a-19-amino-acid-alphabet…`
  (the proof-of-principle paper; equations transcribed in `.cache/equations/`)
- **Baseline:** `.cache/refresh_baseline.json` — 189 flags across 44 papers,
  0 HTML errors, 0 broken images, 0 dangling links.

The agents' *ops* are largely disposable — 88% of the first pilot's 576 were
retired by later code fixes, and the second agent judged 34 of its own 55
unnecessary. Their **escalations** are the product. Weight the brief that way.

## Open, in rough priority order

1. **`fragment` and `caption-as-prose` audit flags are still miscalibrated**
   (71 and 18 of the remaining 149). `table-dump` was retuned — 21 flags of
   which one was a real table became 3 of which two are — by requiring *no
   sentence break* rather than a digit count alone. `fragment` needs the same
   treatment: measure what it catches before trusting the count.
2. **Caption/prose cross-contamination at column boundaries** — five paragraphs
   on one paper ended mid-clause with caption text welded on. The alignment
   `restore_dropped_text` now uses would fix it; captions were left out of that
   pass deliberately, to keep one change to one class.
3. **Equations** are transcribed by reading the crops. pix2tex was tried and
   produced confident nonsense that *still parsed* as MathML — parseability is
   not correctness. Crops are in `.cache/equation_crops/<slug>/`.
4. **Δ+gene romanisation (`DmlaE` for ΔmlaE) is deliberately not repaired** —
   the same shape matches tool names like `DockQ`. Needs a reader, not a regex.

## What the last round changed

- **Text GROBID drops is now taken back automatically.** `restore_dropped_text`
  in `ingest_tei.py` matches our paragraphs to GROBID's on shared six-word runs
  and, where ours holds more, prefers ours; where GROBID never emitted the
  paragraph at all it is placed after whichever neighbour matched. ~120
  paragraphs recovered corpus-wide and 37 column-break splits rejoined. Nodes
  carry `restored`, `inserted` or `edited`, so the change is visible in the doc.
  `--no-restore` turns the pass off, which is how its effect was measured.
- **`scripts/coverage.py`** is that measurement: our text that never reached the
  rendered page. Compare against the *page*, not against GROBID's document — a
  truncated abstract is printed in full from the record, and comparing documents
  called it lost. Furniture (licence boilerplate, consortium author lists,
  citation lines) has to be filtered or the signal drowns in it.
- **Restoring text without duplicating it is the whole difficulty.** Taking our
  paragraph wholesale printed 500 repeated word-runs on one paper, because our
  pass reads as one paragraph what GROBID split into two. Only the words a swap
  *adds* are checked, and against every other node. Note that a duplicate-run
  count is not comparable between papers: Methods repeat protocol sentences and
  mutant lists legitimately, so only a before/after delta on the same paper
  means anything.
- **Overlay ops survive text repairs.** Ids are content hashes, so mending a
  hyphen changed an id and silently unmoored every op on that node — that is how
  Figure 4 lost its image while the `drop` of the wrong image still applied, and
  11 citations pointed at nothing. Ops now also resolve by a remembered text
  fingerprint (`at`, stamped on every successful apply) and by paragraph
  similarity, and `prune_edits` uses the builder's resolver instead of its own,
  so it cannot retire an op the builder can still place.
- **An insert whose text extraction now supplies is skipped** and pruned as
  redundant — agent ops are meant to be temporary. Prose only: a figure insert
  carries the same caption as the wrong figure it replaces, and reading that as
  "already present" left two figures unreferenced.
- State: **149 flags** (from 182), 0 dangling links, 0 broken images, 0 stale
  ops, 78 live ops across 7 overlays.

## Things that bit, so they don't bite again

- **Absolute text offsets do not survive the pipeline.** Six passes rewrite a
  node's text after links are recorded. Links now carry their span text and are
  re-anchored at the end; a span that cannot be found is dropped.
- **A check that answers a nearby question is worse than no check.**
  `hasTextMinedTerms` stood in for "full text available" (it isn't);
  any non-200 stood in for "no full text exists" (it was throttling);
  `'<li>'` counted parsed bibliography entries at zero because they carry an
  `id`. Each looked like a pass.
- **Measure before repairing.** A pattern for Δ-mangling matched 945 ordinary
  words starting with D. Fixing on that basis would have corrupted every paper.
- **Nothing is committed.** `papers/`, `assets/papers/`, `edits/`, `scripts/`
  are all untracked, so the whole switch to GROBID is still reversible.
  `assets/papers/` is ~38 MB of figures — a deliberate `git add`, not a casual one.

## Environment

- `.venv/bin/python` for everything. PyMuPDF, lxml, requests, Pillow,
  latex2mathml, pix2tex (unused), texify (broken against transformers 4.57).
- **GROBID must be running** for `ingest_tei.py` and `equations.py`:
  `cd <scratchpad>/grobid && JAVA_HOME=<scratchpad>/jdk21/Contents/Home ./gradlew run`
  It needs Java 21 (Java 17 builds it but the service task refuses to start).
  Homebrew has no bottle for this macOS, so the JDKs are unpacked Temurin
  tarballs under the session scratchpad — those are **temporary**; a new session
  will need them again.
