/* blog-post.html behaviour — externalised so the strict CSP needs no inline
 * script. Fetches the post from the API, falls back to a bundled copy when the
 * backend is unreachable, and renders it with text-safe escaping.
 */
(function () {
  'use strict';

  var slug = null;
  var params = new URLSearchParams(window.location.search);
  if (params.get('slug')) {
    slug = params.get('slug');
  } else {
    var parts = window.location.pathname.split('/').filter(Boolean);
    if (parts.length >= 2 && parts[0] === 'blog') {
      slug = parts[1];
    } else if (parts.length === 1 && parts[0] !== 'blog' && parts[0] !== 'blog-post.html') {
      slug = parts[0];
    }
  }
  if (slug === 'introducing-voxy-2-0') {
    slug = 'introducing-voxylis-3-0';
  }

  var container = document.getElementById('postContainer');
  var loading = document.getElementById('postLoading');
  var notFound = document.getElementById('postNotFound');
  var related = document.getElementById('relatedSection');

  // Offline fallback: the same four posts the API seeds, shown when the backend
  // is unreachable (e.g. static hosting without an API server).
  var FALLBACK_POSTS = {
    "introducing-voxylis-3-0": { title: "Introducing Voxylis 3.0", date: "2026-09-23", category: "Product Update", read_time: "4 min read", content: "## What changed\n\nVoxylis 3.0 turns the tray utility into a desktop application.\n\n- **A real main window** - Home, History, Microphone, AI Providers, Shortcuts, Privacy, Account, Diagnostics and About. The overlay is now just a transient status pill.\n- **Encrypted API keys** - stored in the OS credential store (Windows DPAPI or your keyring), automatically migrated out of the plaintext settings file.\n- **User data outside the install directory** - settings, history, logs and temp audio live under `%LOCALAPPDATA%` inside a Voxylis folder.\n- **Local SQLite history** - per-entry delete, retention, export, and an off switch.\n- **Recorded shortcuts** - every shortcut field captures real key presses and rejects reserved Windows combinations.\n\n## Honest limits\n\nVoxylis does not train or host a speech model; your Groq or OpenAI key does the recognition. Paid plans are described on the pricing page but cannot be purchased yet." },
    "bitterest-lesson-voice-ai": { title: "The Bitterest Lesson in Voice AI", date: "2026-08-28", category: "Engineering", read_time: "6 min read", content: "## The lesson\n\nScaling **data and compute** beat every clever algorithmic trick we tried.\n\n## What worked\n\n- More diverse **training audio** across accents and microphones.\n- Tighter **feedback loops** from real user corrections.\n- Simple pipelines that are easy to measure and improve.\n\n## Takeaway\n\nBetter pipelines and feedback loops beat bigger models." },
    "ai-too-good-to-be-true": { title: "AI: Too Good to Be True, Too Bad to Type", date: "2026-08-10", category: "Product", read_time: "5 min read", content: "## The bottleneck\n\nAI writing assistants are everywhere, but you still have to **type the prompt**. That gap is the reason this app exists.\n\n## What the app does\n\n1. **Capture** - hold your shortcut, speak, release.\n2. **Transcribe** - the audio goes to the provider whose key you supplied.\n3. **Optionally rewrite** - Formal, Casual, Technical, Concise, Creative, or your own prompt.\n4. **Insert** - clipboard, then SendInput, then character-by-character typing, with a real result either way.\n\n## No invented multipliers\n\nHow much faster speech is than typing depends on you, your microphone and your provider. We publish no single fixed number for it." },
    "where-your-data-goes": { title: "Where your audio and transcripts actually go", date: "2026-07-22", category: "Engineering", read_time: "5 min read", content: "## On the network\n\nOne request per utterance, to the provider whose key you configured: speech-to-text, and (only if you enabled it) enhancement. Nothing at all if you only use voice commands. There is no analytics endpoint and no usage tracking.\n\nThe one optional exception is crash reporting, which is **off until you turn it on** in Settings then Privacy. When it is on, a failure sends the error type, a stack trace, the app version, your OS and the provider name - never a transcript, a clipboard item, an API key or your email address.\n\n## On disk\n\n- **Audio** is a temporary WAV inside your user-data folder, deleted after upload.\n- **Transcripts** live in a SQLite database under `%LOCALAPPDATA%` with retention and per-entry delete.\n- **API keys** live in the OS credential store, never in a settings file or diagnostics.\n- **Logs** record sizes, languages and model names. Transcript text is not logged.\n\n## Removing everything\n\nSettings then Privacy wipes the history database, and the data folder is one click away.\n\n## What we do not claim\n\nAudio does leave your machine for the provider, under their retention policy. On-device transcription is not offered yet." }
  };

  function esc(str) {
    var div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function inlineFormat(text) {
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    return text;
  }

  function renderContent(content) {
    var lines = content.split('\n');
    var out = [];
    var inList = false;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) {
        if (inList) { out.push('</ul>'); inList = false; }
        continue;
      }
      if (line.match(/^## /)) {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push('<h2>' + inlineFormat(line.replace(/^## /, '')) + '</h2>');
        continue;
      }
      if (line.match(/^### /)) {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push('<h3>' + inlineFormat(line.replace(/^### /, '')) + '</h3>');
        continue;
      }
      if (line.match(/^[-*] /)) {
        if (!inList) { out.push('<ul>'); inList = true; }
        out.push('<li>' + inlineFormat(line.replace(/^[-*] /, '')) + '</li>');
        continue;
      }
      if (line.match(/^> /)) {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push('<blockquote>' + inlineFormat(line.replace(/^> /, '')) + '</blockquote>');
        continue;
      }
      if (inList) { out.push('</ul>'); inList = false; }
      out.push('<p>' + inlineFormat(line) + '</p>');
    }
    if (inList) out.push('</ul>');
    return out.join('\n');
  }

  function renderPost(post) {
    document.title = post.title + ' — Voxylis';

    var html = '<article class="post-header">';
    html += '<a href="/blog" class="post-back">← Back to Blog</a>';
    html += '<div class="post-meta">';
    if (post.category) html += '<span class="post-badge">' + esc(post.category) + '</span>';
    if (post.date) html += '<span class="post-date">' + esc(post.date) + '</span>';
    if (post.read_time) html += '<span class="post-readtime">' + esc(post.read_time) + '</span>';
    html += '</div>';
    html += '<h1>' + esc(post.title) + '</h1>';
    html += '</article>';

    html += '<div class="post-body">';
    html += renderContent(post.content || '');
    html += '</div>';

    html += '<div class="share-row">';
    html += '<span class="label share-label">Share this post</span>';
    html += '<button class="share-btn" data-share="twitter" type="button">Twitter</button>';
    html += '<button class="share-btn" data-share="linkedin" type="button">LinkedIn</button>';
    html += '<button class="share-btn" data-share="copy" type="button">Copy Link</button>';
    html += '</div>';

    loading.outerHTML = html;
    related.hidden = false;
  }

  function showNotFound() {
    loading.hidden = true;
    notFound.hidden = false;
  }

  if (!slug) {
    showNotFound();
    return;
  }

  voxyFetch('/api/blog/' + encodeURIComponent(slug))
    .then(function (res) {
      if (!res.ok) throw new Error('Not found');
      return res.json();
    })
    .then(renderPost)
    .catch(function () {
      if (FALLBACK_POSTS[slug]) renderPost(FALLBACK_POSTS[slug]);
      else showNotFound();
    });

  function shareTwitter() {
    var title = document.title;
    var url = window.location.href;
    window.open('https://twitter.com/intent/tweet?text=' + encodeURIComponent(title) + '&url=' + encodeURIComponent(url), '_blank', 'width=550,height=420');
  }
  function shareLinkedIn() {
    var url = window.location.href;
    window.open('https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(url), '_blank', 'width=550,height=420');
  }
  function copyLink(btn) {
    if (!btn) return;
    function done() {
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.textContent = 'Copy Link';
        btn.classList.remove('copied');
      }, 2000);
    }
    navigator.clipboard.writeText(window.location.href).then(done).catch(function () {
      var ta = document.createElement('textarea');
      ta.value = window.location.href;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      done();
    });
  }

  document.addEventListener('click', function (event) {
    var btn = event.target.closest ? event.target.closest('[data-share]') : null;
    if (!btn) return;
    var kind = btn.getAttribute('data-share');
    if (kind === 'twitter') shareTwitter();
    else if (kind === 'linkedin') shareLinkedIn();
    else if (kind === 'copy') copyLink(btn);
  });
})();
