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

  // ============================================================
  // Easter Egg: Procedural AOE Sheep Mutating MSA Band
  // ============================================================
  function initAoeSheep() {
    var footer = document.querySelector('.site-footer');
    if (!footer || document.getElementById('aoe-sheep-wrap')) return;

    var isToolsPage = location.pathname.indexOf('/tools') > -1 || location.pathname.indexOf('tools') > -1 || !!document.querySelector('#toolSearch');

    var container = document.createElement('div');
    container.id = 'aoe-sheep-wrap';
    container.style.cssText = 'position:absolute;top:4px;left:-60px;z-index:99;user-select:none;display:flex;align-items:center;' + (isToolsPage ? 'cursor:pointer;' : 'cursor:default;');
    
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
    function drawProceduralSheep(legOffset, isFlipped, isEating, isHeld, dangleFrame, squashFrame) {
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.save();

      if (isFlipped) {
        ctx.translate(cv.width, 0);
        ctx.scale(-1, 1);
      }

      // Ground Shadow (hidden completely when lifted!)
      if (!isHeld) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.22)';
        ctx.beginPath();
        ctx.ellipse(24, 41, 16, 3.2, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // Landing impact compression & knee bend calculation
      var bend = squashFrame > 0 ? Math.sin((squashFrame / 12) * Math.PI) * 4 : 0;
      var bob = isHeld ? 6 : (isEating ? 1.5 : Math.abs(legOffset) * 0.3);
      var bodyY = 24 - bob + bend; // Body compresses downward on landing!

      // 4 Legs (bend outwards at knee joints on landing impact)
      ctx.lineWidth = 2.8;
      ctx.lineCap = 'round';

      // Rhythmic pendulum leg rocking when held!
      var rockAngle = isHeld ? Math.sin(dangleFrame * 0.15) * 5 : 0;
      var legWalk = isHeld ? 0 : (isEating ? 0 : legOffset * 0.7);

      var hipY = bodyY + 9;
      var footY = isHeld ? hipY + 11 : 39;

      function drawBentLeg(x1, y1, x2, y2, bendDir) {
        ctx.beginPath();
        if (bend > 0.2) {
          var kX = (x1 + x2) / 2 + bendDir * (bend * 0.95);
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

      // Back legs (standing X positions)
      ctx.strokeStyle = '#241f18';
      var bX1 = 14, bX2 = 29;
      drawBentLeg(bX1, hipY, bX1 + rockAngle - legWalk, footY, -1);
      drawBentLeg(bX2, hipY, bX2 + rockAngle + legWalk, footY, -1);

      // Front legs (standing X positions)
      ctx.strokeStyle = '#3a3428';
      var fX1 = 19, fX2 = 33;
      drawBentLeg(fX1, hipY, fX1 + rockAngle + legWalk, footY, 1);
      drawBentLeg(fX2, hipY, fX2 + rockAngle - legWalk, footY, 1);

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
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      });

      // Dark Head — Lowers when eating, surprised look when held!
      var headY = isHeld ? bodyY - 3 : (isEating ? bodyY + 6 : bodyY - 1);
      var headX = isEating ? 39 : 36;

      ctx.fillStyle = '#241f18';
      ctx.beginPath();
      ctx.ellipse(headX, headY, 5.2, 4.0, isEating ? 0.6 : (isHeld ? -0.2 : 0.2), 0, Math.PI * 2);
      ctx.fill();

      // Ear - rocks with body when held!
      var earAngle = isHeld ? -0.4 + rockAngle * 0.05 : -0.4;
      ctx.fillStyle = '#3a3428';
      ctx.beginPath();
      ctx.ellipse(headX - 3, headY - 2, 3.0, 1.5, earAngle, 0, Math.PI * 2);
      ctx.fill();

      // Eye - wide when held!
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(headX + 1.5, headY - 1, isHeld ? 1.25 : 0.85, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }

    // Mutates MSA sequence cells under the sheep's mouth, querying ALL SVG tiles in the band
    function mutateMsaAt(pX) {
      var containerRect = container.getBoundingClientRect();
      if (!containerRect) return;

      var mouthScreenX = containerRect.left + ((direction === 1) ? 41 : 10);
      var svgList = footer.querySelectorAll('.msa-band svg');
      var colors = ['#6e9e4f', '#4e7fc4', '#e0a32e', '#d75a45', '#8e5b9f', '#c9c1ad'];

      svgList.forEach(function(svgEl) {
        var svgRect = svgEl.getBoundingClientRect();
        if (!svgRect || svgRect.width === 0) return;

        if (mouthScreenX >= svgRect.left - 20 && mouthScreenX <= svgRect.right + 20) {
          var viewBoxAttr = svgEl.getAttribute('viewBox');
          var viewBoxW = viewBoxAttr ? (parseFloat(viewBoxAttr.split(' ')[2]) || 1200) : 1200;
          var scaleX = viewBoxW / svgRect.width;
          var mouthSvgX = (mouthScreenX - svgRect.left) * scaleX;

          var rects = svgEl.querySelectorAll('rect');
          rects.forEach(function(rect) {
            var rx = parseFloat(rect.getAttribute('x'));
            if (Math.abs(rx - mouthSvgX) < 18) {
              if (Math.random() < 0.35) {
                rect.setAttribute('fill', colors[Math.floor(Math.random() * colors.length)]);
                rect.setAttribute('opacity', '0.95');
              }
            }
          });
        }
      });
    }

    var state = 'WALKING'; // 'WALKING', 'EATING', 'HELD', or 'FALLING'
    var posX = 60;
    var posY = 4;
    var velY = 0;
    var gravity = 0.8;
    var speed = 0.85;
    var direction = 1;
    var walkFrame = 0;
    var dangleFrame = 0;
    var squashFrame = 0;
    var stateTimer = 180;
    var isDragging = false;

    // Grab & Drop interaction on non-tool pages (2D Vertical Lifting + Gravity Drop)
    if (!isToolsPage) {
      container.style.cursor = 'grab';

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

        var maxX = footer.offsetWidth - 54;
        newX = Math.max(10, Math.min(maxX, newX));

        // Update facing direction dynamically based on drag movement!
        if (newX > posX + 0.5) {
          direction = 1; // Facing RIGHT
        } else if (newX < posX - 0.5) {
          direction = -1; // Facing LEFT
        }

        posX = newX;
        posY = newY; // Unlimited page-wide lifting anywhere on the page!

        container.style.left = posX + 'px';
        container.style.top = posY + 'px';
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
      }
    }

    function updateSheep() {
      var maxX = footer.offsetWidth - 54;
      var minX = 10;

      if (state === 'FALLING') {
        velY += gravity;
        if (velY > 22) velY = 22; // Terminal velocity cap
        posY += velY;
        dangleFrame += 1;

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
          posX += speed * direction;
          walkFrame += 0.22;

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
        dangleFrame += 1;
      }

      container.style.left = posX + 'px';
      var legOffset = (state === 'WALKING') ? Math.sin(walkFrame) * 3.5 : 0;
      drawProceduralSheep(legOffset, direction === -1, state === 'EATING', state === 'HELD' || state === 'FALLING', dangleFrame, squashFrame);

      if (squashFrame > 0) squashFrame--;
      requestAnimationFrame(updateSheep);
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
