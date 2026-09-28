/* The museum's small amount of behaviour. Every page works without it:
   links filter, forms submit, carousels scroll. This only adds what a
   plain page cannot -- dots that follow a swipe, a filter sheet that stays
   open while you pick, suggestions as you type, and a remembered colour mode. */
(function () {
  'use strict';

  /* ---- colour mode: Day, Auto (follow the device), Evening ---- */
  function stored() { try { return localStorage.getItem('rr-mode') || 'auto'; } catch (e) { return 'auto'; } }
  function setMode(m) {
    var root = document.documentElement;
    if (m === 'light' || m === 'dark') root.setAttribute('data-theme', m); else root.removeAttribute('data-theme');
    try { if (m === 'auto') localStorage.removeItem('rr-mode'); else localStorage.setItem('rr-mode', m); } catch (e) {}
    document.querySelectorAll('.rr-mode [data-mode]').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-mode') === m ? 'true' : 'false');
    });
  }

  /* ---- pictures: a failed thumbnail becomes the matted fallback ---- */
  function broken(img) {
    if (img.hasAttribute('data-frame')) {
      var frame = img.closest('.rr-frame');
      if (frame) frame.classList.add('is-empty');
    }
    img.remove();
  }
  document.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t.tagName === 'IMG' && (t.hasAttribute('data-frame') || t.hasAttribute('data-hide-broken'))) broken(t);
  }, true);

  /* ---- carousels: dots, count, arrows and arrow keys follow the swipe ---- */
  function carousel(c) {
    var track = c.querySelector('.rr-track'), dots = c.querySelector('.rr-dots');
    if (!track) return;
    var slides = Array.prototype.slice.call(track.children), n = slides.length;
    if (!n) return;
    function left(i) { return slides[i].offsetLeft - slides[0].offsetLeft; }
    function current() {
      var x = track.scrollLeft, best = 0, d = Infinity;
      slides.forEach(function (s, i) { var dd = Math.abs(left(i) - x); if (dd < d) { d = dd; best = i; } });
      return best;
    }
    function go(i) { i = Math.max(0, Math.min(n - 1, i)); track.scrollTo({ left: left(i), behavior: 'smooth' }); }
    var shown = Math.min(n, 7);
    if (dots && n > 1) {
      var html = '';
      for (var i = 0; i < shown; i++) html += '<button type="button" aria-label="Slide ' + (i + 1) + '"></button>';
      dots.innerHTML = html + '<span class="count" aria-live="polite"></span>';
      dots.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        var k = Array.prototype.indexOf.call(dots.querySelectorAll('button'), b);
        go(k === shown - 1 && n > shown ? n - 1 : k);
      });
    }
    function paint() {
      if (!dots || n < 2) return;
      var k = current(), dot = n > shown && k >= shown - 1 ? shown - 1 : k;
      dots.querySelectorAll('button').forEach(function (b, i) { b.setAttribute('aria-current', i === dot ? 'true' : 'false'); });
      var cnt = dots.querySelector('.count'); if (cnt) cnt.textContent = (k + 1) + ' / ' + n;
    }
    var shelf = c.closest('.rr-shelf');
    if (shelf) shelf.querySelectorAll('[data-dir]').forEach(function (b) {
      b.addEventListener('click', function () { go(current() + Number(b.getAttribute('data-dir')) * 3); });
    });
    track.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { e.preventDefault(); go(current() + 1); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); go(current() - 1); }
    });
    var t; track.addEventListener('scroll', function () { clearTimeout(t); t = setTimeout(paint, 60); }, { passive: true });
    paint();
  }

  /* ---- the phone filter sheet ---- */
  function sheet(details) {
    var body = details.querySelector('.rr-sheet .body');
    var tabs = Array.prototype.slice.call(details.querySelectorAll('.tabs a'));
    function lock() { document.documentElement.classList.toggle('rr-sheet-open', details.open); }
    details.addEventListener('toggle', lock);
    // Picking an option reloads with #filters: reopen, so several can be chosen in a row.
    if (location.hash === '#filters') { details.open = true; lock(); }
    details.querySelectorAll('.rr-sheet-scrim, [data-close]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); details.open = false; history.replaceState(null, '', location.pathname + location.search); });
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && details.open) details.open = false; });
    tabs.forEach(function (a) {
      a.addEventListener('click', function (e) {
        var target = body && body.querySelector(a.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        body.scrollTo({ top: target.offsetTop - body.offsetTop - 8, behavior: 'smooth' });
        tabs.forEach(function (x) { x.setAttribute('aria-selected', x === a ? 'true' : 'false'); });
      });
    });
    if (body) body.addEventListener('scroll', function () {
      var top = body.scrollTop + 24, on = tabs[0];
      tabs.forEach(function (a) { var s = body.querySelector(a.getAttribute('href')); if (s && s.offsetTop - body.offsetTop <= top) on = a; });
      tabs.forEach(function (x) { x.setAttribute('aria-selected', x === on ? 'true' : 'false'); });
    }, { passive: true });
  }

  /* ---- suggestions under the search field ---- */
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  var GLYPH = { room: '<span class="glyph" aria-hidden="true">&#8962;</span>', tag: '<span class="glyph" aria-hidden="true">#</span>' };
  function suggest(form) {
    var input = form.querySelector('input[name="q"]');
    if (!input) return;
    var panel = document.createElement('div');
    panel.className = 'rr-suggest'; panel.hidden = true; panel.id = 'suggest-' + Math.random().toString(36).slice(2, 8);
    panel.setAttribute('role', 'listbox');
    form.appendChild(panel);
    input.setAttribute('aria-controls', panel.id); input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-autocomplete', 'list');
    var timer, seq = 0, sel = -1;
    function links() { return Array.prototype.slice.call(panel.querySelectorAll('li a')); }
    function close() { panel.hidden = true; input.setAttribute('aria-expanded', 'false'); sel = -1; }
    function mark(i) { var l = links(); sel = i; l.forEach(function (a, k) { a.setAttribute('aria-selected', k === i ? 'true' : 'false'); }); }
    function render(data) {
      if (!data.groups || !data.groups.length) { close(); return; }
      var html = data.groups.map(function (g) {
        return '<h4 class="rr-label is-muted">' + esc(g.title) + '</h4><ul>' + g.rows.map(function (r) {
          var lead = r.kind === 'item' ? '<span class="mini">' + (r.thumb ? '<img src="' + esc(r.thumb) + '" alt="" referrerpolicy="no-referrer" data-hide-broken>' : '') + '</span>'
            : r.kind === 'creator' ? '<span class="glyph is-creator" aria-hidden="true">' + esc(r.initials) + '</span>'
            : r.kind === 'date' ? '<span class="glyph is-date" aria-hidden="true">&#9719;</span>'
            : (GLYPH[r.kind] || '');
          return '<li><a role="option" href="' + esc(r.href) + '">' + lead + '<span class="t"><b>' + esc(r.label) + '</b><span>' + esc(r.sub) + '</span></span></a></li>';
        }).join('') + '</ul>';
      }).join('');
      html += '<div class="foot"><span class="rr-muted">' + esc(data.total) + ' ' + (data.total === 1 ? 'result' : 'results') + ' for “' + esc(data.q) + '”</span><a href="' + esc(data.href) + '">Search →</a></div>';
      panel.innerHTML = html; panel.hidden = false; input.setAttribute('aria-expanded', 'true'); sel = -1;
    }
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(function () {
        var mine = ++seq;
        fetch('/suggest.json?q=' + encodeURIComponent(q)).then(function (r) { return r.json(); })
          .then(function (d) { if (mine === seq) render(d); }).catch(close);
      }, 160);
    });
    input.addEventListener('keydown', function (e) {
      var l = links();
      if (panel.hidden || !l.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); mark((sel + 1) % l.length); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); mark(sel <= 0 ? l.length - 1 : sel - 1); }
      else if (e.key === 'Enter' && sel >= 0) { e.preventDefault(); location.href = l[sel].href; }
      else if (e.key === 'Escape') { close(); }
    });
    document.addEventListener('click', function (e) { if (!form.contains(e.target)) close(); });
  }

  function init() {
    setMode(stored());
    document.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('.rr-mode [data-mode]');
      if (b) setMode(b.getAttribute('data-mode'));
    });
    document.querySelectorAll('img[data-frame], img[data-hide-broken]').forEach(function (img) {
      if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) broken(img);
    });
    document.querySelectorAll('.rr-carousel').forEach(carousel);
    document.querySelectorAll('.rr-filters-mobile').forEach(sheet);
    document.querySelectorAll('form[data-suggest]').forEach(suggest);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
