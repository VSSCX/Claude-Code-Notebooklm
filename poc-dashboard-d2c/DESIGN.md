---
name: Dashboard D2C · Cruce VTEX vs SAP
description: Order-desk board where every panel is a printed logistics label on a grey desk, beside an ink rail.
colors:
  desk: "#E4E8EC"
  paper: "#FDFDFC"
  paper-2: "#F2F4F5"
  paper-3: "#E9EDEF"
  ink: "#12171C"
  ink-2: "#39424B"
  muted: "#586069"
  hair: "#CBD1D7"
  edge: "#7A838D"
  track: "#DCE1E6"
  rail: "#12171C"
  rail-ink: "#C5CCD3"
  rail-hair: "#2A323A"
  logo-plate: "#FFFFFF"
  accent: "#2442D6"
  accent-ink: "#FFFFFF"
  accent-soft: "#E6EBFB"
  ok: "#17724A"
  ok-solid: "#1B7F50"
  ok-soft: "#DDF0E5"
  warn: "#8F5200"
  warn-solid: "#D98A00"
  warn-soft: "#FBEBCD"
  err: "#B3261E"
  err-soft: "#FADDD9"
  sched: "#3F6A99"
  sched-soft: "#DDE8F3"
  on-err: "#FFFFFF"
  on-warn: "#1F1400"
  desk-dark: "#0E1216"
  paper-dark: "#161C22"
  ink-dark: "#E8ECF0"
  accent-dark: "#8FA3FF"
typography:
  brand:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.015em"
  kpi-value:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "min(1.75rem, 2.3cqw)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.025em"
    fontFeature: "tnum"
  panel-title:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.005em"
  body:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
  table:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "0.78125rem"
    fontWeight: 400
    fontFeature: "tnum"
  field-legend:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.07em"
  code:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.93em"
    fontWeight: 700
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
rounded:
  r: "2px"
  dot: "50%"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1.125rem"
  rail-width: "11.5rem"
components:
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "0 0 2px 2px"
    padding: "0.5rem 0.75rem 0.375rem"
  kpi-row:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "0.5625rem 0.75rem 0.5rem"
  alert-marker:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    height: "2rem"
    padding: "0 0.625rem 0 0.75rem"
  alert-marker-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  order-tile:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "0.4375rem 0.75rem"
  order-tile-pressed:
    backgroundColor: "{colors.accent-soft}"
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    height: "1.875rem"
    padding: "0 0.75rem"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    height: "1.875rem"
    padding: "0 0.5rem"
  rail:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.rail-ink}"
    width: "11.5rem"
    padding: "1rem 0.75rem 0.75rem"
  rail-nav-current:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    padding: "0.5rem 0.625rem"
  tag:
    backgroundColor: "{colors.paper-3}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.r}"
    padding: "0 0.4375rem"
  logo-plate:
    backgroundColor: "{colors.logo-plate}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    padding: "0.5rem 0.625rem"
  toast:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.r}"
    padding: "0.5625rem 1rem"
---

# Design System: Dashboard D2C · Cruce VTEX vs SAP

## Overview

**Creative North Star: "The Logistics Docket"**

Every panel is a printed label or docket lying on a cool grey desk. Paper is near-white, edged by a hairline, and headed by a 2px ink rule like the bar on a shipping label. A near-black ink rail on the left carries the brand, the three screens and the controls. Fields, buttons and tags are tools on the desk: 2px corners, 1px borders, no decoration. The system is inherited from the sibling Order Desk (Trazabilidad) and is the same world here, applied to a VTEX-versus-SAP cross-check.

Density is high and exact. Figures are tabular, state is carried by five fixed colors, and one blue accent is reserved for selection, focus and the sorted column. The board fits the window like Power BI "fit to page" and never scrolls on desktop; the rem is scaled by `--u`, set from the window size.

The build rejects the SaaS card grid with soft shadows and hero metrics. KPIs are one label with six fields, not six floating cards.

**Key Characteristics:**
- Ink rail plus paper panels with a 2px ink top rule on a grey desk.
- Flat at rest; the only shadow belongs to the floating toast.
- One accent (blue); five fixed order-state colors; everything else is neutral.
- Hanken Grotesk for text, JetBrains Mono for order numbers and counts, both served locally.
- Light and dark themes through the same token names; auto by OS, overridable by the rail toggle.

## Colors

Cool-grey neutrals with a single cobalt accent and a closed set of state colors. Values below are the light theme; dark values are listed in the dark paragraph.

