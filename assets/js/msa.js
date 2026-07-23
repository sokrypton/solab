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
    var STEP = 3.4, SEP = 4.8;

    // 1. topology — always a mixed α/β fold
    var elems = [], e;
    function coil(len) { return { h: true, len: len }; }
    function strand(len) { return { h: false, len: len }; }
    for (e = 0; e < 4 + ((Math.random() * 2) | 0); e++)
      elems.push(Math.random() < 0.5 ? coil(9 + ((Math.random() * 7) | 0)) : strand(5 + ((Math.random() * 3) | 0)));
    // guarantee both a sheet (≥2 paired strands) and at least one helix
    var nStr = elems.filter(function (x) { return !x.h; }).length;
    for (var f = 0; nStr < 2 && f < elems.length; f++) if (elems[f].h) { elems[f] = strand(5 + ((Math.random() * 3) | 0)); nStr++; }
    if (!elems.some(function (x) { return x.h; })) elems[elems.length - 1] = coil(11 + ((Math.random() * 6) | 0));

    var strandEls = elems.filter(function (x) { return !x.h; });
    var helixEls = elems.filter(function (x) { return x.h; });
    var HR = 2.3, HRISE = 1.5, HTURN = 1.75;             // idealized α-helix
    function coilPts(base, axis, len) {
      var u = vnorm(vcross(axis, Math.abs(axis.z) < 0.9 ? V(0, 0, 1) : V(1, 0, 0)));
      var w = vnorm(vcross(axis, u)), out = [];
      for (var tt = 0; tt < len; tt++) {
        var ph = tt * HTURN, along = (tt - (len - 1) / 2) * HRISE;
        out.push(vadd(base, vadd(vscale(axis, along), vadd(vscale(u, Math.cos(ph) * HR), vscale(w, Math.sin(ph) * HR)))));
      }
      return out;
    }
    var sheetC = V(0, 0, 0);

    if (strandEls.length) {
      // 2. β-sheet: strands as adjacent meander rows (alternating direction), curled
      var CURL = 0.28, Rc = SEP / CURL;
      strandEls.forEach(function (s, r) {
        var dir = r % 2 === 0 ? 1 : -1, cy = Rc * Math.sin(r * CURL), cz = Rc * Math.cos(r * CURL);
        s.coords = [];
        for (var tt = 0; tt < s.len; tt++) {
          var x = (tt - (s.len - 1) / 2) * STEP * dir;
          s.coords.push(V(x, cy, cz + Math.sin(x * 0.09) * 0.7));
        }
      });
      var scnt = 0;
      strandEls.forEach(function (s) { s.coords.forEach(function (p) { sheetC = vadd(sheetC, p); scnt++; }); });
      sheetC = scnt ? vscale(sheetC, 1 / scnt) : sheetC;

      // 3a. pack helices against alternating faces, staggered, close enough to contact
      var faceSlot = { p: 0, n: 0 };
      helixEls.forEach(function (hh, hi) {
        var face = hi % 2 === 0 ? 1 : -1, key = face > 0 ? 'p' : 'n', slot = faceSlot[key]++;
        var yoff = slot === 0 ? 0 : (slot % 2 ? 1 : -1) * Math.ceil(slot / 2) * SEP * 1.7;
        var base = vadd(sheetC, V((Math.random() * 2 - 1) * STEP, yoff, face * 7.2));
        hh.coords = coilPts(base, vnorm(V(1, 0, 0.08)), hh.len);
      });
    } else {
      // 3b. α-helix bundle: up-down helices side by side, spaced ~10 Å so adjacent
      //     helices pack together
      helixEls.forEach(function (hh, hi) {
        var xoff = (hi - (helixEls.length - 1) / 2) * 10.0, flip = hi % 2 === 0 ? 1 : -1;
        hh.coords = coilPts(V(xoff, 0, 0), vnorm(V(0.05, flip, 0)), hh.len);
      });
      var cc = V(0, 0, 0), ct = 0;
      helixEls.forEach(function (hh) { hh.coords.forEach(function (p) { cc = vadd(cc, p); ct++; }); });
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

    // thread the chain along the best order; loops follow the (now short) 3D gaps
    var P = [], T = [], lastPos = null;
    best.order.forEach(function (oi) {
      var c = elems[oi].coords.slice();
      if (lastPos === null) { if (best.fr) c.reverse(); }
      else {
        if (vlen(vsub(c[c.length - 1], lastPos)) < vlen(vsub(c[0], lastPos))) c.reverse();
        var entry = c[0], gap = vlen(vsub(entry, lastPos));
        var cntL = Math.max(2, Math.min(6, Math.round(gap / 3.5)));
        for (var q = 1; q <= cntL; q++) {
          var f = q / (cntL + 1), mid = vadd(vscale(lastPos, 1 - f), vscale(entry, f));
          var out = vsub(mid, sheetC); out = vlen(out) > 0.001 ? vnorm(out) : V(0, 0, 1);
          P.push(vadd(mid, vscale(out, Math.sin(f * Math.PI) * 2.5))); T.push('L');
        }
      }
      for (var r2 = 0; r2 < c.length; r2++) { P.push(c[r2]); T.push(elems[oi].h ? 'H' : 'E'); }
      lastPos = c[c.length - 1];
    });

    // 5. derive contacts from the coordinates (this IS the structure's map):
    //    local helix (i,i+3/4), β pairing, and inter-element packing (helix-helix,
    //    helix-sheet) all fall out of the distance test
    var n = P.length, CUT = 8.5, pairs = [];
    for (var i = 0; i < n; i++) for (var j = i + 3; j < n; j++) {
      if (vlen(vsub(P[i], P[j])) < CUT) {
        var kind = (T[i] === 'H' && T[j] === 'H' && j - i <= 5) ? 'helix'
          : (T[i] === 'E' && T[j] === 'E') ? 'beta' : 'tert';
        pairs.push({ i: i, j: j, kind: kind });
      }
    }

    // 6. center + scale to unit radius
    var ctr = V(0, 0, 0); P.forEach(function (p) { ctr = vadd(ctr, p); }); ctr = vscale(ctr, 1 / n);
    var maxr = 0, Pc = P.map(function (p) { var d = vsub(p, ctr); maxr = Math.max(maxr, vlen(d)); return d; });
    var s = 1 / (maxr || 1), pts = [];
    for (i = 0; i < n; i++) pts.push({ p: vscale(Pc[i], s), t: T[i] });
    return { pairs: pairs, pts: pts };
  }

  // Contact map: ink backbone diagonal + the contacts derived from the fold,
  // coloured by kind (coral helix / blue β / gold tertiary).
  function contactMap(pairs, n, cell) {
    var gap = 1, pitch = cell + gap;
    var svg = svgEl(n, n, cell, gap);
    var grid = {};
    function put(i, j, color, op) {
      if (i < 0 || j < 0 || i >= n || j >= n) return;
      grid[i * n + j] = { c: color, o: op }; grid[j * n + i] = { c: color, o: op };
    }
    for (var i = 0; i < n; i++) { put(i, i, INK, 1); put(i, i + 1, INK, 0.8); }
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

  function proteinTrace(pts, canvas) {
    var ctx = canvas.getContext('2d');
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
    var fine = [];
    function setFold(pp) {
      var n = pp.length, WID = new Array(n), i;
      for (i = 0; i < n; i++) {
        var ty = pp[i].t;
        if (ty === 'H') WID[i] = 0.05;
        else if (ty === 'E') {
          var e = i; while (e + 1 < n && pp[e + 1].t === 'E') e++;
          var fe = e - i;
          WID[i] = fe === 0 ? 0.012 : fe === 1 ? 0.05 : fe === 2 ? 0.066 : 0.042;
        } else WID[i] = 0.018;
      }
      var out = [], SUB = 8;
      for (i = 0; i < n - 1; i++) {
        var p0 = (pp[i - 1] || pp[i]).p, p1 = pp[i].p, p2 = pp[i + 1].p, p3 = (pp[i + 2] || pp[i + 1]).p;
        for (var sIdx = 0; sIdx < SUB; sIdx++) {
          var f = sIdx / SUB;
          out.push({ p: cr(p0, p1, p2, p3, f), t: pp[i].t, w: WID[i] * (1 - f) + WID[i + 1] * f });
        }
      }
      out.push({ p: pp[n - 1].p, t: pp[n - 1].t, w: WID[n - 1] });
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
      var R = s * 0.9, cx = s / 2, cy = s / 2;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.clearRect(0, 0, s, s);
      var sc = fine.map(function (q) {
        var p = q.p, x = M[0] * p.x + M[1] * p.y + M[2] * p.z,
          y = M[3] * p.x + M[4] * p.y + M[5] * p.z,
          z = M[6] * p.x + M[7] * p.y + M[8] * p.z, pe = 1 / (1.9 - z * 0.55);
        return { x: cx + x * R * pe, y: cy - y * R * pe, z: z, t: q.t, w: q.w, pe: pe };
      });
      var segs = [], k;
      for (k = 0; k < sc.length - 1; k++) segs.push({ a: sc[k], b: sc[k + 1], z: (sc[k].z + sc[k + 1].z) / 2, t: sc[k + 1].t, w: (sc[k].w + sc[k + 1].w) / 2, pe: (sc[k].pe + sc[k + 1].pe) / 2 });
      segs.sort(function (m, o) { return m.z - o.z; });
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      segs.forEach(function (g) {
        var near = (g.z + 1) / 2; near = near < 0 ? 0 : near > 1 ? 1 : near;
        ctx.strokeStyle = shade(COL[g.t], near);
        ctx.lineWidth = Math.max(1, g.w * s * g.pe);
        ctx.beginPath(); ctx.moveTo(g.a.x, g.a.y); ctx.lineTo(g.b.x, g.b.y); ctx.stroke();
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

  // Home hero: inline the vector logo, keep the ring static, and orbit each
  // element around the ring centre while it stays upright (outer group spins
  // one way; each element group counter-spins about its own centre → the net
  // motion is a pure orbit, no self-spin).
  function animateHero(el) {
    var src = el.getAttribute('data-svg'); if (!src) return;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var CXR = 487.26, CYR = 354.63;                   // ring centre (inner-circle path)
    fetch(src).then(function (r) { return r.text(); }).then(function (txt) {
      var tmp = document.createElement('div'); tmp.innerHTML = txt;
      var svg = tmp.querySelector('svg'); if (!svg) return;
      [].forEach.call(svg.querySelectorAll('[fill-opacity="0.0"]'), function (nd) { nd.parentNode.removeChild(nd); });
      var g = svg.querySelector('g'); if (!g) return;
      svg.removeAttribute('width'); svg.removeAttribute('height'); svg.setAttribute('class', 'hero-svg');
      el.insertBefore(svg, el.firstChild);            // in the DOM so getBBox works

      var tags = { path: 1, image: 1, rect: 1, circle: 1, ellipse: 1, polygon: 1, polyline: 1, line: 1, g: 1 };
      var nodes = [].slice.call(g.childNodes).filter(function (nd) { return nd.nodeType === 1 && tags[nd.tagName]; });
      var info = nodes.map(function (nd) {
        var b; try { b = nd.getBBox(); } catch (e) { b = { x: CXR, y: CYR, width: 0, height: 0 }; }
        return { n: nd, x: b.x, y: b.y, w: b.width, h: b.height, cx: b.x + b.width / 2, cy: b.y + b.height / 2 };
      });
      var extent = 0;
      info.forEach(function (i) { extent = Math.max(extent, i.w, i.h); });
      // large spans (the ring / annulus) stay static; everything else orbits
      var big = info.filter(function (i) { return i.w > 0.5 * extent || i.h > 0.5 * extent; });
      var els = info.filter(function (i) { return !(i.w > 0.5 * extent || i.h > 0.5 * extent); });

      // cluster element parts into whole elements (union-find on centre distance)
      var D = 78, par = els.map(function (_, i) { return i; });
      function find(a) { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; }
      for (var a = 0; a < els.length; a++) for (var b2 = a + 1; b2 < els.length; b2++) {
        var dx = els[a].cx - els[b2].cx, dy = els[a].cy - els[b2].cy;
        if (dx * dx + dy * dy < D * D) par[find(a)] = find(b2);
      }
      var groups = {};
      els.forEach(function (e, i) { var r = find(i); (groups[r] = groups[r] || []).push(e); });

      // ring radius (for spotting the genes that sit on the genome band)
      var Rring = 0; big.forEach(function (i) { Rring = Math.max(Rring, Math.max(i.w, i.h) / 2); });

      var staticG = document.createElementNS(NS, 'g');   // the genome ring — stays put
      big.forEach(function (i) { staticG.appendChild(i.n); });

      var items = [], maxR = 0;   // each orbiting element group + its centre + mode
      Object.keys(groups).forEach(function (k) {
        var cl = groups[k];
        var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        cl.forEach(function (i) { x0 = Math.min(x0, i.x); y0 = Math.min(y0, i.y); x1 = Math.max(x1, i.x + i.w); y1 = Math.max(y1, i.y + i.h); });
        var gcx = (x0 + x1) / 2, gcy = (y0 + y1) / 2;
        var rad = Math.hypot(gcx - CXR, gcy - CYR);
        maxR = Math.max(maxR, rad + Math.max(x1 - x0, y1 - y0) / 2);
        var eg = document.createElementNS(NS, 'g');
        cl.forEach(function (i) { eg.appendChild(i.n); });
        // genes sit on the genome band → they ride the ring (tangent); everything
        // else orbits but stays upright
        var onRing = Rring > 0 && rad > 0.6 * Rring && rad < 1.08 * Rring;
        items.push({ el: eg, cx: gcx, cy: gcy, tangent: onRing });
      });
      big.forEach(function (i) { maxR = Math.max(maxR, Math.hypot(i.cx - CXR, i.cy - CYR) + Math.max(i.w, i.h) / 2); });

      g.textContent = '';
      g.appendChild(staticG);                       // ring behind
      items.forEach(function (it) { g.appendChild(it.el); });   // elements in front
      var R = maxR + 10;
      svg.setAttribute('viewBox', (CXR - R) + ' ' + (CYR - R) + ' ' + (2 * R) + ' ' + (2 * R));
      var img = el.querySelector('img'); if (img) img.remove();

      // one shared angle drives everything (no drift): orbit about the ring
      // centre, then counter-rotate the uprights about their own centre
      if (!reduce) {
        var PERIOD = 150000, t0 = performance.now();
        (function spin(now) {
          var th = ((now - t0) / PERIOD) * 360;
          items.forEach(function (it) {
            var t = 'rotate(' + th.toFixed(3) + ' ' + CXR + ' ' + CYR + ')';
            if (!it.tangent) t += ' rotate(' + (-th).toFixed(3) + ' ' + it.cx.toFixed(2) + ' ' + it.cy.toFixed(2) + ')';
            it.el.setAttribute('transform', t);
          });
          requestAnimationFrame(spin);
        })(performance.now());
      }
    }).catch(function () {});
  }

  function sectionWord() {
    var a = document.querySelector('.nav-links a.active');
    if (a && a.textContent.trim()) return a.textContent.trim();
    var pt = document.querySelector('.page-title');
    if (pt && pt.textContent.trim()) return pt.textContent.trim().split(/\s+/)[0];
    return 'solab';
  }

  function inject() {
    var word = sectionWord();
    var hero = document.querySelector('.hero-band');
    if (hero && !hero.querySelector('.msa-band')) {
      var hb = document.createElement('div');
      hb.className = 'msa-band'; hb.setAttribute('data-rows', '10'); hb.setAttribute('aria-hidden', 'true');
      hero.appendChild(hb);
    }
    [].forEach.call(document.querySelectorAll('.site-footer'), function (f) {
      if (!f.querySelector('.msa-band')) {
        var b = document.createElement('div');
        b.className = 'msa-band'; b.setAttribute('data-rows', '8'); b.setAttribute('aria-hidden', 'true');
        f.insertBefore(b, f.firstChild);
      }
    });
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
        if (mapEl) { mapEl.textContent = ''; mapEl.appendChild(contactMap(fold.pairs, fold.pts.length, 7)); }
        if (canvas) {
          if (!started) { proteinTrace(fold.pts, canvas); started = true; }
          else if (canvas.__setFold) canvas.__setFold(fold.pts);   // swap fold, keep the running loop
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
