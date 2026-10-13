/* Legal pages behaviour (Terms / Privacy):
 *  - builds the table of contents from the document's h2 headings
 *  - scroll-spies the active section
 *  - section search filter
 *  - text-size preference (A- / A / A+), persisted in localStorage
 *  - print / "save as PDF" hand-off to the browser dialog
 * No dependencies, CSP-safe (external file), everything degrades gracefully.
 */
(function () {
  'use strict';

  var doc = document.querySelector('.legal-doc');
  var tocHost = document.getElementById('legalToc');
  if (!doc || !tocHost) return;

  var FS_KEY = 'voxy_legal_fs';

  /* ---- toolbar -------------------------------------------------------- */
  var tools = document.createElement('div');
  tools.className = 'legal-tools';

  var search = document.createElement('input');
  search.type = 'search';
  search.className = 'legal-search';
  search.placeholder = 'Filter sections\u2026';
  search.setAttribute('aria-label', 'Filter sections');

  function fsBtn(label, value, title) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'legal-btn';
    b.textContent = label;
    b.title = title;
    b.addEventListener('click', function () {
      try { localStorage.setItem(FS_KEY, value); } catch (e) {}
      applyFs(value);
    });
    return b;
  }
  var fsMinus = fsBtn('A\u2212', 'sm', 'Smaller text');
  var fsReset = fsBtn('A', 'md', 'Default text size');
  var fsPlus = fsBtn('A+', 'lg', 'Larger text');
  var fsMax = fsBtn('A++', 'xl', 'Largest text');
  var printBtn = document.createElement('button');
  printBtn.type = 'button';
  printBtn.className = 'legal-btn';
  printBtn.textContent = 'Print / PDF';
  printBtn.title = 'Print this page, or save it as a PDF';
  printBtn.addEventListener('click', function () { window.print(); });

  tools.appendChild(search);
  tools.appendChild(fsMinus);
  tools.appendChild(fsReset);
  tools.appendChild(fsPlus);
  tools.appendChild(fsMax);
  tools.appendChild(printBtn);
  tocHost.appendChild(tools);

  function applyFs(v) {
    if (v === 'sm') { document.documentElement.removeAttribute('data-fs'); }
    else { document.documentElement.setAttribute('data-fs', v === 'xl' ? 'xl' : v); }
    [fsMinus, fsReset, fsPlus, fsMax].forEach(function (b) { b.removeAttribute('aria-pressed'); });
    var active = { sm: fsMinus, md: fsReset, lg: fsPlus, xl: fsMax }[v];
    if (active) active.setAttribute('aria-pressed', 'true');
  }
  var savedFs = 'md';
  try { savedFs = localStorage.getItem(FS_KEY) || 'md'; } catch (e) {}
  applyFs(savedFs);

  /* ---- table of contents from h2 headings ------------------------------ */
  var sections = Array.prototype.slice.call(doc.querySelectorAll('.legal-sec'));
  var nav = document.createElement('nav');
  nav.setAttribute('aria-label', 'On this page');
  var links = [];

  sections.forEach(function (sec, i) {
    if (!sec.id) sec.id = 'sec-' + (i + 1);
    var h2 = sec.querySelector('h2');
    if (!h2) return;
    var a = document.createElement('a');
    a.href = '#' + sec.id;
    a.textContent = h2.textContent;
    nav.appendChild(a);
    links.push([a, sec]);
  });
  tocHost.appendChild(nav);

  if ('IntersectionObserver' in window && links.length) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (pair) {
          pair[0].classList.toggle('active', pair[1] === e.target);
        });
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    sections.forEach(function (s) { spy.observe(s); });
  }

  /* ---- mobile TOC toggle ------------------------------------------------ */
  if (links.length) {
    var tgl = document.createElement('button');
    tgl.type = 'button';
    tgl.className = 'legal-btn toc-mobile-toggle';
    tgl.textContent = 'On this page \u25BE';
    tgl.setAttribute('aria-expanded', 'false');
    tgl.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      tgl.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    tocHost.insertBefore(tgl, nav);
  }

  /* ---- section filter ----------------------------------------------------- */
  search.addEventListener('input', function () {
    var q = search.value.trim().toLowerCase();
    sections.forEach(function (sec) {
      var hit = !q || sec.textContent.toLowerCase().indexOf(q) !== -1;
      sec.classList.toggle('no-match', !hit);
    });
    links.forEach(function (pair) {
      var sec = pair[1];
      pair[0].style.display = sec.classList.contains('no-match') ? 'none' : '';
    });
  });
})();
