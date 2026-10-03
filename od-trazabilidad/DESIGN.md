---
name: Trazabilidad Order Desk
description: Cada pedido es una etiqueta logística impresa; herramienta densa para analistas de Order Desk.
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
  ultramarine: "#2442D6"
  ultramarine-soft: "#E6EBFB"
  delivered-green: "#17724A"
  delivered-green-solid: "#1B7F50"
  delivered-green-soft: "#DDF0E5"
  attention-amber: "#8F5200"
  attention-amber-solid: "#D98A00"
  attention-amber-soft: "#FBEBCD"
  void-red: "#B3261E"
  void-red-soft: "#FADDD9"
  scheduled-blue: "#3F6A99"
  scheduled-blue-soft: "#DDE8F3"
typography:
  display-num:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.025em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  subtitle:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.25
  body:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.42
  body-sm:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.42
  label:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "0.01em"
  field-cap:
    fontFamily: "Hanken Grotesk, Segoe UI, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.07em"
  code:
    fontFamily: "JetBrains Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.93em"
    fontWeight: 700
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
rounded:
  base: "2px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  btn:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "5px 12px"
    height: "32px"
  btn-primary:
    backgroundColor: "{colors.ultramarine}"
    textColor: "#FFFFFF"
    rounded: "{rounded.base}"
    padding: "5px 12px"
    height: "32px"
  btn-danger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.void-red}"
    rounded: "{rounded.base}"
  tag:
    backgroundColor: "{colors.paper-3}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.base}"
    padding: "1px 7px"
  tag-ok:
    backgroundColor: "{colors.delivered-green-soft}"
    textColor: "{colors.delivered-green}"
  tag-warn:
    backgroundColor: "{colors.attention-amber-soft}"
    textColor: "{colors.attention-amber}"
  tag-err:
    backgroundColor: "{colors.void-red-soft}"
    textColor: "{colors.void-red}"
  label:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
  docket:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "12px 14px"
  paso:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.muted}"
    padding: "6px 8px 7px"
  paso-done:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  paso-next:
    backgroundColor: "{colors.ultramarine-soft}"
    textColor: "{colors.ultramarine}"
  paso-last:
    backgroundColor: "{colors.delivered-green-solid}"
    textColor: "#FFFFFF"
  seg:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    height: "30px"
  seg-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  chip-cam:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "7px 10px 8px"
    width: "172px"
  item:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "6px 6px 6px 8px"
  sug:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
  barra-opc:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "10px 12px"
  toast:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.base}"
    padding: "9px 16px"
---

# Design System: Trazabilidad Order Desk

## Overview

**Creative North Star: "La etiqueta logística"**

Cada pedido se imprime como una etiqueta de despacho GS1: campos encajonados, una regla gruesa de tinta y un código de barras escaneable. La herramienta se lee como una etiqueta de pallet bien impresa, no como un dashboard SaaS. El sistema rechaza la grilla de tarjetas, la tira de métricas heroicas y la carcasa redondeada con sombras suaves.

La superficie de trabajo es papel de etiqueta (casi blanco) sobre un escritorio gris frío; el riel y las reglas son tinta casi negra. El ultramar aparece solo en selección, acción principal y foco; los colores de estado hacen trabajo (entregado, requiere atención, anulado o error, programado). La densidad es alta, las cifras son tabulares y las esquinas casi rectas. Tema claro y oscuro, ambos desde los mismos tokens.

**Key Characteristics:**
- Papel sobre escritorio: `paper` sobre `desk`, riel de tinta fijo a la izquierda.
- Reglas de tinta de 1px y 2px; radio máximo 2px.
- Campos encajonados con leyendas pequeñas en mayúsculas.
- Código 128 real del número de pedido, siempre sobre placa clara.
- Una sola sombra suave, solo en diálogos y toast.
- Hanken Grotesk para texto; JetBrains Mono solo para códigos y cantidades.

## Colors

