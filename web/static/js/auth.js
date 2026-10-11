/* auth.html behaviour — externalised so the strict CSP needs no inline script.
 * Password sign-in form only. Social login is intentionally absent from the
 * website: the only backend Auth0 endpoint (POST /api/auth/auth0) consumes a
 * pre-obtained id_token, and the website has no token source — the desktop
 * app runs its own OAuth device flow instead. Dead provider buttons that
 * 405/404 would be worse than their absence.
 */
(function () {
  'use strict';

  // ?mode=signin (default) | signup | forgot. The links in the card point
  // here; each mode posts to the matching backend endpoint.
  var mode = 'signin';
  try {
    var m = window.location.search.match(/[?&]mode=([^&]+)/);
    if (m && (m[1] === 'signup' || m[1] === 'forgot')) mode = m[1];
  } catch (e) { /* default to signin */ }

  var form = document.getElementById('signinForm');
  if (form) {
    var title = document.getElementById('authTitle');
    var subtitle = document.getElementById('authSubtitle');
    var nameGroup = document.getElementById('nameGroup');
    var passwordGroup = document.getElementById('passwordGroup');
    var rememberRow = document.getElementById('rememberRow');
    var submit = document.getElementById('authSubmit');
    var modeSwitch = document.getElementById('modeSwitch');
    if (mode === 'signup') {
      if (title) title.textContent = 'Create your account';
      if (subtitle) subtitle.textContent = 'One account for the dashboard, history, and subscription.';
      if (nameGroup) nameGroup.hidden = false;
      if (submit) submit.textContent = 'Sign Up';
      if (modeSwitch) modeSwitch.innerHTML = 'Have an account? <a href="/auth" class="auth-link">Sign in</a>';
    } else if (mode === 'forgot') {
      if (title) title.textContent = 'Reset your password';
      if (subtitle) subtitle.textContent = 'We will email you a one-hour reset link if the address exists.';
      if (passwordGroup) passwordGroup.hidden = true;
      if (rememberRow) rememberRow.hidden = true;
      if (submit) submit.textContent = 'Send Reset Link';
      if (modeSwitch) modeSwitch.innerHTML = 'Remembered it? <a href="/auth" class="auth-link">Sign in</a>';
    }
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      var email = form.email.value.trim();
      var password = form.password.value;
      var remember = form.remember.checked;
      var original = btn.textContent;

      if (!email || (mode !== 'forgot' && !password)) return;

      btn.disabled = true;
      btn.textContent = 'Working\u2026';

      var url, body;
      if (mode === 'signup') {
        // NOTE: form.name would read the form's own name attribute, not the
        // input — address the field by id.
        var name = ((document.getElementById('name') || {}).value || '').trim();
        if (!name) { btn.disabled = false; btn.textContent = original; return; }
        url = '/api/auth/signup';
        body = { name: name, email_or_phone: email, password: password };
      } else if (mode === 'forgot') {
        url = '/api/auth/forgot-password';
        body = { email: email };
      } else {
        url = '/api/auth/login';
        body = { email_or_phone: email, password: password, remember: remember };
      }
      try {
        var resp = await fetch((window.VOXYLIS_API_BASE || '') + url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        var data = await resp.json();
        if (!resp.ok) throw new Error(data.error || data.message || 'Request failed');
        if (mode === 'forgot') {
          alert(data.message || 'If an account exists, a reset link has been sent.');
          window.location.href = '/auth';
        } else if (data.session_id) {
          try { localStorage.setItem('session_id', data.session_id); } catch (err) {}
          window.location.href = '/dashboard';
        } else {
          throw new Error('No session returned');
        }
      } catch (err) {
        btn.disabled = false;
        btn.textContent = original;
        alert(err.message);
      }
    });
  }
})();
