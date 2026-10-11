/* Voxylis cookie consent banner.
 *
 * Honest by construction: this site currently sets NO analytics or marketing
 * cookies — sign-in session and API choice live in localStorage, and login
 * pages briefly touch Auth0/Google/GitHub only while you log in. The banner
 * therefore defaults everything optional to OFF, records the visitor's choice
 * in localStorage (voxy_cookie_consent), and never loads anything optional.
 *
 * Future optional loaders MUST gate on window.voxyCookieConsent():
 *   const c = window.voxyCookieConsent();
 *   if (c && c.analytics) { ...load analytics... }
 *
 * Reopen any time: window.voxyShowCookieBanner()
 * (the footer "Cookie choices" link clears the stored choice and reloads).
 */
(function () {
  'use strict';

  var KEY = 'voxy_cookie_consent';
  var CATS = ['necessary', 'preferences', 'analytics', 'marketing'];

  /* Banner styling lives in /static/css/cookie-consent.css (same-origin
   * stylesheet, so the strict CSP needs no inline <style> injection). */

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return null;
      var c = JSON.parse(raw);
      if (!c || c.necessary !== true) return null;
      return c;
    } catch (e) {
      return null;
    }
  }

  function save(prefs) {
    var c = { necessary: true, ts: new Date().toISOString() };
    CATS.slice(1).forEach(function (k) {
      c[k] = !!(prefs && prefs[k]);
    });
    try {
      localStorage.setItem(KEY, JSON.stringify(c));
    } catch (e) {}
    return c;
  }

  // Public: optional loaders gate on this. Null = visitor hasn't chosen yet
  // (treat as necessary-only).
  window.voxyCookieConsent = read;
  window.voxyShowCookieBanner = show;

  function el(html) {
    var d = document.createElement('div');
    d.innerHTML = html;
    return d.firstChild;
  }

  function current() {
    return read() || { necessary: true, preferences: false, analytics: false, marketing: false };
  }

  function hideBanner() {
    var b = document.getElementById('voxy-cc');
    if (b) b.classList.remove('open');
  }

  function show() {
    var b = document.getElementById('voxy-cc');
    if (b) b.classList.add('open');
  }

  function acceptAll() {
    save({ preferences: true, analytics: true, marketing: true });
    hideBanner();
  }

  function rejectNonEssential() {
    save({ preferences: false, analytics: false, marketing: false });
    hideBanner();
  }

  function openCustomize() {
    var c = current();
    document.getElementById('voxy-cm-preferences').checked = !!c.preferences;
    document.getElementById('voxy-cm-analytics').checked = !!c.analytics;
    document.getElementById('voxy-cm-marketing').checked = !!c.marketing;
    document.getElementById('voxy-cm').classList.add('open');
  }

  function closeCustomize() {
    document.getElementById('voxy-cm').classList.remove('open');
  }

  function saveCustomize() {
    save({
      preferences: document.getElementById('voxy-cm-preferences').checked,
      analytics: document.getElementById('voxy-cm-analytics').checked,
      marketing: document.getElementById('voxy-cm-marketing').checked,
    });
    closeCustomize();
    hideBanner();
  }

  function build() {
    if (document.getElementById('voxy-cc')) return;

    var banner = el(
      '<div class="voxy-cc" id="voxy-cc" role="dialog" aria-label="Cookie notice">' +
        '<h2>Cookie Notice</h2>' +
        '<p>Voxylis needs storage to keep you signed in. Optional categories stay off — ' +
        'we run no analytics or marketing cookies today — and turn on only if you allow them. ' +
        '<a href="/privacy#cookies">Read our Cookie Policy</a></p>' +
        '<button class="voxy-cc-btn primary" id="voxy-cc-accept" type="button">Accept all</button>' +
        '<button class="voxy-cc-btn" id="voxy-cc-reject" type="button">Reject non-essential</button>' +
        '<button class="voxy-cc-custom" id="voxy-cc-custom" type="button">Customize</button>' +
        '</div>'
    );

    var modal = el(
      '<div class="voxy-cm" id="voxy-cm" role="dialog" aria-modal="true" aria-label="Customize cookies">' +
        '<div class="voxy-cm-box">' +
        '<h3>Cookie choices</h3>' +
        '<p>Necessary storage is always on — the site cannot sign you in without it. ' +
        'Everything else is off until you allow it.</p>' +
        '<div class="voxy-cm-row"><div><b>Necessary</b>' +
        '<span>Sign-in session, security, load balancing. Always active.</span></div>' +
        '<input type="checkbox" checked disabled aria-label="Necessary (always on)"></div>' +
        '<div class="voxy-cm-row"><div><b>Preferences</b>' +
        '<span>Remembering choices like your API host. No tracking.</span></div>' +
        '<input type="checkbox" id="voxy-cm-preferences" aria-label="Preferences"></div>' +
        '<div class="voxy-cm-row"><div><b>Analytics</b>' +
        '<span>Anonymous usage measurement. Not used today.</span></div>' +
        '<input type="checkbox" id="voxy-cm-analytics" aria-label="Analytics"></div>' +
        '<div class="voxy-cm-row"><div><b>Marketing</b>' +
        '<span>Ads and cross-site tracking. Not used today.</span></div>' +
        '<input type="checkbox" id="voxy-cm-marketing" aria-label="Marketing"></div>' +
        '<div class="voxy-cm-actions">' +
        '<button class="voxy-cm-cancel" id="voxy-cm-cancel" type="button">Cancel</button>' +
        '<button class="voxy-cm-save" id="voxy-cm-save" type="button">Save choices</button>' +
        '</div></div></div>'
    );

    document.body.appendChild(banner);
    document.body.appendChild(modal);

    document.getElementById('voxy-cc-accept').addEventListener('click', acceptAll);
    document.getElementById('voxy-cc-reject').addEventListener('click', rejectNonEssential);
    document.getElementById('voxy-cc-custom').addEventListener('click', openCustomize);
    document.getElementById('voxy-cm-cancel').addEventListener('click', closeCustomize);
    document.getElementById('voxy-cm-save').addEventListener('click', saveCustomize);
    modal.addEventListener('click', function (e) {
      if (e.target.id === 'voxy-cm') closeCustomize();
    });
  }

  function boot() {
    build();
    if (!read()) show();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
