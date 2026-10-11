/* blog.html behaviour — externalised so the strict CSP needs no inline script. */
(function () {
  'use strict';

  var FALLBACK_POSTS = [
    { slug: 'introducing-voxylis-3-0', date: '2026-09-23', category: 'Product Update', title: 'Introducing Voxylis 3.0', excerpt: 'A real desktop window, API keys in the OS credential store, and local SQLite history.', read_time: '4 min read' },
    { slug: 'bitterest-lesson-voice-ai', date: '2026-08-28', category: 'Engineering', title: 'The Bitterest Lesson in Voice AI', excerpt: 'Why scaling data and compute beat every clever algorithmic trick we tried - and what that means for the future of voice input.', read_time: '6 min read' },
    { slug: 'ai-too-good-to-be-true', date: '2026-08-10', category: 'Product', title: 'AI: Too Good to Be True, Too Bad to Type', excerpt: 'AI writing assistants are everywhere - but typing is still the bottleneck. Voice input is the unlock.', read_time: '5 min read' },
    { slug: 'where-your-data-goes', date: '2026-07-22', category: 'Engineering', title: 'Where your audio and transcripts actually go', excerpt: 'A precise walkthrough of every place a recording touches disk or the network, and how to remove all of it.', read_time: '5 min read' }
  ];

  function esc(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function renderPosts(posts) {
    var grid = document.getElementById('blog-grid');
    if (!grid) return;
    if (!posts || posts.length === 0) {
      grid.innerHTML = '<div class="blog-empty"><p>No posts yet — check back soon.</p></div>';
      return;
    }
    grid.innerHTML = posts.map(function (p) {
      var d = new Date(p.date);
      var dateStr = isNaN(d.getTime()) ? '' : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
      return '<a href="/blog/' + encodeURIComponent(p.slug) + '" class="card blog-card">' +
        '<div class="blog-meta"><span class="blog-tag">' + esc(p.category || 'General') + '</span><span>' + esc(dateStr) + '</span></div>' +
        '<h3 class="card-title">' + esc(p.title) + '</h3>' +
        '<div class="blog-excerpt">' + esc(p.excerpt) + '</div>' +
        '<span class="blog-readmore">Read more →</span>' +
        '</a>';
    }).join('');
  }

  voxyFetch('/api/blog').then(function (r) {
    return r.ok ? r.json() : Promise.reject();
  }).then(function (data) {
    var posts = Array.isArray(data) ? data : (data.posts || []);
    renderPosts(posts);
  }).catch(function () {
    renderPosts(FALLBACK_POSTS);
  });
})();
