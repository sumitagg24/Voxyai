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

  /* Signed-in nav state: after login the marketing pages must show WHO is
     signed in (name + live lamp, linking to the dashboard) instead of
     pretending the visitor is anonymous. Silent no-op when logged out. */
  function initSignedInNav() {
    var right = document.querySelector('.nav-right');
    if (!right || right.querySelector('.nav-user')) return;
    var sid = '';
    try { sid = localStorage.getItem('session_id') || ''; } catch (e) {}
    if (!sid || typeof window.voxyFetch !== 'function') return;
    window.voxyFetch('/api/me').then(function (resp) {
      if (!resp || !resp.ok) return;
      return resp.json().then(function (data) {
        var u = data && data.user;
        if (!u) return;
        var chip = document.createElement('a');
        chip.className = 'nav-user';
        chip.href = '/download';
        chip.title = u.email_or_phone || ('User #' + u.id);
        var lamp = document.createElement('span');
        lamp.className = 'lamp lamp--live';
        lamp.setAttribute('aria-hidden', 'true');
        var label = document.createElement('span');
        label.className = 'nav-user-name';
        label.textContent = u.name || u.email_or_phone || 'Dashboard';
        chip.appendChild(lamp);
        chip.appendChild(label);
        right.insertBefore(chip, right.firstChild);
      });
    }).catch(function () { /* navigation must never depend on this */ });
  }

  /* Reveal-on-scroll: quiet entrance for section headers and cards.
     No-JS and reduced-motion users see everything immediately. */
  function initReveal() {
    if (!('IntersectionObserver' in window)) return;
    var els = document.querySelectorAll('.section-header, .card, .legal-sec');
    for (var i = 0; i < els.length; i++) els[i].classList.add('reveal');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  }

  function boot() {
    initNavToggle();
    initCookieChoices();
    initSignedInNav();
    initReveal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
