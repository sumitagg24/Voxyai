/* contact.html behaviour — externalised so the strict CSP needs no inline script. */
(function () {
  'use strict';

  var form = document.getElementById('contact-form');
  if (!form) return;

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    var btn = document.getElementById('submit-btn');
    var success = document.getElementById('msg-success');
    var error = document.getElementById('msg-error');
    success.classList.remove('show');
    error.classList.remove('show');
    btn.disabled = true;
    btn.textContent = 'Sending…';

    var data = {
      name: document.getElementById('name').value,
      email: document.getElementById('email').value,
      subject: document.getElementById('subject').value,
      message: document.getElementById('message').value,
    };

    try {
      var res = await voxyFetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        success.classList.add('show');
        form.reset();
      } else {
        var err = await res.json().catch(function () { return {}; });
        error.textContent = err.message || err.error || 'Something went wrong. Please try again.';
        error.classList.add('show');
      }
    } catch (e) {
      error.textContent = 'Network error. Please try again later.';
      error.classList.add('show');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Send Message';
    }
  });
})();
