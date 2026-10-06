/* Footprint — live results for the search and brand pages.
   Everything arrives as Server-Sent Events; nothing here talks to a platform.
   Text from the outside world is only ever set with textContent. */
(function () {
  'use strict';

  var $ = function (sel, root) { return (root || document).querySelector(sel); };

  function el(tag, props, kids) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      var v = props[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'text') node.textContent = v;
      else if (k === 'class') node.className = v;
      else node.setAttribute(k, v);
    });
    (kids || []).forEach(function (kid) {
      if (kid) node.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid);
    });
    return node;
  }

  function safeHref(url) {
    return /^https?:\/\//i.test(url || '') ? url : null;
  }

  function ago(iso) {
    if (!iso) return '';
    var days = Math.round((Date.now() - new Date(iso).getTime()) / 86400000);
    if (isNaN(days)) return '';
    if (days < 1) return 'today';
    if (days < 60) return days + ' days ago';
    if (days < 730) return Math.round(days / 30) + ' months ago';
    return Math.round(days / 365) + ' years ago';
  }

  /* ------------------------------------------------------------ colour mode */
  function initMode() {
    var buttons = document.querySelectorAll('.mode button');
    var current = 'auto';
    try { current = localStorage.getItem('fp-mode') || 'auto'; } catch (e) {}
    function apply(mode) {
      if (mode === 'auto') document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', mode);
      buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.mode === mode)); });
      try { localStorage.setItem('fp-mode', mode); } catch (e) {}
    }
    buttons.forEach(function (b) { b.addEventListener('click', function () { apply(b.dataset.mode); }); });
    apply(current);
  }

  /* --------------------------------------------------- health chip, polled */
  function initHealthChip() {
    var chip = $('#health-chip');
    if (!chip || !chip.classList.contains('running')) return;
    var timer = setInterval(function () {
      fetch('/health/progress').then(function (r) { return r.json(); }).then(function (s) {
        var label = chip.lastChild;
        if (s.running) {
          label.textContent = ' Checking sites… ' + s.progress.done + '/' + s.progress.total;
        } else {
          chip.classList.remove('running');
          label.textContent = ' ' + s.working + ' sites working · ' + s.set_aside + ' set aside';
          clearInterval(timer);
        }
      }).catch(function () { clearInterval(timer); });
    }, 4000);
  }

  /* ------------------------------------------------------------ the 24h chart */
  function drawClock(bars, labels, hint) {
    bars.textContent = '';
    labels.textContent = '';
    var peak = Math.max.apply(null, hint.histogram) || 1;
    var q = hint.quiet_utc;
    hint.histogram.forEach(function (n, h) {
      var quiet = q && ((q[0] <= q[1] && h >= q[0] && h < q[1]) || (q[0] > q[1] && (h >= q[0] || h < q[1])));
      var bar = el('span', { class: quiet ? 'quiet' : '', title: (h < 10 ? '0' : '') + h + ':00 UTC · ' + n + ' posts' });
      bar.style.height = (100 * n / peak) + '%';
      bars.appendChild(bar);
      labels.appendChild(el('span', { text: h % 3 === 0 ? String(h) : '' }));
    });
  }

  var STATE_WORDS = {
    found: 'Found', not_found: 'Not found', unclear: 'Unclear', cant_exist: "Can't exist", skipped: 'Set aside'
  };
  var PLAIN = {
    confirmed: 'Looks like a real profile, and not like a "no such account" page.',
    likely: 'No "not found" message — but this site has only one sign to check.'
  };
  var BAND_WORDS = {
    very_likely: 'Very likely the same', possibly: 'Possibly the same', no_evidence: 'No evidence'
  };

  /* ---------------------------------------------------------------- search */
  function initSearch() {
    var form = $('#search-form');
    if (!form) return;
    var source = null, ticker = null, t0 = 0;
    var tiles = {}, names = {}, counts = {};
    var total = 0, answered = 0;

    form.addEventListener('submit', function (e) { e.preventDefault(); start(); });
    if ($('#u').value.trim()) start();

    function tile(site, name, container) {
      var t = el('article', { class: 'tile waiting', 'data-site': site }, [
        el('div', { class: 'site', text: name }),
        el('div', { class: 'state' })
      ]);
      container.appendChild(t);
      tiles[site] = t;
      names[site] = name;
      return t;
    }

    function reset(u) {
      $('#run').hidden = false;
      $('#hero-name').textContent = '@' + u;
      ['#big', '#more', '#same-grid', '#tz-bars', '#tz-labels'].forEach(function (s) { $(s).textContent = ''; });
      ['#more-wrap', '#same', '#tz', '#tz-chart'].forEach(function (s) { $(s).hidden = true; });
      ['unclear', 'not_found', 'cant_exist', 'skipped'].forEach(function (k) {
        var d = $('#d-' + k);
        $('.n', d).textContent = '0';
        var body = $('.body', d);
        var list = $('ul', body);
        (list || body).textContent = '';
      });
      tiles = {}; names = {}; counts = {}; total = 0; answered = 0;
      $('#m-phase').textContent = 'Asking…';
      meter();
    }

    function meter() {
      $('#m-answered').textContent = answered;
      $('#m-total').textContent = total;
      $('#m-found').textContent = counts.found || 0;
      $('#m-unclear').textContent = counts.unclear || 0;
      $('#meter-fill').style.width = total ? (100 * answered / total) + '%' : '0';
    }

    function drawer(r) {
      var d = $('#d-' + r.status);
      if (!d) return;
      var n = $('.n', d);
      n.textContent = String(Number(n.textContent) + 1);
      var body = $('.body', d);
      var list = $('ul', body);
      if (list) {
        list.appendChild(el('li', {}, [el('span', { class: 'k', text: r.name }), el('span', { class: 'v', text: r.reason })]));
      } else {
        body.appendChild(el('a', { href: safeHref(r.url), target: '_blank', rel: 'noopener', title: r.reason, text: r.name }));
      }
    }

    function onResult(r) {
      answered += 1;
      counts[r.status] = (counts[r.status] || 0) + 1;
      meter();
      if (r.status !== 'found') drawer(r);
      var t = tiles[r.site];
      if (!t) {
        if (r.status !== 'found') return;
        $('#more-wrap').hidden = false;
        t = tile(r.site, r.name, $('#more'));
      }
      t.className = 'tile ' + r.status + (r.confidence ? ' ' + r.confidence : '') + ' just';
      $('.state', t).textContent = STATE_WORDS[r.status] || r.status;
      if (r.ms !== null && r.ms !== undefined && r.status !== 'skipped') {
        t.appendChild(el('span', { class: 'ms', text: (r.ms / 1000).toFixed(1) + 's' }));
      }
      if (r.status === 'found') {
        var state = $('.state', t);
        state.textContent = 'Found ';
        state.appendChild(el('span', { class: 'badge ' + r.confidence, text: r.confidence }));
        t.appendChild(el('a', { href: safeHref(r.url), target: '_blank', rel: 'noopener', text: r.url.replace(/^https?:\/\/(www\.)?/, '') }));
        // Plain words on the tile; the exact evidence is one hover away.
        t.appendChild(el('div', { class: 'why', title: r.reason, text: PLAIN[r.confidence] || r.reason }));
        t.appendChild(el('div', { class: 'who' }));
      } else if (r.status === 'unclear') {
        t.appendChild(el('div', { class: 'why', text: r.reason }));
      } else {
        t.title = r.reason;
      }
    }

    function onDetails(p) {
      var t = tiles[p.site];
      if (!t) return;
      var who = $('.who', t);
      if (!who) return;
      who.textContent = '';
      var pic = p.photo_thumb || safeHref(p.avatar_url);
      who.appendChild(pic ? el('img', { src: pic, alt: '', loading: 'lazy', referrerpolicy: 'no-referrer' }) : el('span', { class: 'ph' }));
      var facts = el('div', { class: 'facts' });
      if (p.hidden) facts.appendChild(el('span', { class: 'hidden-note', text: p.note }));
      if (p.location) facts.appendChild(el('span', { text: '📍 ' + p.location }));
      if (p.last_active) facts.appendChild(el('span', { text: 'active ' + ago(p.last_active) }));
      else if (p.created_at) facts.appendChild(el('span', { text: 'joined ' + ago(p.created_at) }));
      if (p.links && p.links.length) facts.appendChild(el('span', { text: p.links.length + (p.links.length === 1 ? ' link' : ' links') }));
      who.appendChild(el('div', {}, [
        p.display_name ? el('div', { class: 'dn', text: p.display_name }) : null,
        p.bio ? el('div', { class: 'bio', text: p.bio }) : null,
        facts
      ]));
    }

    function onMatch(a) {
      var sites = Object.keys(a.profiles);
      if (sites.length < 2) return;
      $('#same').hidden = false;
      var main = $('#same-main');
      main.textContent = a.main.length > 1
        ? 'Very likely the same person or brand: ' + a.main.map(function (s) { return names[s] || s; }).join(' · ')
        : 'No two accounts here show strong evidence of being the same person.';
      var grid = $('#same-grid');
      sites.sort(function (x, y) { return a.profiles[y].score - a.profiles[x].score; });
      sites.forEach(function (s) {
        var m = a.profiles[s];
        var bar = el('div', { class: 'scorebar' }, [el('span')]);
        bar.firstChild.style.width = m.score + '%';
        var reasons = el('ul');
        m.reasons.concat(m.notes || []).forEach(function (r) { reasons.appendChild(el('li', { text: r })); });
        if (!m.reasons.length && !(m.notes || []).length) reasons.appendChild(el('li', { text: 'Nothing on the profile links it to the others.' }));
        grid.appendChild(el('div', { class: 'match-card' }, [
          el('div', { class: 'head' }, [
            el('strong', { text: names[s] || s }),
            el('span', { class: 'band ' + m.band, text: BAND_WORDS[m.band] + ' · ' + m.score })
          ]),
          m['with'] ? el('div', { class: 'why', text: 'compared with ' + (names[m['with']] || m['with']) }) : null,
          bar, reasons
        ]));
      });
    }

    function onTimezone(h) {
      if (!h.posts) return;
      $('#tz').hidden = false;
      $('#tz-summary').textContent = h.summary;
      if (h.offset !== null && h.offset !== undefined) {
        $('#tz-chart').hidden = false;
        $('#tz-n').textContent = h.posts + ' public posts on ' + h.platforms.join(', ');
        drawClock($('#tz-bars'), $('#tz-labels'), h);
      }
    }

    function stop(phase) {
      if (source) source.close();
      source = null;
      clearInterval(ticker);
      $('#go').disabled = false;
      if (phase) $('#m-phase').textContent = phase;
    }

    function start() {
      var u = $('#u').value.trim().replace(/^@/, '');
      if (!u) return;
      var scope = form.querySelector('input[name=scope]:checked').value;
      var nsfw = form.querySelector('input[name=nsfw]').checked ? 1 : 0;
      try { history.replaceState(null, '', '/?u=' + encodeURIComponent(u)); } catch (e) {}
      stop();
      reset(u);
      $('#go').disabled = true;
      t0 = performance.now();
      ticker = setInterval(function () { $('#m-time').textContent = ((performance.now() - t0) / 1000).toFixed(1); }, 100);
      source = new EventSource('/search/stream?u=' + encodeURIComponent(u) + '&scope=' + scope + '&nsfw=' + nsfw);
      var on = function (name, fn) { source.addEventListener(name, function (e) { fn(JSON.parse(e.data)); }); };
      on('start', function (s) {
        total = s.total;
        s.big.forEach(function (b) { tile(b.site, b.name, $('#big')); });
        meter();
      });
      on('result', onResult);
      on('details', onDetails);
      on('searched', function (s) {
        clearInterval(ticker);
        $('#m-time').textContent = s.seconds.toFixed(1);
        $('#m-phase').textContent = (counts.found ? 'Reading the public profiles…' : 'Done.');
      });
      on('match', onMatch);
      on('timezone', onTimezone);
      on('done', function (d) { stop('Done — every site answered in ' + d.searched.toFixed(1) + ' s.'); });
      on('failed', function (f) { stop('Something went wrong: ' + f.message); });
      // The stream ends on its own after "done"; anything else is a dropped
      // connection. Don't let the browser silently start the search again.
      source.onerror = function () { if (source) stop('The connection dropped. Search again to retry.'); };
    }
  }

  /* ----------------------------------------------------------------- brand */
  function initBrand() {
    var form = $('#brand-form');
    if (!form) return;
    var source = null, report = null, answered = 0, found = 0;

    form.addEventListener('submit', function (e) { e.preventDefault(); start(); });

    function stop(phase) {
      if (source) source.close();
      source = null;
      $('#b-go').disabled = false;
      if (phase) $('#b-phase').textContent = phase;
    }

    function start() {
      var params = new URLSearchParams({
        name: $('#b-name').value.trim(), site: $('#b-site').value.trim(),
        handles: $('#b-handles').value.trim(),
        scope: form.querySelector('input[name=scope]:checked').value
      });
      stop();
      answered = 0; found = 0; report = null;
      $('#b-run').hidden = false;
      $('#b-report').hidden = true;
      $('#b-website').hidden = true;
      $('#b-answered').textContent = '0';
      $('#b-found').textContent = '0';
      $('#b-fill').style.width = '5%';
      $('#b-phase').textContent = 'Reading the website…';
      $('#b-go').disabled = true;
      source = new EventSource('/brand/stream?' + params.toString());
      var on = function (name, fn) { source.addEventListener(name, function (e) { fn(JSON.parse(e.data)); }); };
      on('website', onWebsite);
      on('result', function (r) {
        answered += 1;
        if (r.status === 'found') found += 1;
        $('#b-answered').textContent = answered;
        $('#b-found').textContent = found;
        $('#b-phase').textContent = 'Checking the handles…';
        $('#b-fill').style.width = Math.min(90, 10 + answered / 2) + '%';
      });
      on('details', function () { $('#b-phase').textContent = 'Reading the public profiles…'; });
      on('report', function (r) {
        $('#b-fill').style.width = '100%';
        stop('Done.');
        render(r);
      });
      on('failed', function (f) { stop('Something went wrong: ' + f.message); });
      source.onerror = function () { if (source) stop('The connection dropped. Build the report again to retry.'); };
    }

    function onWebsite(w) {
      $('#b-website').hidden = false;
      $('#b-site-title').textContent = 'Your website: ' + w.domain;
      var chips = $('#b-site-links');
      chips.textContent = '';
      if (w.error) {
        $('#b-site-sub').textContent = w.error;
        return;
      }
      $('#b-site-sub').textContent = w.profiles.length
        ? 'It links to ' + w.profiles.length + (w.profiles.length === 1 ? ' profile' : ' profiles') + ' — these count as confirmed yours.'
        : "It doesn't link to any profiles Footprint knows. Every account will be judged on its own evidence.";
      w.profiles.forEach(function (p) {
        chips.appendChild(el('a', { href: safeHref(p.url), target: '_blank', rel: 'noopener', text: p.site + ' @' + p.username + ' · ' + p.how }));
      });
    }

    var COUNT_WORDS = [['confirmed', 'Confirmed ours'], ['probably', 'Probably ours'], ['possibly', 'Possibly ours'],
      ['taken', 'Taken by others'], ['free', 'Free to claim'], ['dead_link', 'Dead links'], ['unknown', "Couldn't check"]];

    function render(r) {
      report = r;
      $('#b-report').hidden = false;
      var counts = $('#b-counts');
      counts.textContent = '';
      COUNT_WORDS.forEach(function (c) {
        if (!r.counts[c[0]]) return;
        counts.appendChild(el('div', { class: 'count ' + c[0] }, [el('b', { text: String(r.counts[c[0]]) }), el('span', { text: c[1] })]));
      });
      var findings = $('#b-findings');
      findings.textContent = '';
      (r.findings.length ? r.findings : [{ level: 'good', title: 'Nothing to fix that this report can see.' }]).forEach(function (f) {
        findings.appendChild(el('li', { class: f.level }, [el('div', { class: 't', text: f.title }), f.detail ? el('div', { class: 'd', text: f.detail }) : null]));
      });
      var rows = $('#b-rows');
      rows.textContent = '';
      r.rows.forEach(function (row) {
        var p = row.profile || {};
        var pic = p.photo_thumb || safeHref(p.avatar_url);
        var why = row.evidence.length ? el('ul', { class: 'evidence' })
          : el('span', { class: 'why', text: row.reason, title: row.detail && row.detail !== row.reason ? row.detail : null });
        row.evidence.forEach(function (e) { why.appendChild(el('li', { text: e })); });
        rows.appendChild(el('tr', {}, [
          el('td', { text: row.name }),
          el('td', {}, [el('div', { class: 'who' }, [
            pic ? el('img', { src: pic, alt: '', referrerpolicy: 'no-referrer' }) : null,
            el('div', {}, [
              el('a', { href: safeHref(row.url), target: '_blank', rel: 'noopener', text: '@' + row.username }),
              p.display_name ? el('div', { class: 'bio', text: p.display_name }) : null,
              p.location ? el('div', { class: 'bio', text: '📍 ' + p.location }) : null
            ])
          ])]),
          el('td', {}, [el('span', { class: 'pill ' + row.status, text: row.label })]),
          el('td', {}, [why])
        ]));
      });
      $('#b-tz-summary').textContent = r.posting.summary;
      if (r.posting.posts >= 30) {
        $('#b-tz-chart').hidden = false;
        drawClock($('#b-tz-bars'), $('#b-tz-labels'), r.posting);
      } else {
        $('#b-tz-chart').hidden = true;
      }
      picks(r);
      $('#b-json').href = '/brand/report/' + encodeURIComponent(r.id) + '.json';
    }

    function picks(r) {
      var box = $('#b-picks');
      box.textContent = '';
      r.rows.forEach(function (row) {
        if (['confirmed', 'probably', 'possibly'].indexOf(row.status) < 0) return;
        var input = el('input', { type: 'checkbox', value: row.url });
        input.checked = row.status !== 'possibly';
        input.addEventListener('change', update);
        box.appendChild(el('label', {}, [input, row.name + ' — ' + row.url + ' (' + row.label.toLowerCase() + ')']));
      });
      update();
    }

    function update() {
      var chosen = Array.prototype.map.call(document.querySelectorAll('#b-picks input:checked'), function (i) { return i.value; });
      var block = { '@context': 'https://schema.org', '@type': 'Organization' };
      if (report.brand.name) block.name = report.brand.name;
      block.url = report.brand.website;
      block.sameAs = chosen;
      $('#b-jsonld').textContent = '<script type="application/ld+json">\n' + JSON.stringify(block, null, 2) + '\n</' + 'script>';
      var q = new URLSearchParams({ download: '1' });
      chosen.forEach(function (u) { q.append('same_as', u); });
      if (!chosen.length) q.append('same_as', '');
      $('#b-download').href = '/brand/report/' + encodeURIComponent(report.id) + '?' + q.toString();
    }

    $('#b-copy').addEventListener('click', function () {
      var text = $('#b-jsonld').textContent;
      var btn = this;
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () {
        btn.textContent = 'Copied';
        setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
      }).catch(function () {
        var range = document.createRange();
        range.selectNodeContents($('#b-jsonld'));
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initMode();
    initHealthChip();
    initSearch();
    initBrand();
  });
})();
