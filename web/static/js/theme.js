/* Voxylis theme engine — light / dark / system.
 * Loaded from <head> (before first paint) so the chosen theme applies
 * without a flash. Preference persists in localStorage (voxy_theme);
 * "system" follows prefers-color-scheme live, including OS changes.
 * The nav toggle (injected into every page) cycles light -> dark -> system.
 */
(function () {
  'use strict';

  var KEY = 'voxy_theme';
  var ORDER = ['light', 'dark', 'system'];

  function get() {
    try {
      var v = localStorage.getItem(KEY);
      return ORDER.indexOf(v) !== -1 ? v : 'system';
    } catch (e) {
      return 'system';
    }
  }

  function apply() {
    var t = get();
    document.documentElement.setAttribute('data-theme', t);
    var b = document.querySelector('.theme-toggle');
    if (b) {
      b.setAttribute('data-state', t);
      b.setAttribute('aria-label', 'Colour theme: ' + t + ' (click to change)');
      b.setAttribute('title', 'Theme: ' + t);
    }
  }

  function cycle() {
    var next = ORDER[(ORDER.indexOf(get()) + 1) % ORDER.length];
    try { localStorage.setItem(KEY, next); } catch (e) { /* stay per-load */ }
    apply();
  }

  var mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  if (mql && mql.addEventListener) {
    mql.addEventListener('change', function () {
      if (get() === 'system') apply();
    });
  }

  window.voxyThemeCycle = cycle;
  apply();

  function bind() {
    var b = document.querySelector('.theme-toggle');
    if (b) {
      b.addEventListener('click', cycle);
      b.setAttribute('data-state', get());
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
