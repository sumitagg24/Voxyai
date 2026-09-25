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

  var CSS = [
    '.voxy-cc{position:fixed;left:20px;bottom:20px;z-index:2000;max-width:380px;background:#fff;color:#1e1e1e;border-radius:16px;box-shadow:0 12px 48px rgba(0,0,0,.22);padding:24px;font-family:"Host Grotesk",Inter,"Helvetica Neue",Arial,sans-serif;display:none}',
    '.voxy-cc.open{display:block}',
    '.voxy-cc h2{font-size:20px;font-weight:700;letter-spacing:-0.01em;margin:0 0 10px}',
    '.voxy-cc p{font-size:14px;line-height:1.6;color:#3a3a3a;margin:0 0 18px}',
    '.voxy-cc a{color:#1a73e8;text-decoration:none}',
    '.voxy-cc a:hover{text-decoration:underline}',
    '.voxy-cc button{font-family:inherit;cursor:pointer}',
    '.voxy-cc-btn{display:block;width:100%;padding:12px;border:1px solid #e0e0e0;background:#fff;color:#1e1e1e;border-radius:999px;font-size:15px;font-weight:600;margin-bottom:10px;transition:background .15s,border-color .15s}',
    '.voxy-cc-btn:hover{background:#f5f5f5;border-color:#1e1e1e}',
    '.voxy-cc-btn.primary{background:#1e1e1e;color:#fff;border-color:#1e1e1e}',
    '.voxy-cc-btn.primary:hover{background:#000}',
    '.voxy-cc-custom{display:block;width:100%;background:none;border:none;color:#1e1e1e;font-size:15px;font-weight:500;padding:6px;text-decoration:none}',
    '.voxy-cc-custom:hover{text-decoration:underline}',
    '.voxy-cm{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2001;display:none;align-items:center;justify-content:center;padding:20px}',
    '.voxy-cm.open{display:flex}',
    '.voxy-cm-box{background:#fff;color:#1e1e1e;border-radius:16px;max-width:440px;width:100%;padding:28px;font-family:"Host Grotesk",Inter,"Helvetica Neue",Arial,sans-serif}',
    '.voxy-cm-box h3{font-size:20px;font-weight:700;margin:0 0 6px}',
    '.voxy-cm-box>p{font-size:14px;color:#3a3a3a;margin:0 0 16px;line-height:1.6}',
    '.voxy-cm-row{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:12px 0;border-top:1px solid #eee}',
    '.voxy-cm-row b{display:block;font-size:15px}',
    '.voxy-cm-row span{display:block;font-size:13px;color:#858585;margin-top:2px;line-height:1.5}',
    '.voxy-cm-row input{width:44px;height:24px;accent-color:#1e1e1e;flex-shrink:0;margin-top:2px;cursor:pointer}',
    '.voxy-cm-row input:disabled{cursor:not-allowed}',
    '.voxy-cm-actions{display:flex;gap:12px;margin-top:20px}',
    '.voxy-cm-actions button{flex:1;padding:12px;border-radius:999px;font-size:15px;font-weight:600;cursor:pointer;font-family:inherit}',
    '.voxy-cm-save{background:#1e1e1e;color:#fff;border:1px solid #1e1e1e}',
    '.voxy-cm-cancel{background:#fff;color:#1e1e1e;border:1px solid #e0e0e0}',
    '@media(max-width:480px){.voxy-cc{left:12px;right:12px;bottom:12px;max-width:none}}',
  ].join('\n');

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

  function injectCss() {
    if (document.getElementById('voxy-cc-css')) return;
    var s = document.createElement('style');
    s.id = 'voxy-cc-css';
    s.textContent = CSS;
    document.head.appendChild(s);
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
    injectCss();

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
        '<input type="checkbox" id="voxy-cm-preferences"></div>' +
        '<div class="voxy-cm-row"><div><b>Analytics</b>' +
        '<span>Anonymous usage measurement. Not used today.</span></div>' +
        '<input type="checkbox" id="voxy-cm-analytics"></div>' +
        '<div class="voxy-cm-row"><div><b>Marketing</b>' +
        '<span>Ads and cross-site tracking. Not used today.</span></div>' +
        '<input type="checkbox" id="voxy-cm-marketing"></div>' +
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
