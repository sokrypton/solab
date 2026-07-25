# Contact-page fold generator — sandbox notes

**This branch (`sandbox`) is a working playground. It is never merged into `main`.**
Ideas are prototyped and measured here; only the ones that prove out get hand-ported
into `main` as small, self-contained changes. This file is the index of what's here,
whether it's proven, where it lives, and what we learned.

**Architecture (2026-07-25):** the branch now mirrors `main`'s split — all protein
structure / contacts / visuals live in `assets/js/contact.js` (loaded only on
`/contact/`), and `assets/js/msa.js` keeps only the site-wide header/sequence strips.
`contact.js` includes the map hover/pin connectors ported to `main`.

> **Experimental generation** from the old monolith — the fold-type builders (β-barrel,
> TIM barrel, bundle, layer, sandwich, jelly-roll), the compaction bias, and the live
> Rg minimiser — is **preserved at commit `e97efeb`** (`git show e97efeb:assets/js/msa.js`)
> and catalogued below. It is not in the working tree; re-port pieces as needed.

> The `?v=NN` query on the `contact.js` `<script>` tag in `index.html` is a cache-buster —
> Chrome heuristically caches assets with no `Cache-Control`, so bump it whenever you
> edit `contact.js` or the browser may serve a stale copy.

---

## Contact model — per-SS virtual Cβ  ·  **PROVEN**

- **Where:** module-scope `CBOFF`, `CBCUT`, `deriveContacts` (top of the IIFE).
- **What:** each residue gets a virtual Cβ placed `CBOFF[ss]` Å out from the Cα along
  the Cα-bond bisector; two residues contact when their points are within
  `CBCUT(ssi,ssj)`. `CBOFF = {H:3.0, E:4.0, L:3.5}`, `CBCUT = HH 8.0 else 8.5`.
- **Learned:** fitted against ConFind (deg>0.01) over the 151 native domains. Per-SS
  beats a single offset/cutoff — **F1 0.79** (vs 0.78 single 3.5/8, ~0.3 for raw Cα).
  Strand side chains reach further (4.0) than helix (3.0). Splitting E into paired vs
  unpaired gave no aggregate gain (unpaired strands too rare) — not worth it.
- **Port target:** this is the cleanest, highest-value thing to lift into `main`.

## Coordinate-derived contact map  ·  **PROVEN**
- **Where:** `deriveContacts` + `contactMap`; `buildFold` returns `{pairs, pts, sep}`.
- **What:** every contact is measured from the built coordinates, not from any
  sheet-pairing bookkeeping. Coloured by SS: E–E = β (blue), H–H = helix (coral,
  intra- AND inter-helix), else tertiary (gold).
- **Learned:** map and structure agree by construction; a broken ladder shows up.

