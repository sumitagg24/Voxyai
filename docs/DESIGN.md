# Voxylis Design System — Light Editorial

**Identity**: A precision instrument for voice, on paper. Clean light surfaces,
ink typography, hairline borders, one red record lamp as the only live
indicator. The site and the desktop app are one product: the marketing pages,
the dashboard and `ui/theme.py` share one palette.

## Visual Language & Metaphor
- **Primary metaphor**: Precision instrument sheet. Light paper + ink + one live
  indicator (REC lamp). Everything reads as a confident spec sheet.
- **Borrowed**: Editorial layout for the marketing pages; monospace for
  metadata/timecodes/sizes in the dashboard.
- **Anti-metaphor**: No knobs, faders, patch cables, VU needles, console photos.
  No gradient overlays, glassmorphism, rounded-corner soup, badge clutter,
  stock "AI waveform" hero art. No dark theme anywhere.

## Color System (CSS Custom Properties)
```css
:root {
  --bg-deep:       #fafafa;   /* page paper */
  --bg-surface:    #ffffff;   /* cards, nav on scroll */
  --bg-elevated:   #f1f1ef;   /* hover fills, meters track */
  --fg-primary:    #1e1e1e;   /* ink */
  --fg-muted:      #5f636e;
  --fg-inverse:    #ffffff;
  --border-hair:   #e5e5e5;
  --rec-lamp:      #ff5c5c;   /* decorative REC lamp motif */
  --rec-strong:    #d64545;   /* REC/destructive — AA on light */
  --success:       #1f9d63;   /* ONLY success/online — AA on light */
  --focus-ring:    #1e1e1e;
  --shadow-card:   0 1px 2px rgba(0,0,0,.05), 0 1px 3px rgba(0,0,0,.04);
  --shadow-pop:    0 8px 24px rgba(0,0,0,.08);
}
```
The dashboard's tokens are the same values (`#1e1e1e` ink, `#5f636e` muted,
`#e5e5e5` hairline, pink/teal accents it already owned). Red never glows.
Green never appears except success/online.

## Typography
- **Heading/Body**: One grotesk (self-hosted). No Google Fonts CDN.
- **Labels/Numbers/Timecodes**: One monospace (self-hosted).
- **Families**: 2 total. **Weights**: 4 max.
- **Scale**: fluid steps; `font-display: swap`; preload both families.

## Spacing & Shape
- **Spacing scale**: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 (CSS vars `--sp-*`).
- **Radii**: 6–8px (`--radius-sm: 6px`, `--radius-md: 8px`). No pill buttons.
- **Borders**: 1px hairline. Shadows only the two tokens above (card, pop).
- **Grid**: Single 12-col fluid grid (`--container-max: 1280px`).

## Components
- **Button**: Primary (ink bg, white text), Secondary (hairline border, ink
  text), Destructive (`--rec-strong`). Subtle hover lift, no gradient.
- **Card**: White surface, 1px hairline, 8px radius, `--shadow-card`.
- **Input**: White bg, 1px hairline, 6px radius, ink focus ring.
- **Meter/Level**: mono labels, `--rec-strong` bars, no gradients.
- **Lamp**: solid dot + ring, red when live. 150–250ms ease-out.

## Motion
- **Allowed**: state transitions only (lamp fade, meter bars, modal open/close).
- **Duration**: 150–250ms ease-out. Respects `prefers-reduced-motion`.
- **Never**: float, bounce, parallax, loading spinners.

## Imagery
- **Real screenshots** of the actual app (light theme) only.
- **og-image**: Lamp motif, 1200×630.
- **Everything else**: Typographic. No illustrations, no 3D blobs, no stock.

## Explicit ANTI-PATTERNS
- ❌ A dark theme anywhere (site or desktop) — light is the only shipped look
- ❌ Red glow/bloom/box-shadow
- ❌ Gradient overlays (backgrounds, buttons, text)
- ❌ Glassmorphism / backdrop-filter (exception: the sticky nav's translucent
  blur is allowed — it blurs the light paper, never dark content)
- ❌ Rounded-corner soup (pill buttons, full-round cards)
- ❌ Badge clutter (status chips, "NEW", "PRO" pills)
- ❌ Stock "AI voice waveform" hero art / stock photos
- ❌ More than 2 font families / 4 weights
- ❌ Shadow soup (layered box-shadows beyond the two tokens)
- ❌ CDN font/script loading (vendor instead)

---

## Desktop (PyQt5 app)
The desktop reads as the same product as the website. `ui/theme.py` is the
single source of tokens for Qt (`stylesheet()`, `palette()`, font stacks) and
is **light-only** — the dark palette was removed by owner decision.

- ❌ Gradient buttons/backgrounds (flat fills only)
- ❌ Emoji or stock icons in place of text glyphs; no qtawesome
- ❌ Magic hex colours outside `ui/theme.py` — use `theme.palette()` tokens
- ❌ `setStyleSheet` outside `ui/theme.py` (token-built f-string helpers excepted)
- ❌ Off-scale margins/spacing — use the 4 / 8 / 12 / 16 / 24 / 32 scale
- ❌ Decorative animations (the overlay waveform is a live readout)
- ❌ One-off window styling that drifts from the app

**Contrast**: the LIGHT palette passes WCAG ≥4.5:1 for text, muted, dim,
success, warning, danger, recording, accent-as-text, and white-on-button.

---

## Implementation Notes
- **Vendor**: Chart.js → `web/static/vendor/chart.min.js` (dashboard only).
- **Fonts**: self-hosted in `web/static/fonts/`. Preload + swap.
- **CSS**: `web/static/css/base.css` (tokens + components) + one per-page file.
- **JS**: `api.js` + `config.js` + small per-page modules (< 60KB excl Chart.js).
- **CSP**: `default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self' ...sentry.io`. No `unsafe-inline`, no CDN.
- **Downloads**: buttons hit same-origin `/download/<platform>` routes that 302
  to the resolved release asset — visitors download from the site, never a
  GitHub page.
- **Honesty**: features/pricing from `web/tier.py`; availability from
  `/api/download/urls`; pricing CTAs respect `checkout_available`.
- **A11y**: landmarks, focus-visible, contrast ≥4.5:1, reduced-motion, alt text.
- **Responsive**: 1440 / 768 / 390. Mobile nav without a library.
