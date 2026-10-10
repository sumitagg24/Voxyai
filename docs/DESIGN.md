# Voxylis Design System — Control Room

**Identity**: A precision instrument for voice. Dark console surfaces, one red record lamp as the only live indicator. Abstract metaphor — type, hairlines, one lamp — never literal hardware.

## Visual Language & Metaphor
- **Primary metaphor**: Broadcast control room. Dark surface + one live indicator (REC lamp). Everything reads as a precise readout.
- **Borrowed**: Instrument Panel spec-sheet density for dashboard; Field Recorder monospace for metadata/timecodes/sizes.
- **Anti-metaphor**: No knobs, faders, patch cables, VU needles, console photos. No gradient overlays, glassmorphism, rounded-corner soup, badge clutter, stock "AI waveform" hero art.

## Color System (CSS Custom Properties)
```css
:root {
  --bg-deep:       #0e0f12;
  --bg-surface:    #16181d;
  --bg-elevated:   #1d2027;
  --fg-primary:    #eaeaea;
  --fg-muted:      #8a8d93;
  --fg-inverse:    #0e0f12;
  --border-hair:   #2a2d35;
  --rec-lamp:      #ff5c5c;    /* ONLY: recording/live/REC + destructive */
  --success:       #3ecf8e;    /* ONLY: success/online */
  --focus-ring:    #ff5c5c;
  --shadow-none:   none;
}
```
No other colors. Red never glows/blooms. Green never appears except success/online.

## Typography
- **Heading/Body**: One grotesk (vendored `.woff2`, self-hosted). No Google Fonts CDN.
- **Labels/Numbers/Timecodes**: One monospace (vendored `.woff2`).
- **Families**: 2 total. **Weights**: 4 max (regular, medium, semibold, bold).
- **Scale**: `clamp()` fluid steps; `font-display: swap`; preload both families.
- **No** letter-spacing tricks, no text-transform for hierarchy.

## Spacing & Shape
- **Spacing scale**: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 (CSS vars `--sp-*`).
- **Radii**: 4–6px only (`--radius-sm: 4px`, `--radius-md: 6px`). No pill, no full-round.
- **Borders**: 1px hairline (`var(--border-hair)`). No shadows (`box-shadow: none`).
- **Grid**: Single 12-col fluid grid (`--container-max: 1280px`).

## Components
- **Button**: Primary (rec-lamp bg, inverse text), Secondary (hairline border, fg text), Destructive (rec-lamp, inverse). No gradient, no shadow.
- **Card**: Surface bg, 1px hairline border, 6px radius. No shadow.
- **Input**: Surface bg, 1px hairline, 4px radius, focus ring = rec-lamp.
- **Table/Log**: Monospace cells, hairline horizontal rules, timestamp column.
- **Meter/Level**: Strip chart — mono labels, rec-lamp bars, no gradients.
- **Lamp**: Solid 8–10px dot + 1px ring, rec-lamp fill when live. Fade 150–250ms ease-out.

## Motion
- **Allowed**: State transitions only (lamp fade, meter bars, modal open/close).
- **Duration**: 150–250ms ease-out.
- **Respects**: `prefers-reduced-motion` → instant.
- **Never**: Float, bounce, parallax, hover grow/shrink, loading spinners (use lamp).

## Imagery
- **Real screenshots** of the actual app (dark theme) only.
- **og-image**: Lamp motif on charcoal, 1200×630.
- **Everything else**: Typographic. No illustrations, no 3D blobs, no stock photos.

## Explicit ANTI-PATTERNS
- ❌ Red glow/bloom/box-shadow
- ❌ Gradient overlays (backgrounds, buttons, text)
- ❌ Glassmorphism / backdrop-filter
- ❌ Rounded-corner soup (pill buttons, full-round cards)
- ❌ Badge clutter (status chips, "NEW", "PRO" pills)
- ❌ Stock "AI voice waveform" hero art
- ❌ Stock photos / generic illustrations
- ❌ More than 2 font families / 4 weights
- ❌ More than 3 colors in any view (bg, fg, rec-lamp OR success)
- ❌ Shadow soup (layered box-shadows)
- ❌ Floating/bouncing/breathing decorative elements
- ❌ CDN font loading (fonts.googleapis.com, fonts.gstatic.com)
- ❌ CDN script loading (cdn.jsdelivr.net, unpkg.com — vendor instead)

---

## Implementation Notes
- **Vendor**: Chart.js → `web/static/vendor/chart.min.js` (only on dashboard). `web/static/vendor/` for all 3rd-party.
- **Fonts**: `.woff2` in `web/static/fonts/`. Preload + `font-display: swap`.
- **CSS**: `web/static/css/base.css` (tokens + components) + one small per-page file max.
- **JS**: `web/static/js/api.js` + `config.js` + small per-page modules. Total < 60KB minified (excl Chart.js).
- **CSP**: `default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self' https://*.ingest.sentry.io`. No `unsafe-inline`, no CDN.
- **Pages**: index, pricing, download, auth, dashboard, blog, blog-post, about, contact, privacy, terms, docs/*, 404.
- **Honesty**: All features/pricing from `web/tier.py`; download from `/api/download/urls`; pricing CTAs from `checkout_available`; Q&A shows real 403 upgrade.
- **Session**: All requests via `voxyFetch()`; `X-Session-Rotated` handled in `api.js`.
- **A11y**: Landmarks, focus-visible, contrast ≥4.5:1, `prefers-reduced-motion`, keyboard-reachable, alt text.
- **Responsive**: 1440 / 768 / 390. Mobile nav without library.
- **Perf**: `font-display: swap`, preload woff2, lazy images, JS < 60KB minified (excl Chart.js).

---

## Handoff Checklist (P3.3 BUILD)
- [ ] `docs/DESIGN.md` written (this file)
- [ ] Fonts vendored to `web/static/fonts/`
- [ ] Chart.js vendored to `web/static/vendor/`
- [ ] `web/static/css/base.css` with all tokens + components
- [ ] Per-page CSS files (max 1 each)
- [ ] All inline styles removed from HTML
- [ ] CSP header updated in `web/app.py`
- [ ] `web/static/js/config.js` for `VOXYLIS_API_BASE`
- [ ] Chart.js only on dashboard
- [ ] Honest copy from `web/tier.py` + API endpoints
- [ ] Mobile nav works without library
- [ ] `prefers-reduced-motion` honored
- [ ] `py -m pytest tests -q` + `py -m web.verify_routes` green