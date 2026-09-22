/* Voxylis shared API helper.
 * Same-origin by default: the Flask backend serves the frontend and the
 * /api/* routes together, so relative calls just work.
 *
 * To point this static site at a separately-hosted backend (e.g. the
 * Vercel frontend talking to a Render/Railway API), do ANY of:
 *   - set window.VOXYLIS_API_BASE = 'https://your-backend.example.com'
 *     in a script tag BEFORE api.js loads, or
 *   - open any page once with ?api=https://your-backend.example.com
 *     (the choice is remembered in localStorage as voxy_api_base).
 * Every page on this site routes its API calls through voxyFetch(),
 * so one setting connects the whole frontend.
 */
(function () {
  var base = '';
  try {
    var m = window.location.search.match(/[?&]api=([^&]+)/);
    if (m) base = decodeURIComponent(m[1]);
    if (window.VOXYLIS_API_BASE) base = window.VOXYLIS_API_BASE;
    if (!base) base = localStorage.getItem('voxy_api_base') || '';
    if (base) {
      try { localStorage.setItem('voxy_api_base', base); } catch (e) {}
    }
  } catch (e) { /* ignore - fall back to same-origin */ }
  window.VOXY_API_BASE = String(base || '').replace(/\/+$/, '');
  window.voxyFetch = function (path, opts) {
    opts = opts || {};
    var headers = new Headers(opts.headers || {});
    var sid = '';
    try { sid = localStorage.getItem('session_id') || ''; } catch (e) {}
    if (sid && !headers.has('X-Session-Id')) headers.set('X-Session-Id', sid);
    opts.headers = headers;
    return fetch(window.VOXY_API_BASE + path, opts);
  };
  window.voxyBeacon = function (path, payload) {
    var url = window.VOXY_API_BASE + path;
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url, typeof payload === 'string' ? payload : JSON.stringify(payload));
        return;
      }
    } catch (e) { /* fall through to fetch */ }
    try {
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: typeof payload === 'string' ? payload : JSON.stringify(payload),
        keepalive: true
      }).catch(function () {});
    } catch (e) { /* analytics must never break the page */ }
  };
})();
