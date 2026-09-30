# KBC design audit

Recorded **before** the frontend was styled, from KBC's live public assets
rather than from memory. Everything below is observed, with the source file
named, so each value can be re-checked.

## Sources

| File | What it gave |
|---|---|
| `https://www.kbc.be/particulieren/nl.html` | The asset manifest that led to the rest |
| `.../kbc/components/kdl-design-tokens.latest.min.css` | **KDL — KBC Design Language.** The complete semantic token set: brand, surface, text, system, channel and category colours, across four themes (light, dark, high-contrast, private banking). |
| `.../settings/wcm/designs/particulieren/clientlibs/main.min.css` | Implemented radii, shadows, font usage |
| `.../kbc/components/websites/cta-button.min.css` | Button geometry and states |
| `.../kbc/fonts/shared/museo.min.css` | Typeface and shipped weights |

## Audit

```
Primary color:      #0D2A50  deep navy   (--kdl-color-primary-main)
                    Used for text, headings, the app bar and dark surfaces.
Secondary color:    #0097DB  KBC blue    (--kdl-color-primary-accent)
                    Used for CTAs, links, active states. Hover #007AB1.
Background:         #F2FAFF  (--kdl-color-func-background-dashboard)
                    Note: the *dashboard* background is the pale blue, not the
                    grey #F2F2F2 used for generic page surfaces.
Card radius:        8px primary, 4px for dense/inner elements.
                    Frequency in main.min.css: 4px x32, 8px x21, 100px x9.
Typical button:     FULLY ROUNDED PILL - border-radius:100px, min-height:40px,
                    padding:7px 24px, font-weight:500, transition all .22s
                    ease-in-out. Primary = filled accent. Secondary = 1px
                    accent border on transparent. This is the single most
                    KBC-identifying detail: a square-cornered button reads as
                    "not KBC" immediately.
Typography:         MuseoSans, weights 300 / 500 / 700 ONLY.
                    Body weight is 500, not 400 - KBC's text sits heavier than
                    a default system stack. Licensed typeface.
Navigation:         Desktop: horizontal mega-menu under a navy bar.
                    Mobile app: bottom tab bar.
                    Pill-shaped active state on tab items.
Common spacing:     4px rhythm; 16px and 24px dominate card padding.
Visual characteristics:
                    - Soft, wide, low-opacity shadow: 0 4px 16px rgba(0,54,101,.08)
                      (and .16 for raised). Shadow is TINTED NAVY, never neutral black.
                    - Generous whitespace; cards float on a tinted background
                      rather than sitting in bordered boxes.
                    - Colour is used sparingly: navy + one blue accent carry
                      almost everything; system colours appear only for status.
                    - No gradients in the component system (one is used here
                      only on the single hero card).
```

## Details worth stealing

**Channel colours.** KDL ships a colour per KBC channel — `--kdl-color-os-kate`
`#55C7DF`, `-mobile` `#1FADC1`, `-live` `#1DA594`, `-visit` `#5387C5`. These are
used directly on the architecture page's channel chips, which makes the "one
Twin, many channels" story render in KBC's own visual vocabulary rather than an
invented palette.

**Category colours.** `--kdl-color-category-01..20` is KBC's spending-category
palette, carried into `tokens.css` for any future charting.

**System colours are muted.** Success `#5BA215` is an olive-leaning green, error
`#D64040` a soft brick — noticeably less saturated than default framework
palettes. Using bright `#00C853` / `#F44336` would look wrong next to KBC blue.

## How this was applied

1. `frontend/src/styles/tokens.css` — every value above as a CSS custom
   property, each commented with its KDL name so the mapping is auditable.
2. `frontend/src/styles/app.css` — the component layer. **No raw colour, radius,
   spacing or font value appears in it**; every rule references a token.
3. `frontend/src/components.js` — the component set (`KbcHeader`, `KbcCard`,
   `KbcPrimaryButton`, `KbcBottomNavigation`, `KbcTimeline`, `KbcGoalCard`,
   `KbcTwinInsight`, `KbcAdvisorPanel`, …). Screens are assembled from these, so
   the prototype visibly comes from one system.

## Deliberate departures

- **Confidence is a segmented meter, not a progress bar.** A continuous bar
  reads as a quantity; confidence is not a quantity of anything. KBC has no
  component for this because KBC has no product that needs it.
- **Provenance chips** (`Observed` / `Calculated` / `Assumption` / `You told
  us`) are new. They use KDL system colours, but the pattern is specific to
  this idea.
- **Uncertain timeline markers are dashed.** Uncertainty is carried in the
  shape, not only the wording.
- **One gradient**, on the single hero Twin card. KBC's system does not use
  gradients; this is one deliberate exception for the demo's focal point.

## IP position

No KBC logo, illustration, photograph or proprietary icon is reproduced. The
wordmark is plain text in a rounded box. Icons are neutral inline SVG drawn for
this project. MuseoSans is referenced but not embedded — Mulish, an open
substitute, is loaded instead. The prototype labels itself "prototype" in the
header and states that its data is synthetic on the home screen and the
architecture page.
