---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: []
---

# Surface brief: Trazabilidad Order Desk (web/index.html + web/js/*)

Mode: Operate. Redesign of the whole frontend (Pedidos, Por hacer, Cubicador, Proyección, SAP, Configuración, dialogs, 3D visor frame). Backend, API contract, data model and VBA are out of scope for this round. Desktop-first on large monitors; touch is occasional.

Audience and job: Order Desk analysts, long daily sessions, many open orders. Priorities: Pedidos with delivery detail, and Cubicador with the 3D visor. Main pain: delay between click and visible result (so optimistic updates), then screen redraws that lose scroll and focus.

Constraints: no build step on the analyst machine (plain HTML/CSS/JS served by FastAPI, Store as the only data access), Spanish (Chile), fonts and libraries served locally (corporate networks block CDNs), final goal is hosting at a URL.

## Direction contract

THESIS: Every order is a logistics label: boxed fields, one heavy ink rule, a scannable code. The tool reads like a well-printed pallet label, not a SaaS dashboard. It refuses the card grid, the hero-metric strip and the soft-shadowed rounded shell.

OWN-WORLD: Label-stock paper (near white, slightly warm) work surfaces on a cooler grey desk ground; ink near-black rail and rules; ultramarine accent only for selection, primary action and focus; state colours do jobs (green delivered, amber needs attention, red void or error, blue-grey scheduled). 1px ink rules, 2px radius at most, boxed field cells with small tabular captions, Hanken Grotesk for text and JetBrains Mono only for codes and quantities. Dense rows, tabular figures everywhere, no shadows beyond a single soft lift on overlays.

STORY: An analyst opens it and sees what needs action first. A click on a step changes the screen at once and saves in the background; nothing redraws under their hands; failures roll back with a clear message.

FIRST VIEWPORT: Left ink rail with text navigation (Pedidos, Por hacer, Cubicador, Proyección, SAP, Configuración) and sync status at its foot. Centre-left column: search, filters and a dense order list (order number in mono, client, fixed-scale progress bar, next action). Right: the selected order printed as a label, a ruled grid of boxed fields (cliente, OC, canal, recibido) beside the order number in large type with a real Code 128 barcode of that number, heavy rule below, then tabs and delivery rows each carrying the 9-step route strip. Primary action sits top right of the label.

FORM: Logistics pallet label (GS1 style), IMPECCABLE'S PICK; seed key ef8db7a7. Signature move: the label header with real Code 128 barcode, and the 9-step strip drawn as ruled label cells (done = ink fill, next = accent outline, delivered = green).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved decisions
- Hosting target and auth model (last phase, after frontend and backend review).
- How SAP GUI actions run from a hosted server (they need the analyst's own PC session).
- 3D visor template (web/visor/Plantilla_Visor.html) restyle is secondary; first pass only frames it.
