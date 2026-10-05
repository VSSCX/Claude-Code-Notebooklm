---
name: Dashboard D2C · Cruce VTEX vs SAP
description: Ant-style enterprise seller-center board: white header over a grey canvas, white 8px cards with 1px hairlines, one blue accent, dense tables that fit the window.
colors:
  primary: "#1677FF"
  primary-strong: "#0958D9"
  primary-soft: "#E6F4FF"
  primary-line: "#91CAFF"
  on-primary: "#FFFFFF"
  on-strong: "#FFFFFF"
  canvas: "#F5F5F5"
  surface: "#FFFFFF"
  surface-2: "#FAFAFA"
  surface-3: "#F3F4F6"
  line: "#EBEBEB"
  line-control: "#D1D5DB"
  text: "#111827"
  text-2: "#4B5563"
  text-3: "#5F6673"
  ok: "#15803D"
  ok-solid: "#16A34A"
  ok-soft: "#DCFCE7"
  warn: "#B45309"
  warn-solid: "#D97706"
  warn-soft: "#FEF3C7"
  on-warn: "#1F1400"
  err: "#DC2626"
  err-strong: "#B91C1C"
  err-soft: "#FEE2E2"
  on-err: "#FFFFFF"
  neutral-solid: "#9CA3AF"
  logo-plate: "#FFFFFF"
  canvas-dark: "#141414"
  surface-dark: "#1F1F1F"
  surface-2-dark: "#262626"
  line-dark: "#303030"
  text-dark: "#ECEDEF"
  primary-dark: "#3C89FF"
  primary-strong-dark: "#69B1FF"
  primary-soft-dark: "#111D2C"
typography:
  text-base:
    fontFamily: "Plus Jakarta Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
  card-title:
    fontFamily: "Plus Jakarta Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.005em"
  kpi-value:
    fontFamily: "Plus Jakarta Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "min(1.5rem, 2cqw)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
    fontFeature: "tabular-nums"
  table-cell:
    fontFamily: "Plus Jakarta Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Plus Jakarta Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.3
  code:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.93em"
    fontWeight: 700
    letterSpacing: "-0.01em"
    fontFeature: "tabular-nums"
rounded:
  sm: "4px"
  md: "8px"
  full: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "32px"
  button-default-hover:
    textColor: "{colors.primary-strong}"
  button-pressed:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-strong}"
  button-primary:
    backgroundColor: "{colors.primary-strong}"
    textColor: "{colors.on-strong}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "{colors.primary}"
  alert-marker:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 8px 0 14px"
    height: "36px"
  alert-marker-active:
    backgroundColor: "{colors.primary-strong}"
    textColor: "{colors.on-strong}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  tag:
    backgroundColor: "{colors.surface-3}"
    textColor: "{colors.text-2}"
    rounded: "{rounded.sm}"
    padding: "0 8px"
    height: "24px"
  tag-blue:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-strong}"
  table-header:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text-2}"
    padding: "8px 10px"
  nav-item:
    textColor: "{colors.text-2}"
    padding: "0 14px"
    height: "56px"
  nav-item-active:
    textColor: "{colors.primary-strong}"
  seg-control-active:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-strong}"
    rounded: "{rounded.md}"
    width: "28px"
    height: "24px"
  notification-bell:
    textColor: "{colors.text-2}"
    rounded: "{rounded.md}"
    size: "36px"
  notification-badge:
    backgroundColor: "{colors.err}"
    textColor: "{colors.on-err}"
    rounded: "9px"
    height: "17px"
---

# Design System: Dashboard D2C · Cruce VTEX vs SAP

## Overview

**Creative North Star: "The Seller Center"**

This is a replacement world. The board is an enterprise seller-center console in the Ant Design idiom: a white header strip sits on a light grey canvas, content lives in white cards with a 1px hairline and an 8px radius, and a single blue carries every interactive and selected state. It is an operations dashboard, not a marketing page, so there is no hero, the board fits the window without scrolling, tables are dense, and color is spent on order state rather than decoration.

The taste rules behind it: one accent, one radius scale (4 and 8), a real icon library (Tabler outline), skeleton loaders instead of spinners, no em dash, a rationed middle dot, and dials VARIANCE 3 / MOTION 3 / DENSITY 6. Motion is short (120 to 220 ms, ease-out) and reserved for feedback: hover, press, popover open, toast entry, bell ring, new-row flash.

