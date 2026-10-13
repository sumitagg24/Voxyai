/* auth.html behaviour — externalised so the strict CSP needs no inline script.
 * Sign-in form, OAuth buttons, and the explicit-consent overlay for social
 * login (no Voxylis session exists until the visitor presses Continue).
 */
(function () {
  'use strict';

  var form = document.getElementById('signinForm');
  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      var email = form.email.value.trim();
      var password = form.password.value;
      var remember = form.remember.checked;

      if (!email || !password) return;

      btn.disabled = true;
      btn.textContent = 'Signing in\u2026';

      try {
        var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email_or_phone: email, password: password, remember: remember }),
        });
        var data = await resp.json();
        if (!resp.ok) throw new Error(data.error || data.message || 'Sign in failed');
        if (data.session_id) {
          try { localStorage.setItem('session_id', data.session_id); } catch (err) {}
          window.location.href = '/dashboard';
        } else {
          throw new Error('No session returned');
        }
      } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Sign In';
        alert(err.message);
      }
    });
  }

  // OAuth button handlers with consent overlay
  var pendingIdToken = '';
  function showConsent(idToken) {
    // showConsent(tokens.id_token) - called by auth0 flow
    pendingIdToken = idToken;
    document.getElementById('consent-overlay').classList.add('open');
  }
  function hideConsent() {
    document.getElementById('consent-overlay').classList.remove('open');
    pendingIdToken = '';
  }
  function bind(id, fn) {
    var b = document.getElementById(id);
    if (b) b.addEventListener('click', fn);
  }
  bind('consent-cancel', function () { hideConsent(); });
  bind('consent-continue', async function () {
    var token = pendingIdToken;
    if (!token) { hideConsent(); return; }
    hideConsent();
    try {
      var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/auth0', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: token }),
      });
      var data = await resp.json();
      if (!resp.ok) throw new Error(data.error || data.message || 'Auth failed');
      if (data.session_id) {
        try { localStorage.setItem('session_id', data.session_id); } catch (e) {}
        window.location.href = '/dashboard';
      }
    } catch (err) {
      alert(err.message);
    }
  });
  // Social login: send the visitor to Auth0's /authorize endpoint (built from
  // the server's public config). Auth0 returns to /auth#id_token=...; the
  // handler below parses it, the consent overlay gates it, and the existing
  // POST /api/auth/auth0 exchanges it for a session. Nothing is trusted
  // client-side - the backend verifies the token signature, audience, issuer
  // and email_verified.
  var auth0Cfg = null;
  fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/auth0/config')
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      auth0Cfg = cfg;
      if (!cfg || !cfg.enabled) {
        // Honest UI: hide social buttons when the server has no Auth0 config.
        ['googleBtn', 'githubBtn'].forEach(function (id) {
          var b = document.getElementById(id);
          if (b) b.classList.add('hidden');
        });
      }
    })
    .catch(function () { /* buttons stay; click explains */ });

  function auth0Authorize(connection) {
    if (!auth0Cfg || !auth0Cfg.enabled) {
      alert('Social sign-in is not available right now. Please use email and password.');
      return;
    }
    var nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
    try { sessionStorage.setItem('voxy_auth0_nonce', nonce); } catch (e) {}
    var url = 'https://' + auth0Cfg.domain + '/authorize'
      + '?response_type=id_token'
      + '&client_id=' + encodeURIComponent(auth0Cfg.clientId)
      + '&redirect_uri=' + encodeURIComponent(window.location.origin + '/auth')
      + '&scope=' + encodeURIComponent('openid email profile')
      + '&state=' + encodeURIComponent(nonce)
      + '&nonce=' + encodeURIComponent(nonce)
      + '&connection=' + encodeURIComponent(connection);
    window.location.href = url;
  }
  bind('googleBtn', function () { auth0Authorize('google-oauth2'); });
  bind('githubBtn', function () { auth0Authorize('github'); });

  // Exported for the token-exchange flow.
  window.voxyShowConsent = showConsent;

  // Returning from Auth0: /auth#id_token=...&state=... Parse the fragment,
  // verify the state/nonce pair we set before redirecting, clear the URL,
  // and gate the exchange behind the consent overlay.
  (function parseAuth0Return() {
    if (!window.location.hash || window.location.hash.indexOf('id_token=') === -1) return;
    var parts = {};
    window.location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
      var i = kv.indexOf('=');
      if (i > 0) {
        parts[decodeURIComponent(kv.slice(0, i))] = decodeURIComponent(kv.slice(i + 1));
      }
    });
    var saved = '';
    try { saved = sessionStorage.getItem('voxy_auth0_nonce') || ''; } catch (e) {}
    if (!parts.id_token || !parts.state || parts.state !== saved) return;
    try { sessionStorage.removeItem('voxy_auth0_nonce'); } catch (e) {}
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname);
    }
    showConsent(parts.id_token);
  })();
})();
