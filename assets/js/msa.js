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

  // ---- secondary-structure model shared by the contact map and the 3D trace ----
  function buildSSE(n) {
    var sse = [], pos = 1 + ((Math.random() * 3) | 0);
    while (pos < n - 6) {
      var isH = Math.random() < 0.55;
      var len = isH ? 8 + ((Math.random() * 10) | 0) : 4 + ((Math.random() * 4) | 0);
      if (pos + len > n - 2) break;
      sse.push({ h: isH, s: pos, e: pos + len - 1 });
      pos += len + 2 + ((Math.random() * 3) | 0);
    }
    return sse;
  }

  // Deterministic N→C fold: lay the β-strands as adjacent sheet rows (correct
  // register + direction so their contacts form by construction), pack helices
  // against an anchor, connect with interpolated loops. Returns the 3D Cα points
  // AND the contact list — the SAME contacts the map draws, so they always match.
  // No iterative relaxation, so it's cheap.
  function buildFold(sse, n) {
    var T = new Array(n); for (var t = 0; t < n; t++) T[t] = 'L';
    sse.forEach(function (x) { for (var i = x.s; i <= x.e && i < n; i++) T[i] = x.h ? 'H' : 'E'; });

    var strands = sse.filter(function (x) { return !x.h; });
    var helices = sse.filter(function (x) { return x.h; });
    for (var a = strands.length - 1; a > 0; a--) {           // shuffled order = spatial sheet order
      var b = (Math.random() * (a + 1)) | 0, tmp = strands[a]; strands[a] = strands[b]; strands[b] = tmp;
    }

    var STEP = 3.4, SEP = 4.8, pairs = [], place = {}, dirOf = [], xoffOf = [];
    for (var m = 0; m < strands.length; m++) {
      var Q = strands[m];
      if (m === 0) { dirOf[m] = 1; xoffOf[m] = 0; continue; }
      var P = strands[m - 1], anti = Math.random() < 0.7;
      dirOf[m] = anti ? -dirOf[m - 1] : dirOf[m - 1];
      var q0 = anti ? Q.e : Q.s;                              // Q residue that pairs with P.s
      xoffOf[m] = xoffOf[m - 1] - dirOf[m] * (q0 - Q.s) * STEP;
      var L = Math.min(P.e - P.s, Q.e - Q.s);
      for (var k = 0; k <= L; k++) pairs.push({ i: P.s + k, j: anti ? Q.e - k : Q.s + k, kind: 'beta' });
    }
    strands.forEach(function (S, mi) {
      for (var res = S.s; res <= S.e && res < n; res++) {
        var xp = xoffOf[mi] + dirOf[mi] * (res - S.s) * STEP;
        place[res] = V(xp, mi * SEP, Math.sin(xp * 0.12 + mi * 0.5) * 1.6); // gentle sheet twist
      }
    });
    var sheetC = V(0, 0, 0), cnt = 0;
    for (var rk in place) { sheetC = vadd(sheetC, place[rk]); cnt++; }
    sheetC = cnt ? vscale(sheetC, 1 / cnt) : sheetC;

    helices.forEach(function (H, hi) {
      var keys = Object.keys(place), anchorRes = keys.length ? (keys[(Math.random() * keys.length) | 0] | 0) : null;
      var anchor = anchorRes != null ? place[anchorRes] : sheetC;
      var hMid = (H.s + H.e) >> 1;
      if (anchorRes != null && Math.abs(hMid - anchorRes) > 4) {   // tertiary packing contact
        pairs.push({ i: hMid, j: anchorRes, kind: 'tert' });
        pairs.push({ i: hMid + 1, j: anchorRes, kind: 'tert' });
      }
      var axis = vnorm(V(1, hi % 2 ? 0.4 : -0.4, 0.25));
      var u = vnorm(vcross(axis, V(0, 1, 0.01))), w = vnorm(vcross(axis, u));
      var base = vadd(anchor, V(0, (hi % 2 ? -1 : 1) * SEP, 7 + hi * 5)); // packed off the sheet face
      var Hlen = H.e - H.s;
      for (var kk = 0; kk <= Hlen && H.s + kk < n; kk++) {
        var ph = kk * 1.75, along = (kk - Hlen / 2) * 1.5;
        place[H.s + kk] = vadd(base, vadd(vscale(axis, along),
          vadd(vscale(u, Math.cos(ph) * 2.3), vscale(w, Math.sin(ph) * 2.3))));
      }
    });

    var i = 0;                                               // loops: interpolate between placed ends
    while (i < n) {
      if (place[i]) { i++; continue; }
      var j = i; while (j < n && !place[j]) j++;
      var prev = (i - 1 >= 0 && place[i - 1]) ? place[i - 1] : (place[j] || sheetC);
      var next = (j < n && place[j]) ? place[j] : prev;
      for (var q = i; q < j; q++) {
        var f = (q - i + 1) / (j - i + 1);
        place[q] = vadd(vadd(vscale(prev, 1 - f), vscale(next, f)), V(0, 0, Math.sin(f * Math.PI) * 3));
      }
      i = j;
    }
    if (!place[0]) place[0] = place[1] || sheetC;

    var P2 = []; for (i = 0; i < n; i++) P2.push(place[i] || sheetC);
    var ctr = V(0, 0, 0); P2.forEach(function (p) { ctr = vadd(ctr, p); }); ctr = vscale(ctr, 1 / n);
    var maxr = 0; P2 = P2.map(function (p) { var d = vsub(p, ctr); maxr = Math.max(maxr, vlen(d)); return d; });
    var sc = 1 / (maxr || 1);
    var pts = []; for (i = 0; i < n; i++) pts.push({ p: vscale(P2[i], sc), t: T[i] });
    return { pairs: pairs, pts: pts };
  }

  // Contact map from the SSE model + shared contact list: thin backbone diagonal,
  // helices thickening it (i,i+3 / i,i+4), β ladders and tertiary blobs off-diagonal.
  function contactMap(sse, pairs, n, cell) {
    var gap = 1, pitch = cell + gap;
    var svg = svgEl(n, n, cell, gap);
    var grid = {};
    function put(i, j, color, op) {
      if (i < 0 || j < 0 || i >= n || j >= n) return;
      grid[i * n + j] = { c: color, o: op };
      grid[j * n + i] = { c: color, o: op };
    }
    for (var i = 0; i < n; i++) { put(i, i, INK, 1); put(i, i + 1, INK, 0.8); }
    sse.forEach(function (x) {
      if (!x.h) return;
      for (var a = x.s; a <= x.e - 3; a++) put(a, a + 3, RES[3], 0.9);
      for (a = x.s; a <= x.e - 4; a++) put(a, a + 4, RES[3], 0.5);
    });
    pairs.forEach(function (c) {
      if (c.kind === 'beta') {
        put(c.i, c.j, RES[1], 0.95); put(c.i, c.j + 1, RES[1], 0.4); put(c.i + 1, c.j, RES[1], 0.4);
      } else {
        for (var di = -1; di <= 1; di++) for (var dj = -1; dj <= 1; dj++)
          if (Math.random() < 0.7) put(c.i + di, c.j + dj, RES[2], 0.5);
      }
    });
    for (var z = 0, nz = (n * 0.05) | 0; z < nz; z++) {
      var ni = (Math.random() * n) | 0, nj = (Math.random() * n) | 0;
      if (Math.abs(ni - nj) > 3) put(ni, nj, RES[4], 0.2);
    }
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
    function draw(theta, tilt) {
      var s = size();
      if (canvas.width !== Math.round(s * DPR)) { canvas.width = canvas.height = Math.round(s * DPR); }
      var R = s * 0.86, cx = s / 2, cy = s / 2, ct = Math.cos(theta), st = Math.sin(theta), tl = tilt, cT = Math.cos(tl), sT = Math.sin(tl);
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.clearRect(0, 0, s, s);
      var sc = pts.map(function (q) {
        var x = q.p.x * ct + q.p.z * st, z = -q.p.x * st + q.p.z * ct, y = q.p.y;
        var y2 = y * cT - z * sT, z2 = y * sT + z * cT, pe = 1 / (1.9 - z2 * 0.55);
        return { x: cx + x * R * pe, y: cy + y2 * R * pe, z: z2, t: q.t, w: pe };
      });
      var segs = [], k;
      for (k = 0; k < sc.length - 1; k++) segs.push({ a: sc[k], b: sc[k + 1], z: (sc[k].z + sc[k + 1].z) / 2, t: sc[k + 1].t });
      segs.sort(function (m, o) { return m.z - o.z; });
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      segs.forEach(function (g) {
        var near = (g.z + 1) / 2;
        ctx.strokeStyle = shade(COL[g.t], near < 0 ? 0 : near > 1 ? 1 : near);
        ctx.lineWidth = (g.t === 'L' ? 3.2 : 6.5) * ((g.a.w + g.b.w) / 2);
        ctx.beginPath(); ctx.moveTo(g.a.x, g.a.y); ctx.lineTo(g.b.x, g.b.y); ctx.stroke();
      });
    }
    resize();
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var rotY = 0.5, rotX = -0.5, dragging = false, lx = 0, ly = 0;
    function clampX(v) { return v < -1.45 ? -1.45 : v > 1.45 ? 1.45 : v; }
    canvas.style.touchAction = 'none';
    var stage = canvas.closest ? canvas.closest('.viz-stage') : null;
    function isMain() { return !stage || stage.getAttribute('data-main') === 'struct'; }
    canvas.addEventListener('pointerdown', function (e) {
      if (!isMain()) return;                 // when inset, let the click expand instead of rotate
      dragging = true; lx = e.clientX; ly = e.clientY;
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
      canvas.style.cursor = 'grabbing'; e.preventDefault();
    });
    canvas.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      rotY += (e.clientX - lx) * 0.011; rotX = clampX(rotX + (e.clientY - ly) * 0.011);
      lx = e.clientX; ly = e.clientY;
      if (reduce) draw(rotY, rotX);
    });
    function end() { dragging = false; canvas.style.cursor = 'grab'; }
    canvas.addEventListener('pointerup', end);
    canvas.addEventListener('pointercancel', end);
    if (reduce) { draw(rotY, rotX); }
    else {
      var last = performance.now();
      (function loop(now) {
        var dt = now - last; last = now;
        if (!dragging) rotY += dt / 9000;      // gentle auto-spin when idle
        draw(rotY, rotX);
        canvas.__raf = requestAnimationFrame(loop);
      })(performance.now());
    }
    window.addEventListener('resize', function () { resize(); draw(rotY, rotX); });
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
    // contact page: one fold drives both the 3D trace and its contact map,
    // shown as a main view + inset that you can click to swap.
    var stage = document.querySelector('.viz-stage');
    if (stage) {
      var N = 46, sse = buildSSE(N), fold = buildFold(sse, N);
      var canvas = stage.querySelector('.struct-3d canvas');
      var mapEl = stage.querySelector('.contact-map');
      if (canvas) proteinTrace(fold.pts, canvas);
      if (mapEl) { mapEl.textContent = ''; mapEl.appendChild(contactMap(sse, fold.pairs, N, 7)); }
      var cap = document.querySelector('.viz-cap');
      function setMain(which) {
        stage.setAttribute('data-main', which);
        if (cap) cap.textContent = (which === 'struct' ? 'predicted structure' : 'contact map') + ' · click the inset to swap';
      }
      var sfig = stage.querySelector('.struct-3d');
      if (sfig) sfig.addEventListener('click', function () { setMain('struct'); });
      if (mapEl) mapEl.addEventListener('click', function () { setMain('map'); });
      setMain(stage.getAttribute('data-main') || 'struct');
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
