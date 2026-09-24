/* Voxylis browser error monitoring.
 *
 * Off by default. The file does nothing until /api/public-config (or a
 * window.VOXYLIS_SENTRY_DSN set before this script) provides a browser DSN, so
 * a deployment without Sentry makes no third-party request at all and a
 * statically hosted site that has no backend simply stays quiet.
 *
 * What is reported
 *   uncaught errors, unhandled promise rejections, and failed API calls
 *   (route + HTTP status, never the response body or the submitted payload).
 *
 * What is never reported
 *   passwords, session ids, auth tokens, API keys, transcripts, question or
 *   answer text, and any URL carrying a token. Request bodies, headers and
 *   cookies are dropped before an event leaves the browser.
 *
 * A Sentry *browser* DSN is public by design. An organization or auth token
 * must never be placed here — release uploads live in CI.
 */
(function () {
  'use strict';

  var TOKEN_PARAM = /(?:token|reset_token|verify_token|session|key|secret|code)=/i;
  var SENSITIVE_FIELD = /pass|secret|token|key|credential|session|transcript|answer|question|message|content|text|email|phone/i;
  var SDK_URL = 'https://cdn.jsdelivr.net/npm/@sentry/browser@8/build/bundle.min.js';

  function isSensitiveKey(key) {
    return SENSITIVE_FIELD.test(String(key));
  }

  function scrub(value, depth) {
    depth = depth || 0;
    if (depth > 6) return '[redacted]';
    if (value instanceof Error) return { name: value.name, message: value.message };
    if (Array.isArray(value)) return value.map(function (item) { return scrub(item, depth + 1); });
    if (value && typeof value === 'object') {
      var out = {};
      Object.keys(value).forEach(function (key) {
        out[key] = isSensitiveKey(key) ? '[redacted]' : scrub(value[key], depth + 1);
      });
      return out;
    }
    if (typeof value === 'string' && value.length > 400) return '[' + value.length + ' chars withheld]';
    return value;
  }

  function stripUrl(url) {
    try {
      return String(url || '').split('?')[0].split('#')[0];
    } catch (e) {
      return '';
    }
  }

  function beforeSend(event) {
    try {
      delete event.query_string;
      if (event.request) {
        if (event.request.url) event.request.url = stripUrl(event.request.url);
        delete event.request.data;
        delete event.request.headers;
        delete event.request.cookies;
        delete event.request.query_string;
        delete event.request.env;
      }
      ['extra', 'contexts', 'breadcrumbs', 'tags', 'exception'].forEach(function (section) {
        if (event[section]) event[section] = scrub(event[section]);
      });
      if (event.message) event.message = scrub(String(event.message));
      // Locals are where a raw password or transcript would sit.
      var values = event.exception && event.exception.values ? event.exception.values : [];
      values.forEach(function (entry) {
        var frames = (entry.stacktrace && entry.stacktrace.frames) || [];
        frames.forEach(function (frame) { delete frame.vars; });
      });
      if (event.user) event.user = { id: event.user.id ? String(event.user.id) : undefined };
      if (event.breadcrumbs) {
        event.breadcrumbs = event.breadcrumbs.filter(function (crumb) {
          return !TOKEN_PARAM.test((crumb && crumb.data && crumb.data.url) || '');
        });
      }
    } catch (e) { /* scrubbing must never break the page */ }
    return event;
  }

  function loadSdk(dsn) {
    var script = document.createElement('script');
    script.src = SDK_URL;
    script.crossOrigin = 'anonymous';
    script.onload = function () { start(dsn); };
    script.onerror = function () { /* monitoring is optional */ };
    document.head.appendChild(script);
  }

  function start(dsn) {
    if (!window.Sentry || typeof window.Sentry.init !== 'function') return;
    try {
      window.Sentry.init({
        dsn: dsn,
        environment: window.VOXYLIS_ENV || 'production',
        release: window.VOXYLIS_RELEASE || undefined,
        tracesSampleRate: 0.05,
        sendDefaultPii: false,
        maxValueLength: 200,
        beforeSend: beforeSend,
        denyUrls: [
          /extensions\//i,
          /^chrome:\/\//i,
          /safari-extension/i
        ],
        ignoreErrors: [
          'ResizeObserver loop limit exceeded',
          'Non-Error promise rejection captured'
        ],
        initialScope: { tags: { component: 'website' } }
      });
    } catch (e) { return; }
    wrapApiCalls();
  }

  /* An API failure is the most useful signal on this site, and the safest to
   * report: route, method and status only. */
  function wrapApiCalls() {
    if (typeof window.voxyFetch !== 'function' || window.voxyFetch.__voxylisWrapped) return;
    var inner = window.voxyFetch;
    window.voxyFetch = function (path, opts) {
      var method = (opts && opts.method) || 'GET';
      var route = stripUrl(path);
      return inner.apply(this, arguments).then(function (response) {
        if (response && response.status >= 500) {
          window.Sentry.captureMessage('api error ' + response.status + ' ' + method + ' ' + route, {
            level: 'error',
            tags: { route: route, method: method, status: String(response.status) }
          });
        }
        return response;
      }).catch(function (err) {
        window.Sentry.captureException(err, {
          tags: { route: route, method: method, error_category: 'network' }
        });
        throw err;
      });
    };
    window.voxyFetch.__voxylisWrapped = true;
  }

  function boot() {
    var dsn = window.VOXYLIS_SENTRY_DSN || '';
    if (dsn) { loadSdk(dsn); return; }
    if (typeof fetch !== 'function') return;
    fetch('/api/public-config').then(function (r) { return r.json(); }).then(function (cfg) {
      if (!cfg || !cfg.sentry_dsn) return; /* monitoring stays off */
      window.VOXYLIS_ENV = cfg.environment || 'production';
      window.VOXYLIS_RELEASE = cfg.sentry_release || '';
      loadSdk(cfg.sentry_dsn);
    }).catch(function () { /* static hosting without an API: stay quiet */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