**Key Characteristics:**
- White surfaces on a grey canvas, separated by 1px hairlines rather than shadows.
- One blue (#1677FF family); text and filled buttons use the stronger #0958D9 so white text keeps contrast.
- Five order-state colors (--st-*) drive charts, heat matrices, tags and legends from the same tokens.
- Sentence-case labels above controls, tabular numerals everywhere, monospace for codes and counts.
- The whole board scales with window size through one variable, 1rem = 16px x scale.

## Reference and extraction

Source: the Ant design skill from awesome-design-skills (its DESIGN.md, SKILL.md and the preview image registry-examples/ant-marketing.png), interpreted through the taste-skill rules and the image-to-code extraction rules (typography, spacing, color, component extraction).

Honest note on method: no image generation was available, so the image-to-code step worked from the reference preview image and the reference DESIGN.md directly, not from a generated mock of this dashboard.

**Taken from the reference image:**
- Top navigation with icon + label items and a blue active state (blue text with a 2px blue underline).
- White header over a grey canvas (#F5F5F5).
- Light-blue tag (#E6F4FF fill, #91CAFF line, #0958D9 text).
- Primary filled button and outlined (default) button, 32px high.
- 8px radius on cards, buttons and inputs, 4px on tags and small chips.
- 1px hairlines (#EBEBEB) as the main separator; light-blue soft fills for selected and hover-selected states.
- Type and spacing scale: 12/14/16/20/24 type steps, 4/8/12/16/24 spacing.

**Adapted for an operations dashboard:**
- No hero or marketing band: the first viewport is the live board.
- Board fits the window (no page scroll on desktop); the scale variable replaces responsive reflow.
- Dense tables (13px cells, 5px vertical padding) with a grey sticky header, hover rows and sort chevrons.
- State colors (green, amber, red, grey, plus the blue for "in progress") added beside the single brand accent, as soft fills and solid heat cells.
- Notification center, TV mode and flow mode have no counterpart in the reference.

## Colors

A neutral grey and white field with one saturated blue; green, amber and red appear only as order or alert state.

### Primary
- **Ant Blue** (#1677FF, `primary`): brand fill, focus ring, hover borders, the "in progress" order state, chart series, unread dot, loading bar.
- **Deep Ant Blue** (#0958D9, `primary-strong`): text on white, active nav, pressed segments, and the background of filled buttons and active alert markers (white on it is contrast-checked). Hover on a filled button lightens it to Ant Blue.
- **Sky Wash** (#E6F4FF, `primary-soft`) and **Sky Line** (#91CAFF, `primary-line`): selected rows, pressed buttons, blue tags, unread notifications, focus halo, new-row flash.

### Neutral
- **Canvas Grey** (#F5F5F5): page background behind all cards.
- **Surface White** (#FFFFFF): header, filter bar, cards, popovers, toasts. `surface-2` (#FAFAFA) is table headers, hover rows and totals; `surface-3` (#F3F4F6) is chip fills and bar tracks.
- **Hairline** (#EBEBEB, `line`): card borders and dividers. **Control Line** (#D1D5DB, `line-control`): borders of inputs, selects and buttons (3:1 against white).
- **Ink** (#111827), **Ink 2** (#4B5563), **Ink 3** (#5F6673): primary, secondary and muted text.
- **Logo Plate** (#FFFFFF): fixed white plate behind the corporate logo in both themes.

### State
- **Green** `ok` (#15803D text), `ok-solid` (#16A34A fill), `ok-soft` (#DCFCE7): invoiced / on time.
- **Amber** `warn` (#B45309 text), `warn-solid` (#D97706 fill), `warn-soft` (#FEF3C7): pending, at risk; `on-warn` (#1F1400) is the ink on amber heat cells.
- **Red** `err` (#DC2626), `err-strong` (#B91C1C text on soft), `err-soft` (#FEE2E2): overdue, critical, error banner, unread badge; `on-err` is white.
- **Neutral solid** (#9CA3AF): canceled and idle.
- Order states map: invoiced = green solid, in progress = Ant Blue, not invoiced = red, pending = amber solid, canceled = neutral solid.

### Dark theme
Same roles, remapped: canvas #141414, surface #1F1F1F, surface-2 #262626, line #303030, control line #5C5C5C, text #ECEDEF, primary #3C89FF, strong (text and fills) #69B1FF with dark ink (#0B1220) on it, soft fills #111D2C. Cards drop their shadow in dark. Theme follows the system by default and the header segmented control (sun, moon, auto) overrides it.

### Named Rules
**The One Blue Rule.** Interactive and selected state is Ant Blue and nothing else. Green, amber and red mean order state only, never decoration or hover.
**The Strong-Blue-For-Text Rule.** Blue text and filled-button backgrounds use `primary-strong`; the brighter `primary` is for fills, rings and chart marks. In dark the roles invert in lightness, but the same split holds.
**The Token-Read Rule.** Charts, matrices and tags read the same `--st-*` and surface tokens (Chart.js reads them through computed style), so a theme switch repaints everything with no second palette.

## Typography

**Text Font:** Plus Jakarta Sans (with Segoe UI, system-ui, sans-serif), variable 200 to 800, self-hosted woff2 (OFL, from Google Fonts).
**Code Font:** JetBrains Mono (with ui-monospace, Cascadia Mono, Consolas), self-hosted woff2, for order codes, sequence numbers and count chips.

**Character:** A friendly geometric sans for labels and headings, with a mono for identifiers so codes align in columns. Hierarchy comes from weight and size, never from uppercase tracking.

### Hierarchy
- **KPI value** (700, min(1.5rem, 2cqw), 1.15, -0.02em, tabular): the six indicator cells; shrinks with the card via container query.
- **Card title / header title** (700, 1rem, 1.25): card headings and the h1 in the header; clamped to two lines.
- **Body** (400, 0.875rem, 1.45): default text, inputs, selects.
- **Table cell** (400 to 600, 0.8125rem): dense table and matrix text; numeric cells right-aligned with tabular numerals; code cells in mono 700 at 0.9em.
- **Label** (500 to 600, 0.75rem, 1.3): filter labels (sentence case, above the control), table headers (600), sublines, tag text, status line.
- **Count chip** (mono 700, 0.8125rem): counts on alert markers.
- **Row value** (700, 1.25rem, 1): the large count on each order-state row in the left rail.

### Named Rules
**The Sentence-Case Rule.** Labels, headers and buttons are sentence case in Spanish; no uppercase micro-labels with letter-spacing.
**The Tabular Rule.** Every number uses tabular numerals; identifiers and counts that must align use the mono.

## Layout

A column app: header (56px), filter bar, optional error banner, then a board that fills the remaining height and does not scroll. The board is an absolutely positioned CSS grid inset 12px top and bottom and 24px left and right, with 12px gaps. Three screens:
- **Pedidos:** alert markers across the top; a left rail (17%, 12.5 to 17rem) with state cards and cause, a main orders table; three charts (1.4fr / 1fr / 1fr); a delivery matrix at the bottom.
- **Resumen:** the KPI card, a combo area, two lower cards, and a tall closing card on the right.
- **Diagnóstico:** two cards over a matrix and a detail table.

Spacing rhythm is 4/8/12/16/24 (px at scale 1). Scale: `--u` = min(3, window / 1440x860 reference), set by JS on the root font size so rem tracks the window. Below 0.9 scale the "flow" mode locks type at 0.9 and the page scrolls (main height 48rem). Columns of tables hide by card width (amount under 800px, created under 660px, scaled) and matrix headers abbreviate under 440px.

**TV mode:** the same board enlarged from a 1280x720 reference canvas; filters, the theme control and Demo tag are hidden and replaced by a one-line filter summary, creation and SLA columns drop, card bodies are cut with a "+N más" line, the cursor hides after 4s idle. It is still the desktop board enlarged, not a room recomposition (known gap).

**Mobile (under 900px):** page scrolls; header wraps with nav on its own scrollable row; filters collapse behind a "Filtros" disclosure; cards stack at min 16rem, tables cap at 26rem; KPI card goes to two columns; the notification panel and toasts become full-width.

## Elevation & Depth

Flat by default: depth is tonal (grey canvas, white card) plus a 1px hairline. Cards carry only a faint ambient shadow, and none in dark. Real elevation is reserved for things that float above the board.

### Shadow Vocabulary
- **Card** (`box-shadow: 0 1px 2px rgba(17,24,39,.04)`): cards and the KPI card; removed in dark.
- **Popover** (`box-shadow: 0 6px 16px rgba(17,24,39,.12), 0 3px 6px -4px rgba(17,24,39,.12), 0 9px 28px 8px rgba(17,24,39,.05)`): notification panel, toasts, loading progress card. Dark uses `0 6px 16px rgba(0,0,0,.5), 0 3px 6px -4px rgba(0,0,0,.5)`.
- **Focus halo** (`0 0 0 3px primary-soft`): focused inputs, with a primary border; elsewhere a 2px primary outline at 2px offset.

### Named Rules
**The Hairline-First Rule.** Separate with a 1px line or a tonal step before reaching for a shadow; shadows belong only to floating layers.

## Shapes

One radius scale: 8px for cards, buttons, inputs, selects, popovers, toasts and segmented controls; 4px for tags, count chips, the logo plate, sort headers and links; 50% only for icon discs and small state dots in rows. Bars and legend swatches use 2px. Borders are always 1px; the only dashed border is the "clear" alert marker. The logo sits on a fixed white plate with a 1px ring so the wordmark stays legible in dark.

## Components

### Header and navigation
White 56px bar with a bottom hairline. Left: logo on its white plate, h1. Nav items are Tabler icon (outline) + label, 500 weight, secondary ink; hover gives a grey fill; the active item is Deep Ant Blue, 600, with a 2px blue underline flush with the header bottom. Right: status text with a live dot (green, amber or red by connection state; the second line hides under 1700px), the Demo tag (amber) with a simulate button when in demo, a theme segmented control (icon only, pressed segment = Sky Wash + Deep Blue), the Modo TV button, and the notification bell. A 2px loading bar animates under the header while queries run.

### Buttons
- **Default (outlined):** white, 1px control line, 8px radius, 32px high, 500 weight; hover turns border to blue and text to Deep Blue; press scales to .97; pressed state (toggle) = Sky Wash with Sky Line border.
- **Primary (filled):** Deep Ant Blue with white text; hover lightens to Ant Blue.
- **Small:** 24px high, 12px text. **Link button:** Deep Blue 600 text, soft-blue hover fill.

### Filter bar
White strip with a bottom hairline; each control has a sentence-case 12px label above a 32px select or input (8px radius, control-line border, blue border on hover, blue border plus 3px soft halo on focus). Only what is used all day sits in the bar: Canal, Cliente, Bodega (EC01 + POST, EC01, POST_Fechado, all), Período de creación (mes en curso, mes anterior, últimos 30 días, todo, personalizado; date inputs appear only for personalizado) and the search. Status, SLA Type and Alcance live in a "Más filtros" popover (16.5rem, popover shadow) with a count chip for the active ones. Search input debounced 350ms.

### Alert markers
36px outlined buttons (8px radius) with a label and a count chip in mono; the critical marker's chip is red-soft with strong-red text; active marker fills Deep Blue with an inverted chip; "clear" is dashed. Context text right-aligned.

### Cards
White, 1px hairline, 8px radius, header with 16px bold title and a right-aligned 12px muted subline, body scrolls internally with 8px padding.

### KPI row
One card holding six equal cells split by 1px hairlines: label, large tabular value, delta (green up, red down, grey flat); risk cells color the value red. Two columns on mobile.

### Tables
Ant style: sticky 12px header on `surface-2` with 600 weight and a bottom hairline, 13px cells with 5px vertical padding and hairline row dividers, row hover on `surface-2`, sortable headers show a chevron at 45% opacity that goes full and blue when active, totals rows bold on `surface-2`, new rows flash Sky Wash with a "Nuevo" filled tag.

### Tags
24px, 4px radius, 12px 500 text. Variants: grey (default), green, red, amber (soft fill, strong text), blue (Sky Wash with Sky Line border and Deep Blue text).

### Heat matrices
Matrix cells color through `color-mix` on the `--st-*` tokens; the delivery matrix uses solid red (`err` with white) and amber (`warn-solid` with `on-warn`) cells, zeros muted at 65% opacity, sticky first column with a 1px edge, column headers carry a 3px state-color bar.

### Charts
Chart.js reading tokens: gridlines in `line`, ticks in `text-3` at 11.5px (scaled), bars 2px radius, legends as square swatches. The closing combo chart (compliance % in `text`, average age on a right axis in `primary`) is meant for two or more closed months (unverified, see gaps); a single closed month renders as two KPI fields instead of a curve.

### Loading
Skeleton blocks in the board's shape (white, hairline, shimmer sweep 1.4s) with a centered progress card listing each query with a state icon (green ok, amber loading, red error) and a count.

### Sales by Clasif2 and its zoom
The third chart card of Pedidos VTEX: title, a muted "top n de total", the total sales in bold and an icon-only zoom button (24px, soft-blue hover). Bars use the primary blue and money labels abbreviated ("$195,2 mill."). The zoom is a centered sheet (inset 4.5rem 3rem 2rem, board background, popover shadow, 160ms scale-fade) over a 35% scrim: a header with the title, a muted line ("Sin pedidos cancelados. Respeta los filtros y los clics del tablero"), two small export buttons and a close button; two cards side by side, classifications on the left (the chosen bar keeps full color, the rest drop to 30% alpha) and the products of the chosen one on the right with a select above it as the keyboard path to the same choice. Hidden in TV mode.

### Order drawer
Clicking an order row (detail table, critical table, a notification, an assistant answer) opens a side sheet 33rem wide (full width under 900px) anchored under the header, over a 20% scrim, so the board stays visible on the left. Header: package disc, "Pedido" plus mono Sequence, VTEX order id, previous/next buttons that walk the detail table, close button. Body: state pill, VTEX status and pending cause as tags; a two-column facts grid (customer and channel, order amount, creation, estimated delivery, SLA, warehouse, SAP order, units); the lines table (SAP code in mono, wrapping description, quantity, price, amount, a totals row; price hides under 900px) in a focusable scroll region; a note when the lines do not add up to the VTEX total; an inline warning listing the available columns when description or price could not be found. Slides in 220ms; Esc, the scrim or the X close it and focus returns to the row.

### Assistant
A query icon (message bubble with a question mark) in the header opens a chat sheet with the same geometry as the drawer and no scrim, so it can stay open while working. Empty state: a blue icon disc, a title and four clickable example questions. The input carries the same query icon on its left. User messages are solid deep-blue bubbles aligned right; answers sit next to a 28px deep-blue disc with the sparkles icon and are white cards with the figure at 28px bold, one sentence, the other measures as a quiet stat line (pedidos, unidades, ventas), filter chips, an optional table in a focusable scroll region (columns typed by the server: text, number, pesos, percent, date, order; an order number is a mono link that opens the order drawer; header sticky, numbers right-aligned and never wrapped, descriptions wrap), a "Descargar CSV" link, muted notes (for example excluded cancelled orders) and a row of follow-up question pills ("Seguir con"); a skeleton bubble shows while waiting. The sheet is 42rem wide because list tables are wide. The header subline says which engine answers and whether data leaves the network. Hidden in TV mode.

### Toast
Top right, 22rem, white 8px card with popover shadow, a blue icon disc, bold title and muted subline, a close button; slides in 220ms, auto-closes at 7s, fades out 180ms.

### Notification center
Bell button (36px, 8px radius) with a red count badge (17px pill, white 2px ring) and a ring animation (0.9s) plus a pop on the badge when new orders arrive. The popover (24rem, max 32rem tall, 8px radius, popover shadow, opens with a 140ms scale-fade from the top right) has a header with "Marcar todas como leídas", a list of items (icon disc, bold title, muted time and channel; unread = Sky Wash background, blue filled icon disc and a blue dot), an empty state, and a footer note that the last 50 are kept in this browser. Under 900px the panel is full width.

## Cross-filter selection

Clicking a bar or table row filters the whole board like Power BI. The clicked chart keeps every category: unselected bars drop to 28% alpha of their color (30% for state segments), the selected ones keep full color. Selected table rows use `--primary-soft`. The matching filter control above always shows the selection (several values read "N seleccionados"). Hover on a clickable bar uses a pointer cursor. Clicking the selection again clears it; Ctrl or Shift adds values.

## Do's and Don'ts

### Do:
- **Do** use Ant Blue only for interactive and selected state; use `primary-strong` for blue text and filled buttons.
- **Do** separate surfaces with a 1px `line` hairline on white cards over the #F5F5F5 canvas.
- **Do** use 8px radius for containers and controls and 4px for tags and chips; no third radius.
- **Do** read colors from the tokens (CSS and Chart.js) so light and dark stay in sync; check any new pair for contrast.
- **Do** keep the board fitted to the window: new content must share the existing grid and scale with `--u`.
- **Do** use Tabler outline icons through the local icon map, and skeletons for loading.
- **Do** write labels in sentence case with tabular numerals; use JetBrains Mono for codes and counts.

### Don't:
- **Don't** add a second accent hue or use green, amber or red for anything but order and alert state.
- **Don't** add hero bands, gradients as decoration, or hard offset shadows; floating layers only use the popover shadow.
- **Don't** use em dashes or glyph or emoji icons; use the middle dot sparingly.
- **Don't** let the board scroll on desktop; use the existing flow mode below 0.9 scale instead.
- **Don't** put white text on `primary` (#1677FF); use `primary-strong` for that pairing.

## Provenance

The only raster is public/img/logo.png, the corporate logo (Electrolux wordmark) supplied by the user and extracted unchanged from the v2.6 page, always on a fixed white plate. Fonts: Plus Jakarta Sans (Google Fonts, OFL) and JetBrains Mono, both self-hosted woff2. Icons: Tabler Icons (MIT), outline, served locally from iconos.js.

## Known gaps

- TV mode is still the desktop board enlarged, not a recomposition for a room.
- The closing combo chart with two or more closed months (second series `primary`) is unverified because demo data has only one closed month.
- The image-to-code step used the reference preview image and its DESIGN.md instead of a generated mock, because no image generation was available.
