/* Contents rail: tracks which section you are reading, and keeps only that
   section's sub-headings unfolded so the rail never outgrows the viewport.
   Purely an affordance — the links work fine without any of this. */
(function () {
  var toc = document.querySelector('.paper-toc');
  if (!toc) return;

  var links = {};
  [].forEach.call(toc.querySelectorAll('a[href^="#"]'), function (a) {
    links[decodeURIComponent(a.getAttribute('href').slice(1))] = a;
  });
  var targets = Object.keys(links)
    .map(function (id) { return document.getElementById(id); })
    .filter(Boolean);
  if (!targets.length) return;

  var subs = [].slice.call(toc.querySelectorAll('li[data-parent]'));
  var current = null;

  function unfold(id) {
    subs.forEach(function (li) {
      li.classList.toggle('is-open', li.getAttribute('data-parent') === id);
    });
  }

  function mark(el) {
    if (!el || el === current) return;
    if (current) current.classList.remove('is-active');
    el.classList.add('is-active');
    current = el;

    // open the branch this heading lives in, fold the others away
    var li = el.parentNode;
    unfold(li.getAttribute('data-parent') || li.getAttribute('data-section') || '');

    // keep the active entry inside the rail's own scroll window
    var r = el.getBoundingClientRect(), box = toc.getBoundingClientRect();
    if (r.top < box.top + 8 || r.bottom > box.bottom - 8) {
      toc.scrollTop += (r.top - box.top) - toc.clientHeight / 3;
    }
  }

  // Position-based rather than IntersectionObserver: a jump (anchor click, a
  // restored scroll position) can skip an observer's trigger band entirely and
  // leave the rail stuck on whatever happened to be highlighted last.
  function update() {
    var line = window.innerHeight * 0.32;   // the "currently reading" line
    var best = targets[0];
    for (var i = 0; i < targets.length; i++) {
      if (targets[i].getBoundingClientRect().top <= line) best = targets[i];
    }
    mark(links[best.id]);
  }

  var queued = false;
  function onScroll() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; update(); });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  update();
})();