## β-sheet generation — coherent grid + anchored strands  ·  **PROVEN**
- **Where:** `strandInSheet`, strand branch of `seqBuild`.
- **What:** strands share one axial grid; a new strand is anchored in-register beside
  its partner (N-terminus at the aligned entry, grown across the partner's range) so
  ladder overlap is full by construction and the connecting loop is a short turn.
- **Learned:** anchoring (don't centre + line up afterward) gives 0% isolated strands,
  full pairing, fewer clashes. Pleat is per-residue zigzag (`SPLEAT_AX 3.35`,
  `SPLEAT_H 0.89` → 3.8 Å Cα, ~124° pseudo-angle).

## Helix generation — sheet-aligned parametric  ·  **PROVEN**
- **Where:** helix branch (A) of `seqBuild`; `coilPts`.
- **What:** when a sheet exists, a helix packs on a face, axis ∥ the sheet axis, length
  set to span the sheet (`≈ span/HRISE`), so its ends line up with strand ends → short
  arc loops. Min helix length **11** (~3 turns): shorter helices render as bowties.

## Rendering fixes  ·  **PROVEN (each is a discrete bug fix)**
- **Helix ribbon width from the spline tangent (`axis:null`).** Storing the helix axis
  (as strands do) made the width vector *circumferential* → the two ribbon edges spiral
  through each other for the whole helix (view-invariant "X through the centre"). This
  was the big one — same class as the old sheet edge-crossing.
- **Flat strands as per-segment quads, depth-sorted, grouped.** A single ribbon polygon
  self-intersects when the pleated edges weave at oblique angles → zero-winding fill
  HOLES. Per-segment convex quads always fill; grouped so nothing interleaves (no seams).
- **Helix = per-segment quads** (spiral self-occludes); **strand = grouped quads**;
  **loop = round tube**. Seamless SSE↔loop junctions: the terminal Cα keeps its SSE
  type (ribbon reaches the tip) and a segment is a tube if *either* endpoint is a loop
  (ribbon and tube share the boundary Cα).
- **Tangent clamp at SSE ends** so the adjacent loop Cα doesn't hook the centreline.
- Debug flags (all default `false`): `DEBUG_CA` (Cα spheres by SS), `DEBUG_CB`
  (Cα→virtual-Cβ sticks), `DEBUG_EDGES` was removed after use.

## Fold-type selector  ·  **NICE / LOWER-RISK**
- **Where:** dispatch in `buildFold(type)`; `.fold-type` select + change handler.
- Types: `markov` (SS-Markov build-up), `layer` (samples an α/β layer stack —
  `buildLayered`), `barrel` (twisted closed, `buildBarrel`), `tim` ((βα)₈, `buildTIM`),
  `sandwich` (`sandwichTopo`), `jelly` (interleaved sheets, `jellyTopo`), `bundle`
  (`buildBundle`). The geometric builders are deterministic + clash-free by construction.

## Compaction bias  ·  **MEASURED**
- **Where:** `COMPACT` weight + centroid penalty in the `seqBuild` candidate scores;
  tightened structural offsets (helix-on-sheet, bundle, sandwich gaps).
- **Learned:** pulls each SSE toward the growing centroid. Rg scaling exponent matches
  native (0.37); prefactor within the native spread. Scoring bias saturates ~2.8
  (it can only reorder valid poses); further compaction needs tighter offsets.
- **Note:** currently `COMPACT` is low (0.25) so folds generate loose enough for the
  live minimizer to have visible work — raise it if the default fold should be compact
  without pressing ▶.

## Live minimizer (▶)  ·  **EXPERIMENTAL (verified safe, animation caveat)**
- **Where:** `makeMinimizer(pts)`; play wiring in the contact-page DOM handler.
- **What:** Cα gradient descent that drives Rg toward the native TARGET
  (`2.36·N^0.366`, not min) while harmonic restraints hold bonds (3.8 Å), intra-SSE
  distances, and β-ladder pairings (Cα<5.6 pairs); soft clash repulsion (<4.2 Å) pushes
  too-close loops apart. Auto-spin pauses while relaxing.
- **Verified on natives** (`scratchpad/nattest.js`): SSEs and β-pairings preserved
  (drift ≤0.02 Å), bonds held, no collapse. On generated folds it compacts to target.
- **Caveat:** targeting Rg (not minimizing it) is what keeps it from over-collapsing —
  a pure Rg-min packs *tighter* than native. **Larger steps break it** (bonds rupture);
  keep `LR≈0.006`, `MAXSTEP≈0.2`.
- **Open:** on-screen motion looked static in headless/automation Chrome
  (requestAnimationFrame throttled). Needs confirming it animates in a real focused tab;
  if not, add an explicit step/repaint loop rather than relying on rAF.

---

## Verification harnesses (in the session scratchpad, not committed)
`harness.js` (bonds/clashes/isolated/contacts), `rg.js` (Rg vs native scaling),
`cbsweep.js`/`cbfit.js` (contact-model fitting), `nattest.js` (minimizer on natives),
`gentest.js` (minimizer on generated folds). All load `msa.js` with a DOM stub.
