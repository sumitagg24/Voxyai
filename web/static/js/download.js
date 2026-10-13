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

  // Availability notes. Buttons point at the same-origin /download/<platform>
  // routes (in the HTML), which resolve the real asset server-side — clicks
  // download from the site and never land on a GitHub page.
  function applyDownloadUrls(d) {
    var avail = d.available || {};
    function setNote(id, ok, okNote, fallbackNote) {
      var note = document.getElementById(id);
      if (note) note.textContent = ok ? okNote : fallbackNote;
    }
    setNote('dl-win-note', avail.windows,
      'Installer (.exe) — clicking starts the download',
      'No packaged installer yet — build from source (see releases)');
    setNote('dl-macos-note', avail.macos,
      'Packaged download — clicking starts the file',
      'Source archive (.zip) — unzip and run run.sh');
    setNote('dl-linux-note', avail.linux,
      'Packaged download — clicking starts the file',
      'Source archive (.tar.gz) — extract and run run.sh');
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

  // Scroll reveal (progressive enhancement).
  try {
    var revealEls = document.querySelectorAll('.card, .req-card');
    if ('IntersectionObserver' in window && revealEls.length) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); }
        });
      }, { threshold: 0.1 });
      revealEls.forEach(function (el) { el.classList.add('reveal'); io.observe(el); });
    }
  } catch (e) { /* reveal is decorative */ }
})();
