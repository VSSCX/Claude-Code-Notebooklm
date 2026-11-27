---
name: Trazabilidad Order Desk
description: Paneles blancos y suaves sobre un escritorio azul grisáceo; herramienta clara y con aire para analistas de Order Desk.
colors:
  desk: "#EEF1F6"
  paper: "#FFFFFF"
  paper-2: "#F6F8FB"
  paper-3: "#ECEFF4"
  ink: "#161B26"
  ink-2: "#3A4352"
  muted: "#5B6574"
  hair: "#E1E6ED"
  edge: "#8893A3"
  track: "#E3E8EF"
  rail: "#131A2B"
  rail-ink: "#B9C2D3"
  rail-hair: "#232C42"
  ultramarine: "#2F4FE0"
  ultramarine-soft: "#E8EDFE"
  delivered-green: "#14724A"
  delivered-green-solid: "#1E8A5B"
  delivered-green-soft: "#E1F4EA"
  attention-amber: "#8A5300"
  attention-amber-solid: "#E09100"
  attention-amber-soft: "#FFF1D6"
  void-red: "#B42318"
  void-red-soft: "#FDE4E1"
  scheduled-blue: "#3D68A0"
  scheduled-blue-soft: "#E1EBF7"
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
  base: "8px"
  lg: "14px"
  pill: "999px"
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
    padding: "6px 14px"
    height: "34px"
  btn-primary:
    backgroundColor: "{colors.ultramarine}"
    textColor: "#FFFFFF"
    rounded: "{rounded.base}"
    padding: "6px 14px"
    height: "34px"
  btn-danger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.void-red}"
    rounded: "{rounded.base}"
  tag:
    backgroundColor: "{colors.paper-3}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
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
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "10px 16px 10px 10px"
---

# Design System: Trazabilidad Order Desk

## Overview

**Creative North Star: "El escritorio despejado"**

Una herramienta de uso intensivo que se siente tranquila: paneles blancos de esquinas suaves apoyados sobre un escritorio azul grisáceo, mucho aire entre bloques y una jerarquía que sale de peso y tamaño, no de reglas negras. Cada pedido conserva su identidad de despacho (número grande, código de barras escaneable, ruta de nueve pasos), pero sin el aspecto de formulario encajonado: bordes finos, una sombra apenas visible y color solo donde significa algo.

El riel lateral es de tinta azulada, con un resalte que se desliza de un apartado al otro. El ultramar aparece en selección, acción principal y foco; verde, ámbar, rojo y azul grisáceo mantienen su significado. Las alertas ya no tapan la pantalla: van a una campanita con tres niveles (Urgente, Alerta, Aceptado). Tema claro y oscuro, ambos desde los mismos tokens.

**Key Characteristics:**
- Paneles `paper` sobre `desk`, radio de 14px en contenedores y 8px en controles.
- Bordes de 1px `hair`; una sola sombra suave en paneles y una grande solo en overlays.
- Leyendas en minúscula normal (sin mayúsculas espaciadas); cifras tabulares.
- Tags en píldora; ruta de pasos con celdas suaves (hecho = tinta, siguiente = ultramar, entregado = verde).
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
**The Soft Lift Rule.** Los paneles se despegan con una sombra mínima (`sh-1`); la sombra grande (`sh-2`) es solo de lo que flota: diálogos, alertas, menús y toast.

## Shapes

Esquinas suaves: 8px en controles (`--r`), 14px en paneles, etiquetas, expedientes y diálogos (`--r-lg`; 18px en diálogos y alertas) y píldora en tags, filtros y contadores. Círculos para el número de paso y los puntos de estado. Bordes de 1px `hair` en reposo y `line` en botones; los campos de texto usan `edge` para mantener 3:1. Sin filetes de color mayores de 1px en avisos ni tarjetas.

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

### Toast y alertas
Tarjeta `paper` en la esquina inferior derecha, con chip de icono del nivel (verde Aceptado, ámbar Alerta, rojo Urgente), sombra `sh-2` y radio 14px. Dura 3,2 s (Aceptado), 6,5 s (Alerta) o 10 s (Urgente), se queda mientras el puntero está encima y ofrece «Ver» o una acción (p. ej. Deshacer, 7 s). Todo aviso queda además en la campanita del riel: panel de 440px con filtros por nivel, historial de 14 días en este equipo, contador de sin leer con el color del nivel más grave y una animación breve al llegar algo urgente.

### Inputs
Mín. 34px, borde `edge`, fondo papel, radio 8px; hover borde `ink-2`; foco: contorno ultramar de 2px y borde ultramar. Solo lectura sobre `paper-2`. Cantidades alineadas a la derecha en tabulares. Textarea en mono 13px.

### Navegación (riel)
Fondo `rail`; marca con logo ultramar de 36px y nombre en blanco; campanita de alertas a la derecha. Ítems de 10px 12px con radio 11px; un resalte único se desliza de un ítem al otro al pasar el puntero (240ms, ease in-out) y el icono se desplaza 2px; el activo (`aria-current`) lleva fondo translúcido y contador ultramar. Pie con punto de sincronización y usuario.

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
