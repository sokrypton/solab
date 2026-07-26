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
    // the band svg draws in CSS pixels (no viewBox), so the column pitch has to
    // be derived from the band's real height or the lower rows get clipped —
    // most visible on phones, where the footer band is only ~44px tall.
    var bandH = band.clientHeight || band.offsetHeight || rows * 12;
    var pitch = bandH / rows;
    var gap = Math.max(0.75, Math.min(2, pitch * 0.17));
    var cell = Math.max(1.5, pitch - gap);
    band.textContent = '';

    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('shape-rendering', 'geometricPrecision');
    svg.style.cssText = 'display:block;width:100%;height:100%;overflow:hidden;';

    var streamGroup = document.createElementNS(NS, 'g');
    svg.appendChild(streamGroup);
    band.appendChild(svg);

    var scrollX = 0;
    var nextColIndex = 0;
    var columns = []; // Array of active columns: { index, x, group, rects }

    function createColumn(cIndex) {
      var g = document.createElementNS(NS, 'g');
      var cX = cIndex * pitch;
      var consensus = pick();
      var cons = 0.5 + Math.random() * 0.45;
      var rects = [];

      for (var r = 0; r < rows; r++) {
        if (Math.random() < 0.05) continue;
        var fill = Math.random() < cons ? consensus : (Math.random() < 0.8 ? pick() : GRAY);
        var rect = cellRect(cIndex, r, pitch, cell, fill);
        g.appendChild(rect);
        rects.push(rect);
      }

      return { index: cIndex, x: cX, group: g, rects: rects };
    }

    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var speed = reduce ? 0 : 0.6; // Ambient drift speed

    function animateStream() {
      var bandW = band.offsetWidth || window.innerWidth || 1200;

      if (!reduce) {
        scrollX += speed;
        streamGroup.setAttribute('transform', 'translate(' + (-scrollX.toFixed(2)) + ', 0)');
      }

      // Append new columns on the right continuously as needed
      while ((nextColIndex * pitch) - scrollX < bandW + 180) {
        var col = createColumn(nextColIndex);
        streamGroup.appendChild(col.group);
        columns.push(col);
        nextColIndex++;
      }

      // Prune off-screen columns on the left to keep DOM lightweight
      while (columns.length > 0 && (columns[0].x + pitch) < scrollX - 60) {
        columns[0].group.remove();
        columns.shift();
      }

      requestAnimationFrame(animateStream);
    }

    requestAnimationFrame(animateStream);

    // Attach stream controller to band element for sheep mutagenesis
    band._msaStream = {
      mutateAt: function(mouthScreenX) {
        var svgRect = svg.getBoundingClientRect();
        if (!svgRect || svgRect.width === 0) return;

        // the svg has no viewBox, so its local units are CSS pixels 1:1
        var mouthStreamX = (mouthScreenX - svgRect.left) + scrollX;

        var colors = ['#6e9e4f', '#4e7fc4', '#e0a32e', '#d75a45', '#8e5b9f', '#c9c1ad'];

        columns.forEach(function(col) {
          if (Math.abs(col.x - mouthStreamX) < pitch * 1.5) {
            col.rects.forEach(function(rect) {
              if (Math.random() < 0.35) {
                rect.setAttribute('fill', colors[Math.floor(Math.random() * colors.length)]);
                rect.setAttribute('opacity', '0.95');
              }
            });
          }
        });
      }
    };
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

  // ============================================================
  // Easter Egg: Procedural AOE Sheep Mutating MSA Band
  // ============================================================
  function initAoeSheep() {
    var footer = document.querySelector('.site-footer');
    if (!footer || document.getElementById('aoe-sheep-wrap')) return;

    var isToolsPage = location.pathname.indexOf('/tools') > -1 || location.pathname.indexOf('tools') > -1 || !!document.querySelector('#toolSearch');

    var container = document.createElement('div');
    container.id = 'aoe-sheep-wrap';
    container.style.cssText = 'position:absolute;top:4px;left:0px;z-index:102;user-select:none;touch-action:none;display:flex;align-items:center;' + (isToolsPage ? 'cursor:pointer;' : 'cursor:grab;');
    
    if (isToolsPage) {
      container.setAttribute('title', 'Age of Epochs — Click to play!');
    }

    container.innerHTML = `
      <canvas id="aoe-sheep-canvas" width="56" height="48" style="display:block;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.35));"></canvas>
    `;

    footer.style.position = 'relative';
    footer.appendChild(container);

    var cv = container.querySelector('#aoe-sheep-canvas');
    var ctx = cv.getContext('2d');

    if (isToolsPage) {
      container.addEventListener('click', function() {
        window.open('http://ageofepochs.com/', '_blank');
      });
    }

    // Procedural 2D Canvas Sheep Renderer (cloud body lifts UP, legs rock in unison when held)
    // s: { walking, walk, trip, chomp, flipped, eating, held, falling, swing, squash, chew, velY }
    function drawProceduralSheep(s) {
      var isFlipped = s.flipped, isEating = s.eating;
      var isHeld = s.held, swing = s.swing, squashFrame = s.squash;
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.save();

      if (isFlipped) {
        ctx.translate(cv.width, 0);
        ctx.scale(-1, 1);
      }

      // Landing impact compression & knee bend calculation
      var impact = squashFrame > 0 ? Math.sin((squashFrame / 12) * Math.PI) : 0;
      var bend = impact * 3;
      // falling stretches the wool the other way, harder the faster it drops
      var stretch = s.falling ? Math.min(0.18, Math.abs(s.velY) * 0.012) : 0;
      // grazing: a slow sweep along the band with a faster nibble on top
      var graze = isEating ? Math.sin(s.chew * 0.085) : 0;
      var nibble = isEating ? Math.sin(s.chew * 0.42) : 0;

      // Walk cycle: a heavy four-beat plod. `walk` is the gait phase; the body
      // drops onto each planted pair (twice a cycle) rather than bouncing, and
      // rolls side to side, so the weight reads as lumbering, not trotting.
      var walking = s.walking, walk = s.walk;
      var plant = walking ? Math.max(0, Math.sin(walk * 2)) : 0;      // weight landing
      var waddle = walking ? Math.sin(walk) : 0;                       // side-to-side lurch
      var trip = s.trip;                                               // 0..1 stumble
      var chomp = s.chomp;                                             // 0..1 bite of page text

      // Ground Shadow (hidden completely when lifted!)
      if (!isHeld) {
        ctx.fillStyle = 'rgba(0, 0, 0, ' + (0.22 + plant * 0.03).toFixed(3) + ')';
        ctx.beginPath();
        // shadow widens and darkens as the body flattens into the ground
        ctx.ellipse(24 + graze * 1.2 + waddle * 0.5, 41,
          16 + impact * 3 + plant * 0.5, 3.2 + impact * 0.6, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      var bob = isHeld ? 6 : (isEating ? 1.5 - nibble * 0.5 : -plant * 0.5);
      var bodyY = 24 - bob + bend + trip * 1.4; // Body compresses downward on landing!

      // 4 Legs (bend outwards at knee joints on landing impact)
      ctx.lineWidth = 2.8;
      ctx.lineCap = 'round';

      // Legs hang as damped pendulums when lifted: `swing` is the physics
      // offset (px at the hoof) integrated in stepSheep from the drag motion.
      var rockAngle = isHeld ? swing : 0;

      var hipY = bodyY + 9;
      // a hard swing shortens the vertical drop, as a real pendulum would
      var swingDrop = isHeld ? Math.sqrt(Math.max(4, 121 - swing * swing)) : 11;
      var groundY = 39;

      function drawBentLeg(x1, y1, x2, y2, bendDir, kneeBend) {
        ctx.beginPath();
        var k = bend + (kneeBend || 0);
        if (k > 0.2) {
          var kX = (x1 + x2) / 2 + bendDir * (k * 0.5);
          var kY = (y1 + y2) / 2 + 1;
          ctx.moveTo(x1, y1);
          ctx.lineTo(kX, kY);
          ctx.lineTo(x2, y2);
        } else {
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
        }
        ctx.stroke();
      }

      // One leg: hangs from the hip when lifted, otherwise steps through the
      // gait. `phase` staggers the four legs; short, heavy strides with a low
      // hoof lift and a bent knee through the swing.
      function drawLeg(hipX, hangSwing, phase, bendDir) {
        if (isHeld) {
          drawBentLeg(hipX, hipY, hipX + hangSwing, hipY + swingDrop, bendDir);
          return;
        }
        if (!walking) { drawBentLeg(hipX, hipY, hipX, groundY, bendDir); return; }
        var st = Math.sin(walk + phase);
        var lift = Math.max(0, Math.sin(walk + phase + Math.PI / 2));   // hoof off the ground
        var footX = hipX + st * 2.4 + trip * bendDir * 2;
        var footY = groundY - lift * lift * 1.1 + trip * 1.0;
        drawBentLeg(hipX + waddle * 0.35, hipY, footX, footY, bendDir, lift * 0.6 + trip * 1.8);
      }

      // Back legs (standing X positions) — lead the front pair by ~a third of a
      // cycle, the way a heavy quadruped shoves its weight forward
      ctx.strokeStyle = '#241f18';
      var bX1 = 14, bX2 = 29, backSwing = rockAngle * 0.82, frontSwing = rockAngle * 1.14;
      drawLeg(bX1, backSwing, 0, -1);
      drawLeg(bX2, backSwing, Math.PI, -1);

      // Front legs (standing X positions)
      ctx.strokeStyle = '#3a3428';
      var fX1 = 19, fX2 = 33;
      drawLeg(fX1, frontSwing, Math.PI * 0.62, 1);
      drawLeg(fX2, frontSwing, Math.PI * 1.62, 1);

      // Wool mass: squashes flat on impact, stretches tall in freefall, leans
      // forward and rolls gently while grazing. Head is drawn outside this
      // transform so it keeps its shape and can lag behind the body.
      // walking: the wool settles on each footfall and the whole mass waddles
      var sx = 1 + impact * 0.20 - stretch + plant * 0.025 + chomp * 0.03;
      var sy = 1 - impact * 0.22 + stretch - plant * 0.03 - chomp * 0.04;
      var tilt = isEating ? 0.07 + graze * 0.035 : (s.falling ? -0.05 : waddle * 0.03 + trip * 0.07);
      var bodyX = 24 + (isEating ? graze * 1.6 : waddle * 0.7);

      ctx.save();
      ctx.translate(bodyX, bodyY);
      ctx.rotate(tilt);
      ctx.scale(sx, sy);
      ctx.translate(-24, -bodyY);

      // Base wool body shape
      ctx.fillStyle = '#f4efe4';
      ctx.strokeStyle = '#ded7c5';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(24, bodyY, 15, 10.5, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Cloud Puffs
      var cloudPuffs = [
        { x: 24, y: bodyY - 9, r: 7.8 }, // TOP CENTER BUMP
        { x: 15, y: bodyY - 6, r: 6.2 },
        { x: 31, y: bodyY - 5, r: 6.0 },
        { x: 9,  y: bodyY - 1, r: 5.5 },
        { x: 37, y: bodyY + 1, r: 5.2 },
        { x: 33, y: bodyY + 4, r: 5.0 },
        { x: 25, y: bodyY + 5, r: 5.5 },
        { x: 17, y: bodyY + 4, r: 5.2 },
        { x: 11, y: bodyY + 2, r: 4.8 },
        { x: 22, y: bodyY - 1, r: 7.0 }
      ];

      ctx.fillStyle = '#ffffff';
      cloudPuffs.forEach(function(p) {
        ctx.beginPath();
        // outer puffs jiggle a beat behind the body on impact
        var lag = impact * (p.y - bodyY) * 0.12;
        ctx.arc(p.x, p.y + lag, p.r * (1 + impact * 0.06), 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();

      // Dark Head — grazes down into the band, lags on landing, cranes up in freefall
      var headY, headX, headRot;
      if (isHeld && s.falling) {
        headY = bodyY - 4 - stretch * 6;          // cranes upward as it drops
        headX = 36 - swing * 0.12;
        headRot = -0.55;
      } else if (isHeld) {
        // each letter it catches gets a proper chomp: lunge down and forward,
        // then snap back, with the fleece bouncing a little behind it
        headY = bodyY - 3 + chomp * 5.5;
        headX = 36 - swing * 0.18 + chomp * 3.0;  // head counter-swings in the hand
        headRot = -0.2 + swing * 0.012 + chomp * 0.95;
      } else if (isEating) {
        // muzzle reaches down into the alignment, but the skull stays tucked
        // into the fleece — the head is never a separate ball on a neck
        headY = bodyY + 9 + nibble * 1.4;
        headX = 37.5 + graze * 1.8;
        headRot = 0.85 + nibble * 0.12;
      } else {
        // walking: the head nods a beat behind the body, heavier than it bobs
        var nod = walking ? Math.sin(walk - 0.8) : 0;
        headY = bodyY - 1 - impact * 3 + nod * 0.7 + trip * 0.9;   // head keeps falling after the body stops
        headX = 36 + impact * 1.5 + nod * 0.5 - trip * 0.9;
        headRot = 0.2 + impact * 0.25 + nod * 0.05 + trip * 0.12;
      }

      ctx.save();
      ctx.translate(headX, headY);
      ctx.rotate(headRot);

      ctx.fillStyle = '#241f18';
      ctx.beginPath();
      ctx.ellipse(0, 0, 5.2, 4.0, 0, 0, Math.PI * 2);
      ctx.fill();

      // Ear - flicks while chewing, flaps in freefall, rocks with the swing
      var earAngle = -0.4;
      if (s.falling) earAngle = -0.4 + Math.sin(s.chew * 0.5) * 0.35;
      else if (isHeld) earAngle = -0.4 + swing * 0.05;
      else if (isEating) earAngle = -0.4 + nibble * 0.22;
      ctx.fillStyle = '#3a3428';
      ctx.beginPath();
      ctx.ellipse(-3, -2, 3.0, 1.5, earAngle, 0, Math.PI * 2);
      ctx.fill();

      // Eye - wide when held!
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(1.5, -1, (isHeld ? 1.25 : 0.85) * (1 - chomp * 0.55), 0, Math.PI * 2);   // squints mid-bite
      ctx.fill();
      ctx.restore();

      ctx.restore();
    }

    // Mutates MSA sequence cells under the sheep's mouth on the continuous stream
    function mutateMsaAt(pX) {
      var containerRect = container.getBoundingClientRect();
      if (!containerRect) return;

      // muzzle sweeps with the grazing motion, so the mutations follow it
      var graze = Math.sin(chewFrame * 0.085) * 2.2 * direction;
      var mouthScreenX = containerRect.left + ((direction === 1) ? 41 : 10) + graze;
      var band = footer.querySelector('.msa-band');
      if (band && band._msaStream) {
        band._msaStream.mutateAt(mouthScreenX);
      }
    }

    // ---- page-text mutagenesis (only while the sheep is being carried) ----
    // The muzzle drops point mutations into whatever text it passes over: one
    // letter is swapped for a random residue and the displaced letter tumbles
    // off the page. Kept deliberately cheap — a single caret hit-test every
    // 150ms, and the falling glyph is a throwaway span animated on the
    // compositor (transform/opacity only), never a per-frame scan of the page.
    var AA = 'ACDEFGHIKLMNPQRSTVWY';
    var MUT_EVERY = 150;
    // Everything on the page is edible — headings, names, links, the lot. Only
    // form fields (whose value is state, not prose) and the sheep's own sprite
    // are off limits. Link hrefs are untouched either way; only the label bites.
    var MUT_SKIP = 'input,textarea,select,#aoe-sheep-wrap';
    var lastTextMut = 0;

    var noAnim = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // The knocked-out letter, cloned where it stood and dropped off the page.
    // Styled from the host element so it falls looking exactly like it did.
    function dropLetter(rect, host, chr) {
      if (noAnim || !rect || !rect.width) return;
      var cs = window.getComputedStyle(host);
      var el = document.createElement('span');
      el.textContent = chr;
      el.setAttribute('aria-hidden', 'true');
      el.style.cssText = 'position:fixed;z-index:101;pointer-events:none;white-space:pre;' +
        'left:' + rect.left.toFixed(1) + 'px;top:' + rect.top.toFixed(1) + 'px;' +
        'color:' + cs.color + ';font-style:' + cs.fontStyle + ';font-weight:' + cs.fontWeight +
        ';font-size:' + cs.fontSize + ';font-family:' + cs.fontFamily + ';line-height:1;';
      document.body.appendChild(el);

      var dx = Math.random() * 26 - 13;
      var spin = Math.random() * 200 - 100;
      var drop = 70 + Math.random() * 60;
      var dur = 900 + Math.random() * 500;
      var frames = [
        { transform: 'translate(0,0) rotate(0deg)', opacity: 1 },
        // knocked loose: a little hop before gravity takes over
        { transform: 'translate(' + (dx * 0.3).toFixed(1) + 'px,-5px) rotate(' +
            (spin * 0.15).toFixed(0) + 'deg)', opacity: 1, offset: 0.18 },
        { transform: 'translate(' + dx.toFixed(1) + 'px,' + drop.toFixed(0) + 'px) rotate(' +
            spin.toFixed(0) + 'deg)', opacity: 0 }
      ];
      var opts = { duration: dur, easing: 'cubic-bezier(.3,.05,.6,1)', fill: 'forwards' };
      if (el.animate) {
        var a = el.animate(frames, opts);
        a.onfinish = function () { el.remove(); };
        setTimeout(function () { el.remove(); }, dur + 400);   // belt and braces
      } else {
        el.remove();
      }
    }

    // Hit-tests the exact character under the drawn muzzle (not the cursor) and
    // swaps that one letter, so the sheep really is eating what it touches.
    function mutateTextUnder() {
      var now = Date.now();
      if (now - lastTextMut < MUT_EVERY) return;
      lastTextMut = now;

      // muzzle position in the sprite, mirrored when the sheep faces left
      var r = container.getBoundingClientRect();
      var x = r.left + (direction === 1 ? 39 : cv.width - 39);
      var y = r.top + 17;

      container.style.pointerEvents = 'none';        // don't hit the sheep itself
      var caret = document.caretRangeFromPoint ? document.caretRangeFromPoint(x, y)
        : (document.caretPositionFromPoint ? document.caretPositionFromPoint(x, y) : null);
      container.style.pointerEvents = '';
      if (!caret) return;

      var node = caret.startContainer || caret.offsetNode;
      var off = caret.startOffset != null ? caret.startOffset : caret.offset;
      if (!node || node.nodeType !== 3 || !node.data) return;
      var host = node.parentElement;
      if (!host || !host.closest || host.closest(MUT_SKIP)) return;

      // the caret lands between characters — bite whichever side is a letter
      var at = -1;
      if (/[A-Za-z]/.test(node.data.charAt(off))) at = off;
      else if (off > 0 && /[A-Za-z]/.test(node.data.charAt(off - 1))) at = off - 1;
      if (at < 0) return;

      var orig = node.data.charAt(at);
      var ch = AA.charAt((Math.random() * AA.length) | 0);
      if (orig === orig.toLowerCase()) ch = ch.toLowerCase();
      if (ch === orig) return;

      // measure the glyph before it is replaced, so the old letter can fall
      // from exactly where it stood
      var glyph = document.createRange();
      glyph.setStart(node, at);
      glyph.setEnd(node, at + 1);
      var box = glyph.getBoundingClientRect();

      node.data = node.data.slice(0, at) + ch + node.data.slice(at + 1);   // mutations stick
      dropLetter(box, host, orig);
      chompFrame = 11;                                                      // and it chews
    }

    var state = 'WALKING'; // 'WALKING', 'EATING', 'HELD', or 'FALLING'
    var posX = 40;
    var posY = 4;
    var velY = 0;
    var gravity = 0.8;
    var speed = 0.55;      // heavy: it shuffles rather than trots
    var direction = 1;
    var walkFrame = 0;
    var dangleFrame = 0;
    var squashFrame = 0;
    var chewFrame = 0;
    var tripFrame = 0;   // counts down through a stumble
    var chompFrame = 0;  // counts down through a bite of page text
    var stateTimer = 180;
    var isDragging = false;

    // damped-pendulum state for the dangling legs (px offset at the hoof)
    var swingAng = 0, swingVel = 0, dragVX = 0, dragVY = 0;

    // Grab & Drop interaction on non-tool pages (2D Vertical Lifting + Gravity Drop)
    if (!isToolsPage) {
      function startDrag(e) {
        isDragging = true;
        state = 'HELD';
        velY = 0;
        container.style.cursor = 'grabbing';
        e.preventDefault();
      }

      function moveDrag(e) {
        if (!isDragging) return;
        var pageX = e.touches ? e.touches[0].clientX : e.clientX;
        var pageY = e.touches ? e.touches[0].clientY : e.clientY;
        var footerRect = footer.getBoundingClientRect();

        var newX = pageX - footerRect.left - 26;
        var newY = pageY - footerRect.top - 20;

        var maxX = Math.max(0, footer.offsetWidth - 56);
        newX = Math.max(0, Math.min(maxX, newX));

        // Update facing direction dynamically based on drag movement!
        if (newX > posX + 0.5) {
          direction = 1; // Facing RIGHT
        } else if (newX < posX - 0.5) {
          direction = -1; // Facing LEFT
        }

        // hand velocity drives the pendulum: legs trail the direction of travel
        dragVX = newX - posX;
        dragVY = newY - posY;

        posX = newX;
        posY = newY; // Unlimited page-wide lifting anywhere on the page!

        container.style.left = posX + 'px';
        container.style.top = posY + 'px';

        // the muzzle drops a point mutation into whatever text it passes over
        // (throttled inside, so this is ~6 hit-tests a second while dragging)
        mutateTextUnder();
      }

      function stopDrag() {
        if (isDragging) {
          isDragging = false;
          container.style.cursor = 'grab';
          if (posY < 4) {
            state = 'FALLING';
            velY = 0.5; // Initial drop velocity
          } else {
            state = 'EATING';
            stateTimer = 90;
            posY = 4;
            container.style.top = '4px';
          }
        }
      }

      container.addEventListener('mousedown', startDrag);
      window.addEventListener('mousemove', moveDrag);
      window.addEventListener('mouseup', stopDrag);

      container.addEventListener('touchstart', startDrag, { passive: false });
      window.addEventListener('touchmove', moveDrag, { passive: false });
      window.addEventListener('touchend', stopDrag);
    }

    function nextState() {
      if (state === 'HELD' || state === 'FALLING') return;

      if (state === 'WALKING') {
        state = 'EATING';
        stateTimer = 90 + Math.floor(Math.random() * 120); // Eat MSA for 1.5 - 3.5s
      } else {
        state = 'WALKING';
        stateTimer = 180 + Math.floor(Math.random() * 240); // Walk for 3.0 - 7.0s
        if (Math.random() < 0.45) {
          direction *= -1; // Flip forward/backward
        }
        // never set off into a wall: at either edge the sheep would bounce
        // straight back into EATING and could sit there indefinitely
        var maxX = Math.max(0, footer.offsetWidth - 56);
        if (posX >= maxX - 1) direction = -1;
        else if (posX <= 1) direction = 1;
      }
    }

    function updateSheep() {
      try {
        stepSheep();
      } catch (err) {
        // a throw here used to skip the rAF below and freeze the sheep for good
        if (window.console) console.warn('sheep', err);
      }
      requestAnimationFrame(updateSheep);
    }

    // one step of a damped spring toward `target`, with a slow idle sway on top
    function integrateSwing(target) {
      dangleFrame += 1;
      swingVel += (target - swingAng) * 0.16;   // stiffness
      swingVel *= 0.86;                          // damping
      swingAng += swingVel;
      if (swingAng > 9) { swingAng = 9; swingVel *= -0.35; }   // leg is 11px long
      if (swingAng < -9) { swingAng = -9; swingVel *= -0.35; }
      dragVX *= 0.72;                            // hand velocity decays between moves
      dragVY *= 0.72;
    }

    function stepSheep() {
      var maxX = Math.max(0, footer.offsetWidth - 56);
      var minX = 0;
      if (!isDragging && posX > maxX) posX = maxX;   // keep in frame after a resize/rotate

      if (state === 'FALLING') {
        velY += gravity;
        if (velY > 22) velY = 22; // Terminal velocity cap
        posY += velY;
        // falling: air drag pushes the legs up and outwards, more the faster it drops
        integrateSwing(Math.min(9, velY * 0.55) * (direction === 1 ? -1 : 1));

        if (posY >= 4) {
          posY = 4;
          velY = 0;
          state = 'EATING'; // Land on MSA band and immediately eat/mutate!
          stateTimer = 90;
          squashFrame = 12; // Trigger landing leg-bending impact bounce!
        }
        container.style.top = posY + 'px';
      } else if (state !== 'HELD') {
        container.style.top = '4px';
        stateTimer--;
        if (stateTimer <= 0) {
          nextState();
        }

        if (state === 'WALKING') {
          // heavy gait: it shuffles forward mostly while a pair is planted, and
          // now and then catches a hoof and stumbles for a few frames
          if (tripFrame > 0) tripFrame--;
          else if (Math.random() < 0.002) tripFrame = 16;

          var thrust = 0.75 + Math.abs(Math.sin(walkFrame * 2)) * 0.3;   // lurch per footfall
          if (tripFrame > 0) thrust *= 0.35;
          posX += speed * thrust * direction;
          walkFrame += tripFrame > 0 ? 0.07 : 0.155;                     // slow, plodding cadence

          if (posX >= maxX) {
            posX = maxX;
            direction = -1;
            state = 'EATING';
            stateTimer = 90;
          } else if (posX <= minX) {
            posX = minX;
            direction = 1;
            state = 'EATING';
            stateTimer = 90;
          }
        } else if (state === 'EATING') {
          mutateMsaAt(posX);
        }
      } else {
        // held: legs trail the hand, plus a lazy idle sway once it settles
        var idle = Math.sin(dangleFrame * 0.11) * 1.6;
        integrateSwing(-dragVX * 1.5 - Math.abs(dragVY) * 0.25 + idle);
      }

      container.style.left = posX + 'px';
      // the canvas is mirrored when facing left, so mirror the swing to keep it
      // trailing in page space rather than sheep space
      var swing = swingAng * (direction === -1 ? -1 : 1);
      if (state === 'EATING') chewFrame += 1; else chewFrame = 0;
      if (state !== 'WALKING') tripFrame = 0;
      drawProceduralSheep({
        walking: state === 'WALKING',
        walk: walkFrame,
        trip: tripFrame > 0 ? Math.sin((tripFrame / 16) * Math.PI) : 0,
        chomp: chompFrame > 0 ? Math.sin((chompFrame / 11) * Math.PI) : 0,
        flipped: direction === -1,
        eating: state === 'EATING',
        held: state === 'HELD' || state === 'FALLING',
        falling: state === 'FALLING',
        swing: swing,
        squash: squashFrame,
        chew: state === 'EATING' ? chewFrame : dangleFrame,
        velY: velY
      });

      if (squashFrame > 0) squashFrame--;
      if (chompFrame > 0) chompFrame--;
    }

    requestAnimationFrame(updateSheep);
  }

  function inject() {
    colorizeBrand();
    wireMembers();
    initAoeSheep();
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
