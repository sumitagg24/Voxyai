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
      var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/auth0/approve', {
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
  bind('googleBtn', function () {
    window.location.href = (window.VOXYLIS_API_BASE || '') + '/api/auth/auth0?provider=google';
  });
  bind('githubBtn', function () {
    window.location.href = (window.VOXYLIS_API_BASE || '') + '/api/auth/auth0?provider=github';
  });

  // Exported for the token-exchange flow.
  window.voxyShowConsent = showConsent;
})();
