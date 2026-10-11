/* Voxylis API origin. Must load BEFORE api.js.
 * Same-origin by default: the Flask backend serves the frontend and the
 * /api/* routes together, so relative calls just work — including on
 * localhost, where a hardcoded remote origin would be blocked by the
 * connect-src CSP directive and leave the dashboard dead.
 * A deployment may inject `window.VOXYLIS_API_BASE = 'https://…'` in a
 * script tag BEFORE this file; api.js also honours ?api=<base-url>
 * (remembered in localStorage as voxy_api_base) for separately-hosted
 * frontends. file:// usage keeps the production API as its base.
 */
(function () {
  var preset = window.VOXYLIS_API_BASE || "";
  if (!preset) {
    if (window.location && window.location.protocol === "file:") {
      preset = "https://voxylis-api.onrender.com";
    } else {
      preset = "";
    }
  }
  window.VOXYLIS_API_BASE = String(preset).replace(/\/+$/, "");
})();
