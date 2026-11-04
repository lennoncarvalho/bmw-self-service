# Single outer content scrollbar — 2026-11-04

Owner request: expanded accordion sections must display their full content,
without competing nested vertical viewports. One outer scrollbar scrolls the
current main page; bottom navigation remains anchored. Continue on the existing
`codex/source-derived-runtime` branch; no push or PR.

## Plan

1. Update UI spec16: main content grows to its natural height; expanded sections
   and page lists have no independent vertical scrollbars. Dialog forms/previews
   remain independent windows with their own existing scrolling.
2. Add one application content scroll area around the page stack, outside the
   persistent header/navigation. Size the stack from its current page, including
   wrapped text and changing accordion visibility; hidden pages must not impose
   their expanded height on other pages.
3. Replace nested Vehicle configuration/ECU/CBS viewports and main-page history,
   journal, diagnostic, backup and coding list viewports with ordinary widgets.
   Use the same current-page sizing for Easy/Advanced coding tabs.
4. Exercise actual Qt layouts with multiple large sections expanded together,
   narrow/wide windows, collapse/reopen, data refresh and page/subtab switching.
   Verify one visible content scrollbar, no clipped rows, shrinking scroll range
   and fixed navigation. Visually inspect screenshots. No `tests/` directory.
5. Obtain independent PySide6 review, fix findings, run full app preflight, commit
   on the same branch. Vehicle behavior/workers/storage are outside this change.

## Implementation

- MainWindow owns one `content_scroll` around the page stack. Header and bottom
  navigation stay siblings of that viewport. The busy overlay is centered on
  the visible viewport, so long content cannot move its controls offscreen.
- `ui/page_stack.py` sizes from the active page and reflows wrapped text. The
  nested coding stack additionally tracks its current content height, because
  the native stacked layout otherwise includes hidden tabs in height-for-width.
- Equipment, ECU and CBS sections, diagnostics/coding/backup lists, history cards
  and history journals are ordinary expanding widgets. All height-capped nested
  viewports in those main pages were removed; dialog scrolling is unchanged.

## Observed offline verification

Retained one-off script and screenshots (not a suite):
`/Users/lennon/BMW-Tool/investigations/source-runtime-20261104/page_scroll_check.py`
and `page-scroll-result.json`, `scroll-vehicle-{top,middle,bottom,narrow}.png`,
`scroll-coding-expanded.png`.

- Actual MainWindow: 60 ECU rows, 45 multi-line equipment descriptions and
  18 CBS cards expanded simultaneously. Exactly one QScrollArea in the main
  window; every row fits its containing section. Scroll range grows to7753px,
  then returns to0 after collapse. Header/navigation stay anchored through
  top/middle/bottom scrolling.
- Wrapping/reflow at800x600,1100x800,1400x900. Narrow range8718px, wide6327px;
  full wrapped labels retained. Refresh with two ECUs removes old excess height.
- Switching from expanded Vehicle to short History leaves no extra scroll range.
  Easy coding expansion grows range0→992px; Advanced then shrinks to274px instead
  of retaining the hidden Easy page's height. This regression was found in
  verification, fixed and rechecked with an explicit assertion.
- Busy overlay remains fully within the window and centered on the viewport
  after scrolling thousands of pixels. Independent review found this related
  regression and the hidden-tab height issue; both were corrected.
- Actual async DEMO connection and four main pages render and close normally;
  no live writer created. Visually inspected top/middle/bottom and narrow-window
  screenshots, plus DEMO main-page views.
- Full `scripts/preflight.sh --fix`: Ruff check, Ruff format check and mypy all
  pass across52 files. `git diff --check` passes. No tests/ or vehicle traffic.

Independent PySide6 review and separate actual-widget exercises passed:
`/tmp/page_history_dtc_check.py`, `/tmp/nested_stack_resize_check.py`.
Expanded25 long DTCs increased the outer range2324→8049px. Expanded25 history
cards (13items each) and15journals (30steps each) increased5991→22642px;
wrapped labels retained their full required heights and the window still had
exactly one QScrollArea. Nested wrapped content shrank/reflowed correctly on
resize, short-tab switching and reopening. Keyboard Tab reveals an offscreen
final control through the outer viewport. No remaining actionable review findings.