### Primary
- **Dispatch Cobalt** (#2442D6): selection, the sorted column, focus rings, the loading calc bar, selected text. Its soft tint (#E6EBFB) fills a pressed order tile. Text on it is white (#FFFFFF).

### Secondary (state colors, fixed meaning)
- **Integrated Green** (#17724A text, #1B7F50 solid, #DDF0E5 soft): Integrado Facturado, positive deltas, OK tags.
- **Amber Hold** (#8F5200 text, #D98A00 solid, #FBEBCD soft): Integrado/No integrado Pendiente, pending cause bars, warnings.
- **Fault Red** (#B3261E, soft #FADDD9): No integrado Facturado, critical markers, risk figures, overdue dates, error banner.
- **Scheduled Blue** (#3F6A99, soft #DDE8F3): Integrado Pendiente.
- Order-state tokens (read by charts, matrices and pills): `--st-if` Integrado Facturado = ok-solid; `--st-ip` Integrado Pendiente = sched; `--st-nf` No integrado Facturado = err; `--st-np` No integrado Pendiente = warn-solid; `--st-ca` Cancelado = edge.

### Neutral
- **Desk Grey** (#E4E8EC): page background behind everything.
- **Label Paper** (#FDFDFC), **Paper 2** (#F2F4F5), **Paper 3** (#E9EDEF): panel surface, subtotal/hover rows, count chips and tags.
- **Ink** (#12171C), **Ink 2** (#39424B), **Muted** (#586069): text tiers; Ink also draws panel top rules and the header underline of tables.
- **Hairline** (#CBD1D7), **Edge** (#7A838D), **Track** (#DCE1E6): row dividers, control borders and Cancelado, progress tracks.
- **Rail Ink** (#12171C bg, #C5CCD3 text, #2A323A hairline): the left rail.
- **Logo Plate** (#FFFFFF): fixed white plate behind the corporate logo in both themes.

Dark theme (same token names): desk #0E1216, paper #161C22, ink #E8ECF0, accent #8FA3FF with ink-on-accent #0B1020; state colors lighten (ok #5CC592, warn #F0B04A, err #F28074) and their soft tints become deep tints. The rail darkens to #0A0D10.

### Named Rules
**The Five States Rule.** An order's state is always one of the five `--st-*` tokens, in the same hue in chips, tiles, chart series and matrix columns. Never introduce a sixth state color or reuse a state hue for decoration.

**The One Accent Rule.** Cobalt means "you selected / you can act / focus". It is never a fill for data series or status.

**The Heat Tint Rule.** Matrix cells are tinted with `color-mix(in srgb, <state token> 14-60%, transparent)`, scaled per column by its maximum; zero cells stay unfilled and muted. The tint never changes hue between columns.

## Typography

**Text Font:** Hanken Grotesk (Segoe UI, system-ui fallback), variable 100-900, local woff2.
**Code Font:** JetBrains Mono (ui-monospace, Cascadia Mono, Consolas fallback), local woff2.

**Character:** a plain humanist grotesk for reading and a mono for identifiers, both with tabular figures. No display face; hierarchy comes from weight and size.

### Hierarchy
- **KPI value** (700, min(1.75rem, 2.3cqw), 1.05, -0.025em): the six KPI fields; sized by container width so six fit in one row.
- **Brand** (700, 1rem, 1.1): product name on the logo plate.
- **Panel title** (650, 0.9375rem, 1.2): panel headings, clamped to two lines.
- **Body** (400, 0.8125rem, 1.4): default text, controls, rail items (550 weight on buttons/nav).
- **Table** (0.78125rem): rows; order numbers use JetBrains Mono 700 at 0.9em.
- **Field legend** (700, 0.75rem, +0.07em, uppercase): the caption above each filter control, KPI field names and table column heads. It names a field; it is not placed above headings.
- **Order tile count** (700, 1.0625rem): number in an order-state tile.

### Named Rules
**The Tabular Rule.** Every number uses tabular figures; identifiers and counts in markers use the mono face.

**The Scale Rule.** Sizes are rem against `--u`; never set px type except chart canvas text, which reads `--u` via `fz()`.

## Layout

The board is a CSS grid inside `.app`: an 11.5rem ink rail and a stage (filters strip, optional error banner, main). `main` is a non-scrolling absolute grid inset 0.75rem top/bottom and 1.125rem left/right, with 0.75rem gaps. Each screen names its own areas: Pedidos (alert markers / order tiles and cause beside detail table / three charts / delivery matrix), Resumen (KPI row / composition / critical + channel / closing), Diagnóstico (two charts over matrix and detail). Spacing steps in use: 0.25, 0.375, 0.5, 0.625, 0.75, 1.125rem.

Fit and scale: `--u` = min(window width / 1440, height / 800), capped at 3, applied to `html` font-size (16px x u). Columns hide by card width (amount below 800u, creation below 660u, matrix abbreviations below 440u).

TV mode (`.tv`): its own reference canvas of 1152x648 (versus 1440x800), so type and figures render much larger; filters and the segmented tools are hidden and replaced by a one-line filter summary; creation and SLA columns are hidden; the column-hide thresholds shrink to 0.72; rows that do not fit whole are cut and a "+N más" line reports the count; the cursor hides when idle; chart text gets a further 1.15x.

Flow mode (`html.flow`): when the fitted scale would fall under 0.9, `--u` is held at 0.9, the page scrolls and `main` gets a 46rem height.

Mobile (<900px): the rail becomes a wrapping top bar, screens stack in a column with 16rem minimum panel height, tables cap at 26rem, KPIs go 2-up, filters collapse behind a button. Print hides rail, toasts and filters.

## Elevation & Depth

Flat and tonal. Depth is made by paper-on-desk contrast, hairline borders and the 2px ink top rule, not shadow. The one shadow (`0 1px 2px rgba(18,23,28,.12), 0 6px 14px rgba(18,23,28,.16); stronger black in dark`) is used by the new-order toast because it is the only object that floats over the board. Sticky table heads sit on paper with an ink underline.

### Named Rules
**The Flat Desk Rule.** Panels, tiles, markers and buttons carry no shadow at rest or on hover; hover changes border to ink or fills paper-2.

## Shapes

Square-cornered paper: the shared radius is 2px (`--r`) on controls, tags and rail items. Panels are rounded only at the bottom (0 0 2px 2px) so the ink top rule stays a straight edge. Status dots and the sync light are circles (50%); legend swatches and column heads use 2px squares or 3px bars. Borders are 1px; the panel top rule is 2px ink; selected tiles add an inset 2px cobalt outline.

## Components

### Rail
Ink column: logo plate, screen nav, then sync status, the three-way theme segment (auto, light, dark) and the TV toggle. Current screen and pressed tools invert to paper-on-ink; hover fills rail hairline; focus ring is white. Press scales to 0.98 over 100ms.

### Panel (docket)
Paper, 1px hairline, 2px ink top, 0.5rem 0.75rem header with title left and muted sub right, body scrolls inside. The panel is the only container; panels are never nested.

### KPI row (label object)
One bordered paper strip with a 2px ink rule, six equal fields separated by 1px hairlines: legend, big tabular value, delta line. Risk field value is red. It is a single object, not six cards.

### Alert markers
Square 2rem buttons: a dot, label, and mono count chip. Pressed = ink fill with paper text. Critical markers use a red dot and a red-soft count chip. "Limpiar" is dashed.

### Order-state tiles
Full-width rows with a state-colored dot, label and a 1.0625rem count; pressed = cobalt-soft fill with inset cobalt outline; changed counts flash paper-3 for 1.4s.

### Tag
2px-cornered 0.75rem/600 chip in soft tint plus matching text: neutral, green, blue, red, amber, cobalt. "NUEVO" is an ink-filled tag.

### Matrices (heatmaps)
Sticky head with a 3px state-colored bar, left column with state dot; cells tinted by the Heat Tint Rule; the delivery matrix marks overdue in solid red and due-soon in solid amber with fixed on-colors.

### Controls
Filter fields: legend above, 1.875rem tall, paper, 1px edge, cobalt focus outline; buttons share the same height and hover border ink.

### Charts
Chart.js reading CSS tokens through `css()`: series use the `--st-*` tokens; gridlines hair; ticks muted; labels ink-2; closing chart pairs ink (compliance) with muted (aging). Legends are square points.

### Loading calc bar and toast
A 3px cobalt gradient sweeps along the top of the stage while data loads (1.1s linear loop). The toast is an ink pill centered at the bottom, 160ms rise.

### Logo
`public/img/logo.png` (Electrolux wordmark, user's existing corporate logo, unchanged) always sits on a fixed white plate with 2px corners so it reads in dark theme.

## Do's and Don'ts

### Do:
- **Do** head every panel with the 2px ink rule over a paper body with a 1px hairline.
- **Do** read order-state colors only from `--st-if/ip/nf/np/ca`.
- **Do** keep motion to 100-160ms ease-out state feedback and respect `prefers-reduced-motion`.
- **Do** write figures with tabular numerals and identifiers in JetBrains Mono.
- **Do** define new colors as light/dark token pairs and use `--u` for all sizes.

### Don't:
- **Don't** wrap metrics in separate soft-shadowed cards or enlarge a single hero number; KPIs stay one label with fields.
- **Don't** add shadows to panels or controls; the toast alone floats.
- **Don't** use the cobalt accent for status or data series.
- **Don't** put an uppercase caption above panel titles or headings; uppercase legends belong to fields, KPI names and column heads only.
- **Don't** load fonts, scripts or images from the internet; everything is served locally.

## Known Gaps

- TV legibility is the desktop board enlarged on a smaller reference canvas, not a recomposition for a room screen.
- The closing combo chart's second series (muted, aging in days) is unverified: demo data has one closed month, which renders the two-field solo view instead of the curve.

## Provenance

The only raster is `public/img/logo.png`, the user's pre-existing corporate logo (Electrolux wordmark), extracted unchanged from the data URI in the v2.6 page (`POC_Dashboard.v2.6.original.py`) and shown on a fixed white plate (#fff). No generated assets.
