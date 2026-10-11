/* download.html behaviour — externalised so the strict CSP needs no inline
 * script. OS detection, real download targets, the version stamp and click
 * tracking. Never points a visitor at an installer that was not published.
 */
(function () {
  'use strict';

  // OS auto-detection: highlight the matching card.
  var ua = navigator.userAgent || '';
  var pl = navigator.platform || '';
  var isAndroid = ua.indexOf('Android') > -1;
  var isWin = pl.indexOf('Win') > -1 || ua.indexOf('Windows') > -1;
  var isMac = pl.indexOf('Mac') > -1 || ua.indexOf('Mac') > -1;
  var isLinux = ua.indexOf('Linux') > -1 && !isAndroid;
  var cardId = isWin ? 'card-windows' : (isMac ? 'card-macos' : (isLinux ? 'card-linux' : null));
  if (cardId) {
    var card = document.getElementById(cardId);
    if (card) {
      card.classList.add('highlighted');
      var badge = document.createElement('div');
      badge.className = 'os-badge';
      badge.textContent = 'Your OS';
      var versionEl = card.querySelector('.version');
      card.insertBefore(badge, versionEl || card.firstChild);
    }
  }

  // Load download URLs from API truth.
  function applyDownloadUrls(d) {
    var avail = d.available || {};
    var releases = d.releases_url || 'https://github.com/sumitagg24/Voxyai/releases';
    function setBtn(id, noteId, url, ok, okNote, fallbackNote) {
      var btn = document.getElementById(id);
      var note = document.getElementById(noteId);
      if (!btn) return;
      if (ok && url) {
        btn.href = url;
        btn.setAttribute('download', '');
        if (note) note.textContent = okNote;
      } else {
        btn.href = releases;
        btn.removeAttribute('download');
        if (note) note.textContent = fallbackNote;
      }
    }
    setBtn('dl-win', 'dl-win-note', d.windows, avail.windows,
      'Installer (.exe) — clicking starts the download',
      'No packaged installer yet — see releases or build from source');
    setBtn('dl-macos', 'dl-macos-note', d.macos, avail.macos,
      'Packaged download — clicking starts the file',
      'Source build — clone the repo and run run.sh (see releases)');
    setBtn('dl-linux', 'dl-linux-note', d.linux, avail.linux,
      'Packaged download — clicking starts the file',
      'Source build — clone the repo and run run.sh (see releases)');
  }

  fetch((window.VOXYLIS_API_BASE || '') + '/api/download/urls')
    .then(function (r) { return r.json(); })
    .then(applyDownloadUrls)
    .catch(function () {});

  // Version.
  fetch('/version.json').then(function (r) { return r.json(); }).then(function (d) {
    if (!d || !d.version) return;
    var els = document.querySelectorAll('[data-voxylis-version]');
    for (var i = 0; i < els.length; i++) els[i].textContent = 'v' + d.version;
  }).catch(function () {});

  function trackDownload(platform) {
    try {
      window.voxyBeacon && window.voxyBeacon('/api/download/track', { platform: platform });
    } catch (e) { /* navigation must never break */ }
  }

  var trackers = document.querySelectorAll('[data-track-download]');
  for (var t = 0; t < trackers.length; t++) {
    (function (el) {
      el.addEventListener('click', function () { trackDownload(el.getAttribute('data-track-download')); });
    })(trackers[t]);
  }

  // No scroll-reveal: content must be visible on load, on anchor jumps and
  // in full-page renders. Decorative scroll animation is outside the
  // Control Room motion spec (state transitions only).
})();