Paleta fría y contenida: neutros azulados, un acento ultramar y cuatro colores de estado con significado fijo. Los valores del frontmatter son los del tema claro; el tema oscuro redefine los mismos tokens (`--accent` pasa a #8FA3FF, `--paper` a #161C22, `--desk` a #0E1216, etc.) por `prefers-color-scheme` o `data-theme="dark"`.

### Primary
- **Ultramar** (`ultramarine`): selección (fila activa, chip activo, sugerencia elegida), botón primario, foco, siguiente paso de la ruta. `ultramarine-soft` es el fondo de lo seleccionado.

### Secondary (estado)
- **Verde entregado** (`delivered-green`, `-solid`, `-soft`): entregado, completo, OK. El `-solid` rellena barras y el último paso.
- **Ámbar atención** (`attention-amber`, `-solid`, `-soft`): requiere acción, sin agendar, avisos.
- **Rojo anulado** (`void-red`, `-soft`): anulado, error, peligro, valor en alerta.
- **Azul grisáceo programado** (`scheduled-blue`, `-soft`): agendado, informativo.

### Neutral
- **Escritorio** (`desk`): fondo del body. **Papel** (`paper`, `paper-2`, `paper-3`): superficies, filas alternas/pies, hover.
- **Tinta** (`ink`), **Tinta 2** (`ink-2`), **Apagado** (`muted`): texto, reglas gruesas, leyendas.
- **Pelo** (`hair`): divisores finos. **Borde** (`edge`): bordes de controles, contraste ≥3:1. **Pista** (`track`): fondo de barras.
- **Riel** (`rail`, `rail-ink`, `rail-hair`): navegación lateral.

### Named Rules
**The Ultramarine Rule.** El ultramar significa "esto está seleccionado, es la acción o tiene foco". Nunca decora.
**The Status Job Rule.** Verde, ámbar, rojo y azul grisáceo se usan solo con su significado; un estado nuevo no toma un color por estética.

## Typography

**Text Font:** Hanken Grotesk (Segoe UI, system-ui), variable 100-900, servida local.
**Code Font:** JetBrains Mono (ui-monospace, Consolas), variable 100-800, servida local.

**Character:** grotesca neutra y legible para lectura larga, mono solo donde el carácter importa (números de pedido, entrega, cantidades, SKU).

### Hierarchy
- **Display numérico** (700, 34px, 1.05, -0.025em): número de pedido en la etiqueta (`.lab-num`); 26px bajo 900px.
- **Headline** (650, 24px, 1.2): título de página.
- **Title** (650, 19px, 1.2): h2 y marca del riel.
- **Subtitle** (650, 16px, 1.25): h3, ID de expediente, cifra de entrega, valor de celda.
- **Body** (400, 14px, 1.42): texto base y controles. Párrafos de panel hasta 72ch.
- **Body-sm** (13px): tablas, metadatos, líneas secundarias. Mínimo de lectura 12px.
- **Label** (600, 12px): leyendas de formulario, tags, texto de paso.
- **Field-cap** (700, 11px, 0.07em, mayúsculas): leyenda dentro de una celda de campo (`.cap`, `.opt > span`), siempre unida al valor que rotula.
- **Code** (700, 0.93em, -0.01em, tabulares): números de pedido en lista (15px), entregas, cantidades.

### Named Rules
**The Mono Is For Codes Rule.** JetBrains Mono solo para códigos y cantidades; el texto corrido nunca.
**The Tabular Rule.** Toda cifra usa `tabular-nums`.

## Layout

Rejilla de dos columnas: riel de 216px y escenario fluido (`#app`, máx. 1720px, relleno 20px 24px). Pedidos es un `split` de lista (330-404px) y etiqueta; el Cubicador es una `mesa` de carga (340-410px) y visor 3D a altura de viewport. La lista es pegajosa y sin scroll de página. Ritmo de espaciado observado: 4, 6, 8, 10, 12, 14, 16, 20, 24px; huecos de 12-16px entre bloques, 8px dentro de filas. Filas densas, controles de 32px (30px en barras de opciones, 26px `sm`).

Responsive: a 1180px las columnas se estrechan y la mesa pasa a una columna; a 900px el riel se vuelve barra horizontal superior, `split` a una columna, la ruta de 9 pasos pasa a 3x3 y las tablas hacen scroll horizontal (min 560px). Se respeta `prefers-reduced-motion`; impresión oculta riel, toast y diálogos.

## Elevation & Depth

Plano por defecto: la profundidad la dan las reglas (pelo 1px, tinta 1px, tinta 2px arriba de expedientes) y el cambio de tono papel/escritorio. Hay una sola sombra, reservada a objetos que flotan sobre la página.

### Shadow Vocabulary
- **Lift** (`box-shadow: 0 1px 2px rgba(18,23,28,.12), 0 6px 14px rgba(18,23,28,.16)`; en oscuro con negro .5): diálogo y toast.

### Named Rules
**The One Lift Rule.** Solo overlays llevan sombra. Paneles, etiquetas, filas y botones no.

## Shapes

Esquinas casi rectas: radio de 2px en todo (`--r`); círculos solo para el número de paso (20px) y los puntos de estado (8px). Bordes de 1px (`hair` en reposo, `ink` en objetos principales como la etiqueta, la ruta, diálogos y visor). Expedientes y chips de camión llevan una regla superior de 2px de tinta, con esquinas inferiores de 2px y superiores rectas.

## Components

### Label (etiqueta de pedido)
Borde de tinta 1px sobre papel. Cabecera con número en display numérico y prefijo apagado, acciones arriba a la derecha (primaria incluida) y el código de barras a la derecha. Rejilla de celdas encajonadas (`cells`, mín. 130px) bajo una regla de tinta de 2px: leyenda field-cap sobre valor de 16px 600; la celda en alerta pinta el valor en rojo. Después, barra de avance, observaciones y pie en `paper-2`; los botones que escriben en SAP llevan borde de tinta y peso 650.

### Código de barras
Code 128 real del número de pedido. Placa fija `#fff` con barras `#000`, 44px de alto, relleno 4px 8px, radio 2px, también en tema oscuro, para que el escáner lo lea. Bajo la placa, el número en mono 11px con tracking .14em.

### Docket (expediente de entrega/camión)
Papel, borde `hair`, regla superior de tinta 2px. Cabecera con ID mono y cantidad; bloque `meta` de celdas con leyenda field-cap; acciones al pie. Anulado: fondo `paper-2`, textos al 70% y tag `void`.

### Ruta y paso
Tira de 9 celdas con borde de tinta 1px y divisores de pelo. Pendiente: papel, texto apagado, círculo numerado de borde `edge`. Hecho: relleno de tinta, círculo invertido con check. Siguiente: `ultramarine-soft` con aro interior de 2px ultramar. Último hecho (entregado): verde sólido con texto blanco. Pasos fijos no son clicables. Clic cambia al instante; guarda en segundo plano.

### Seg
Control segmentado de 30px, borde `edge`, divisores 1px; el pulsado se rellena de tinta con texto papel y peso 650.

### Chip-cam
Chip de camión de 172px: regla superior de tinta 2px, línea de nombre, línea secundaria y mini barra de 6px (verde, ámbar o rojo según ocupación). Activo (`aria-pressed`): `ultramarine-soft` con aro de 2px.

### Item
Fila de producto en el Cubicador: letra de 28px (fondo con el color del producto en el visor, texto claro u oscuro según contraste), cuerpo de tres líneas y stepper numérico (cantidad mono de 62px, botones de 32px). Letra activa: doble aro papel/tinta. Vacío: borde punteado `edge`.

### Sug
Lista de sugerencias bajo el buscador: borde de tinta 1px, filas de 7px 10px separadas por pelo, línea 1 en 650 y línea 2 en 12px apagado. Seleccionada: `ultramarine-soft` con aro de 2px.

### Barra-opc
Barra de opciones del Cubicador: papel, borde `hair`, grupos con leyenda field-cap encima de selects de 30px y controles seg, huecos 8px 18px.

### Btn
2px de radio, mín. 32px, borde `edge`, peso 550. Primario: relleno ultramar con texto `accent-ink`. Peligro: texto y borde rojo (sólido: relleno rojo). Quiet: sin borde ni fondo. `sm` 26px. Hover (solo puntero fino): borde de tinta y fondo `paper-2`; presionado `scale(.97)`; deshabilitado 45%.

### Tag y pip
Tag de 18px de línea, 12px/600, fondo suave del estado con texto de su color pleno: neutro, ok, warn, err, info, ink, y `void` (transparente, aro rojo, mayúsculas con tracking .08em). Pip: punto de 8px con el color del estado.

### Toast (con acción)
Pastilla de tinta con texto papel, centrada abajo (20px), máx. 560px, sombra Lift. Sin acción dura 2,6 s y no captura el puntero. Con acción (p. ej. Deshacer) dura 7 s, activa el puntero y muestra un botón-texto subrayado en 700 al final. Entra con opacidad y 8px de desplazamiento en 120-160ms.

### Inputs
Mín. 32px, borde `edge`, fondo papel, radio 2px; hover borde `ink-2`; foco: contorno ultramar de 2px y borde ultramar. Solo lectura sobre `paper-2`. Cantidades alineadas a la derecha en tabulares. Textarea en mono 13px.

### Navegación (riel)
Fondo `rail`; marca como placa de papel con el nombre en 19px/700. Ítems de 8px 10px con texto 550 y contador en pastilla; activo (`aria-current`): placa de papel con texto de tinta. Pie con punto de sincronización y usuario.

### Movimiento
Transiciones de 100-160ms con `cubic-bezier(.23,1,.32,1)` en color, borde, opacidad y transform; diálogos entran con `scale(.97)` y opacidad. Feedback de acción: `flash` de 900ms en ámbar suave; `busy` baja la opacidad a .55. Carga: esqueleto con brillo lineal y barra de cálculo de 3px en el visor. Sin animación decorativa.

## Do's and Don'ts

### Do:
- **Do** representar cada objeto de trabajo como etiqueta: celdas encajonadas, leyenda field-cap arriba, valor abajo, una regla de tinta gruesa.
- **Do** poner el Code 128 siempre sobre placa clara (`#fff` con barras `#000`), también en tema oscuro.
- **Do** usar ultramar solo para selección, acción principal y foco; estados con sus cuatro colores.
- **Do** mantener radio de 2px, bordes de 1px y una sola sombra (Lift) en overlays.
- **Do** usar `tabular-nums` en cifras y JetBrains Mono solo en códigos y cantidades.
- **Do** actualizar al instante y guardar en segundo plano; las fallas revierten con mensaje claro.
- **Do** usar los tokens `var(--...)` para todo color; los temas claro y oscuro comparten nombres.

### Don't:
- **Don't** usar kickers ni eyebrows (rótulos pequeños sobre títulos). La leyenda field-cap solo rotula un valor dentro de su celda.
- **Don't** usar rayas laterales de color en tarjetas, filas o avisos; la selección es aro completo, y la regla de 2px es superior y de tinta.
- **Don't** usar degradados en texto. Los únicos degradados son el esqueleto de carga y la barra de cálculo.
- **Don't** mostrar el código de barras sobre fondo oscuro o translúcido.
- **Don't** usar grilla de tarjetas, tiras de métricas heroicas ni esquinas redondeadas mayores a 2px.
- **Don't** usar íconos de glifo o emoji; los íconos son SVG (`iconos.js`).
- **Don't** cargar fuentes ni librerías desde CDN; todo se sirve local.

<!-- No canonizado: colores sueltos fuera de tokens (#4CCB8B y #F28074 en .dot; #fff en .btn.danger-solid y .paso.done.last), deriva sin reparar. -->
