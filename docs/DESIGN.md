# Voxylis Design System — SIGNAL SHEET

**Identity**: a precision studio instrument, printed on warm paper. Bone paper,
warm ink, hairline rules like a spec sheet — and exactly one accent: the signal
orange-red of a live channel. The site speaks this language in light and dark;
the desktop app follows `ui/theme.py` (light today, same paper/ink theory).

## Visual Language & Metaphor
- **Primary metaphor**: signal path on an instrument sheet. Paper, ink, ruled
  hairlines, mono metadata labels, one lamp that means *live*.
- **Motion**: 150–250 ms ease-out; hover = hard print lift (`4px 4px 0 0 ink`),
  never soft shadows. Live elements may pulse (the lamp, hero waveform);
  everything respects `prefers-reduced-motion`.
- **Anti-patterns (banned)**: gradients, glassmorphism, soft shadows, rounded
  SaaS cards, badge clutter, floating blobs, purple/blue hero washes, emoji as
  UI icons in marketing chrome.

## Colour System (CSS custom properties, base.css)
Light (`:root`) and dark (`[data-theme="dark"]`, or `"system"` +
`prefers-color-scheme: dark`) define the same token names:

| Token | Light | Dark | Role |
|---|---|---|---|
| `--bg-deep` | `#f4f1ea` bone | `#151310` | page paper |
| `--bg-surface` | `#fcfbf7` | `#1d1a15` | panels |
| `--bg-elevated` | `#ebe6d9` | `#282319` | pressed/hover fills |
| `--fg-primary` | `#171512` ink | `#ece7da` | text, rules |
| `--fg-muted` | `#6b6558` | `#a89f8d` | secondary text |
| `--fg-inverse` | `#f8f6f0` | `#151310` | text on ink fills |
| `--border-hair` | `#d9d3c4` | `#39332a` | hairlines |
| `--signal` | `#e04b26` | `#ff6a42` | THE accent: lamp/live/hover |
| `--signal-btn` | `#c73e1d` | `#ff6a42` | button hover fill (AA) |
| `--signal-btn-text` | `#f8f6f0` | `#171512` | text on signal fills |
| `--signal-deep` | `#b23617` | `#ff8a66` | signal as body text (AA) |
| `--rec-lamp` | `#ff4b26` | `#ff4b26` | live lamp glow only |
| `--rec-strong` | `#c22e12` | `#ff6b4a` | destructive / REC text |
| `--success` | `#1f9d63` | `#3ecf8e` | success/online only |

Rules: red family is RESERVED for REC/live/destructive; green ONLY success.
Contrast: body text ≥ 4.5:1, large display ≥ 3:1, text on signal fills uses
`--signal-btn-text`, signal-as-text uses `--signal-deep`.

## Typography
- Space Grotesk (self-hosted variable) — everything except metadata.
- JetBrains Mono (self-hosted variable) — kickers, labels, buttons, timecodes.
  Buttons are mono, uppercase, letter-spaced: hardware keys, not web pills.
- Scale: 12/14/16/18/24/32/48, hero `clamp(3.2rem, 8vw, 7.5rem)` with a solid
  first line and a hollow outline second line (stroked SVG text — axe-safe,
  and it draws itself on load; reduced-motion users see it static).

## Shape & Components
- Radius 2px everywhere; borders are 1px hairlines; "hard rules" are ink.
- Cards: flat panels; hover lifts with the hard offset and lights a 3px signal
  top rule. `.card.highlighted` is permanent.
- Buttons: `.btn` ink fill (hover: signal fill + print lift), `.btn-ghost`
  hairline, `.btn-destructive` REC red. Loading = disabled + label swap.
- Lamp: `.lamp` idle grey; `.lamp--live` signal glow + slow pulse.
- Consent/banner surfaces: squared, right-anchored, hard-offset shadow.

## Logo
"Voice-print V": ink rounded tile, five vertical voice bars (V silhouette),
centre bar in signal = the live channel. Inline SVG everywhere (theme-aware
via `.lg-tile/.lg-bar/.lg-sig`, with baked-in fills so it renders even under
stale CSS); raster variants: `favicon.ico` (16/32/48), `apple-touch-icon.png`,
`og-image.png`. Wordmark = Space Grotesk Bold.

## Theming Mechanics
- `<script src="/static/js/theme.js">` in `<head>` sets
  `data-theme="light|dark|system"` on `<html>` **before first paint**
  (no flash). Choice persists in `localStorage.voxy_theme`.
- `.theme-toggle` in every nav cycles the three states (sun / moon / auto
  icons; the sun shows before JS assigns a state). Colour crossfades via
  token-scoped transitions.
- Every page stylesheet consumes tokens only — no raw hex outside base.css.

## Accessibility Contract
Visible `:focus-visible` rings; axe-core site audit in CI (serious/critical
block, findings surface as check annotations); contrast rules above; every
icon-only control labelled; decorative SVGs `aria-hidden`.
