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
          frag.appendChild(cellRect(c, r, pitch, cell, GAP));            // gap "-": solid grey
        } else {
          frag.appendChild(cellRect(c, r, pitch, cell, pick(), 0.55));   // stray residue
        }
      }
    }
    svg.appendChild(frag);
    mark.appendChild(svg);
  }

  // ---- protein contact map (contact page) ----
  // Model a chain of secondary-structure elements, then draw the contacts they
  // imply, the way a real Cβ–Cβ map looks:
  //   - backbone diagonal (thin); helices thicken it (i,i+3 / i,i+4) in coral
  //   - β-strands pair in space -> off-diagonal ladders (anti-parallel = anti-
  //     diagonal, parallel = parallel), a few cells thick, in blue
  //   - a couple of tertiary packing blobs (gold); minimal noise
  // Symmetric, and regenerated each load.
  function contactMap(n, cell) {
    var gap = 1, pitch = cell + gap;
    var svg = svgEl(n, n, cell, gap);
    var grid = {};
    function put(i, j, color, op) {
      if (i < 0 || j < 0 || i >= n || j >= n) return;
      grid[i * n + j] = { c: color, o: op };
      grid[j * n + i] = { c: color, o: op };
    }

    // 1. lay out helices (H) and strands (E) along the chain, loops between
    var sse = [], pos = 1 + ((Math.random() * 3) | 0);
    while (pos < n - 6) {
      var isH = Math.random() < 0.55;
      var len = isH ? 8 + ((Math.random() * 10) | 0) : 4 + ((Math.random() * 4) | 0);
      if (pos + len > n - 2) break;
      sse.push({ h: isH, s: pos, e: pos + len - 1 });
      pos += len + 2 + ((Math.random() * 3) | 0);
    }

    // 2. backbone diagonal (thin everywhere)
    for (var i = 0; i < n; i++) { put(i, i, INK, 1); put(i, i + 1, INK, 0.8); }

    // 3. helices thicken the diagonal
    sse.forEach(function (x) {
      if (!x.h) return;
      for (var a = x.s; a <= x.e - 3; a++) put(a, a + 3, RES[3], 0.9);
      for (a = x.s; a <= x.e - 4; a++) put(a, a + 4, RES[3], 0.5);
    });

    // 4. β-sheet: pair strands that are adjacent in space (shuffled order)
    var strands = sse.filter(function (x) { return !x.h; });
    for (var s2 = strands.length - 1; s2 > 0; s2--) {
      var r = (Math.random() * (s2 + 1)) | 0, tmp = strands[s2]; strands[s2] = strands[r]; strands[r] = tmp;
    }
    for (var p = 0; p < strands.length - 1; p++) {
      var A = strands[p], B = strands[p + 1];
      if (A.s > B.s) { var t2 = A; A = B; B = t2; }
      var anti = Math.random() < 0.7;
      var L = Math.min(A.e - A.s, B.e - B.s);
      for (var k = 0; k <= L; k++) {
        var ai = A.s + k, bi = anti ? B.e - k : B.s + k;
        put(ai, bi, RES[1], 0.95);          // register band, a couple cells thick
        put(ai, bi + 1, RES[1], 0.45);
        put(ai + 1, bi, RES[1], 0.45);
      }
    }

    // 5. a couple of tertiary packing blobs between distant elements
    for (var q = 0, nt = 1 + ((Math.random() * 2) | 0); q < nt && sse.length > 1; q++) {
      var e1 = sse[(Math.random() * sse.length) | 0], e2 = sse[(Math.random() * sse.length) | 0];
      if (e1 === e2) continue;
      var ci = e1.s + ((Math.random() * (e1.e - e1.s + 1)) | 0);
      var cj = e2.s + ((Math.random() * (e2.e - e2.s + 1)) | 0);
      if (Math.abs(ci - cj) < 4) continue;
      for (var di = -1; di <= 1; di++) for (var dj = -1; dj <= 1; dj++)
        if (Math.random() < 0.65) put(ci + di, cj + dj, RES[2], 0.5);
    }

    // 6. minimal isolated noise
    for (var z = 0, nz = (n * 0.08) | 0; z < nz; z++) {
      var ni = (Math.random() * n) | 0, nj = (Math.random() * n) | 0;
      if (Math.abs(ni - nj) > 3) put(ni, nj, RES[4], 0.22);
    }

    var frag = document.createDocumentFragment();
    for (var key in grid) {
      var gi = (key / n) | 0, gj = key % n, cd = grid[key];
      frag.appendChild(cellRect(gj, gi, pitch, cell, cd.c, cd.o));
    }
    svg.appendChild(frag);
    return svg;
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
    [].forEach.call(document.querySelectorAll('.contact-map'), function (el) {
      el.textContent = '';
      el.appendChild(contactMap(46, 7));
    });
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
