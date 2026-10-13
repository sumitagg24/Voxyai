/* auth.html behaviour — externalised so the strict CSP needs no inline script.
 *
 * Four modes share one shell (auth.js picks from the URL):
 *   /auth                     -> sign in
 *   /auth?mode=signup         -> create account
 *   /auth?mode=forgot         -> request a reset link
 *   /auth?reset_token=...     -> choose a new password (link from the email)
 *   /auth?verify_token=...    -> email verification (auto-confirms on load)
 *
 * Social login keeps its explicit-consent overlay: no Voxylis session exists
 * until the visitor presses Continue. All errors render inline — no alert().
 */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var errorBox = $('formError');
  var noteBox = $('formNote');

  function showError(msg) {
    if (!errorBox) return;
    errorBox.textContent = msg;
    errorBox.hidden = false;
    if (noteBox) noteBox.hidden = true;
  }
  function clearMessages() {
    if (errorBox) errorBox.hidden = true;
    if (noteBox) noteBox.hidden = true;
  }
  function showNote(msg) {
    if (!noteBox) return;
    noteBox.textContent = msg;
    noteBox.hidden = false;
    if (errorBox) errorBox.hidden = true;
  }

  /* ---- mode switching ------------------------------------------------ */
  var TITLES = {
    signin: ['Welcome back', 'Sign in to access your dashboard, history, and subscription.'],
    signup: ['Create your account', 'One account for the desktop app, your history, and your licence.'],
    forgot: ['Reset your password', 'Enter your email and we\u2019ll send you a one-time reset link.'],
    reset: ['Choose a new password', 'Pick something strong \u2014 the link works only once.'],
  };
  var SWAPS = {
    signin: 'Don\u2019t have an account? <a href="/auth?mode=signup" class="auth-link" data-mode-link="signup">Sign up</a>',
    signup: 'Already have an account? <a href="/auth?mode=signin" class="auth-link" data-mode-link="signin">Sign in</a>',
    forgot: 'Remembered it? <a href="/auth?mode=signin" class="auth-link" data-mode-link="signin">Sign in</a>',
    reset: 'Remembered it? <a href="/auth?mode=signin" class="auth-link" data-mode-link="signin">Sign in</a>',
  };
  var FORMS = ['signinForm', 'signupForm', 'forgotForm', 'resetForm'];

  function setMode(mode) {
    if (FORMS.indexOf(mode === 'reset' ? 'resetForm' : mode + 'Form') === -1) mode = 'signin';
    FORMS.forEach(function (id) {
      var f = $(id);
      if (f) f.classList.toggle('hidden', id !== (mode === 'reset' ? 'resetForm' : mode + 'Form'));
    });
    var t = TITLES[mode] || TITLES.signin;
    var title = document.querySelector('.auth-title');
    var sub = document.querySelector('.auth-head .muted');
    if (title) title.textContent = t[0];
    if (sub) sub.textContent = t[1];
    var swap = $('modeSwapLine');
    if (swap) swap.innerHTML = SWAPS[mode] || SWAPS.signin;
    clearMessages();
  }

  function modeFromUrl() {
    var q = new URLSearchParams(window.location.search);
    if (q.get('reset_token')) return 'reset';
    if (q.get('mode')) return q.get('mode');
    return 'signin';
  }

  /* ---- loading helper ------------------------------------------------ */
  function busy(btn, on, label) {
    if (!btn) return;
    btn.disabled = on;
    if (on) {
      btn.dataset.label = btn.textContent;
      btn.textContent = label || 'Working\u2026';
    } else if (btn.dataset.label) {
      btn.textContent = btn.dataset.label;
    }
  }

  function goHome() { window.location.href = '/'; }

  /* ---- sign in (unchanged contract) ---------------------------------- */
  var form = $('signinForm');
  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearMessages();
      var btn = form.querySelector('button[type="submit"]');
      var email = form.email.value.trim();
      var password = form.password.value;
      var remember = form.remember.checked;
      if (!email || !password) { showError('Enter your email and password.'); return; }
      busy(btn, true, 'Signing in\u2026');
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
          goHome();
        } else {
          throw new Error('No session returned');
        }
      } catch (err) {
        busy(btn, false);
        showError(err.message);
      }
    });
  }

  /* ---- sign up -------------------------------------------------------- */
  var signup = $('signupForm');
  if (signup) {
    signup.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearMessages();
      var btn = signup.querySelector('button[type="submit"]');
      var name = signup.name.value.trim();
      var email = signup.email.value.trim();
      var password = signup.password.value;
      if (!name || !email || !password) { showError('All three fields are required.'); return; }
      if (password.length < 8) { showError('Password must be 8\u2013128 characters.'); return; }
      busy(btn, true, 'Creating account\u2026');
      try {
        var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, email_or_phone: email, password: password }),
        });
        var data = await resp.json();
        if (!resp.ok) throw new Error(data.error || data.message || 'Sign up failed');
        if (data.session_id) {
          try { localStorage.setItem('session_id', data.session_id); } catch (err) {}
          goHome();
        } else {
          showNote('Account created \u2014 check your inbox to verify your email, then sign in.');
          busy(btn, false);
        }
      } catch (err) {
        busy(btn, false);
        showError(err.message);
      }
    });
  }

  /* ---- forgot password ------------------------------------------------- */
  var forgot = $('forgotForm');
  if (forgot) {
    forgot.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearMessages();
      var btn = forgot.querySelector('button[type="submit"]');
      var email = forgot.email.value.trim();
      if (!email) { showError('Enter the email you signed up with.'); return; }
      busy(btn, true, 'Sending\u2026');
      try {
        var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email }),
        });
        var data = await resp.json();
        if (!resp.ok) throw new Error(data.error || data.message || 'Could not send the link');
        showNote('If that email has an account, a reset link is on its way. It expires soon.');
        busy(btn, false);
      } catch (err) {
        busy(btn, false);
        showError(err.message);
      }
    });
  }

  /* ---- reset password (from the emailed link) --------------------------- */
  var reset = $('resetForm');
  if (reset) {
    reset.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearMessages();
      var btn = reset.querySelector('button[type="submit"]');
      var q = new URLSearchParams(window.location.search);
      var token = q.get('reset_token') || '';
      var password = reset.password.value;
      if (!token) { showError('This reset link is missing its token \u2014 request a new one.'); return; }
      if (password.length < 8) { showError('Password must be 8\u2013128 characters.'); return; }
      busy(btn, true, 'Saving\u2026');
      try {
        var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: token, password: password }),
        });
        var data = await resp.json();
        if (!resp.ok) throw new Error(data.error || data.message || 'Reset failed');
        showNote('Password updated. You can sign in with it now.');
        busy(btn, false);
        reset.reset();
      } catch (err) {
        busy(btn, false);
        showError(err.message);
      }
    });
  }

  /* ---- email verification (auto-confirm from the emailed link) ---------- */
  (function verifyFromUrl() {
    var q = new URLSearchParams(window.location.search);
    var token = q.get('verify_token');
    if (!token) return;
    fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/verify-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token }),
    }).then(function (resp) {
      return resp.json().then(function (data) {
        if (resp.ok) showNote('Email verified \u2014 you\u2019re all set. Sign in below.');
        else showError(data.error || data.message || 'That verification link is invalid or expired.');
      });
    }).catch(function () { showError('Could not reach the server to verify your email.'); });
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', '/auth');
    }
  })();

  /* ---- mode links (data-mode-link) — no full reload needed -------------- */
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('[data-mode-link]') : null;
    if (!a) return;
    e.preventDefault();
    var mode = a.getAttribute('data-mode-link');
    setMode(mode);
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', mode === 'signin' ? '/auth' : '/auth?mode=' + mode);
    }
  });

  /* ---- OAuth consent overlay (unchanged contract) ----------------------- */
  var pendingIdToken = '';
  function showConsent(idToken) {
    pendingIdToken = idToken;
    var o = $('consent-overlay');
    if (o) o.classList.add('open');
  }
  function hideConsent() {
    var o = $('consent-overlay');
    if (o) o.classList.remove('open');
    pendingIdToken = '';
  }
  function bind(id, fn) {
    var b = $(id);
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
        goHome();
      }
    } catch (err) {
      showError(err.message);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });

  /* Social login: redirect to Auth0 /authorize built from the server config.
     The backend verifies the returned id_token (RS256, audience, issuer,
     email_verified) — nothing is trusted client-side. */
  var auth0Cfg = null;
  fetch((window.VOXYLIS_API_BASE || '') + '/api/auth/auth0/config')
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      auth0Cfg = cfg;
      if (!cfg || !cfg.enabled) {
        ['googleBtn', 'githubBtn'].forEach(function (id) {
          var b = $(id);
          if (b) b.classList.add('hidden');
        });
      }
    })
    .catch(function () { /* buttons stay; a click explains */ });

  function auth0Authorize(connection) {
    if (!auth0Cfg || !auth0Cfg.enabled) {
      showError('Social sign-in is not available right now. Please use email and password.');
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

  // Returning from Auth0: /auth#id_token=...&state=... — parse the fragment,
  // verify the state/nonce pair, clean the URL, gate on consent.
  (function parseAuth0Return() {
    if (!window.location.hash || window.location.hash.indexOf('id_token=') === -1) return;
    var tokens = {};
    window.location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
      var i = kv.indexOf('=');
      if (i > 0) {
        tokens[decodeURIComponent(kv.slice(0, i))] = decodeURIComponent(kv.slice(i + 1));
      }
    });
    var saved = '';
    try { saved = sessionStorage.getItem('voxy_auth0_nonce') || ''; } catch (e) {}
    if (!tokens.id_token || !tokens.state || tokens.state !== saved) return;
    try { sessionStorage.removeItem('voxy_auth0_nonce'); } catch (e) {}
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname);
    }
    showConsent(tokens.id_token);
  })();

  /* ---- boot mode --------------------------------------------------------- */
  setMode(modeFromUrl());
})();
