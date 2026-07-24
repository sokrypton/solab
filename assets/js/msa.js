/* Live multiple-sequence-alignment graphics, generated fresh on every load.
   - Bands (hero, footer): ambient random alignments, drifting.
   - Title mark: the section name spelled out as conserved columns of an
     alignment, over faint residue texture.
   Purely decorative (aria-hidden). */
(function () {
  var RES = ['#6e9e4f', '#4e7fc4', '#e0a32e', '#d75a45', '#8e5b9f']; // green blue gold coral plum
  var GRAY = '#c9c1ad';
  var DARK = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var GAP = DARK ? '#4a4335' : '#d0c9b7';   // solid grey gap cell ("-"), legible in both themes
  var INK = DARK ? '#d8d0bf' : '#3a3428';   // contact-map diagonal
  var NS = 'http://www.w3.org/2000/svg';

  function pick() { return RES[(Math.random() * RES.length) | 0]; }

  function svgEl(cols, rows, cell, gap) {
    var pitch = cell + gap;
    var W = +(cols * pitch - gap).toFixed(1);
    var H = +(rows * pitch - gap).toFixed(1);
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'xMinYMid meet');
    svg.setAttribute('shape-rendering', 'geometricPrecision');
    return svg;
  }

  function cellRect(c, r, pitch, cell, fill, op) {
    var rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', (c * pitch).toFixed(1));
    rect.setAttribute('y', (r * pitch).toFixed(1));
    rect.setAttribute('width', cell);
    rect.setAttribute('height', cell);
    rect.setAttribute('rx', '1.5');
    rect.setAttribute('fill', fill);
    if (op != null && op < 1) rect.setAttribute('opacity', op);
    return rect;
  }

  // ---- ambient random tile (bands) ----
  function tile(cols, rows, cell, gap) {
    var pitch = cell + gap;
    var svg = svgEl(cols, rows, cell, gap);
    var frag = document.createDocumentFragment();
    for (var c = 0; c < cols; c++) {
      var consensus = pick();
      var cons = 0.5 + Math.random() * 0.45;
      var edge = c < 1 || c >= cols - 1;
      for (var r = 0; r < rows; r++) {
        if (Math.random() < 0.05 * (edge ? 3 : 1)) continue;
        var col = Math.random() < cons ? consensus : (Math.random() < 0.8 ? pick() : GRAY);
        frag.appendChild(cellRect(c, r, pitch, cell, col));
      }
    }
    svg.appendChild(frag);
    return svg;
  }

  function fillBand(band) {
    var rows = +band.getAttribute('data-rows') || 10;
    var cell = 10, gap = 2;
    var cols = Math.min(240, Math.ceil(window.innerWidth / 8) + 4);
    band.textContent = '';
    var row = document.createElement('div');
    row.className = 'msa-row';
    var t = tile(cols, rows, cell, gap);
    row.appendChild(t);
    row.appendChild(t.cloneNode(true));
    band.appendChild(row);
    requestAnimationFrame(function () {
      var w = t.getBoundingClientRect().width;
      if (w) row.style.setProperty('--tile', w + 'px');
    });
  }

  // ---- spell a word into an alignment grid ----
  // Rasterise the text, then map inked pixels to a rows×cols boolean grid.
  function textGrid(text, rows) {
    var cv = document.createElement('canvas');
    var ctx = cv.getContext('2d');
    var F = 64, font = 'bold ' + F + 'px Arial, "Helvetica Neue", sans-serif';
    ctx.font = font;
    var w = Math.max(1, Math.ceil(ctx.measureText(text).width) + 4);
    var h = Math.ceil(F * 1.3);
    cv.width = w; cv.height = h;
    ctx.font = font; ctx.textBaseline = 'alphabetic'; ctx.fillStyle = '#000';
    ctx.fillText(text, 2, F);
    var d = ctx.getImageData(0, 0, w, h).data;
    var top = h, bot = -1, left = w, right = -1, x, y;
    for (y = 0; y < h; y++) for (x = 0; x < w; x++) {
      if (d[(y * w + x) * 4 + 3] > 80) {
        if (y < top) top = y; if (y > bot) bot = y;
        if (x < left) left = x; if (x > right) right = x;
      }
    }
    if (bot < top) return null;
    var gh = bot - top + 1, gw = right - left + 1;
    var cols = Math.max(1, Math.round(rows * gw / gh));
    return {
      cols: cols, rows: rows,
      on: function (c, r) {
        var px = (left + (c + 0.5) / cols * gw) | 0;
        var py = (top + (r + 0.5) / rows * gh) | 0;
        px = px < 0 ? 0 : px > w - 1 ? w - 1 : px;
        py = py < 0 ? 0 : py > h - 1 ? h - 1 : py;
        return d[(py * w + px) * 4 + 3] > 90;
      }
    };
  }

  function fillMark(mark) {
    var word = (mark.getAttribute('data-text') || '').trim().toUpperCase();
    var rows = 9, cell = 6, gap = 1.5, pitch = cell + gap;
    mark.textContent = '';
    var g = word && textGrid(word, rows);
    if (!g) { mark.appendChild(tile(15, 5, 9, 2)); return; }  // fallback to ambient
    var svg = svgEl(g.cols, rows, cell, gap);
    var frag = document.createDocumentFragment();
    var colColor = [];
    for (var c = 0; c < g.cols; c++) colColor[c] = pick();     // each column one residue
    // full alignment: gaps (grey "-") dominate, occasional stray residues,
    // and the word stands out as vivid conserved columns.
    for (c = 0; c < g.cols; c++) {
      for (var r = 0; r < rows; r++) {
        if (g.on(c, r)) {
          frag.appendChild(cellRect(c, r, pitch, cell, colColor[c]));   // the word: vivid
        } else if (Math.random() < 0.93) {
          frag.appendChild(cellRect(c, r, pitch, cell, GAP, 0.35));      // gap "-": faint grey
        } else {
          frag.appendChild(cellRect(c, r, pitch, cell, pick(), 0.5));    // stray residue
        }
      }
    }
    svg.appendChild(frag);
    mark.appendChild(svg);
  }

  // Idealized de-novo–style fold. Lay a β-sheet (paired adjacent strands), pack
  // helices against its faces, then thread the chain N→C choosing loop lengths
  // from the 3D gaps. The contact map is then DERIVED from the coordinates
  // (residues within a distance cutoff), so map and structure are identical by
  // definition. Deterministic per load, no relaxation. Returns {pts, pairs}.
  function buildFold() {
    var STEP = 3.4, SEP = 4.8, CUT = 7.5;  // virtual-Cβ contact cutoff (Å), calibrated
                                           // to ConFind contact degree > 0.01 (see step 5)

    // ---- statistics from a survey of 151 native domains (SS via pydssp) ----
    //   fold-class mix, SSE lengths, sheet sizes, β pairing sense, and the
    //   tertiary-contact sparsity — all baked in as constants (no PDBs shipped).
    function coil(len) { return { h: true, len: len }; }
    function strand(len) { return { h: false, len: len }; }
    function ri(a, b) { return a + ((Math.random() * (b - a + 1)) | 0); }   // int in [a,b]
    function sLen() { return ri(4, 7); }                 // strand 4–7 (median 5)
    function hLen() { return ri(8, 14); }                // helix 8–14 (median 10)
    function sheetSize() {                               // strands-per-sheet, weighted
      var w = [[2, 0.19], [3, 0.11], [4, 0.17], [5, 0.21], [6, 0.08]], tot = 0, r;
      w.forEach(function (e) { tot += e[1]; }); r = Math.random() * tot;
      for (var k = 0; k < w.length; k++) { r -= w[k][1]; if (r <= 0) return w[k][0]; }
      return 4;
    }

    // 1. topology — pick a fold class (α 0.15 / β 0.14 / α-β 0.71) and its SSEs,
    //    capped at ≤ 8 elements / ~90 residues so the compact map/3D stay legible
    var roll = Math.random(), cls = roll < 0.15 ? 'a' : roll < 0.29 ? 'b' : 'ab';
    var nStr = 0, nHel = 0, sandwich = false;
    if (cls === 'a') { nHel = ri(2, 5); }
    else if (cls === 'b') {
      // ~36% of native β proteins are two sheets packed face-to-face (β-sandwich:
      //   Ig-fold, jelly-roll). Build one for a fraction of β folds, with enough
      //   strands to split across two sheets.
      if (Math.random() < 0.45) { sandwich = true; nStr = ri(5, 8); }
      else nStr = sheetSize();
    }
    else { nStr = Math.min(5, sheetSize()); nHel = ri(1, 3); }
    while (nStr + nHel > 8) { if (nHel > (cls === 'a' ? 2 : 0)) nHel--; else nStr--; }

    var strandEls = [], helixEls = [], elems = [];
    for (var si = 0; si < nStr; si++) { var s0 = strand(sLen()); strandEls.push(s0); elems.push(s0); }
    for (var hi0 = 0; hi0 < nHel; hi0++) { var h0 = coil(hLen()); helixEls.push(h0); elems.push(h0); }

    // Every SSE joins the packed core so it makes at least one tertiary contact —
    //   strands pair into the sheet, helices all dock. Sparsity in the map then
    //   comes from each SSE contacting only a few others (native mean ~1.9), never
    //   from elements drifting off; no residue is left contact-free.
    var coreHel = helixEls;

    var HR = 2.3, HRISE = 1.5, HTURN = 1.75;             // idealized α-helix
    // returns Cα coords plus the per-residue ribbon face-normal (the radial from the
    //   helix axis, which rotates ~100°/residue → a winding helix ribbon)
    function coilPts(base, axis, len) {
      var u = vnorm(vcross(axis, Math.abs(axis.z) < 0.9 ? V(0, 0, 1) : V(1, 0, 0)));
      var w = vnorm(vcross(axis, u)), coords = [], norms = [];
      for (var tt = 0; tt < len; tt++) {
        var ph = tt * HTURN, along = (tt - (len - 1) / 2) * HRISE;
        var rad = vadd(vscale(u, Math.cos(ph) * HR), vscale(w, Math.sin(ph) * HR));
        coords.push(vadd(base, vadd(vscale(axis, along), rad)));
        norms.push(vnorm(rad));
      }
      return { coords: coords, norms: norms };
    }
    var sheetC = V(0, 0, 0);
    var betaAdj = [];   // pairs of spatially-adjacent (H-bonded) strands — the known β ladders

    if (strandEls.length) {
      // 2. β-sheet: adjacent meander rows, curled AND twisted. Real sheets aren't
      //    flat (native Cα ~2.8 Å RMS off-plane) and adjacent strands are rotated
      //    ~24° w.r.t. each other — so rows fan about the sheet's up-axis (a gentle
      //    right-handed twist) rather than running perfectly parallel. Strand step
      //    is 3.8 Å (native extended-chain Cα spacing).
      var SSTEP = 3.8;
      // adjacent strands: 81% antiparallel / 19% parallel (native survey)
      var dirs = [1];
      for (var dr = 1; dr < strandEls.length; dr++) dirs.push(Math.random() < 0.19 ? dirs[dr - 1] : -dirs[dr - 1]);

      if (sandwich) {
        // β-sandwich (Ig-fold / jelly-roll): two flat sheets packed face-to-face
        //   ~10 Å apart, the top layer rotated ~25° about the normal (native
        //   inter-sheet twist). The two layers form the hydrophobic core, so they
        //   make tertiary contacts across the interface.
        var GAP = 10, nA = Math.ceil(strandEls.length / 2);
        var layFlat = function (list, O, U, Vv, off) {
          var Nrm = vnorm(vcross(U, Vv)), md = (list.length - 1) / 2;   // layer normal ⟂ strand
          list.forEach(function (s, r) {
            var C = vadd(O, vscale(Vv, (r - md) * SEP)), dir = dirs[off + r], sm = (s.len - 1) / 2;
            s.coords = []; s.norms = []; s.axis = U;   // constant long axis → straight edges
            for (var tt = 0; tt < s.len; tt++) {
              var along = (tt - sm) * SSTEP * dir, pleat = Math.sin(along * 0.09) * 0.7;
              s.coords.push(vadd(vadd(C, vscale(U, along)), vscale(Nrm, pleat)));
              s.norms.push(Nrm);
            }
          });
        };
        var th = 0.44;   // ~25° inter-sheet rotation
        layFlat(strandEls.slice(0, nA), V(0, 0, -GAP / 2), V(1, 0, 0), V(0, 1, 0), 0);
        layFlat(strandEls.slice(nA), V(0, 0, GAP / 2), V(Math.cos(th), Math.sin(th), 0), V(-Math.sin(th), Math.cos(th), 0), nA);
        // ladders run within each layer (consecutive strands); the two layers pack
        //   as a hydrophobic core → tertiary, not a ladder.
        for (var ba = 0; ba < nA - 1; ba++) betaAdj.push([strandEls[ba], strandEls[ba + 1]]);
        for (var bb = nA; bb < strandEls.length - 1; bb++) betaAdj.push([strandEls[bb], strandEls[bb + 1]]);
      } else {
        // single β-sheet: adjacent meander rows, curled AND twisted. Real sheets
        //   aren't flat (native Cα ~2.8 Å RMS off-plane) and adjacent strands are
        //   rotated ~24° w.r.t. each other, so rows fan about the sheet's up-axis
        //   (a gentle right-handed twist). Strand step 3.8 Å (native extended chain).
        var CURL = 0.20, Rc = SEP / CURL, TW = 0.12, smid = (strandEls.length - 1) / 2;
        strandEls.forEach(function (s, r) {
          var dir = dirs[r], cy = Rc * Math.sin(r * CURL), cz = Rc * Math.cos(r * CURL);
          var phi = (r - smid) * TW, ax = V(Math.cos(phi), 0, Math.sin(phi));  // fanned long-axis
          // sheet normal here = the curl's radial, orthogonalized against the strand axis
          var radial = vnorm(V(0, cy, cz));
          var rda = radial.x * ax.x + radial.y * ax.y + radial.z * ax.z;
          var Nrm = vnorm(vsub(radial, vscale(ax, rda)));
          s.coords = []; s.norms = []; s.axis = ax;   // constant long axis → straight edges
          for (var tt = 0; tt < s.len; tt++) {
            var along = (tt - (s.len - 1) / 2) * SSTEP * dir;
            var pleat = Math.sin(along * 0.09) * 0.7;                          // gentle β-pleat
            s.coords.push(vadd(V(0, cy, cz + pleat), vscale(ax, along)));
            s.norms.push(Nrm);
          }
        });
        for (var ba2 = 0; ba2 < strandEls.length - 1; ba2++) betaAdj.push([strandEls[ba2], strandEls[ba2 + 1]]);
      }
      var scnt = 0;
      strandEls.forEach(function (s) { s.coords.forEach(function (p) { sheetC = vadd(sheetC, p); scnt++; }); });
      sheetC = scnt ? vscale(sheetC, 1 / scnt) : sheetC;

      // 3a. dock core helices onto the sheet along its TRUE surface normal. The
      //     sheet is curled, so global-z is not the normal — offsetting in z would
      //     drive a helix into the sheet's curve. We offset along the radial normal
      //     instead; the helix axis lies in the tangent plane, crossing the strands
      //     at ~40° (native HE angle). Helices alternate sides; extra helices on a
      //     side stagger laterally (~11 Å) so several can pack together.
      var nrm = vlen(V(0, sheetC.y, sheetC.z)) > 1e-3 ? vnorm(V(0, sheetC.y, sheetC.z)) : V(0, 0, 1);
      var sdir = V(1, 0, 0);                                    // strands run ~along x
      var tang = vnorm(vcross(nrm, sdir));                      // in-plane, perp to strands
      var sideSlot = { p: 0, n: 0 };
      coreHel.forEach(function (hh, hi) {
        // helices dock on alternating faces at ~11 Å along the normal (native HE
        // distance). Same-side helices stay PARALLEL (same crossing sense) and just
        // shift laterally, so they never X-cross and collide; opposite faces are
        // free to cross. Each crosses the strands at ~40°.
        var side = hi % 2 === 0 ? 1 : -1, key = side > 0 ? 'p' : 'n', slot = sideSlot[key]++;
        var lat = slot === 0 ? 0 : (slot % 2 ? 1 : -1) * Math.ceil(slot / 2) * 11;
        var base = vadd(sheetC, vadd(vscale(nrm, side * 11),
          vadd(vscale(tang, lat), vscale(sdir, (Math.random() * 2 - 1) * SSTEP))));
        var cross = 0.7 * side;                                 // ~40°, parallel per face
        var axis = vnorm(vadd(vscale(sdir, Math.cos(cross)), vscale(tang, Math.sin(cross))));
        var cp = coilPts(base, axis, hh.len); hh.coords = cp.coords; hh.norms = cp.norms;
      });
    } else {
      // 3b. α-helix bundle: helices arranged around a common axis (not a flat row),
      //     alternating up/down, so each packs against its neighbours — a real
      //     bundle with multiple helix–helix interactions. Ring radius set so
      //     neighbours sit ~11 Å apart (native HH packing); a barrel for n ≥ 4.
      var nb = coreHel.length, Rb = nb < 2 ? 0 : 5.5 / Math.sin(Math.PI / nb);
      coreHel.forEach(function (hh, hi) {
        var ang = nb < 2 ? 0 : (hi / nb) * 2 * Math.PI;
        var flip = hi % 2 === 0 ? 1 : -1;
        var base = V(Rb * Math.cos(ang), 0, Rb * Math.sin(ang));
        var cp = coilPts(base, vnorm(V(0.06 * Math.cos(ang), flip, 0.06 * Math.sin(ang))), hh.len);
        hh.coords = cp.coords; hh.norms = cp.norms;
      });
      var cc = V(0, 0, 0), ct = 0;
      coreHel.forEach(function (hh) { hh.coords.forEach(function (p) { cc = vadd(cc, p); ct++; }); });
      sheetC = ct ? vscale(cc, 1 / ct) : cc;
    }

    // 4. choose the N→C visiting order (and per-element direction) that minimises
    //    the total connecting-loop length — a short-path search over the placed
    //    elements. Elements are few (3–5), so brute-force every permutation.
    function ends(el) { var c = el.coords; return [c[0], c[c.length - 1]]; }
    function loopCost(order, firstRev) {
      var total = 0, last = null;
      for (var a = 0; a < order.length; a++) {
        var ep = ends(elems[order[a]]);
        if (last === null) { last = firstRev ? ep[0] : ep[1]; continue; }
        var d0 = vlen(vsub(ep[0], last)), d1 = vlen(vsub(ep[1], last));
        if (d1 < d0) { total += d1; last = ep[0]; } else { total += d0; last = ep[1]; }
      }
      return total;
    }
    var idxs = []; for (var q0 = 0; q0 < elems.length; q0++) idxs.push(q0);
    var best = { c: Infinity, order: idxs.slice(), fr: 0 };
    (function permute(arr) {                                   // Heap's algorithm
      function gen(k) {
        if (k === 1) {
          for (var fr = 0; fr < 2; fr++) { var cc = loopCost(arr, fr); if (cc < best.c) best = { c: cc, order: arr.slice(), fr: fr }; }
          return;
        }
        for (var idx = 0; idx < k; idx++) { gen(k - 1); var j = (k % 2) ? 0 : idx, tmp = arr[k - 1]; arr[k - 1] = arr[j]; arr[j] = tmp; }
      }
      gen(arr.length);
    })(idxs.slice());

    // thread the chain along the best order; loops are kept minimal — just enough
    //   residues to span the 3D gap between consecutive SSE termini (≈ one per
    //   3.8 Å), arced gently outward. They only lengthen when the gap requires it.
    var P = [], T = [], N = [], U = [], lastPos = null, lastN = V(0, 0, 1);
    best.order.forEach(function (oi) {
      var c = elems[oi].coords.slice(), nrms = elems[oi].norms.slice(), ax = elems[oi].axis || null;
      if (lastPos === null) { if (best.fr) { c.reverse(); nrms.reverse(); } }
      else {
        if (vlen(vsub(c[c.length - 1], lastPos)) < vlen(vsub(c[0], lastPos))) { c.reverse(); nrms.reverse(); }
        var entry = c[0], entryN = nrms[0], gap = vlen(vsub(entry, lastPos));
        var cntL = Math.max(2, Math.min(8, Math.round(gap / 3.8)));
        for (var q = 1; q <= cntL; q++) {
          var f = q / (cntL + 1), mp = vadd(vscale(lastPos, 1 - f), vscale(entry, f));
          var out = vsub(mp, sheetC); out = vlen(out) > 0.001 ? vnorm(out) : V(0, 0, 1);
          P.push(vadd(mp, vscale(out, Math.sin(f * Math.PI) * 2.2))); T.push('L');
          N.push(vnorm(vadd(vscale(lastN, 1 - f), vscale(entryN, f))));   // loop normal: lerp flanks
          U.push(null);
        }
      }
      for (var r2 = 0; r2 < c.length; r2++) { P.push(c[r2]); T.push(elems[oi].h ? 'H' : 'E'); N.push(nrms[r2]); U.push(ax); }
      lastPos = c[c.length - 1]; lastN = nrms[nrms.length - 1];
    });

    // 5. derive contacts from the coordinates (this IS the structure's map).
    //    A residue–residue interaction needs the side chains to point at each other,
    //    not just Cα proximity. With Cα-only coords we approximate each side chain by
    //    a virtual Cβ: from the Cα-Cα-Cα geometry, a unit direction pointing away from
    //    the backbone (bisector of the two Cα bonds), placed 3.5 Å out. Two residues
    //    are in contact when their virtual Cβ are within CUT. Calibrated against
    //    ConFind (contact degree > 0.01) over 151 native structures: this
    //    (3.5 Å / CUT 7.5 Å) matches the ConFind contact map far better than a raw Cα
    //    cutoff (F1 0.78 vs ~0.3) — it drops the Cα-close-but-pointing-apart pairs.
    var n = P.length, pairs = [], CB = [], betaSet = {};
    for (var ci = 0; ci < n; ci++) {
      var vv = V(0, 0, 0);
      if (ci > 0) vv = vadd(vv, vsub(P[ci], P[ci - 1]));
      if (ci < n - 1) vv = vadd(vv, vsub(P[ci], P[ci + 1]));
      var dd = vlen(vv) > 1e-6 ? vnorm(vv) : V(0, 0, 1);
      CB.push(vadd(P[ci], vscale(dd, 3.5)));                    // virtual Cβ
    }
    // 5a. exact β ladders. We built the sheet, so we KNOW which strands are paired
    //     (adjacent within a sheet); emit their close residue pairs directly as β
    //     instead of approximating. This guarantees complete, regular ladders
    //     (anti-diagonal for antiparallel, diagonal for parallel).
    var posIndex = new Map();
    for (var pk = 0; pk < n; pk++) posIndex.set(P[pk], pk);
    betaAdj.forEach(function (pr) {
      var A = pr[0].coords, B = pr[1].coords;
      for (var a = 0; a < A.length; a++) for (var b = 0; b < B.length; b++) {
        if (vlen(vsub(A[a], B[b])) < 5.5) {
          var gi1 = posIndex.get(A[a]), gi2 = posIndex.get(B[b]);
          if (gi1 == null || gi2 == null || Math.abs(gi1 - gi2) < 3) continue;
          var lo = Math.min(gi1, gi2), hi = Math.max(gi1, gi2), key = lo + ',' + hi;
          if (!betaSet[key]) { betaSet[key] = 1; pairs.push({ i: lo, j: hi, kind: 'beta' }); }
        }
      }
    });
    // 5b. helix + tertiary from the virtual-Cβ contact test (β already handled above)
    for (var i = 0; i < n; i++) for (var j = i + 3; j < n; j++) {
      if (betaSet[i + ',' + j]) continue;
      if (vlen(vsub(CB[i], CB[j])) < CUT) {
        var kind = (T[i] === 'H' && T[j] === 'H' && j - i <= 5) ? 'helix' : 'tert';
        pairs.push({ i: i, j: j, kind: kind });
      }
    }

    // 6. center + scale to unit radius
    var ctr = V(0, 0, 0); P.forEach(function (p) { ctr = vadd(ctr, p); }); ctr = vscale(ctr, 1 / n);
    var maxr = 0, Pc = P.map(function (p) { var d = vsub(p, ctr); maxr = Math.max(maxr, vlen(d)); return d; });
    var s = 1 / (maxr || 1), pts = [];
    for (i = 0; i < n; i++) pts.push({ p: vscale(Pc[i], s), t: T[i], n: N[i], u: U[i] });  // n = face-normal, u = strand axis
    return { pairs: pairs, pts: pts, sep: SEP * s };   // inter-strand spacing (scaled) for ribbon width
  }

  // Contact map: backbone diagonal coloured by secondary structure (coral helix /
  // blue β / ink loop) + the contacts derived from the fold, coloured by kind
  // (coral helix / blue β / gold tertiary). `types` is the per-residue SS string.
  function contactMap(pairs, types, cell) {
    var n = types.length, gap = 1, pitch = cell + gap;
    var svg = svgEl(n, n, cell, gap);
    var grid = {};
    function put(i, j, color, op) {
      if (i < 0 || j < 0 || i >= n || j >= n) return;
      grid[i * n + j] = { c: color, o: op }; grid[j * n + i] = { c: color, o: op };
    }
    function ssCol(t) { return t === 'H' ? RES[3] : t === 'E' ? RES[1] : INK; }
    for (var i = 0; i < n; i++) { put(i, i, ssCol(types[i]), 1); put(i, i + 1, ssCol(types[i]), 0.75); }
    pairs.forEach(function (c) {
      var col = c.kind === 'helix' ? RES[3] : c.kind === 'beta' ? RES[1] : RES[2];
      put(c.i, c.j, col, 0.92);
    });
    var frag = document.createDocumentFragment();
    for (var key in grid) {
      var gi = (key / n) | 0, gj = key % n, cd = grid[key];
      frag.appendChild(cellRect(gj, gi, pitch, cell, cd.c, cd.o));
    }
    svg.appendChild(frag);
    return svg;
  }

  // ---- 3D Cα backbone trace from the same SSE model (self-contained) ----
  function V(x, y, z) { return { x: x, y: y, z: z }; }
  function vadd(a, b) { return V(a.x + b.x, a.y + b.y, a.z + b.z); }
  function vsub(a, b) { return V(a.x - b.x, a.y - b.y, a.z - b.z); }
  function vscale(a, s) { return V(a.x * s, a.y * s, a.z * s); }
  function vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
  function vnorm(a) { var l = vlen(a) || 1; return vscale(a, 1 / l); }
  function vcross(a, b) { return V(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
  function rnd1() { return Math.random() * 2 - 1; }

  function proteinTrace(pts, canvas, sep) {
    var ctx = canvas.getContext('2d');
    var SEPw = sep || 0.24;                 // scaled inter-strand spacing → ribbon width
    var DPR = Math.min(2, window.devicePixelRatio || 1);
    var BG = DARK ? [25, 21, 16] : [250, 247, 240];
    var COL = { H: [215, 90, 69], E: [78, 127, 196], L: DARK ? [150, 142, 126] : [140, 133, 118] };
    function size() { return canvas.clientWidth || 320; }
    function resize() { var s = size(); canvas.width = s * DPR; canvas.height = s * DPR; }
    function shade(rgb, near) { var f = 0.4 + 0.6 * near; return 'rgb(' + rgb.map(function (v2, k) { return Math.round(v2 * f + BG[k] * (1 - f)); }).join(',') + ')'; }

    // Catmull-Rom
    function cr(p0, p1, p2, p3, t) {
      var t2 = t * t, t3 = t2 * t;
      function a(a0, a1, a2, a3) { return 0.5 * ((2 * a1) + (-a0 + a2) * t + (2 * a0 - 5 * a1 + 4 * a2 - a3) * t2 + (-a0 + 3 * a1 - 3 * a2 + a3) * t3); }
      return V(a(p0.x, p1.x, p2.x, p3.x), a(p0.y, p1.y, p2.y, p3.y), a(p0.z, p1.z, p2.z, p3.z));
    }
    // smooth the Cα backbone into a cartoon tube whose width encodes SS
    // (β-strands taper to an arrowhead at their C-terminus). Reassignable so we
    // can swap in a freshly generated fold without re-adding listeners/loops.
    function dot3(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
    var fine = [];
    function setFold(pp, sepArg) {
      if (sepArg) SEPw = sepArg;
      var n = pp.length, i, k;

      // Face-normal per residue comes straight from buildFold (exact construction
      //   geometry): strand → sheet normal, helix → rotating radial, loop → lerp.
      //   No fragile re-derivation from near-straight Cα here.
      var sp = pp.map(function (q) { return q.p; });
      var Ns = pp.map(function (q) { return q.n || V(0, 0, 1); });

      // ribbon half-width per residue, keyed to the inter-strand spacing so adjacent
      //   β-strands meet edge-to-edge (their touching edges = the backbone H-bonds
      //   of the sheet). Strands are a uniform-width flat ribbon (no arrowhead —
      //   constant width keeps the edges perfectly straight and parallel).
      var body = SEPw * 0.28, hel = SEPw * 0.32, lp = SEPw * 0.13;   // loop = round-tube radius
      var WID = new Array(n);
      for (i = 0; i < n; i++) {
        var ty = pp[i].t;
        WID[i] = ty === 'H' ? hel : ty === 'E' ? body : lp;
      }

      // subsample the spline, carrying width and interpolated face-normal
      var out = [], SUB = 10;
      for (i = 0; i < n - 1; i++) {
        var p0 = sp[i - 1] || sp[i], p1 = sp[i], p2 = sp[i + 1], p3 = sp[i + 2] || sp[i + 1];
        for (var s2 = 0; s2 < SUB; s2++) {
          var f = s2 / SUB;
          out.push({
            p: cr(p0, p1, p2, p3, f), t: pp[i].t,
            w: WID[i] * (1 - f) + WID[i + 1] * f,
            n: vnorm(vadd(vscale(Ns[i], 1 - f), vscale(Ns[i + 1], f))),
            u: pp[i].u   // strand long axis (constant per strand); null for helix/loop
          });
        }
      }
      out.push({ p: sp[n - 1], t: pp[n - 1].t, w: WID[n - 1], n: Ns[n - 1], u: pp[n - 1].u });

      // width (side) vector per fine point = along × face-normal.
      //   Strand: `along` is the strand's CONSTANT long axis (from buildFold), so the
      //     side vector doesn't wobble with the pleated spline → straight, parallel
      //     ribbon edges lying flat in the sheet. Helix/loop: use the spline tangent
      //     (n = radial for helix ⇒ side = axial ⇒ winding ribbon).
      for (i = 0; i < out.length; i++) {
        var along = out[i].u || vnorm(vsub(out[Math.min(out.length - 1, i + 1)].p, out[Math.max(0, i - 1)].p));
        var sd = vcross(along, out[i].n);
        out[i].s = vlen(sd) < 1e-5 ? V(0, 1, 0) : vnorm(sd);
      }
      fine = out;
    }
    setFold(pts);
    canvas.__setFold = setFold;   // used by the regenerate button

    // trackball rotation: an accumulated 3×3 matrix (no gimbal clamp → never sticks)
    function mMul(A, B) {
      var C = new Array(9);
      for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++)
        C[r * 3 + c] = A[r * 3] * B[c] + A[r * 3 + 1] * B[3 + c] + A[r * 3 + 2] * B[6 + c];
      return C;
    }
    function mRotX(a) { var c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, c, -s, 0, s, c]; }
    function mRotY(a) { var c = Math.cos(a), s = Math.sin(a); return [c, 0, s, 0, 1, 0, -s, 0, c]; }

    function draw(M) {
      var s = size();
      if (canvas.width !== Math.round(s * DPR)) { canvas.width = canvas.height = Math.round(s * DPR); }
      var R = s * 0.8, cx = s / 2, cy = s / 2, k;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.clearRect(0, 0, s, s);
      function rot(p) { return { x: M[0] * p.x + M[1] * p.y + M[2] * p.z, y: M[3] * p.x + M[4] * p.y + M[5] * p.z, z: M[6] * p.x + M[7] * p.y + M[8] * p.z }; }
      function proj(v) { var pe = 1 / (1.9 - v.z * 0.55); return { x: cx + v.x * R * pe, y: cy - v.y * R * pe }; }
      // project each fine point: centreline C (+ its perspective) and the two ribbon
      //   edges C ± side × half-width
      var pr = fine.map(function (q) {
        var rc = rot(q.p), rs = rot(q.s), w = q.w, pe = 1 / (1.9 - rc.z * 0.55);
        return {
          C: proj(rc), pe: pe, w: w, z: rc.z, t: q.t,
          L: proj({ x: rc.x + rs.x * w, y: rc.y + rs.y * w, z: rc.z + rs.z * w }),
          Rr: proj({ x: rc.x - rs.x * w, y: rc.y - rs.y * w, z: rc.z - rs.z * w })
        };
      });
      // one primitive per fine segment, painted back-to-front. SSEs are filled
      //   ribbons; loops are round tubes (a flat loop ribbon would twist between the
      //   flanking SSE normals and read as detached — a tube has no face to twist and
      //   its round caps merge into the ribbon ends).
      var loopD = SEPw * 0.22;                      // constant loop-tube diameter
      var prims = [];
      for (k = 0; k < pr.length - 1; k++) {
        var ty = pr[k + 1].t, z = (pr[k].z + pr[k + 1].z) / 2;
        if (ty === 'L') prims.push({ tube: 1, a: pr[k].C, b: pr[k + 1].C, z: z, t: ty, lw: loopD * (pr[k].pe + pr[k + 1].pe) / 2 * R });
        else prims.push({ a: pr[k], b: pr[k + 1], z: z, t: ty });
      }
      prims.sort(function (m, o) { return m.z - o.z; });
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      prims.forEach(function (g) {
        var near = (g.z + 1) / 2; near = near < 0 ? 0 : near > 1 ? 1 : near;
        ctx.fillStyle = ctx.strokeStyle = shade(COL[g.t], near);
        if (g.tube) {
          ctx.lineWidth = Math.max(1.5, g.lw);
          ctx.beginPath(); ctx.moveTo(g.a.x, g.a.y); ctx.lineTo(g.b.x, g.b.y); ctx.stroke();
        } else {
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(g.a.L.x, g.a.L.y); ctx.lineTo(g.b.L.x, g.b.L.y);
          ctx.lineTo(g.b.Rr.x, g.b.Rr.y); ctx.lineTo(g.a.Rr.x, g.a.Rr.y); ctx.closePath();
          ctx.fill(); ctx.stroke();                                 // stroke closes hairline seams
        }
      });
    }
    resize();
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var M = mMul(mRotX(-0.35), mRotY(0.6)), dragging = false, lx = 0, ly = 0;
    canvas.style.touchAction = 'none';
    canvas.addEventListener('pointerdown', function (e) {
      dragging = true; lx = e.clientX; ly = e.clientY;
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
      canvas.style.cursor = 'grabbing'; e.preventDefault();
    });
    canvas.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      var dx = e.clientX - lx, dy = e.clientY - ly; lx = e.clientX; ly = e.clientY;
      // rotate about the screen axes (camera frame) → trackball feel
      M = mMul(mMul(mRotX(dy * 0.01), mRotY(dx * 0.01)), M);
      if (reduce) draw(M);
    });
    function end() { dragging = false; canvas.style.cursor = 'grab'; }
    canvas.addEventListener('pointerup', end);
    canvas.addEventListener('pointercancel', end);
    if (reduce) { draw(M); }
    else {
      var last = performance.now();
      (function loop(now) {
        var dt = now - last; last = now;
        if (!dragging) M = mMul(mRotY(dt / 9000), M);   // gentle auto-spin when idle
        draw(M);
        canvas.__raf = requestAnimationFrame(loop);
      })(performance.now());
    }
    window.addEventListener('resize', function () { resize(); draw(M); });
  }

  // Home hero: compose the logo from its separate parts around the genome ring.
  // The ring image (genes baked in) spins about its centre; every other element
  // orbits the ring but stays upright. Each part is its own <image>, so there's
  // no fragile grouping.
  function animateHero(el) {
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var BASE = 'assets/hero/', C = 320, VB = 640, RINGD = 350;
    // placements measured from the original artboard (each element's rect read
    // from its parent-group matrix in logo.svg, then scaled ~1.06x about the ring
    // centre into the composite's coordinate system) so frame 0 matches the logo
    // centres optimised to minimise overlap across the full rotation. Every element
    // orbits rigidly and stays upright, so pairwise centre distances are constant;
    // the ring's baked-in gene trapezoids (~4 o'clock) rotate with it and are treated
    // as fixed obstacles. Relaxed onto a ring band allowing a little overlap.
    var spec = [
      { f: '01.png', cx: 181, cy: 223, w: 124, h: 101 },   // energy landscape
      { f: '02.png', cx: 275, cy: 157, w: 81, h: 102 },    // green protein
      { f: '03.png', cx: 391, cy: 166, w: 100, h: 127 },   // 3-protein complex
      { f: '06.svg', cx: 478, cy: 258, w: 94, h: 126 },    // network graph
      { f: '05.png', cx: 349, cy: 488, w: 118, h: 92 },    // orange + can cutout
      { f: '07.svg', cx: 209, cy: 448, w: 130, h: 142 },   // MSA block
      { f: '04.png', cx: 152, cy: 335, w: 106, h: 75 }     // active-site protein
    ];
    var svg = document.createElementNS(NS, 'svg');
    // tight square viewBox around the rotation circle so the logo fills its box.
    // radius = farthest element corner from centre while orbiting (+ small margin)
    var reach = 171;   // ring outer radius baseline
    spec.forEach(function (e) {
      var d = Math.sqrt((e.cx - C) * (e.cx - C) + (e.cy - C) * (e.cy - C));
      reach = Math.max(reach, d + Math.sqrt(e.w * e.w + e.h * e.h) / 2);
    });
    var HALF = Math.ceil(reach) + 4;
    svg.setAttribute('viewBox', (C - HALF) + ' ' + (C - HALF) + ' ' + (2 * HALF) + ' ' + (2 * HALF));
    svg.setAttribute('class', 'hero-svg');
    function img(href, x, y, w, h) {
      var im = document.createElementNS(NS, 'image');
      im.setAttributeNS('http://www.w3.org/1999/xlink', 'href', href);
      im.setAttribute('href', href);
      im.setAttribute('x', x); im.setAttribute('y', y); im.setAttribute('width', w); im.setAttribute('height', h);
      return im;
    }
    var ringH = RINGD * (245.62 / 247.95);
    var ring = img(BASE + '08.svg', C - RINGD / 2, C - ringH / 2, RINGD, ringH);
    svg.appendChild(ring);
    var items = [];
    spec.forEach(function (e) {
      var w = e.w, h = e.h;
      var wrap = document.createElementNS(NS, 'g');
      wrap.appendChild(img(BASE + e.f, e.cx - w / 2, e.cy - h / 2, w, h));
      svg.appendChild(wrap);
      items.push({ el: wrap, cx: e.cx, cy: e.cy });
    });
    el.insertBefore(svg, el.firstChild);
    var fb = el.querySelector('img'); if (fb) fb.remove();
    if (!reduce) {
      var PERIOD = 150000, t0 = performance.now();
      (function spin(now) {
        var th = ((now - t0) / PERIOD) * 360, base = 'rotate(' + th.toFixed(3) + ' ' + C + ' ' + C + ')';
        ring.setAttribute('transform', base);
        items.forEach(function (it) {
          it.el.setAttribute('transform', base + ' rotate(' + (-th).toFixed(3) + ' ' + it.cx.toFixed(2) + ' ' + it.cy.toFixed(2) + ')');
        });
        requestAnimationFrame(spin);
      })(performance.now());
    }
  }

  function sectionWord() {
    var a = document.querySelector('.nav-links a.active');
    if (a && a.textContent.trim()) return a.textContent.trim();
    var pt = document.querySelector('.page-title');
    if (pt && pt.textContent.trim()) return pt.textContent.trim().split(/\s+/)[0];
    return 'solab';
  }

  // render the "solab" wordmark like an MSA viewer: each letter in its own
  // residue-coloured cell (five letters, five residues), echoing the favicon.
  function colorizeBrand() {
    var pal = ['#6e9e4f', '#e0a32e', '#4e7fc4', '#d75a45', '#8e5b9f'];
    function ink(hex) {   // dark or light glyph, whichever reads on the cell
      var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
      return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6 ? '#241f18' : '#faf7f0';
    }
    [].forEach.call(document.querySelectorAll('.brand'), function (b) {
      if (b.dataset.msa) return;
      var t = b.textContent.trim();
      if (!t) return;
      b.textContent = '';
      b.style.letterSpacing = '0';
      b.style.display = 'inline-flex';
      b.style.gap = '2px';
      for (var i = 0; i < t.length; i++) {
        var ch = t[i];
        var s = document.createElement('span');
        s.textContent = ch;
        if (ch !== ' ') {
          var c = pal[i % pal.length];
          s.style.cssText = 'display:inline-block;background:' + c + ';color:' + ink(c) +
            ';border-radius:3px;padding:.02em .18em;min-width:.72em;text-align:center;';
        }
        b.appendChild(s);
      }
      b.dataset.msa = '1';
    });
  }

  // make each lab member link to their auto-generated publications profile
  function wireMembers() {
    if (!document.querySelector('.people-grid')) return;
    var base = location.pathname.indexOf('/lab/alumni') > -1 ? '../member/' : 'member/';
    [].forEach.call(document.querySelectorAll('.person'), function (p) {
      if (p.dataset.wired) return;
      var nm = p.querySelector('.name');
      if (!nm) return;
      var href = base + '?name=' + encodeURIComponent(nm.textContent.trim().replace(/\s+/g, '_'));
      var a = document.createElement('a');       // real link on the name (keyboard-accessible)
      a.href = href; a.className = 'name-link'; a.textContent = nm.textContent;
      nm.textContent = ''; nm.appendChild(a);
      p.classList.add('person--link');
      p.addEventListener('click', function (e) {  // whole card clickable, but let inner links work
        if (e.target.closest('a')) return;
        location.href = href;
      });
      p.dataset.wired = '1';
    });
  }

  function inject() {
    colorizeBrand();
    wireMembers();
    var word = sectionWord();
    var hero = document.querySelector('.hero-band');
    if (hero && !hero.querySelector('.msa-band')) {
      var hb = document.createElement('div');
      hb.className = 'msa-band'; hb.setAttribute('data-rows', '10'); hb.setAttribute('aria-hidden', 'true');
      hero.appendChild(hb);
    }
    // one ambient MSA per page: the big hero band on the home page, otherwise
    // a smaller band in the footer (skip the footer band when a hero band exists)
    if (!hero) {
      [].forEach.call(document.querySelectorAll('.site-footer'), function (f) {
        if (!f.querySelector('.msa-band')) {
          var b = document.createElement('div');
          b.className = 'msa-band'; b.setAttribute('data-rows', '8'); b.setAttribute('aria-hidden', 'true');
          f.insertBefore(b, f.firstChild);
        }
      });
    }
    [].forEach.call(document.querySelectorAll('.page-title'), function (h) {
      var prev = h.previousElementSibling;
      if (!prev || !prev.classList.contains('msa-mark')) {
        var m = document.createElement('span');
        m.className = 'msa-mark'; m.setAttribute('aria-hidden', 'true');
        m.setAttribute('data-text', word);
        h.parentNode.insertBefore(m, h);
      }
    });
    [].forEach.call(document.querySelectorAll('.msa-band'), fillBand);
    [].forEach.call(document.querySelectorAll('.msa-mark'), fillMark);
    var heroLive = document.querySelector('.hero-live');
    if (heroLive) animateHero(heroLive);
    // contact page: one fold drives both the 3D trace (left) and its contact map (right)
    var canvas = document.querySelector('.struct-3d canvas');
    var mapEl = document.querySelector('.contact-map');
    if (canvas || mapEl) {
      var started = false;
      function regen() {
        var fold = buildFold();
        if (mapEl) { mapEl.textContent = ''; mapEl.appendChild(contactMap(fold.pairs, fold.pts.map(function (p) { return p.t; }), 7)); }
        if (canvas) {
          if (!started) { proteinTrace(fold.pts, canvas, fold.sep); started = true; }
          else if (canvas.__setFold) canvas.__setFold(fold.pts, fold.sep);   // swap fold, keep the running loop
        }
      }
      regen();
      var btn = document.querySelector('.regen-btn');
      if (btn) btn.addEventListener('click', regen);
    }
  }

  var timer;
  window.addEventListener('resize', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      [].forEach.call(document.querySelectorAll('.msa-band'), fillBand);
    }, 200);
  });

  if (document.readyState !== 'loading') inject();
  else document.addEventListener('DOMContentLoaded', inject);
})();
