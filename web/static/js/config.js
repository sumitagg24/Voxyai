/* Voxylis production API origin (Render). Must load BEFORE api.js.
 * Same-origin by default when this file is absent; api.js also honours
 * ?api=<base-url> (remembered in localStorage as voxy_api_base).
 * Externalised (P2.4) so Content-Security-Policy needs no 'unsafe-inline'.
 */
window.VOXYLIS_API_BASE = "https://voxylis-api.onrender.com";
