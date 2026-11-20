# Bavarian Telemetrics — visual design

This is the visual contract for every page, dialog and shared control. Product
scope and operation rules belong in `plan.md`; this file defines presentation.

## Character and surfaces

Use a restrained automotive night theme: deep carbon backgrounds, layered graphite
surfaces, crisp text, compact spacing and precise line icons. Establish depth with
surface tones and fine borders rather than large shadows or decoration.

The canonical palette below takes precedence over illustrative color variants.
Derived blue, amber, red and green washes may distinguish states on dark surfaces.
Menus, calendars, selection lists and dialogs must be opaque and readable. In Qt
Widgets, express the smoky-glass appearance through solid layered surfaces and
subtle highlights; do not depend on browser blur or transparency for contrast.

| Role | Color |
|---|---|
| Canvas / lowest surface | `#0a0e17` |
| Background / surface / dim surface | `#0f131c` |
| Low / elevated surface | `#181c25` |
| Container | `#1c2029` |
| High container | `#262a34` |
| Highest container | `#31353f` |
| Bright surface | `#353943` |
| Main text | `#dfe2ef` |
| Supporting text | `#c2c6d5` |
| Muted outline | `#8c909e` |
| Container / input outline | `#424753` |
| Primary text / focus / tint | `#adc7ff` |
| Text on primary tint | `#002e68` |
| Primary action container | `#1c69d2` |
| Text on primary container | `#eaeeff` |
| Secondary / secondary container | `#bdc6df` / `#40495d` |
| Text on secondary / container | `#273043` / `#afb8d0` |
| Tertiary / tertiary container | `#a1c9ff` / `#186eba` |
| Text on tertiary / container | `#00325a` / `#e6efff` |
| Error text / error container | `#ffb4ab` / `#93000a` |
| Text on error / container | `#690005` / `#ffdad6` |
| Warning / fault / verified accents | `#f59e0b` / `#ef4444` / `#10b981` |
| Inverse surface / text | `#dfe2ef` / `#2c303a` |
| Inverse primary | `#005bc0` |

Always pair a state color with readable text or a recognizable symbol. A color
does not establish an operation's meaning, availability or success.

## Typography

Bundle fonts locally. Use Space Grotesk for headings, Geist for prose and controls,
and JetBrains Mono for identifiers, hexadecimal data, technical values and compact
tabular labels. Technical numbers must align consistently. Avoid uppercase prose;
reserve modest tracking and uppercase for short labels.

| Role | Size / target line height | Weight |
|---|---|---|
| Display | 36 / 44 px | 700 |
| Large heading / dialog title | 28 / 36 px | 600 |
| Section heading | 22 / 28 px | 600 |
| Small heading | 18 / 24 px | 500 |
| Large body | 15 / 22 px | 400 |
| Body / controls | 13 / 18 px | 400 |
| Supporting body | 12 / 16 px | 400 |
| Large technical label | 13 / 16 px | 600 |
| Medium technical label | 11 / 14 px | 500 |
| Small technical label | 10 / 12 px | 500 |

Respect font metrics, display scaling and wrapping rather than clipping text to
force a nominal line height. Use larger headings sparingly in dense content.
Card titles use the 22 px section-heading style in sentence case. Never use tiny
technical labels as card, section or field headings. Smaller supporting counts
use 12 px semibold text; field and subsection labels use at least 13 px semibold.
Separate selected changes from guidance with compact bordered rows, bold setting
names and blue target values. Keep guidance secondary in size and contrast.

## Geometry and spacing

- Use a 4 px base rhythm: 4, 8, 12, 16, 20, 24 and 32 px. Standard page margin is
  24 px; normal and compact gutters are 16 and 8 px.
- Default corner radius is 4 px. Use 2 px for very compact details, 6–8 px for
  grouped surfaces, up to 12 px for large overlays, and pills only for small badges.
- Keep established navigation compact and visually stable. Align content to a
  consistent grid; let existing columns stack when the available width shrinks.
- Prefer dense, aligned rows: 32 px normally and 24 px when condensed. Expand a
  row when wrapping or its controls need more space; never clip meaningful text.

## Controls and data presentation

- Primary buttons use blue fill, light text and a subtle edge highlight.
  Secondary and dismissive buttons use graphite fill and a fine outline.
  Destructive actions use a red outline and dark red wash. Make hover, pressed,
  keyboard focus and disabled states distinct without shifting the layout.
- Action button roles differ only in colors. Primary, secondary, destructive and
  dismissive actions share an opaque fill, solid 1 px border, 4 px radius, 13 px
  label and 9 px vertical / 14 px horizontal padding (40 px standard height).
  Adjacent action buttons match the width required by the longest label. Do not
  introduce role-specific rounding, border thickness, transparency or density.
  Navigation, disclosure and icon controls retain their functional sizing, with
  consistent geometry across states and color roles within each family.
- Enabled buttons use the pointing-hand cursor. Text editors retain the text
  cursor. Use a visible keyboard focus indicator and readable disabled states.
- Inputs sit in inset dark wells with a 1 px outline and a high-contrast blue
  focus edge. Use consistent heights, padding and visible field labels.
- Use shared standard Qt controls. Calendar triggers use a calendar icon;
  selection triggers use a chevron. Popups show all choices through normal
  scrolling, stay opaque and support keyboard navigation.
- Use compact, opaque tables and lists with aligned headers, subtle alternate
  carbon surfaces and a slate hover highlight. Keep identifiers and technical
  values legible and selectable where useful.
- Table column headers match their row text in size and color: normally 13 px
  and `#dfe2ef`. Use semibold (600) headers over regular (400) rows. Compact
  technical-label sizes do not make table headers smaller than their rows.
- Keep short titles and their units together on one line. Secondary context may
  use an ellipsis when space is constrained; retain its full tooltip, accessible
  name and underlying value.
- Keep badges compact. Use text or symbols alongside color; avoid decorative
  flashing, excessive glow or animation that competes with the content.

## Dialogs and overlays

- Use the same palette, typography, line icons and action roles as the pages.
  Give each dialog a clear title, 24 px outer padding and consistent internal gaps.
- Keep content within the available screen. Long text, forms and acknowledgements
  wrap or scroll; action buttons remain visible in a separate bottom footer.
- Put the primary action at the trailing edge, distinguish dismissal visually,
  and label consequential confirmations with the concrete action. Preserve the
  operation's existing confirmation and keyboard-default behavior.
- Keep long acknowledgement rows fully clickable and keyboard accessible.
  Avoid nested outer scrollbars and fixed sizes that hide content or actions.
- Loading backdrops may dim the page; their foreground panel remains opaque.
  Platform file pickers may retain native operating-system presentation.

## Implementation

Keep QSS in `assets/theme.qss`, shared controls in `ui/form_inputs.py` and shared
dialog presentation in `ui/dialogs.py`. Reuse `DangerButton` from `ui/cockpit.py`
for red page actions; standard dialog buttons use the same `dangerOutline` role.
Keep their normal, hover, pressed, focus and disabled colors in one shared rule set.
Use presentation roles instead of inline styles. Update shared rules in place
instead of adding competing overrides or copying controls into pages. Visual
changes must preserve feature behavior, validation and write guards.
