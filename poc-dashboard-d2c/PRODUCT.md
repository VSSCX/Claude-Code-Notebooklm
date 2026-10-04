# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase: FastAPI backend (`app/`) serving a build-less frontend (`web/index.html`, plain HTML/CSS/JS, Chart.js for the charts). It runs on the analyst's own Windows PC (`run.bat`, `http://127.0.0.1:8000`) and is installed or updated by the single file `POC_Dashboard.py`, which embeds the whole project and never touches `.env`. The frontend rework keeps the backend API (`/api/dashboard`, `/api/filtros`, `/api/version`, `/api/config`, `/api/diagnostico`) and the data contract unchanged.

## Users

Order Desk analysts who follow D2C orders every day: intensive use, hours on screen, many filters and sorts per session, on Windows corporate PCs where HTTPS can be inspected and external CDNs blocked. The same screen is also shown on a large display (TV or meeting-room screen) to be read from a distance. Confirmed by the user; no other audience was named.

## Product Purpose

Cross-check of every VTEX (Azure) order against SAP (ODS): which orders integrated, which are still pending, which were invoiced in SAP but are still pending in VTEX, and what the money at risk is. It replicates an existing Power BI report (same button bookmarks, same page order) with live updates: the server watches the bases and the browser refreshes when a new order arrives. Success: an analyst sees what needs attention (BWS, POS fechado, MKP, integración) without cross-checking Excel or SAP, and a new order shows up without reloading.

## Positioning

A live VTEX-versus-SAP integration monitor on the analyst's own machine, with the Power BI bookmark logic built in (Atención BWS, POS Fechado, Atención MKP, Integración) and a demo mode that runs with no database. A generic BI tool does not carry those rules or the live "NUEVO" arrival feedback.

## Operating Context

- Three screens, in the Power BI order: Pedidos VTEX (alert buttons, order cards, pending cause, order detail, three charts, delivery-date matrix), Resumen ejecutivo (six KPIs, monthly composition, critical invoiced-not-integrated orders, risk by channel, monthly closing) and Diagnóstico (non-integrated by customer, daily status, creation matrix, detail).
- The page never scrolls on desktop: the board scales to fit the window (like "fit to page" in Power BI). It must also hold up on a large TV.
- Live behaviour: the browser polls `/api/version`, reloads data when the version changes, flashes changed figures, marks new orders `NUEVO` for a few minutes and shows a toast.
- Modes: real (needs SQL Server drivers and credentials in `.env`) and DEMO (synthetic data, with a "Simular pedido" button).
- Terminology to keep in Spanish: pedido, Sequence, Pedido SAP, Integrado / No integrado, Facturado / Pendiente / Cancelado, SLA Type, Bodega, Canal, Cliente, Entrega est., Monto en riesgo, Facturado sin despacho, Causa pendiente.

## Capabilities and Constraints

- Notification center (seller-center style): a bell in the header counts unread new VTEX orders, opens a panel with the latest 50 (Sequence, canal, relative time), lets the analyst mark all as read or jump to one order in the detail, and rings once on arrival; read state lives in the browser (localStorage). A toast also appears top right.
- Five order states with fixed meaning: Integrado · Facturado, Integrado · Pendiente, No integrado · Facturado, No integrado · Pendiente, Cancelado.
- Filters (canal, cliente, status, SLA Type, bodega, alcance, creation dates, free search) and column sorting are applied on the server over the whole set, not just the visible rows.
- No Node, no build step, no CDN: corporate networks may block external hosts, so fonts and libraries must be served from the app itself.
- Delivery is a single self-updating `POC_Dashboard.py` (checksum-verified embedded package). Re-running it replaces code and keeps `.env`.
- Real data only appears with the user's credentials; nothing about real volumes, customers or amounts is known here.

## Brand Commitments

The user asked for an enterprise "seller center" look and chose the Ant / Enterprise design skill (awesome-design-skills, typeui.sh: primary #1677ff, Plus Jakarta Sans, radii 4 and 8, spacing 4/8/12/16/24/32) as the reference, built with taste-skill rules and image-to-code extraction. This replaces the earlier "etiqueta logística" look. The corporate logo (Electrolux wordmark, pre-existing) is kept on a white plate.

## Evidence on Hand

- Current frontend: `web/index.html`; installer v2.6 kept as `POC_Dashboard.v2.6.original.py`.
- Demo data generator: `app/demo.py`.
- No real screenshots, user research or load figures were provided; do not invent them.

## Product Principles

1. Attention first: what needs action (alerts, critical, new) is findable before any chart.
2. Dense and exact: tabular figures, no decoration; every number traceable to a filter.
3. Live without disruption: updates never steal focus, scroll or filter state.
4. Local and offline-safe: nothing is fetched from the internet.
5. One installer, always updatable: the update path never breaks `.env` or the demo mode.

## Accessibility & Inclusion

No product-specific standard was established. Keep text contrast at least 4.5:1 (3:1 for large text), visible keyboard focus, reduced-motion respected, and legibility at TV distance. Spanish (es-CL) throughout.
