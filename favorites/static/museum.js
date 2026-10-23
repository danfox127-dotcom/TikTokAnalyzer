/* The museum's small amount of behaviour. Every page works without it:
   links filter, forms submit, carousels scroll. This only adds what a
   plain page cannot -- dots that follow a swipe, a filter sheet that stays
   open while you pick, suggestions as you type, a remembered colour mode, and
   two small scroll touches: blocks that rise into view once, and a masthead
   that takes on the colour of the band beneath it.

   And, for the phone: a Back that knows where you came from (a home-screen
   app has no browser Back button), sheets that pull down to close, saves
   that don't leave the page, search results that keep coming, and
   Shuffle's feed, which loads more as you flick. */
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

  /* ---- motion: subtle, and only in answer to scrolling ----
     One observer reveals .rr-reveal blocks the first time they come into view;
     another tints the masthead with the band under it. No scroll listeners,
     nothing per frame. Content is only hidden once this has run (.rr-motion),
     so with no script -- or with reduced motion -- everything is simply there. */
  function motion() {
    var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !('IntersectionObserver' in window)) return;
    var blocks = document.querySelectorAll('.rr-reveal');
    if (blocks.length) {
      document.documentElement.classList.add('rr-motion');
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
      }, { rootMargin: '0px 0px -6% 0px', threshold: 0.01 });
      blocks.forEach(function (el) { io.observe(el); });
    }
    var mast = document.querySelector('.rr-masthead');
    var bands = document.querySelectorAll('.rr-band');
    if (mast && bands.length) {
      var tint = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) mast.style.setProperty('--here', getComputedStyle(e.target).backgroundColor);
        });
      }, { rootMargin: '-64px 0px -88% 0px' });
      bands.forEach(function (b) { tint.observe(b); });
      // Back above the first band: the plain wall again.
      var hero = document.querySelector('.rr-hero');
      if (hero) new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) mast.style.removeProperty('--here'); });
      }, { rootMargin: '-64px 0px -88% 0px' }).observe(hero);
    }
  }

  /* ---- storage that may not be there (private mode, previews) ---- */
  function load(key, fallback) { try { var v = sessionStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch (e) { return fallback; } }
  function keep(key, value) { try { if (value == null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) {} }

  /* ---- Back: the trail of pages that led here ----
     A home-screen app has no Back button, and a link to a page's "parent"
     is rarely where you were. So every page notes itself on a trail kept for
     this visit; the masthead's Back names the page before and returns to it.
     A tab's own page (no Back) starts the trail afresh. */
  var TRAIL = 'rr-trail';
  function here() { return location.pathname + location.search; }
  function hereTitle() { return document.body.getAttribute('data-here') || document.title.replace(/ · Faves$/, ''); }
  function arrive(cameBack) {
    var trail = load(TRAIL, []), now = here(), at = -1, top = trail[trail.length - 1];
    trail.forEach(function (e, i) { if (e.u === now) at = i; });
    var going = load('rr-going-back', null); keep('rr-going-back', null);
    var nav = (window.performance && performance.getEntriesByType && performance.getEntriesByType('navigation')[0] || {}).type;
    var returning = cameBack || going === now || nav === 'back_forward';
    // Back on a page drawn before something was saved -- a list still showing
    // a save you've since given a topic: draw it afresh.
    var stale = load('rr-stale', []);
    if (stale.indexOf(now) >= 0) {
      keep('rr-stale', stale.filter(function (u) { return u !== now; }));
      if (returning) {
        if (at >= 0) keep(TRAIL, trail.slice(0, at + 1));
        location.reload();
        return;
      }
    }
    if (document.body.hasAttribute('data-root')) {
      trail = [{ u: now, t: hereTitle() }];
    } else if (at >= 0 && returning) {
      trail = trail.slice(0, at + 1);                        // back to an earlier page: drop the ones above it
      if (going === now && trail[at].y) setTimeout(function () { window.scrollTo(0, trail[at].y); }, 0);
    } else if (top && top.u === now) {
      // A reload, or a save that refreshed the page: the same place.
    } else {
      // Refining a search replaces it rather than stacking every filter.
      if (top && top.u.split('?')[0] === '/search' && location.pathname === '/search') trail.pop();
      var prev = trail[trail.length - 1];
      trail.push({ u: now, t: hereTitle(), h: !!prev && document.referrer === location.origin + prev.u });
    }
    trail[trail.length - 1].t = hereTitle();
    keep(TRAIL, trail.slice(-30));
    var before = trail[trail.length - 2];
    document.querySelectorAll('[data-back]').forEach(function (a) {
      if (!before) return;
      a.setAttribute('href', before.u);
      var label = a.querySelector('[data-back-label]');
      if (label) label.textContent = before.t.length > 22 ? before.t.slice(0, 21) + '…' : before.t;
    });
  }
  // The feed moves its own address along as you flick; the trail follows.
  function renamed() { var trail = load(TRAIL, []); if (trail.length) { trail[trail.length - 1].u = here(); keep(TRAIL, trail); } }
  function goBack(e) {
    var a = e.target.closest && e.target.closest('[data-back]');
    if (!a) return;
    var trail = load(TRAIL, []), me = trail[trail.length - 1], before = trail[trail.length - 2];
    if (!before) return;                                      // the link's own parent page
    e.preventDefault();
    // Straight back through history when that is where we came from: the
    // page comes back as it was, scrolled where it was.
    if (me && me.h && history.length > 1) { history.back(); return; }
    keep('rr-going-back', before.u);
    location.href = before.u;
  }
  window.addEventListener('pagehide', function () {
    // A sheet left open would still be open when the page comes back.
    document.querySelectorAll('dialog[open]').forEach(function (d) { d.close(); });
    var trail = load(TRAIL, []);
    if (trail.length && trail[trail.length - 1].u === here()) { trail[trail.length - 1].y = Math.round(window.scrollY); keep(TRAIL, trail); }
  });
  window.addEventListener('pageshow', function (e) { if (e.persisted) arrive(true); });
  // Something was saved: every page behind this one on the trail may now be
  // out of date, and is drawn afresh when you go back to it.
  function changed() {
    var stale = load('rr-stale', []);
    load(TRAIL, []).slice(0, -1).forEach(function (e) { if (stale.indexOf(e.u) < 0) stale.push(e.u); });
    keep('rr-stale', stale.slice(-30));
  }

  /* ---- a word after saving, carried across the reload ---- */
  function toast(text) {
    var t = document.querySelector('.rr-toast');
    if (!t || !text) return;
    t.hidden = true; t.textContent = text;
    void t.offsetWidth;                                       // restart the animation
    t.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(function () { t.hidden = true; }, 2700);
  }

  /* ---- sheets: open, close on the scrim, pull down to close ---- */
  function openSheet(name, opener) {
    var d = document.getElementById(name + '-sheet');
    if (!d || typeof d.showModal !== 'function') return false;
    if (opener) d.dispatchEvent(new CustomEvent('rr-open', { detail: opener }));
    d.style.transform = '';
    d.showModal();
    return true;
  }
  function sheetDialog(d) {
    d.addEventListener('click', function (e) {
      if (e.target !== d) return;
      var r = d.getBoundingClientRect();
      if (e.clientY < r.top || e.clientY > r.bottom || e.clientX < r.left || e.clientX > r.right) d.close();
    });
    var y0 = null, dy = 0;
    d.querySelectorAll('.grab, header').forEach(function (h) {
      h.addEventListener('touchstart', function (e) { y0 = e.touches[0].clientY; dy = 0; d.classList.add('is-dragging'); }, { passive: true });
    });
    d.addEventListener('touchmove', function (e) {
      if (y0 == null) return;
      dy = Math.max(0, e.touches[0].clientY - y0);
      d.style.transform = 'translateY(' + dy + 'px)';
    }, { passive: true });
    d.addEventListener('touchend', function () {
      if (y0 == null) return;
      y0 = null; d.classList.remove('is-dragging');
      if (dy > 90) { d.close(); d.style.transform = ''; return; }
      d.classList.add('is-settling'); d.style.transform = '';
      setTimeout(function () { d.classList.remove('is-settling'); }, 220);
    });
  }

  /* ---- saving in place: no new page, so Back still goes where you were ---- */
  function post(form, submitter) {
    var data = new FormData(form);
    if (submitter && submitter.name) data.append(submitter.name, submitter.value);
    return fetch(form.getAttribute('action'), {
      method: 'POST', body: data, credentials: 'same-origin', headers: { Accept: 'application/json' }
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      changed();
      return r;
    });
  }
  function inplace(form) {
    form.addEventListener('submit', function (e) {
      if (form.hasAttribute('data-plain') || !window.fetch || !window.FormData) return;
      e.preventDefault();
      var by = e.submitter;
      form.classList.add('is-busy');
      post(form, by).then(function () {
        keep('rr-flash', form.getAttribute('data-inplace') + ' ✓');
        location.reload();                                    // the same page, the same place in history
      }).catch(function () {
        form.classList.remove('is-busy');
        form.setAttribute('data-plain', '');
        if (form.requestSubmit) form.requestSubmit(by || undefined); else form.submit();
      });
    });
  }

  /* ---- search results that keep coming as you scroll ----
     Each page of results arrives as its own wall below the last, so nothing
     already on screen reflows. The page links stay for no script. */
  function moreResults(pager) {
    var next = pager.querySelector('[data-next]');
    if (!next || !('IntersectionObserver' in window) || !window.DOMParser) return;
    pager.classList.add('is-auto');
    next.innerHTML = 'Show more';
    var busy = false, io;
    function fetchMore() {
      if (busy) return;
      busy = true; next.classList.add('is-busy');
      fetch(next.getAttribute('href'), { credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var wall = doc.querySelector('.explore-results .rr-salon');
        if (wall) pager.parentNode.insertBefore(document.importNode(wall, true), pager);
        var after = doc.querySelector('.pager [data-next]');
        if (after) { next.setAttribute('href', after.getAttribute('href')); busy = false; next.classList.remove('is-busy'); }
        else { io.disconnect(); pager.remove(); }
      }).catch(function () { location.href = next.getAttribute('href'); });
    }
    next.addEventListener('click', function (e) { e.preventDefault(); fetchMore(); });
    io = new IntersectionObserver(function (es) { es.forEach(function (x) { if (x.isIntersecting) fetchMore(); }); }, { rootMargin: '700px 0px' });
    io.observe(pager);
  }

  /* ---- Shuffle: the feed ----
     The page arrives with a first batch; more load three cards before the
     end, and earlier ones when you flick back up from where you came in.
     The address follows the card on screen, so coming back from a save's
     page -- or reloading -- lands on the same one. */
  function deck(feed) {
    var src = feed.getAttribute('data-cards');
    var more = feed.getAttribute('data-more') === '1', earlier = feed.getAttribute('data-earlier') === '1';
    var busy = false, shown = null;
    var hint = document.querySelector('.deck-hint'), left = document.querySelector('[data-left]');
    feed.querySelectorAll('[data-no-js]').forEach(function (n) { n.remove(); });
    function cards() { return feed.querySelectorAll('.rr-deckcard'); }
    function batch(param, id) {
      busy = true;
      return fetch(src + (src.indexOf('?') < 0 ? '?' : '&') + param + '=' + id, { credentials: 'same-origin' })
        .then(function (r) {
          if (!r.ok) throw new Error(r.status);
          return r.text().then(function (html) {
            var t = document.createElement('template'); t.innerHTML = html;
            return { nodes: t.content, more: r.headers.get('X-Deck-More') === '1' };
          });
        })
        .then(function (b) { busy = false; return b; }, function (err) { busy = false; throw err; });
    }
    function step(dir) { feed.scrollBy({ top: dir * feed.clientHeight, behavior: 'smooth' }); }
    function onScroll() {
      var h = feed.clientHeight || 1, i = Math.round(feed.scrollTop / h), screens = feed.children, card = screens[i];
      if (card && card.getAttribute('data-id') && card.getAttribute('data-id') !== shown) {
        shown = card.getAttribute('data-id');
        var p = new URLSearchParams(location.search);
        p.set('at', shown); p.delete('after');
        history.replaceState(history.state, '', location.pathname + '?' + p.toString());
        renamed();
      }
      if (hint && !hint.hidden && feed.scrollTop > 24) { hint.hidden = true; try { localStorage.setItem('rr-deck-hint', '1'); } catch (e) {} }
      var all = cards();
      if (more && !busy && all.length && i >= screens.length - 4) {
        batch('after', all[all.length - 1].getAttribute('data-id')).then(function (b) { feed.appendChild(b.nodes); more = b.more; }).catch(function () {});
      }
      if (earlier && !busy && all.length && i <= 1) {
        batch('before', all[0].getAttribute('data-id')).then(function (b) {
          var tall = feed.scrollHeight;
          feed.insertBefore(b.nodes, feed.firstChild);
          feed.scrollTop += feed.scrollHeight - tall;          // Safari has no scroll anchoring: stay on this card
          earlier = b.more;
        }).catch(function () {});
      }
    }
    var tick;
    feed.addEventListener('scroll', function () { if (!tick) tick = requestAnimationFrame(function () { tick = null; onScroll(); }); }, { passive: true });
    document.addEventListener('keydown', function (e) {
      if (document.querySelector('dialog[open]') || /INPUT|TEXTAREA|SELECT/.test((e.target || {}).tagName || '')) return;
      if (e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === 'j' || e.key === ' ') { e.preventDefault(); step(1); }
      if (e.key === 'ArrowUp' || e.key === 'PageUp' || e.key === 'k') { e.preventDefault(); step(-1); }
    });
    try { if (hint && !localStorage.getItem('rr-deck-hint')) hint.hidden = false; } catch (e) {}
    feed.focus({ preventScroll: true });
    onScroll();

    // Untagged: tap a topic or two, Done, and on to the next.
    feed.addEventListener('submit', function (e) {
      var form = e.target.closest && e.target.closest('.tagger');
      if (!form || !window.fetch) return;
      e.preventDefault();
      var card = form.closest('.rr-deckcard');
      if (!form.querySelector('input[name="room"]:checked')) { toast('Tap a topic first'); return; }
      post(form).then(function (r) { return r.json(); }).then(function (j) {
        card.classList.add('is-done');
        paintTopics(card, j);
        if (left) { var n = Math.max(0, parseInt(left.textContent, 10) - 1); left.textContent = n + ' left'; }
        toast('Filed under ' + (j.labels || []).join(', ') + ' ✓');
        setTimeout(function () { step(1); }, 420);
      }).catch(function () { form.submit(); });
    });

    // Every other card: topics and a note, in sheets over the feed.
    var topicSheet = document.getElementById('topic-sheet'), noteSheet = document.getElementById('note-sheet');
    var forCard = null;
    function paintTopics(card, j) {
      card.setAttribute('data-themes', (j.themes || []).join('|'));
      var label = card.querySelector('[data-topic]');
      if (label && j.labels && j.labels.length) label.textContent = j.labels[0];
    }
    if (topicSheet) topicSheet.addEventListener('rr-open', function (e) {
      forCard = e.detail.closest('.rr-deckcard');
      var have = (forCard.getAttribute('data-themes') || '').split('|');
      topicSheet.querySelectorAll('input[name="room"]').forEach(function (b) { b.checked = have.indexOf(b.value) >= 0; });
      topicSheet.querySelector('form.sheet-form').setAttribute('action', '/item/' + forCard.getAttribute('data-id') + '/rooms');
    });
    if (noteSheet) noteSheet.addEventListener('rr-open', function (e) {
      forCard = e.detail.closest('.rr-deckcard');
      noteSheet.querySelector('textarea').value = forCard.querySelector('[data-note]').textContent.trim();
      noteSheet.querySelector('form.sheet-form').setAttribute('action', '/item/' + forCard.getAttribute('data-id') + '/note');
    });
    [topicSheet, noteSheet].forEach(function (d) {
      if (!d) return;
      d.querySelector('form.sheet-form').addEventListener('submit', function (e) {
        e.preventDefault();
        var card = forCard;
        post(e.target).then(function (r) { return r.json(); }).then(function (j) {
          if (d === topicSheet) { paintTopics(card, j); toast('Topics saved ✓'); }
          else { var n = card.querySelector('[data-note]'); n.textContent = j.note; n.hidden = !j.note; toast('Note saved ✓'); }
          d.close();
        }).catch(function () { toast("Couldn't save that -- is Faves still running?"); });
      });
    });
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
    arrive(false);
    document.addEventListener('click', goBack);
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('[data-sheet-open]');
      if (a && openSheet(a.getAttribute('data-sheet-open'), a)) e.preventDefault();
    });
    document.querySelectorAll('.rr-sheet-dialog').forEach(sheetDialog);
    document.querySelectorAll('form[data-inplace]').forEach(inplace);
    document.querySelectorAll('.explore-results .pager').forEach(moreResults);
    document.querySelectorAll('[data-deck]').forEach(deck);
    var said = load('rr-flash', null);
    if (said) { keep('rr-flash', null); toast(said); }
    motion();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
