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
    // ambient MSA band in the footer on all pages, flush at top of site-footer
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
    // (contact-page 3D structure + map now live in contact.js, loaded only there)
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
