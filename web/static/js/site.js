/* Voxylis shared site behaviour.
 *
 * Externalised (P3.3) so every page works under a strict
 * Content-Security-Policy: script-src 'self' with no inline handlers.
 * Covers the two behaviours every page shares:
 *   - the mobile navigation toggle
 *   - the footer "Cookie choices" re-opener (clears the stored choice and
 *     reloads so the consent banner shows again)
 */
(function () {
  'use strict';

  function initNavToggle() {
    var toggle = document.querySelector('.nav-toggle');
    if (!toggle) return;
    toggle.addEventListener('click', function () {
      var links = document.querySelector('.nav-links');
      var right = document.querySelector('.nav-right');
      if (links) links.classList.toggle('open');
      if (right) right.classList.toggle('open');
    });
  }

  function initCookieChoices() {
    var links = document.querySelectorAll('[data-cookie-choices]');
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener('click', function (event) {
        event.preventDefault();
        try {
          localStorage.removeItem('voxy_cookie_consent');
        } catch (e) { /* storage may be unavailable; the banner still opens */ }
        if (typeof window.voxyShowCookieBanner === 'function') {
          window.voxyShowCookieBanner();
        } else {
          window.location.reload();
        }
      });
    }
  }

  function boot() {
    initNavToggle();
    initCookieChoices();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
