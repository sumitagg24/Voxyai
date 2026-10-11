/* pricing.html behaviour — externalised so the strict CSP needs no inline
 * script. The CTAs are honest: they only open a hosted checkout when the
 * backend reports one is configured.
 */
(function () {
  'use strict';

  function setCTA(btn, available) {
    if (!btn) return;
    if (available) return; // let the anchor href work (hosted checkout link)
    btn.href = '/pricing';
    btn.textContent = btn.id === 'cta-free'
      ? 'Get Started (not available)'
      : (btn.id === 'cta-pro' ? 'Upgrade to Pro (not available)' : 'Contact Sales (not available)');
    btn.classList.add('btn-ghost');
    btn.addEventListener('click', function (event) {
      event.preventDefault();
      alert("Plans can't be purchased in this deployment yet.");
    });
  }

  async function wireCTAs() {
    try {
      var resp = await fetch((window.VOXYLIS_API_BASE || '') + '/api/subscription', {
        headers: { Accept: 'application/json' },
      });
      if (!resp.ok) return;
      var data = await resp.json();
      var available = data.subscription && data.subscription.checkout_available === true;
      setCTA(document.getElementById('cta-free'), available);
      setCTA(document.getElementById('cta-pro'), available);
      setCTA(document.getElementById('cta-business'), available);
    } catch (e) { /* leave the honest default copy in place */ }
  }
  wireCTAs();

  fetch('/version.json').then(function (r) { return r.json(); }).then(function (d) {
    if (!d || !d.version) return;
    var els = document.querySelectorAll('[data-voxylis-version]');
    for (var i = 0; i < els.length; i++) els[i].textContent = 'v' + d.version;
  }).catch(function () {});
})();
