# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase: FastAPI backend (`app/`) serving a build-less frontend (`web/index.html` + `web/js/*.js`, plain HTML/CSS/JS, `Store` object as the only data access). Stack decision for the rework: **delegated**. The user's only constraint is the end goal: the platform must be hosted on a server and reachable by URL, so each analyst does not install it or run localhost. Frontend rework comes first, backend review second, hosting last. Hosting target (corporate server vs. other) is still undecided.

## Users

Order Desk analysts who follow customer purchase orders (OC) from arrival to pack list. Intensive daily use: many open orders, hours in the screen, repeated operations per order and per delivery. Today a single analyst runs it on their own PC (phase 1); phase 2 opens it to the whole team.

## Product Purpose

Traceability of every order from OC to pack list, tracked per product and per delivery, fed directly by the SAP macros (Excel + SAP GUI). Success is that an analyst sees, without cross-checking Excel, what is pending, what has a confirmed appointment, what is invoiced and what was delivered, and can act on it quickly.

## Positioning

A traceability platform that receives data straight from the analyst's own SAP macros (packages posted to `/api/paquetes`) and keeps a per-step history of each delivery. A generic order tracker cannot reproduce the SAP macro integration, the cubicaje (load/pallet fit) engine and the 3D truck viewer in one place.

## Operating Context

- Analysts work in Windows corporate PCs with Excel and SAP GUI; macros (VBA, `TrazWeb.bas`) run on each analyst's PC and send packages to the platform URL.
- Actions that drive SAP (update bases, cubicar, simular, create deliveries/groups, 3D viewer) need the analyst's own SAP GUI session, so they run on the analyst's machine, not on a remote server. This conflicts with a pure server-hosted web app and must be resolved when hosting is designed.
- Data changes arrive from scripts while the web is open (the web polls `/api/version` every 10 s).
- Phase 1 SQLite, phase 2 SQL Server with Power BI reading the tables directly; corporate login (Microsoft Entra ID) planned before opening to the team.
- Business context: unit of business MDA/SDA and modality Stock/Predistribuido (cell E2 of the workbook).

## Capabilities and Constraints

- Domain terms (keep in Spanish): pedido, OC, entrega, grupo, cita, camión, línea, SKU, pendiente, externa, cubicaje, pallet, pack list, proyección, visor 3D, acciones.
- Pendiente = pedido − en entregas − externa. One truck = deliveries with the same appointment number (cita).
- Delivery steps (9): cita pedida → cita confirmada (needs date and time) → fecha en SAP → ETQ → portal de despacho → proyección → facturada (needs invoice number) → pack list → entregado. Rescheduling a cita reopens confirmada, SAP, portal and proyección.
- The script never lowers an order quantity; manual edits are not overwritten.
- Screens today: pedidos (list + detail with entregas), SAP/acciones, base, cubicador, proyección, plus the standalone 3D viewer `web/visor/Plantilla_Visor.html`.
- Constraints: Excel import via local `xlsx.full.min.js` (CDN fallback); corporate networks may inspect HTTPS and block external CDNs; no Node on analyst PCs today.
- Scope order: (1) entire frontend rework, backend/API/data model/VBA untouched; (2) backend review; (3) hosting. Undecided: hosting target, authentication approach, how local SAP actions work against a hosted server.

## Brand Commitments

None stated. The name in use is "Trazabilidad de pedidos · Order Desk".

## Evidence on Hand

- `README.md` (architecture, data model, rules, API, roadmap).
- Real-workbook test suites in `tests/` (API flow, cubicaje, SAP reading) and control cases folder `casos/` (empty so far).
- Existing UI in `web/` as incumbent implementation.
- No usage analytics, user research, screenshots or customer testimonials are on hand; none should be invented.

## Product Principles

1. Speed of the repeated task beats novelty: an analyst handling many orders must move through them with minimal clicks and no waiting.
2. Truth from SAP is never silently overwritten or hidden; every state shows where it came from (web or script) and when.
3. Show what needs action first: pending quantities, missing dates/invoices and blocked steps outrank completed history.
4. Errors from SAP actions are explicit and stop before touching data.
5. The platform must reach the whole team by URL without per-PC installation, without losing the analyst's local SAP actions.

## Accessibility & Inclusion

No specific standard was stated. Interface language is Spanish (Chile). Dense, long-session use implies readable contrast and keyboard-operable controls.
