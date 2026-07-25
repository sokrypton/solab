/* Contact-page protein widget — fold generation (from the site's generator) plus the
   improved 3D cartoon renderer and coordinate-derived, per-SS virtual-Cβ contact map.
   Loaded ONLY on the contact page so the rest of the site keeps a lean msa.js. */
(function () {
  var RES = ['#6e9e4f', '#4e7fc4', '#e0a32e', '#d75a45', '#8e5b9f']; // green blue gold coral plum
  var GRAY = '#c9c1ad';
  var DARK = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var GAP = DARK ? '#4a4335' : '#d0c9b7';   // solid grey gap cell ("-"), legible in both themes
  var INK = DARK ? '#d8d0bf' : '#3a3428';   // contact-map diagonal
  var NS = 'http://www.w3.org/2000/svg';
  // per-SS virtual-Cβ contact model, fitted to ConFind over 151 native domains
  var CBOFF = { H: 3.0, E: 4.0, L: 3.5 };
  function CBCUT(a, b) { return (a === 'H' && b === 'H') ? 8.0 : 8.5; }
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

  function V(x, y, z) { return { x: x, y: y, z: z }; }
  function vadd(a, b) { return V(a.x + b.x, a.y + b.y, a.z + b.z); }
  function vsub(a, b) { return V(a.x - b.x, a.y - b.y, a.z - b.z); }
  function vscale(a, s) { return V(a.x * s, a.y * s, a.z * s); }
  function vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
  function vnorm(a) { var l = vlen(a) || 1; return vscale(a, 1 / l); }
  function vcross(a, b) { return V(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
  function rnd1() { return Math.random() * 2 - 1; }

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
            // pleat along the sheet NORMAL (not global z); otherwise on a curled
            //   sheet it shifts the centreline sideways and the ribbon edges wobble
            s.coords.push(vadd(vadd(V(0, cy, cz), vscale(ax, along)), vscale(Nrm, pleat)));
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
      //     side stagger — along the in-plane direction PERPENDICULAR to the helix
      //     axis (not tang), so the ~11 Å offset is fully a separation and the
      //     helices don't end up nearly overlapping.
      var nrm = vlen(V(0, sheetC.y, sheetC.z)) > 1e-3 ? vnorm(V(0, sheetC.y, sheetC.z)) : V(0, 0, 1);
      var sdir = V(1, 0, 0);                                    // strands run ~along x
      var tang = vnorm(vcross(nrm, sdir));                      // in-plane, perp to strands
      var sideSlot = { p: 0, n: 0 };
      coreHel.forEach(function (hh, hi) {
        var side = hi % 2 === 0 ? 1 : -1, key = side > 0 ? 'p' : 'n', slot = sideSlot[key]++;
        // helices cross the strands at ~40°; same-face helices stay parallel (same
        //   sign) — forcing them to cross each other makes them collide (a lateral
        //   stagger can't separate crossing helices), so α/β helices pack a bit more
        //   parallel than native. Opposite faces are free to cross.
        var cross = (0.6 + Math.random() * 0.25) * side;
        var axis = vnorm(vadd(vscale(sdir, Math.cos(cross)), vscale(tang, Math.sin(cross))));
        var perp = vnorm(vcross(nrm, axis));                    // in-plane, ⟂ the helix axis
        var lat = slot === 0 ? 0 : (slot % 2 ? 1 : -1) * Math.ceil(slot / 2) * 10.5;
        var base = vadd(sheetC, vadd(vscale(nrm, side * 11),
          vadd(vscale(perp, lat), vscale(sdir, (Math.random() * 2 - 1) * 1.5))));
        var cp = coilPts(base, axis, hh.len); hh.coords = cp.coords; hh.norms = cp.norms;
      });
    } else {
      // 3b. α-helix cluster as a herringbone stack: helices stacked ~10 Å apart along
      //     one axis, consecutive ones tilted by OPPOSITE angles so each adjacent pair
      //     CROSSES. Native helix packing spans the whole 15–90° range (parallel/
      //     antiparallel bundles through steep crossings), so we draw the crossing
      //     angle per fold from that range rather than fixing it — reproducing the
      //     native distribution, not just its median. Stack spacing keeps it clash-free.
      var nb = coreHel.length, STEPz = 10;
      var thBase = (16 + Math.random() * 70) * Math.PI / 360;      // per-fold crossing 16–86° ⇒ ±half
      coreHel.forEach(function (hh, hi) {
        var th = (hi % 2 ? -thBase : thBase) + (Math.random() * 2 - 1) * 0.1;
        var base = V((Math.random() * 2 - 1) * 2.5, (Math.random() * 2 - 1) * 2.5,
          (hi - (nb - 1) / 2) * STEPz);
        var cp = coilPts(base, vnorm(V(Math.sin(th), Math.cos(th), 0)), hh.len);
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

    // thread the chain along the best order. Each connecting loop is a circular arc
    //   with segments of EXACTLY 3.8 Å (the ideal Cα-Cα virtual-bond length), so
    //   loop residues — and the SSE↔loop junctions — keep correct backbone spacing.
    //   The arc bulges outward when the gap is short (a tight turn); it flattens as
    //   the gap approaches the straight length. Segment count is the fewest that can
    //   span the gap at 3.8 Å (min 2 loop residues), giving native-like short turns.
    function vdot3(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
    function solveBeta(ratio, m) {                    // sin(m·b)/sin(b) = ratio, b∈(0,π/m)
      var lo = 1e-5, hi = Math.PI / m - 1e-5;         // ratio decreases monotonically in b
      for (var it = 0; it < 44; it++) {
        var b = (lo + hi) / 2;
        if (Math.sin(m * b) / Math.sin(b) > ratio) lo = b; else hi = b;
      }
      return (lo + hi) / 2;
    }
    var P = [], T = [], N = [], U = [], lastPos = null, lastN = V(0, 0, 1), SB = 3.8;
    best.order.forEach(function (oi) {
      var c = elems[oi].coords.slice(), nrms = elems[oi].norms.slice(), ax = elems[oi].axis || null;
      if (lastPos === null) { if (best.fr) { c.reverse(); nrms.reverse(); } }
      else {
        if (vlen(vsub(c[c.length - 1], lastPos)) < vlen(vsub(c[0], lastPos))) { c.reverse(); nrms.reverse(); }
        var entry = c[0], entryN = nrms[0], gap = vlen(vsub(entry, lastPos));
        var m = Math.max(3, Math.min(9, Math.ceil(gap / SB) + 1));   // # segments (loop residues = m-1)
        var u = vscale(vsub(entry, lastPos), 1 / (gap || 1));
        var w = vsub(vscale(vadd(lastPos, entry), 0.5), sheetC);     // bulge outward from core
        w = vsub(w, vscale(u, vdot3(w, u)));                         // ⟂ to the chord
        w = vlen(w) > 1e-3 ? vnorm(w) : vnorm(vcross(u, Math.abs(u.y) < 0.9 ? V(0, 1, 0) : V(1, 0, 0)));
        var b = solveBeta(gap / SB, m), R = SB / (2 * Math.sin(b)), Phi = 2 * m * b;
        var Cen = vsub(vscale(vadd(lastPos, entry), 0.5), vscale(w, R * Math.cos(Phi / 2)));
        for (var q = 1; q <= m - 1; q++) {
          var an = -Phi / 2 + q * (Phi / m);
          P.push(vadd(Cen, vadd(vscale(w, R * Math.cos(an)), vscale(u, R * Math.sin(an))))); T.push('L');
          var ff = q / m;
          N.push(vnorm(vadd(vscale(lastN, 1 - ff), vscale(entryN, ff))));
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
    for (i = 0; i < n; i++) pts.push({ p: Pc[i], t: T[i], n: N[i], u: U[i] });  // n = face-normal, u = strand axis
    return { pairs: pairs, pts: pts, sep: SEP };   // inter-strand spacing (scaled) for ribbon width
  }

  function deriveContacts(P, T) {
    var n = P.length, pairs = [], CB = [], i, j;
    for (i = 0; i < n; i++) {
      var vv = V(0, 0, 0);
      if (i > 0) vv = vadd(vv, vsub(P[i], P[i - 1]));
      if (i < n - 1) vv = vadd(vv, vsub(P[i], P[i + 1]));
      var dd = vlen(vv) > 1e-6 ? vnorm(vv) : V(0, 0, 1);
      CB.push(vadd(P[i], vscale(dd, CBOFF[T[i]] || 3.5)));
    }
    for (i = 0; i < n; i++) for (j = i + 3; j < n; j++) {
      if (vlen(vsub(CB[i], CB[j])) >= CBCUT(T[i], T[j])) continue;
      var kind = (T[i] === 'E' && T[j] === 'E') ? 'beta' : (T[i] === 'H' && T[j] === 'H') ? 'helix' : 'tert';
      pairs.push({ i: i, j: j, kind: kind });
    }
    return pairs;
  }

  // Cα minimiser: drag Rg down (pull each Cα toward the centroid) while HARMONIC restraints
  //   hold the local structure — bonds (3.8 Å), intra-SSE distances (helix/strand shape),
  //   and β-ladder pairings (the sheet H-bonds) — plus a soft clash repulsion so the fold
  //   compacts instead of collapsing. Mutates pts[i].p in place. Restraints are snapshot
  //   from the STARTING structure, so a native (already compact) barely moves — its SSEs
  //   and pairings are held; a loose de-novo fold tightens toward native Rg.

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

  function proteinTrace(pts, canvas, sep) {
    var ctx = canvas.getContext('2d');
    var rawSep = sep || 4.8;                // inter-strand spacing in Å (fold is in Å)
    var SEPw = 0.16;                        // set per-fold in setFold (rawSep / fold-radius)
    var DPR = Math.min(2, window.devicePixelRatio || 1);
    var BG = DARK ? [25, 21, 16] : [250, 247, 240];
    var COL = { H: [215, 90, 69], E: [78, 127, 196], L: DARK ? [150, 142, 126] : [140, 133, 118] };
    // DEBUG-sphere palette: deliberately DIFFERENT hues from the ribbon (COL) so a Cα
    //   sphere's colour reports its INTENDED secondary structure independently — if a
    //   sphere's colour disagrees with the ribbon shape it sits on, the rendering (not
    //   the geometry) is off. Bright/saturated so they read on top of any ribbon.
    var DBGCOL = { H: [255, 40, 120], E: [40, 220, 120], L: [255, 210, 30] };
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
    var fine = [], caDbg = [], DEBUG_CA = false;   // DEBUG_CA: draw a sphere at every Cα (rendering vs geometry check)
    var cbDbg = [], DEBUG_CB = false;   // DEBUG_CB: draw the Cα→virtual-Cβ stick (the side-chain direction the contact test uses)
    // through-space connectors driven by the contact map: a set of PINNED pairs (clicked,
    //   accent colour) plus one transient HOVER pair (preview, cooler colour).
    var links = { pins: [], hover: null };
    function setFold(pp, sepArg) {
      if (sepArg) rawSep = sepArg;
      var n = pp.length, i, k;

      // The fold arrives in Å; fit it to the viewport here (the one place scale is
      //   applied). Radius = farthest Cα from the centre; normalise coords to unit
      //   radius and express the ribbon width as rawSep/radius, so all the projection
      //   math below is scale-independent.
      var maxr = 0; pp.forEach(function (q) { var d = vlen(q.p); if (d > maxr) maxr = d; }); maxr = maxr || 1;
      SEPw = rawSep / maxr;
      // Face-normal per residue comes straight from buildFold (exact construction
      //   geometry): strand → sheet normal, helix → rotating radial, loop → lerp.
      //   No fragile re-derivation from near-straight Cα here.
      var sp = pp.map(function (q) { return vscale(q.p, 1 / maxr); });
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
        // Clamp SSE end tangents. Catmull-Rom uses the neighbour beyond each end as a
        //   control point; at an SSE's terminal span that neighbour is a LOOP Cα off the
        //   SSE axis, so the centreline hooks sideways at the tip. When the hook radius is
        //   below the ribbon half-width the inner edge folds over the outer one → an
        //   X/arrowhead at every strand tip. Reflect the outside control point so the
        //   spline keeps the SSE's own direction to the tip. (Loop spans keep their real
        //   neighbours so the tube still meets the SSE smoothly.)
        if (pp[i].t !== 'L') {
          if (!pp[i - 1] || pp[i - 1].t !== pp[i].t) p0 = vadd(p1, vsub(p1, p2));       // extrapolate backward
          if (!pp[i + 2] || pp[i + 2].t !== pp[i + 1].t) p3 = vadd(p2, vsub(p2, p1));   // extrapolate forward
        }
        // A span joining two residues of DIFFERENT type is a transition. Since elements
        //   are always separated by a loop, every transition is SSE↔loop — and it must be
        //   drawn as the LOOP (round tube), so the flat SSE ribbon ends exactly at the
        //   SSE's terminal Cα and the tube bridges Cα→Cα. Typing the span by the earlier
        //   residue (pp[i]) instead drew the strand-leaving-into-turn span as sheet.
        var segT = (pp[i].t === 'L' || pp[i + 1].t === 'L') ? 'L' : pp[i].t;
        for (var s2 = 0; s2 < SUB; s2++) {
          var f = s2 / SUB;
          // The point sitting exactly ON residue i (f=0) keeps residue i's OWN SS, so an
          //   SSE's terminal Cα stays part of the SSE ribbon (the flat ribbon reaches the
          //   true tip); interior transition points (f>0) are the loop tube.
          var pt = s2 === 0 ? pp[i].t : segT;
          out.push({
            p: cr(p0, p1, p2, p3, f), t: pt,
            w: WID[i] * (1 - f) + WID[i + 1] * f,
            n: vnorm(vadd(vscale(Ns[i], 1 - f), vscale(Ns[i + 1], f))),
            u: pt === 'L' ? null : pp[i].u   // strand long axis (constant per strand); null for loop/helix
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
      caDbg = pp.map(function (q, idx) { return { p: vscale(q.p, 1 / maxr), t: q.t }; });   // TRUE (pleated) Cα for debug spheres
      // virtual Cβ per residue (same construction as the contact test): bisector of the
      //   two Cα bonds, CBOFF[ss] Å out from the Cα — drawn as a debug stick.
      cbDbg = caDbg.map(function (q, idx) {
        var p = q.p, vv = V(0, 0, 0);
        if (idx > 0) vv = vadd(vv, vsub(p, caDbg[idx - 1].p));
        if (idx < caDbg.length - 1) vv = vadd(vv, vsub(p, caDbg[idx + 1].p));
        var dd = vlen(vv) > 1e-6 ? vnorm(vv) : V(0, 0, 1);
        return vadd(p, vscale(dd, (CBOFF[q.t] || 3.5) / maxr));
      });
    }
    setFold(pts);
    canvas.__setFold = setFold;   // used by the regenerate button
    canvas.__draw = function () { draw(M); };   // force a repaint (e.g. live minimiser under reduced-motion)
    // Set the connectors: pins = array of {i,j} (pinned), hover = {i,j} or null (preview).
    //   Under reduced motion the auto-spin loop isn't repainting, so force a draw.
    canvas.__setLinks = function (pins, hover) {
      links.pins = pins || [];
      links.hover = (hover && hover.i !== hover.j) ? hover : null;
      if (reduce) draw(M);
    };

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
        var rc = rot(q.p), rs = rot(q.s), rn = rot(q.n), w = q.w, pe = 1 / (1.9 - rc.z * 0.55);
        return {
          rc: rc, rs: rs, rn: rn, C: proj(rc), pe: pe, w: w, z: rc.z, t: q.t,
          L: proj({ x: rc.x + rs.x * w, y: rc.y + rs.y * w, z: rc.z + rs.z * w }),
          Rr: proj({ x: rc.x - rs.x * w, y: rc.y - rs.y * w, z: rc.z - rs.z * w })
        };
      });
      // Primitives painted back-to-front. Each contiguous SSE run is ONE filled ribbon
      //   polygon (down the L edge, back up the R edge) — a single path has no internal
      //   quad seams and can't be sliced open by another primitive sorting between its
      //   segments, which was breaking the sheet edges. Loops stay per-segment round
      //   tubes (a flat loop ribbon would twist between the flanking SSE normals and
      //   read as detached; the tubes' round caps overlap so they never break).
      var loopD = SEPw * 0.22;                      // constant loop-tube diameter
      var prims = [];
      k = 0;
      while (k < pr.length - 1) {
        // A segment is a loop tube if EITHER endpoint is a loop point, so the flat ribbon
        //   spans exactly an SSE's own Cα (first→last) and the tube bridges terminal-Cα→
        //   terminal-Cα through the turn; they SHARE the boundary Cα → seamless junction.
        if (pr[k].t === 'L' || pr[k + 1].t === 'L') {
          prims.push({ tube: 1, a: pr[k].C, b: pr[k + 1].C, z: (pr[k].z + pr[k + 1].z) / 2, t: 'L', lw: loopD * (pr[k].pe + pr[k + 1].pe) / 2 * R });
          k++;
        } else if (pr[k].t === 'H') {
          // HELIX: flat ribbon, one quad per segment, depth-sorted so the spiral occludes
          //   itself (near turns over far turns).
          prims.push({ ribbon: [pr[k], pr[k + 1]], z: (pr[k].z + pr[k + 1].z) / 2, t: 'H' });
          k++;
        } else {                                    // STRAND: one continuous polygon (clean parallel edges, no seams)
          var start = k, zs = 0, cnt = 0, ty = pr[k].t;
          while (k < pr.length - 1 && pr[k + 1].t !== 'L' && pr[k + 1].t === ty) { zs += (pr[k].z + pr[k + 1].z) / 2; cnt++; k++; }
          prims.push({ ribbon: pr.slice(start, k + 1), z: zs / cnt, t: ty });
        }
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
          // STRAND: per-segment quads, internally depth-sorted and painted as one group.
          //   Each quad is convex so it always fills — unlike a single ribbon polygon, which
          //   self-intersects when the pleated edges weave at oblique angles and leaves
          //   zero-winding HOLES ("missing faces"). Grouped so nothing interleaves (no seams).
          var rp = g.ribbon, qi, quads = [];
          for (qi = 0; qi < rp.length - 1; qi++) quads.push([rp[qi], rp[qi + 1], (rp[qi].z + rp[qi + 1].z) / 2]);
          quads.sort(function (m, o) { return m[2] - o[2]; });
          ctx.lineWidth = 1;
          quads.forEach(function (q) {
            ctx.beginPath();
            ctx.moveTo(q[0].L.x, q[0].L.y); ctx.lineTo(q[1].L.x, q[1].L.y);
            ctx.lineTo(q[1].Rr.x, q[1].Rr.y); ctx.lineTo(q[0].Rr.x, q[0].Rr.y);
            ctx.closePath(); ctx.fill(); ctx.stroke();
          });
        }
      });
      // DEBUG: a small sphere at every Cα, painted back-to-front on top of the ribbon,
      //   coloured by INTENDED SS from a distinct bright palette (helix magenta / strand
      //   green / loop yellow — deliberately unlike the ribbon's coral/blue/grey). The
      //   sphere colour is the geometry's ground truth; if it disagrees with the ribbon
      //   shape beneath it, the RENDERING is off, not the coordinates.
      if (DEBUG_CA) {
        caDbg.map(function (q) { var rc = rot(q.p); return { P: proj(rc), z: rc.z, t: q.t, pe: 1 / (1.9 - rc.z * 0.55) }; })
          .sort(function (m, o) { return m.z - o.z; })
          .forEach(function (d) {
            var near = (d.z + 1) / 2; near = near < 0 ? 0 : near > 1 ? 1 : near;
            var b = 0.55 + 0.45 * near, c = DBGCOL[d.t];   // dim for depth without desaturating
            ctx.beginPath(); ctx.arc(d.P.x, d.P.y, Math.max(1.5, 3 * d.pe), 0, 6.2832);
            ctx.fillStyle = 'rgb(' + Math.round(c[0] * b) + ',' + Math.round(c[1] * b) + ',' + Math.round(c[2] * b) + ')'; ctx.fill();
            ctx.lineWidth = 0.8; ctx.strokeStyle = DARK ? '#000' : '#fff'; ctx.stroke();
          });
      }
      // DEBUG_CB: a stick from each Cα to its virtual Cβ (the side-chain direction used
      //   to derive contacts) + a dot at the Cβ tip.
      if (DEBUG_CB) {
        ctx.lineWidth = 1.2; ctx.lineCap = 'round';
        for (var ib = 0; ib < cbDbg.length; ib++) {
          var a = proj(rot(caDbg[ib].p)), b2 = proj(rot(cbDbg[ib]));
          ctx.strokeStyle = DARK ? '#7fd4ff' : '#0a6cff';
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b2.x, b2.y); ctx.stroke();
          ctx.fillStyle = DARK ? '#7fd4ff' : '#0a6cff';
          ctx.beginPath(); ctx.arc(b2.x, b2.y, 1.6, 0, 6.2832); ctx.fill();
        }
      }
      // Contact-map connectors: through-space links between residue pairs, painted last so
      //   they read on top at any depth (halo + dashed colour + end knobs). Pinned pairs use
      //   the accent colour; the hovered pair uses a cooler preview colour.
      function drawLink(pair, col) {
        if (!pair || !caDbg[pair.i] || !caDbg[pair.j]) return;
        var A = proj(rot(caDbg[pair.i].p)), B = proj(rot(caDbg[pair.j].p));
        ctx.lineCap = 'round';
        ctx.lineWidth = 4.5; ctx.strokeStyle = DARK ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.8)';
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
        ctx.lineWidth = 1.8; ctx.strokeStyle = col; ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
        ctx.setLineDash([]);
        [A, B].forEach(function (P) {
          ctx.beginPath(); ctx.arc(P.x, P.y, 3.6, 0, 6.2832);
          ctx.fillStyle = col; ctx.fill();
          ctx.lineWidth = 1; ctx.strokeStyle = DARK ? '#000' : '#fff'; ctx.stroke();
        });
      }
      var ACC = DARK ? '#ffd23c' : '#c2481f', HOV = DARK ? '#8fb6ff' : '#2f6ea8';
      links.pins.forEach(function (p) { drawLink(p, ACC); });
      if (links.hover) {
        var h = links.hover, dup = links.pins.some(function (p) { return p.i === h.i && p.j === h.j; });
        if (!dup) drawLink(h, HOV);
      }
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
        if (!dragging && !canvas.__nospin) M = mMul(mRotY(dt / 9000), M);   // gentle auto-spin when idle (paused during minimise)
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

  // Map cursor position over the contact-map SVG to a residue pair (row = i, col = j)
  //   and ask the 3D canvas to draw the through-space connector between them. The SVG
  //   is a square viewBox (n·pitch − gap) drawn xMinYMid/meet, so it scales uniformly:
  //   scale = min(rendered w,h)/W, left-aligned, vertically centred.
  // Feedback on the map itself: hovering outlines a cell (and its symmetric mirror) in the
  //   HOVER colour and previews its connector; clicking toggles the pair into a set of PINS
  //   drawn in the ACCENT colour. Multiple pairs can be pinned at once; click a pinned cell
  //   again to release it. Markers are rebuilt each change (counts are tiny).
  function wireHover(svg, n, cell, gap, canvas) {
    var pitch = cell + gap, W = n * pitch - gap;
    var ACC = DARK ? '#ffd23c' : '#c2481f', HOV = DARK ? '#8fb6ff' : '#2f6ea8';
    var layer = document.createElementNS(NS, 'g');
    layer.setAttribute('pointer-events', 'none'); svg.appendChild(layer);
    function rectAt(i, j, col, sw, fillOp) {
      var r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', j * pitch); r.setAttribute('y', i * pitch);
      r.setAttribute('width', cell); r.setAttribute('height', cell); r.setAttribute('rx', '1.5');
      r.setAttribute('fill', col); r.setAttribute('fill-opacity', fillOp);
      r.setAttribute('stroke', col); r.setAttribute('stroke-width', sw);
      layer.appendChild(r);
    }
    function mark(p, col, sw, fillOp) {
      rectAt(p.i, p.j, col, sw, fillOp);
      if (p.i !== p.j) rectAt(p.j, p.i, col, sw, fillOp);
    }
    var pins = [], hover = null;
    function idxOf(p) { for (var k = 0; k < pins.length; k++) if (pins[k].i === p.i && pins[k].j === p.j) return k; return -1; }
    function cellAt(e) {
      var rect = svg.getBoundingClientRect();
      var scale = Math.min(rect.width, rect.height) / W;
      if (!(scale > 0)) return null;
      var vx = (e.clientX - rect.left) / scale;
      var vy = (e.clientY - rect.top - (rect.height - W * scale) / 2) / scale;
      var j = Math.floor(vx / pitch), i = Math.floor(vy / pitch);
      if (i < 0 || j < 0 || i >= n || j >= n || i === j) return null;
      return { i: i, j: j };
    }
    function render() {
      layer.textContent = '';
      pins.forEach(function (p) { mark(p, ACC, 1.6, 0.28); });
      if (hover && idxOf(hover) < 0) mark(hover, HOV, 1.3, 0.2);   // don't double-mark a pinned cell
      if (canvas.__setLinks) canvas.__setLinks(pins, hover);
    }
    svg.style.cursor = 'pointer';
    svg.addEventListener('pointermove', function (e) { hover = cellAt(e); render(); });
    svg.addEventListener('pointerleave', function () { hover = null; render(); });
    svg.addEventListener('click', function (e) {
      var p = cellAt(e);
      if (!p) return;
      var k = idxOf(p);
      if (k >= 0) pins.splice(k, 1); else pins.push(p);   // toggle this pair in/out of the pinned set
      hover = p; render();
    });
  }

  // ---- contact page: one fold drives the 3D trace (left) and its contact map (right)
  function boot() {
    var canvas = document.querySelector('.struct-3d canvas');
    var mapEl = document.querySelector('.contact-map');
    if (!canvas && !mapEl) return;
    var started = false;
    function regen() {
      var fold = buildFold();
      var types = fold.pts.map(function (p) { return p.t; });
      if (mapEl) {
        var pairs = deriveContacts(fold.pts.map(function (p) { return p.p; }), types);
        mapEl.textContent = '';
        var mapSvg = contactMap(pairs, types, 7);
        mapEl.appendChild(mapSvg);
        if (canvas) wireHover(mapSvg, types.length, 7, 1, canvas);
      }
      if (canvas) {
        if (!started) { proteinTrace(fold.pts, canvas, fold.sep); started = true; }
        else if (canvas.__setFold) { canvas.__setFold(fold.pts, fold.sep); if (canvas.__setLinks) canvas.__setLinks([], null); if (canvas.__draw) canvas.__draw(); }
      }
    }
    regen();
    var btn = document.querySelector('.regen-btn');
    if (btn) btn.addEventListener('click', regen);
  }
  if (document.readyState !== 'loading') boot();
  else document.addEventListener('DOMContentLoaded', boot);
})();
