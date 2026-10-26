/* Vista de pedidos: lista, detalle, entregas, camiones, análisis y cubicaje.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Vista: Pedidos ============ */
function clientes(){ return [...new Set(Store.list('pedidos').map(p => p.cliente).filter(Boolean))].sort(); }
function filtroCliente(){
  return `<select data-cliente aria-label="Filtrar por cliente"><option value="">Todos los clientes</option>${clientes().map(c => `<option ${c === UI.cliente ? 'selected' : ''}>${esc(c)}</option>`).join('')}</select>`;
}
// Ordena: primero la cita más próxima; después lo que no tiene cita; al final lo cerrado
function urgencia(p){
  const ents = entregasDe(p.pedido).filter(e => !e.anulada && !pasoOk(e, 'entregado'));
  const f = ents.map(e => (e.cita || {}).fecha).filter(Boolean).sort()[0];
  if (f) return '1' + f;
  const {tot} = resumen(p);
  if (tot.pendiente > 0 || ents.length) return '2' + (p.actualizado || '');
  return '3' + (p.actualizado || '');
}
const _busq = {rev: -1, m: new Map()};
function textoBusqueda(p){
  if (_busq.rev !== Store.rev){ _busq.rev = Store.rev; _busq.m = new Map(); }
  let t = _busq.m.get(p);
  if (t === undefined){
    t = normH([p.pedido, p.oc, p.cliente, ...(p.lineas || []).map(l => l.sku + ' ' + l.desc),
      ...entregasDe(p.pedido).map(e => e.entrega + ' ' + e.grupo + ' ' + (e.cita?.numero || ''))].join(' '));
    _busq.m.set(p, t);
  }
  return t;
}

function vistaPedidos(){
  const q = normH(UI.q);
  const todos = Store.list('pedidos');
  const peds = todos
    .filter(p => !UI.cliente || p.cliente === UI.cliente)
    .filter(p => !q || textoBusqueda(p).includes(q))
    .filter(p => !UI.soloAbiertos || !cerrado(p))
    .sort((a, b) => urgencia(a).localeCompare(urgencia(b)));
  if (UI.sel && !Store.get('pedidos', UI.sel)) UI.sel = null;
  if (!UI.sel && peds.length && window.innerWidth > 960) UI.sel = safeId(peds[0].pedido);

  const lista = peds.length ? `<ul class="olist ${UI.juntar ? 'juntando' : ''}">${peds.map(p => {
      const {tot} = resumen(p); const id = safeId(p.pedido); const nx = proximaAccion(p);
      const casilla = UI.juntar ? `<label class="jchk" title="${esc(puedeJuntar(p) ? 'Cubicar junto con otros pedidos' : 'Solo se juntan pedidos ya analizados')}">
        <input type="checkbox" data-jsel="${esc(id)}" ${UI.juntarSel.has(id) ? 'checked' : ''} ${puedeJuntar(p) ? '' : 'disabled'} aria-label="Juntar el pedido ${esc(p.pedido)}"></label>` : '';
      return `<li data-k="p-${esc(id)}" class="${UI.juntar ? 'con-sel' : ''}">${casilla}<button class="orow" data-sel="${esc(id)}" aria-current="${UI.sel === id && !UI.verConjunto}">
        <span class="o-1"><span class="o-num">${esc(p.pedido)}</span><span class="o-cli">${esc(p.cliente || 'Sin cliente')}</span><span class="o-pct" data-flash>${pct(tot.agendado + tot.entregado, tot.pedida)}</span></span>
        <span class="o-2 block">OC <span class="code">${esc(p.oc || '—')}</span> · <span class="num">${fmt(tot.pedida)}</span> un.${tot.pendiente ? ` · <span class="num">${fmt(tot.pendiente)}</span> por suministrar` : ''}</span>
        ${barHTML(tot)}
        <span class="o-next ${nx.tono}" data-flash>${esc(nx.txt)}</span></button></li>`; }).join('')}</ul>`
    : `<div class="empty"><h3>${todos.length ? 'Ningún pedido coincide' : 'Aún no hay pedidos'}</h3><p>${todos.length ? 'Cambia el filtro o la búsqueda.' : 'Analiza uno desde SAP, créalo a mano o importa un Excel exportado de SAP.'}</p></div>`;

  return `<div class="split">
    <section class="panel list-col" aria-label="Pedidos">
      <div class="list-tools">
        <div class="searchbox">${ICON.search}<input type="search" placeholder="Pedido, OC, SKU, entrega…" value="${esc(UI.q)}" data-q aria-label="Buscar pedidos"></div>
        <div class="row tight" style="width:100%"><button class="btn primary sm" data-act="abrirAnalisis">Analizar pedido de SAP</button>
          <button class="btn sm" data-act="nuevoPedido">${ICON.plus} Cargar a mano</button></div>
        <div class="row">${filtroCliente()}
          <label class="chk"><input type="checkbox" data-abiertos ${UI.soloAbiertos ? 'checked' : ''}> Ocultar cerrados</label></div>
        <div class="row tight" style="width:100%"><button class="btn sm" data-act="juntarModo" aria-pressed="${UI.juntar}" title="Marca varios pedidos analizados para cubicarlos juntos en los mismos camiones (los conchos de uno viajan con otro)">${ICON.cube} ${UI.juntar ? 'Terminar de juntar' : 'Juntar pedidos'}</button>
          ${UI.conjunto && !UI.verConjunto ? `<button class="btn quiet sm" data-act="verConjunto">Volver al cubicaje conjunto</button>` : ''}</div>
      </div>
      ${lista}
      ${UI.juntar ? barraJuntar(todos) : ''}
    </section>
    <section aria-label="Detalle del pedido" class="${!(UI.verConjunto && UI.conjunto) && !UI.juntar && UI.sel ? 'detalle-pane' : ''}">${UI.verConjunto && UI.conjunto ? vistaConjunto() : UI.juntar ? vistaJuntar() : UI.sel ? detallePedido(Store.get('pedidos', UI.sel)) : `<div class="panel empty"><h3>Selecciona un pedido</h3><p>Verás su avance por producto y cada entrega con sus pasos.</p></div>`}</section>
  </div>`;
}

/* ---- Juntar pedidos: cubicar varios en los mismos camiones (multipedido del Excel) ---- */
const puedeJuntar = () => true;       // cualquier pedido se puede marcar: el panel dice qué le falta a cada uno
function seleccionJuntar(todos){
  const ps = [...UI.juntarSel].map(id => Store.get('pedidos', id)).filter(Boolean);
  const clientes_ = [...new Set(ps.map(p => (p.cliente || '').trim().toUpperCase()))];
  return {ps, clientes: clientes_.filter(Boolean)};
}
/* En qué situación está cada pedido marcado para juntar. Un pedido cuyas entregas ya se crearon con su análisis NO se puede juntar
   tal cual: duplicaría lo despachado. Hay que volver a analizarlo (SAP resta lo entregado) y queda solo lo que falta: el concho. */
function estadoJuntar(p){
  const f = flujoDe(p), {tot} = resumen(p);
  if (UI.trayendo === p.pedido) return {k: 'trayendo', tono: 'info', txt: 'Leyendo SAP…', det: 'No uses SAP mientras tanto'};
  if (!f.an) return {k: 'sin', tono: 'warn', txt: 'Sin analizar', det: 'Analízalo para saber qué falta', accion: 'Analizar'};
  if (f.desact) return {k: 'viejo', tono: 'warn', txt: 'Cambió el cliente', det: 'Vuelve a analizarlo', accion: 'Analizar'};
  const usado = f.ents.length > 0 && (!f.cb || f.ents.length >= f.cb.camiones);
  if (usado) return tot.pendiente > 0
    ? {k: 'usado', tono: 'warn', txt: `Quedan ${fmt(tot.pendiente)} un.`, det: 'Sus entregas ya están creadas: trae lo que quedó', accion: 'Traer lo que quedó'}
    : {k: 'nada', tono: 'err', txt: 'Ya se despachó todo', det: 'No tiene nada pendiente: quítalo de la selección'};
  if (!(f.an.carga > 0)) return {k: 'nada', tono: 'err', txt: 'Nada que cargar', det: 'El análisis no deja unidades para este pedido'};
  return {k: 'listo', tono: 'ok', txt: `Listo · ${fmt(f.an.carga)} un.`, det: f.an.suministro > 1 ? `Suministro ${f.an.suministro}: solo lo que faltaba` : 'Listo para cubicar'};
}
function juntarListo(){
  const {ps} = seleccionJuntar();
  return ps.length >= 2 && !UI.conjuntoCargando && !UI.trayendo && ps.every(p => estadoJuntar(p).k === 'listo');
}
function barraJuntar(todos){
  const {ps} = seleccionJuntar(todos);
  const msg = !ps.length ? 'Marca los pedidos que viajarán juntos.' : ps.length === 1 ? 'Marca al menos otro pedido más.'
    : juntarListo() ? `${ps.length} pedidos listos para cubicar juntos.` : 'Revisa el panel de la derecha: a algún pedido le falta un paso.';
  return `<div class="juntar-bar" role="region" aria-label="Juntar pedidos">
    <span class="small" aria-live="polite">${esc(msg)}</span>
    <button class="btn primary sm" data-act="cubicarJuntos" ${juntarListo() ? '' : 'disabled'}>${UI.conjuntoCargando ? 'Cubicando…' : 'Cubicar juntos'}</button></div>`;
}
/* Panel guiado: qué es juntar, en qué paso va y qué botón sigue */
function vistaJuntar(){
  const {ps} = seleccionJuntar();
  const est = ps.map(p => [p, estadoJuntar(p)]);
  const aTraer = est.filter(([, e]) => e.accion), listo = juntarListo();
  const marcados = ps.length >= 2, hechoTraer = marcados && !aTraer.length && !est.some(([, e]) => e.k === 'nada' || e.k === 'trayendo');
  const paso = (n, txt, hecho, actual) => `<span class="cj-paso ${hecho ? 'ok' : ''} ${actual ? 'actual' : ''}"><i>${hecho ? ICON.check : n}</i>${txt}</span>`;
  const actual = !marcados ? 1 : !hechoTraer ? 2 : 3;
  const siguiente = !ps.length ? 'Marca en la lista, con la casilla, los pedidos que quieres cargar en el mismo camión. Puedes marcar pedidos que ya fueron entregados y facturados si les quedó un concho.'
    : ps.length === 1 ? 'Marca al menos otro pedido más.'
    : aTraer.length ? `Falta traer lo que quedó de ${aTraer.length === 1 ? 'un pedido' : aTraer.length + ' pedidos'}. Se lee SAP (VL01N, solo lectura) y el pedido queda con <b>únicamente lo que falta</b>: lo ya entregado se descuenta.`
    : est.some(([, e]) => e.k === 'nada') ? 'Hay pedidos sin nada que cargar: desmárcalos para seguir.'
    : listo ? 'Todo listo. Al cubicar juntos se arman los camiones con la carga de todos los pedidos.' : 'Esperando a SAP…';
  return `<div class="panel juntar-guia" data-k="juntar-guia">
    <div class="panel-h"><h3>Juntar pedidos en un camión</h3><span class="spacer"></span><span class="small muted">Cada pedido mantiene su entrega; comparten camión y cita</span></div>
    <div class="cj-pasos" role="list" aria-label="Pasos para juntar pedidos">
      ${paso(1, 'Marca los pedidos', marcados, actual === 1)}${paso(2, 'Trae lo que quedó', hechoTraer, actual === 2)}${paso(3, 'Cubica juntos', false, actual === 3)}</div>
    <p class="juntar-sig"><b>Ahora:</b> ${siguiente}</p>
    ${ps.length ? `<div class="scroll"><table class="tbl"><thead><tr><th>Pedido</th><th>Cliente</th><th>Situación</th><th></th></tr></thead><tbody>
      ${est.map(([p, e]) => `<tr><td class="code"><b>${esc(p.pedido)}</b></td><td>${esc(p.cliente || '—')}</td>
        <td><span class="tag ${e.tono}">${esc(e.txt)}</span><div class="small muted">${esc(e.det)}</div></td>
        <td class="n">${e.accion ? `<button class="btn sm" data-act="traerQuedo" data-ped="${esc(p.pedido)}" ${UI.trayendo ? 'disabled' : ''}>${esc(e.accion)}</button>` : ''}
          <button class="btn quiet sm icon" data-act="quitarJuntar" data-ped="${esc(safeId(p.pedido))}" title="Quitar de la selección" aria-label="Quitar ${esc(p.pedido)} de la selección">${ICON.x}</button></td></tr>`).join('')}
    </tbody></table></div>` : `<div class="empty"><h3>Ningún pedido marcado</h3><p>Usa las casillas de la lista de la izquierda.</p></div>`}
    ${estadoJob()}
    <div class="row" style="margin-top:14px;justify-content:flex-end">
      ${aTraer.length > 1 ? `<button class="btn" data-act="traerTodos" ${UI.trayendo ? 'disabled' : ''}>Traer lo que quedó de los ${aTraer.length}</button>` : ''}
      <button class="btn primary" data-act="cubicarJuntos" ${listo ? '' : 'disabled'}>${UI.conjuntoCargando ? 'Cubicando…' : 'Cubicar juntos'}</button></div>
    <p class="juntar-nota">Después de cubicar eliges si los pedidos comparten grupo de SAP o cada uno lleva el suyo, creas las entregas, los grupos y confirmas la cita del camión.</p>
  </div>`;
}
/* Volver a analizar desde el panel, con los datos de siempre (puesto de Configuración, fecha de hoy y el cliente del pedido) */
async function traerQuedo(pedido){
  const p = Store.get('pedidos', safeId(pedido)); if (!p || UI.trayendo) return;
  if (!(p.cliente || '').trim()){ UI.sel = safeId(pedido); return abrirLecturaSap('analizar'); }       // sin cliente se pregunta
  UI.trayendo = pedido; render();
  try { await lanzarAnalisis(pedido, {puesto: (config().puesto || 'PN01').toUpperCase(), fecha: new Date().toISOString().slice(0, 10), cliente: p.cliente}); await Store.refresh(); }
  finally { UI.trayendo = null; render(); }
}
async function traerTodos(){
  for (const p of seleccionJuntar().ps){
    if (!estadoJuntar(p).accion) continue;
    await traerQuedo(p.pedido);
    const e = estadoJuntar(Store.get('pedidos', safeId(p.pedido)) || p);
    if (e.accion) return;                                  // algo falló: el aviso ya salió, no se sigue con los otros
  }
}
async function cubicarJuntos(){
  const ids = UI.verConjunto && UI.conjunto ? [...UI.conjunto.conjunto.pedidos] : [...UI.juntarSel];
  if (ids.length < 2) return;
  if (!(UI.verConjunto && UI.conjunto)) UI.conjOpts = null;       // un conjunto nuevo parte de cero, sin opciones de otro
  UI.conjuntoCargando = true; render();
  const opciones = {};
  for (const [k, v] of Object.entries(UI.conjOpts || {})) if (v) opciones[k] = v;
  try {
    UI.conjunto = await api('POST', '/cubicaje-conjunto', {pedidos: ids, ...opciones});
    UI.verConjunto = true;
    ids.forEach(id => { delete UI.cubicaje[id]; UI.autoCub[id] = true; });
    await Store.refresh();
  } catch(e){ Avisos.agregar('error', 'No se pudieron cubicar juntos', e.message); }
  UI.conjuntoCargando = false; render();
}
async function abrirConjuntoDe(cid){
  try { UI.conjunto = await api('GET', '/cubicaje-conjunto/' + encodeURIComponent(cid)); UI.verConjunto = true; render(); }
  catch(e){ toast(e.message); }
}
const entregasDelConjunto = cid => Store.list('entregas').filter(e => !e.anulada && (e.camion_ref || '').startsWith(cid + '-'));
function vistaConjunto(){
  const d = UI.conjunto, cid = d.conjunto.id, peds = d.conjunto.pedidos;
  const cliDe = d.conjunto.clientes || {}, distintos = d.conjunto.distintos || [];
  const ents = entregasDelConjunto(cid);
  // Categoría de grupo de cada pedido: los de distinta categoría comparten camión pero van en entregas y grupos separados
  const catDe = n => ((d.categorias || {})[n]) || 'A';
  const cats = [...new Set(peds.map(catDe))].sort(), varias = cats.length > 1;
  const camiones = d.camiones.map(c => {
    const filas = d.filas.filter(f => f.camion === c.numero);
    const porPed = {}; filas.forEach(f => { porPed[f.pedido] = (porPed[f.pedido] || 0) + f.unidades; });
    const dePed = ents.filter(e => e.camion_ref === `${cid}-${c.numero}`);
    const faltan = Object.keys(porPed).filter(n => !dePed.some(e => e.pedido === n));
    // un grupo de SAP por categoría presente en este camión
    const gruposCat = cats.map(k => {
      const delCat = Object.keys(porPed).filter(n => catDe(n) === k);
      if (!delCat.length) return null;
      const es = dePed.filter(e => delCat.includes(e.pedido));
      const num = es.length && es.every(e => e.grupo) ? [...new Set(es.map(e => e.grupo))].join(', ') : '';
      return {k, es, grupo: num, listo: es.length > 0 && delCat.every(n => es.some(e => e.pedido === n))};
    }).filter(Boolean);
    const ocup = filas.length ? filas[filas.length - 1].ocup_acum : 0;
    return {c, filas, porPed, dePed, faltan, gruposCat, ocup};
  });
  const faltanEnt = camiones.reduce((a, x) => a + x.faltan.length, 0), totalEnt = camiones.reduce((a, x) => a + Object.keys(x.porPed).length, 0);
  const todosGrupos = camiones.flatMap(x => x.gruposCat);
  const porCrear = todosGrupos.filter(x => x.listo && !x.grupo);
  const modos = ['MDA', 'MDA PREDISTRIBUIDO', 'SDA STOCK', 'SDA PREDISTRIBUIDO'];
  const o = UI.conjOpts = UI.conjOpts || {modo: d.modo, caja_master: d.caja_master || '', piso_pallet: d.piso_pallet || '', cliente: d.conjunto.reglas_de || ''};
  const sel3 = (attr, opciones, valor) => `<select ${attr}>${opciones.map(x => `<option value="${esc(x.v)}" ${x.v === valor ? 'selected' : ''}>${esc(x.t)}</option>`).join('')}</select>`;
  const paso = (n, txt, hecho) => `<span class="cj-paso ${hecho ? 'ok' : ''}"><i>${hecho ? ICON.check : n}</i>${txt}</span>`;
  return `<div class="label" data-k="conjunto">
    <div class="label-top"><div style="min-width:0;flex:1">
      <h2 class="lab-num"><span class="lab-pre">Cubicaje conjunto</span> ${peds.length} pedidos</h2>
      <p class="small muted" style="margin:4px 0 0">${esc(distintos.length > 1 ? distintos.join(' + ') : d.cliente || '')} · ${esc(d.modo)} · ${d.camiones.length} camión(es) · ${fmt(d.unidades)} un.</p></div>
      <div class="label-act"><button class="btn sm" data-act="salirConjunto">Volver a los pedidos</button></div></div>
    <div class="cells">${peds.map(n => `<div class="cell"><span class="cap">Pedido</span><button class="enlace" data-sel="${esc(safeId(n))}" data-salir-conj style="font-size:var(--t-md);margin:0">${esc(n)}</button>
      <span class="small muted num">${distintos.length > 1 && cliDe[n] ? esc(cliDe[n]) + ' · ' : ''}${fmt((d.por_pedido[n] || {}).unidades || 0)} un.</span>
      <label class="cat-grupo" title="${ents.length ? 'Ya hay entregas creadas: la categoría ya no se puede cambiar' : 'Pedidos de distinta categoría viajan en el mismo camión pero van en entregas y grupos de SAP separados'}">Grupo de SAP
        <select data-conjcat="${esc(n)}" ${ents.length ? 'disabled' : ''} aria-label="Categoría de grupo del pedido ${esc(n)}">${[...'ABCDEFGH'].map(k => `<option value="${k}" ${catDe(n) === k ? 'selected' : ''}>Categoría ${k}</option>`).join('')}</select></label></div>`).join('')}</div>
    <div class="grp-modo" role="radiogroup" aria-label="Cómo van los grupos de SAP">
      <span class="cap">Grupos de SAP</span>
      <label class="opcion ${!varias ? 'on' : ''}"><input type="radio" name="grpmodo" value="camion" data-conjgrp ${!varias ? 'checked' : ''} ${ents.length ? 'disabled' : ''}>
        <span><b>Un grupo por camión</b><small>Pedidos del mismo tipo: cada pedido con su entrega, todos en el mismo grupo.</small></span></label>
      <label class="opcion ${cats.length === peds.length ? 'on' : ''}"><input type="radio" name="grpmodo" value="pedido" data-conjgrp ${cats.length === peds.length ? 'checked' : ''} ${ents.length || peds.length > 8 ? 'disabled' : ''}>
        <span><b>Un grupo por pedido</b><small>Distinta categoría: comparten camión y cita, pero cada pedido va en su propio grupo.</small></span></label>
      ${varias && cats.length !== peds.length ? `<span class="small muted">Personalizado: ${cats.length} grupos por camión (ajústalos en «Grupo de SAP» de cada pedido).</span>` : ''}
      ${ents.length ? `<span class="small muted">Ya hay entregas creadas: la forma de agrupar ya no se puede cambiar.</span>` : ''}</div>
    <div class="label-flujo"><div class="cj-pasos" role="list" aria-label="Pasos del cubicaje conjunto">
      ${paso(1, 'Cubicar juntos', true)}${paso(2, `Entregas ${totalEnt - faltanEnt} de ${totalEnt}`, totalEnt > 0 && !faltanEnt)}${paso(3, `Grupos ${todosGrupos.filter(x => x.grupo).length} de ${todosGrupos.length}`, todosGrupos.every(x => x.grupo))}</div></div>
    <p class="cj-sig"><b>Siguiente:</b> ${faltanEnt ? `crea las entregas en SAP: una por camión y por pedido (${faltanEnt === totalEnt ? totalEnt : faltanEnt} en total). Con «Ensayo en SAP» revisas sin guardar nada.`
      : porCrear.length ? `crea ${porCrear.length === 1 ? 'el grupo' : 'los ' + porCrear.length + ' grupos'} de SAP (VL06)${varias ? ': uno por camión y categoría' : ''}.`
      : 'todo está creado. Confirma la cita de cada camión desde la pestaña Grupos de los pedidos (fecha, hora y referencia) y se lleva sola a SAP.'}</p>
    <div class="label-foot">
      ${faltanEnt ? `<button class="btn quiet sm" data-act="entregasConjunto" data-ensayo="1" title="Recorre VL01N sin guardar">Ensayo en SAP</button>
        <button class="btn primary sm" data-act="entregasConjunto">Crear ${faltanEnt === totalEnt ? '' : 'las que faltan: '}${faltanEnt} entrega(s) en SAP</button>` : ''}
      ${d.visor ? `<button class="btn sm" data-act="pdfConjunto" title="PDF para operaciones, un archivo por camión">${ICON.descargar} Descargar PDF</button>` : ''}
      ${!faltanEnt && porCrear.length ? `<button class="btn primary sm" data-act="gruposConjunto">Crear ${porCrear.length} grupo(s) en SAP</button>` : ''}
      <span class="spacer"></span><span class="small muted">Una entrega por camión y pedido; un grupo por camión${varias ? ' y categoría' : ''}.</span></div>
    ${estadoJob()}
  </div>
  ${(d.avisos || []).map(a => `<p class="small" style="margin:10px 0 0"><span class="tag warn">Aviso</span> ${esc(a)}</p>`).join('')}
  <div class="panel" style="margin-top:16px"><div class="panel-h"><h3>Camiones</h3><span class="spacer"></span><span class="small muted">Cada camión puede llevar carga de varios pedidos</span></div>
    <div class="scroll"><table class="tbl"><thead><tr><th>Camión</th><th>Vehículo</th><th>Pedidos que lleva</th><th class="n">Unidades</th><th class="n">Ocupación</th><th class="n">Kilos</th><th>Entregas</th><th>${varias ? 'Grupos' : 'Grupo'}</th></tr></thead><tbody>
    ${camiones.map(x => `<tr><td><b>${x.c.numero}</b></td><td>${esc(x.c.tipo)}</td>
      <td>${Object.entries(x.porPed).map(([n, u]) => `<span class="tag ${Object.keys(x.porPed).length > 1 ? 'info' : ''}">${esc(n)} · ${fmt(u)}</span>`).join(' ')}</td>
      <td class="n">${fmt(x.filas.reduce((a, f) => a + f.unidades, 0))}</td><td class="n">${pctCub(x.ocup)}</td><td class="n">${kgTxt(((d.carga_por_camion || []).find(y => y.camion === x.c.numero) || {}).kilos) || '—'}</td>
      <td>${x.faltan.length ? `<span class="tag warn">Faltan ${x.faltan.length}</span>` : x.dePed.length ? `<span class="tag ok">${x.dePed.map(e => esc(e.entrega)).join(' · ')}</span>` : ''}</td>
      <td>${x.gruposCat.map(gc => `<div style="white-space:nowrap">${varias ? `<span class="small muted">${gc.k} </span>` : ''}${gc.grupo ? `<span class="tag ok code">${esc(gc.grupo)}</span>` : gc.listo ? '<span class="tag warn">Por crear</span>' : '—'}</div>`).join('')}</td></tr>`).join('')}
    </tbody></table></div></div>
  ${d.visor ? `<div class="visor-caja" style="margin-top:16px;min-height:480px"><iframe data-k="visor-conj" title="Visor 3D del cubicaje conjunto" src="${esc(d.visor)}"></iframe></div>` : ''}
  <div class="row" style="gap:12px;align-items:flex-end;margin-top:16px">
    ${distintos.length > 1 ? `<label class="f" title="Los pedidos son de clientes distintos: el pallet, la caja master y el híbrido se toman de este">Reglas de${sel3('data-conjcli', distintos.map(x => ({v: x, t: x})), o.cliente || d.conjunto.reglas_de)}</label>` : ''}
    <label class="f">Modo${sel3('data-conjmodo', modos.map(m => ({v: m, t: m})), o.modo)}</label>
    <label class="f">Caja master${sel3('data-conjcm', [{v: '', t: ''}, {v: 'CON CAJA MASTER', t: 'CON CAJA MASTER'}, {v: 'SIN CAJA MASTER', t: 'SIN CAJA MASTER'}], o.caja_master)}</label>
    <label class="f">Piso / pallet${sel3('data-conjpiso', [{v: '', t: 'Default del modo'}, {v: 'PISO', t: 'PISO'}, {v: 'PALLET', t: 'PALLET'}], o.piso_pallet)}</label>
    ${/SDA/.test(o.modo) || o.piso_pallet === 'PALLET' ? marcaMix(o.mix ?? d.mezclar_pallets, `data-act="conjMix" ${ents.length ? 'disabled' : ''}`) : ''}
    <button class="btn" data-act="cubicarJuntos" ${ents.length ? 'disabled title="Ya hay entregas creadas: volver a cubicar cambiaría los camiones"' : ''}>Volver a cubicar juntos</button></div>`;
}
async function entregasConjunto(ensayo){
  const d = UI.conjunto, cid = d.conjunto.id;
  const ents = entregasDelConjunto(cid);
  for (const n of d.conjunto.pedidos){
    const camiones = [...new Set(d.filas.filter(f => f.pedido === n).map(f => f.camion))]
      .filter(cam => ensayo || !ents.some(e => e.pedido === n && e.camion_ref === `${cid}-${cam}`));
    if (!camiones.length) continue;
    try { UI.job = await api('POST', '/sap/crear_entregas', {pedido: n, camiones, ensayo: !!ensayo}); render(); }
    catch(e){ return Avisos.agregar('error', `No se pudo empezar con el pedido ${n}`, e.message); }
    await seguirJob();
    if (!UI.job || UI.job.estado !== 'ok'){
      return Avisos.agregar('error', `Se detuvo en el pedido ${n}`, (UI.job && UI.job.error) || '', ['Las entregas ya creadas quedan guardadas: puedes seguir con las que faltan.']);
    }
    if (!ensayo) await Store.refresh();
  }
  Avisos.agregar('ok', ensayo ? 'Ensayo de las entregas terminado' : 'Entregas creadas en SAP',
    ensayo ? 'Se recorrió VL01N sin guardar. Revisa la pantalla de SAP.' : `${d.conjunto.pedidos.length} pedidos. Ahora crea los grupos: uno por camión.`);
  render();
}
async function cambiarCategoria(pedido, cat){
  const d = UI.conjunto; if (!d) return;
  try {
    const r = await api('PUT', `/cubicaje-conjunto/${encodeURIComponent(d.conjunto.id)}/categorias`, {categorias: typeof pedido === 'object' ? pedido : {[pedido]: cat}});
    d.categorias = r.categorias;
  } catch(e){ Avisos.agregar('error', 'No se pudo cambiar la categoría', e.message); }
  render();
}
async function gruposConjunto(){
  const d = UI.conjunto, cid = d.conjunto.id;
  const camiones = [...new Set(entregasDelConjunto(cid).map(e => e.camion_ref))].sort();
  for (const ref of camiones){
    const delCamion = entregasDelConjunto(cid).filter(e => e.camion_ref === ref);
    // los pedidos de distinta categoría van en el mismo camión pero en grupos distintos
    for (const cat of [...new Set(delCamion.map(e => e.categoria || 'A'))].sort()){
      const es = delCamion.filter(e => (e.categoria || 'A') === cat);
      if (es.every(e => e.grupo)) continue;
      const clis = [...new Set(es.map(e => (d.conjunto.clientes || {})[e.pedido]).filter(Boolean))];
      await crearGrupoSap(es.map(e => e.entrega), false, ref.split('-').pop(), clis.length > 1 ? clis.join('+') : (clis[0] || d.cliente));
      if (!UI.job || UI.job.estado !== 'ok') return;          // ante el primer problema se detiene (el aviso ya salió)
    }
  }
}
document.addEventListener('change', ev => {
  const el = ev.target; if (!el.matches) return;
  if (el.matches('[data-jsel]')){ el.checked ? UI.juntarSel.add(el.dataset.jsel) : UI.juntarSel.delete(el.dataset.jsel); render(); }
  else if (el.matches('[data-conjcat]')) cambiarCategoria(el.dataset.conjcat, el.value);
  else if (el.matches('[data-conjgrp]')){                       // un grupo por camión (todos A) o uno por pedido (A, B, C…)
    const peds = UI.conjunto.conjunto.pedidos;
    cambiarCategoria(Object.fromEntries(peds.map((n, i) => [n, el.value === 'pedido' ? 'ABCDEFGH'[i] : 'A'])));
  }
  else if (el.matches('[data-conjmodo]')){ (UI.conjOpts = UI.conjOpts || {}).modo = el.value; }
  else if (el.matches('[data-conjcli]')){ (UI.conjOpts = UI.conjOpts || {}).cliente = el.value; }
  else if (el.matches('[data-conjcm]')){ (UI.conjOpts = UI.conjOpts || {}).caja_master = el.value; }
  else if (el.matches('[data-conjpiso]')){ (UI.conjOpts = UI.conjOpts || {}).piso_pallet = el.value; }
});

const TABS_PEDIDO = [['analisis', 'Análisis'], ['cubicaje', 'Cubicador'], ['entregas', 'Entregas'], ['grupos', 'Grupos'], ['pendientes', 'Pendientes']];

/* Cambiar de pestaña: el contenido entra desde el lado hacia el que se avanza y la barra se desliza hasta la nueva */
function cambiarSub(nueva){
  const orden = TABS_PEDIDO.map(t => t[0]), dir = Math.sign(orden.indexOf(nueva) - orden.indexOf(UI.sub));
  if (nueva === UI.sub) return;
  UI.sub = nueva;
  document.documentElement.classList.add('anim-tabs');          // solo en clics de pestaña: elegir otro pedido no anima la barra
  clearTimeout(cambiarSub._t); cambiarSub._t = setTimeout(() => document.documentElement.classList.remove('anim-tabs'), 300);
  render();
  const tb = document.querySelector('.tab-body'); if (tb) tb.scrollTop = 0;       // cada pestaña parte desde arriba
  entrar(tb, 10 * dir, dir ? 0 : 4);
}
function flujoHTML(f){
  return `<div class="ruta flujo" role="group" aria-label="Flujo del pedido">${f.pasos.map((s, i) =>
    `<button class="paso ${s.hecho ? 'done' : ''} ${s.sig ? 'next' : ''} ${s.omit ? 'fixed' : ''}" data-flujo="${s.k}" aria-current="${!!s.sig}"
      title="${esc(s.t + (s.hecho ? ' · hecho' : s.sig ? ' · siguiente' : s.omit ? ' · no aplica' : ''))}"><span class="k">${s.hecho ? ICON.check : i + 1}</span>
      <span class="txt"><span class="t">${esc(s.t)}</span>${s.det ? `<span class="d">${esc(s.det)}</span>` : ''}</span></button>`).join('')}</div>`;
}
/* El botón de un paso (o "siguiente") lleva a donde se hace */
function avanzarFlujo(k){
  const p = UI.sel && Store.get('pedidos', UI.sel); if (!p) return;
  const f = flujoDe(p), paso = f.pasos.find(x => x.k === k);
  if (k === 'analisis' && !(paso && paso.hecho)){ abrirLecturaSap('analizar'); return; }
  if (k === 'cubicaje' && !f.cb) UI.autoCub[p.pedido] = false;      // al entrar se cubica solo, una vez
  cambiarSub(f.tab[k]);
}

function detallePedido(p){
  const {filas, tot} = resumen(p); const ents = entregasDe(p.pedido);
  const activas = ents.filter(e => !e.anulada);
  const gs = gruposDe(p.pedido);
  let cuerpo = '';
  if (!TABS_PEDIDO.some(t => t[0] === UI.sub)) UI.sub = 'analisis';
  const flujo = flujoDe(p);
  if (UI.sub === 'analisis'){
    cuerpo = vistaAnalisis(p);
  } else if (UI.sub === 'cubicaje'){
    cuerpo = vistaCubicaje(p);
  } else if (UI.sub === 'grupos'){
    cuerpo = gs.length ? gs.map(grupoHTML).join('') :
      `<div class="empty"><h3>Todavía no hay grupos</h3><p>Cada entrega se agrupa por camión. Primero se crean las entregas desde el cubicaje.</p></div>`;
  } else if (UI.sub === 'entregas'){
    if (UI.cubicaje[p.pedido] === undefined) setTimeout(() => cargarCubicaje(p.pedido), 0);    // para saber qué camión es cada entrega
    for (const sm of new Set(ents.filter(e => !e.anulada).map(e => e.suministro || 1)))        // y el de los suministros anteriores
      if (sm !== flujo.suministro && UI.cubicaje[`${p.pedido}#s${sm}`] === undefined) setTimeout(() => cargarCubicajeSuministro(p.pedido, sm, `${p.pedido}#s${sm}`), 0);
    cuerpo = ents.length ? listaEntregas(p, ents, flujo.suministro) :
      `<div class="empty"><h3>Este pedido no tiene entregas</h3><p>Crea la primera con las cantidades que suministraste en VL01N.</p><button class="btn primary" data-act="nuevaEntrega">Nueva entrega</button></div>`;
  } else if (UI.sub === 'pendientes'){
    const pen = filas.filter(r => r.pendiente > 0);
    const sms = resumen(p).sums.map(x => x.n);
    cuerpo = pen.length ? `<div class="scroll tabla-larga"><table class="tbl compacta"><thead><tr><th>SKU</th><th>Descripción</th><th class="n">Pedido</th><th class="n">En entregas</th>${sms.length > 1 ? sms.map(n => `<th class="n sum-col">Suministro ${n}</th>`).join('') : ''}<th class="n">Por suministrar</th></tr></thead><tbody>
      ${pen.map(r => `<tr><td class="code">${esc(r.sku)}</td><td class="desc">${esc(r.desc)}</td><td class="n">${fmt(r.pedida)}</td><td class="n">${fmt(r.enEntrega + r.externa)}</td>${sms.length > 1 ? sms.map(n => `<td class="n sum-col">${fmt((r.sum || {})[n] || 0)}</td>`).join('') : ''}<td class="n"><b>${fmt(r.pendiente)}</b></td></tr>`).join('')}
      </tbody></table></div><div class="row" style="margin-top:14px"><button class="btn primary" data-act="nuevaEntrega">Crear entrega con estos pendientes</button></div>`
      : `<div class="empty"><h3>Nada por suministrar</h3><p>Todas las unidades del pedido ya están en alguna entrega.</p></div>`;
  }
  const cuenta = {entregas: activas.length, grupos: gs.length, pendientes: tot.pendiente ? fmt(tot.pendiente) + ' un.' : ''};
  const enCurso = UI.job && UI.job.estado === 'en_curso';
  // Cada cifra lleva el color de su tramo en la barra: así no hace falta una leyenda aparte
  const celda = (cap, val, extra = '', color = '') => `<div class="cell ${extra}"><span class="cap">${color ? `<i class="sw ${color}" aria-hidden="true"></i>` : ''}${cap}</span><span class="val">${val}</span></div>`;
  const sub = [p.cliente || 'Sin cliente', `OC ${p.oc || '—'}`, p.canal, p.fechaOC ? `recibido ${fmtFecha(p.fechaOC)}` : ''].filter(Boolean);
  const archivos = archivosDe(p.pedido, '');
  return `<div class="label" data-k="label-${esc(safeId(p.pedido))}">
    <div class="label-top">
      <div style="min-width:0;flex:1">
        <h2 class="lab-num"><span class="lab-pre">Pedido</span> ${esc(p.pedido)}</h2>
        <p class="lab-sub">${sub.map((x, i) => i === 1 ? `<span class="code">${esc(x)}</span>` : esc(x)).join('<span aria-hidden="true"> · </span>')}</p></div>
      <div class="label-act">
        ${flujo.sig ? `<button class="btn primary sm" data-flujo="${flujo.sig.k}" title="Siguiente paso del pedido">${esc(FLUJO_ACCION[flujo.sig.k])}</button>` : ''}
        <details class="menu-acc"><summary class="btn sm" aria-label="Más acciones del pedido">Acciones ${ICON.chevron}</summary>
          <div class="menu-acc-lista" role="menu">
            <button role="menuitem" data-act="abrirAnalisis" ${enCurso ? 'disabled' : ''} title="Vuelve a leer el pedido en SAP y actualiza cantidades, saldo y stock">${flujo.an ? 'Volver a analizar en SAP' : 'Analizar en SAP'}</button>
            <button role="menuitem" data-act="nuevaEntrega">Nueva entrega</button>
            <button role="menuitem" data-act="editarPedido">Editar pedido</button>
            <a role="menuitem" data-exp-kam href="/api/analisis/${encodeURIComponent(p.pedido)}/excel" download title="Excel para el KAM: lo pedido, lo que está en entrega, lo pendiente, la alerta, el saldo SOP, el stock CD30 y la próxima liberación">Exportar estatus para el KAM (Excel)</a>
            <a role="menuitem" data-exp-kam href="/api/analisis/${encodeURIComponent(p.pedido)}/excel?interno=true" download title="Libro completo para el equipo: estado, suministros, otros stocks, control de calidad y detalle del análisis. No es para enviar al KAM">Exportar detalle interno (Excel)</a>
            <label role="menuitem" class="menu-subir">Subir PDF o imagen<input type="file" accept=".pdf,.png,.jpg,.html" data-subir data-pedido="${esc(p.pedido)}" data-grupo="" style="display:none"></label>
          </div></details></div>
      <div class="label-code">${codigoBarrasSVG(p.pedido, {etiqueta: `Código de barras del pedido ${p.pedido}`})}</div>
    </div>
    <div class="cells compacta">
      ${celda('Solicitado', fmt(tot.pedida))}${celda('Entregado', fmt(tot.entregado), '', 's-ent')}${celda('Agendado', fmt(tot.agendado), '', 's-age')}
      ${celda('Sin cita', fmt(tot.sinCita), '', 's-sin')}${celda('Pendiente', fmt(tot.pendiente), '', 's-pen')}
      ${tot.externa ? celda('Otras entregas SAP', fmt(tot.externa)) : ''}${tot.exceso ? celda('Exceso en entregas', fmt(tot.exceso), 'alert') : ''}
    </div>
    <div class="label-bar">${barHTML(tot)}</div>
    ${suministrosHTML(p, tot, flujo)}
    ${p.obs ? `<p class="label-obs small">${esc(p.obs)}</p>` : ''}
    <div class="label-flujo">${flujoHTML(flujo)}</div>
    ${estadoJob()}
    ${archivos.length || UI.verArchivo ? `<div class="label-files">${listaArchivos(p.pedido, '')}</div>` : ''}
  </div>
  <div class="tabs" role="tablist" aria-label="Secciones del pedido">${TABS_PEDIDO.map(([k, t]) =>
    `<button role="tab" data-sub="${k}" aria-selected="${UI.sub === k}">${t}${cuenta[k] !== undefined && cuenta[k] !== '' ? `<span class="tcount">${cuenta[k]}</span>` : ''}</button>`).join('')}<i class="tab-ind" aria-hidden="true"${UI.tabInd ? ` style="transform:${UI.tabInd}"` : ''}></i></div>
  <div class="tab-body">${cuerpo}</div>`;
}

/* ---- Pestaña Entregas: cada entrega con lo que lleva, y su camión a un clic ---- */
UI.plegadas = new Set();         // entregas con los productos ocultos (por defecto se ven todos)
UI.entCub = null;                // entrega cuyo cubicaje está abierto (solo una a la vez: cada visor 3D usa WebGL)
UI.entLog = new Set();
/* Qué camión del cubicaje es esta entrega: la crearon desde ese camión, así que lleva exactamente sus productos y
   cantidades. Las entregas armadas a mano no coinciden con ninguno y quedan sin camión. */
/* El cubicaje de cada suministro: el actual vive en UI.cubicaje[pedido]; los anteriores, en UI.cubicaje["pedido#s1"] */
function claveCub(p, e){
  const sm = (e && e.suministro) || 1;
  return sm === flujoDe(p).suministro ? p.pedido : `${p.pedido}#s${sm}`;
}
async function cargarCubicajeSuministro(p, sm, clave){
  UI.cubicaje[clave] = {cargando: true};
  try { UI.cubicaje[clave] = await api('GET', `/cubicaje/${encodeURIComponent(p)}?suministro=${sm}`); }
  catch(e){ UI.cubicaje[clave] = {error: e.message}; }
  render();
}
function camionDeEntrega(p, e){
  const cb = UI.cubicaje[claveCub(p, e)];
  if (!cb || !cb.camiones || !cb.filas) return null;
  const clave = lineas => Object.entries(lineas).filter(([, q]) => q > 0).map(([s, q]) => `${s}:${q}`).sort().join('|');
  const suyo = {}; (e.lineas || []).forEach(l => { suyo[l.sku] = (suyo[l.sku] || 0) + (+l.qty || 0); });
  const buscada = clave(suyo);
  const idx = cb.camiones.findIndex(c => {
    const porSku = {};
    cb.filas.filter(f => f.camion === c.numero && (!f.pedido || String(f.pedido) === String(p.pedido)))
      .forEach(f => { porSku[f.sku] = (porSku[f.sku] || 0) + (+f.unidades || 0); });
    return clave(porSku) === buscada;
  });
  if (idx >= 0) return idx;
  const ref = /-(\d+)$/.exec(e.camion_ref || '');                 // camión compartido: la referencia trae su número
  const porRef = ref ? cb.camiones.findIndex(c => c.numero === +ref[1]) : -1;
  return porRef >= 0 ? porRef : null;
}
function cubicajeDeEntrega(p, e, idx){
  const clave = claveCub(p, e), cb = UI.cubicaje[clave], c = cb.camiones[idx];
  const filas = cb.filas.filter(f => f.camion === c.numero);
  const o = filas.length ? filas[filas.length - 1].ocup_acum : 0, tono = o > 0.92 ? 'err' : o > 0.7 ? 'warn' : 'ok';
  return `<div class="ent-cub">
    <div class="ent-cub-top"><b>${esc(c.tipo)} · camión n.º ${c.numero}</b>
      <span class="barra"><span class="${tono}" style="width:${Math.min(100, 100 * o).toFixed(1)}%"></span></span>
      <span class="num">${pctCub(o)} ocupado · ${m3(c.vol_m3)} m³${kgTxt(((cb.carga_por_camion || []).find(x => x.camion === c.numero) || {}).kilos) ? ` · ${kgTxt(cb.carga_por_camion.find(x => x.camion === c.numero).kilos)}` : ''}</span>
      <button class="btn quiet sm" data-act="irCubicaje" data-cam="${idx}">Abrir en Cubicador</button></div>
    ${cb.visor ? visorPedido(p, cb, 420, clave) : '<p class="small muted">Este cubicaje no tiene visor 3D.</p>'}
  </div>`;
}
/* Cuántas veces se suministró este pedido: lo ya suministrado, lo que va en curso y lo que falta */
function suministrosHTML(p, tot, flujo){
  const sums = resumen(p).sums;
  if (sums.length < 2) return '';
  return `<div class="sum-tira" role="group" aria-label="Suministros del pedido">${sums.map(s =>
    `<button class="sum-chip ${s.n === flujo.suministro ? 'actual' : ''}" data-act="verSuministro" data-sm="${s.n}" title="Ver las entregas del suministro ${s.n}">
      <b>Suministro ${s.n}</b><span class="num">${fmt(s.unidades)} un.</span><span class="small">${s.entregas} entrega(s)${s.n === flujo.suministro ? ' · en curso' : s.entregadas >= s.unidades ? ' · entregado' : ''}</span></button>`).join('')}
    <span class="sum-chip falta ${tot.pendiente ? '' : 'ok'}"><b>Por suministrar</b><span class="num">${fmt(tot.pendiente)} un.</span></span></div>`;
}
/* Con un solo suministro la lista es plana; con más, cada tanda lleva su encabezado: lo ya suministrado queda separado de lo nuevo */
UI.entIniciado = {};
function listaEntregas(p, ents, actual){
  // con muchas entregas se parte viendo el resumen de cada una; el detalle se abre con un clic (o «Ver el detalle de todas»)
  if (!UI.entIniciado[p.pedido]){
    UI.entIniciado[p.pedido] = true;
    if (ents.filter(e => !e.anulada).length > 4) ents.forEach(e => UI.plegadas.add(safeId(e.entrega)));
  }
  return barraEntregas(ents) + listaEntregasPorTanda(p, ents, actual);
}
function listaEntregasPorTanda(p, ents, actual){
  const sms = [...new Set(ents.map(e => e.suministro || 1))].sort((a, b) => b - a);
  if (sms.length < 2) return ents.map(entregaHTML).join('');
  return sms.map(sm => {
    const es = ents.filter(e => (e.suministro || 1) === sm), act = es.filter(e => !e.anulada);
    const un = act.reduce((a, e) => a + unidades(e), 0), entregadas = act.length && act.every(e => pasoOk(e, 'entregado'));
    return `<section class="sum" aria-label="Suministro ${sm}"><div class="sum-h"><h3>Suministro ${sm}</h3>
      ${sm === actual ? '<span class="tag info">En curso</span>' : entregadas ? '<span class="tag ok">Entregado</span>' : '<span class="tag">Suministrado</span>'}
      <span class="small muted">${fmt(un)} un. · ${act.length} entrega(s)</span></div>${es.map(entregaHTML).join('')}</section>`;
  }).join('');
}
/* Lo que lleva una entrega según el cubicaje: su camión y los bultos (por entrega y por SKU) */
function cargaDeEntrega(p, e){
  const idx = e.anulada ? null : camionDeEntrega(p, e);
  const cb = UI.cubicaje[claveCub(p, e)];
  if (idx === null || !cb || !cb.camiones) return {idx: null, cb};
  const cam = cb.camiones[idx], carga = (cb.carga_por_camion || []).find(x => x.camion === cam.numero) || null;
  const bultosSku = {};
  if (carga) for (const l of carga.lineas || []) bultosSku[normSku(l.sku)] = (bultosSku[normSku(l.sku)] || 0) + (+l.bultos || 0);
  return {idx, cb, cam, carga, bultosSku};
}
/* La barra de la pestaña: cuántas entregas, cuántas unidades y cómo abrir o cerrar todo el detalle */
function barraEntregas(ents){
  const act = ents.filter(e => !e.anulada);
  const abiertas = act.filter(e => !UI.plegadas.has(safeId(e.entrega))).length;
  return `<div class="ent-barra"><span><b>${act.length}</b> entrega${act.length === 1 ? '' : 's'} · <b>${fmt(act.reduce((a, e) => a + unidades(e), 0))}</b> un.${ents.length > act.length ? ` · ${ents.length - act.length} anulada(s)` : ''}</span>
    <span class="spacer"></span>
    ${act.length > 1 ? `<button class="btn quiet sm" data-act="${abiertas ? 'plegarTodas' : 'expandirTodas'}">${abiertas ? 'Contraer todas' : 'Ver el detalle de todas'}</button>` : ''}</div>`;
}
function entregaHTML(e){
  const id = safeId(e.entrega), plegada = UI.plegadas.has(id);
  const p = Store.get('pedidos', UI.sel) || {pedido: e.pedido};
  const {idx, cb, cam, carga, bultosSku} = cargaDeEntrega(p, e);
  const abierta = UI.entCub === id && idx !== null;
  const lineas = e.lineas || [];
  const sig = e.anulada ? null : STEPS.find(s => !pasoOk(e, s.k));
  const estado = e.anulada ? '<span class="tag void">Anulada</span>' : sig ? `<span class="tag warn">Falta ${esc(sig.t)}</span>` : '<span class="tag ok">Entregada</span>';
  const verCam = e.anulada ? ''
    : idx !== null ? `<button class="btn sm ent-cam" data-act="verCubEntrega" data-ent="${esc(id)}" aria-pressed="${abierta}" title="Ver cómo viaja esta entrega: camión n.º ${cam.numero}">${ICON.truck}<span>Cubicaje</span></button>`
    : `<button class="btn sm ent-cam" disabled title="${(cb || {}).camiones ? 'Esta entrega no salió del cubicaje del pedido, por eso no tiene camión asociado' : 'No hay un cubicaje guardado para esta entrega'}">${ICON.truck}<span>Cubicaje</span></button>`;
  const stat = (n, txt) => `<span class="ent-stat"><b class="num">${fmt(n)}</b> ${txt}</span>`;
  const facturada = pasoOk(e, 'facturada');
  return `<article class="docket ent ${e.anulada ? 'void' : ''}" data-k="e-${esc(id)}">
    <div class="dk-h ent-h">
      <button class="ent-plegar" data-act="plegarEntrega" data-ent="${esc(id)}" aria-expanded="${!plegada}" aria-label="${plegada ? 'Mostrar' : 'Ocultar'} el detalle de la entrega ${esc(e.entrega)}">${ICON.chevronAbajo}</button>
      <div class="ent-id"><span class="cap">Entrega</span><span class="code">${esc(e.entrega)}</span></div>
      <div class="ent-stats">${stat(unidades(e), 'un.')}${carga ? stat(carga.bultos, 'bultos') : ''}${stat(lineas.length, 'SKU')}</div>
      <div class="ent-tags">${cam ? `<span class="tag" title="Camión del cubicaje en que viaja">${ICON.truck} ${esc(cam.tipo)} · n.º ${cam.numero}</span>` : ''}
        ${e.grupo ? `<span class="tag info" title="Grupo de transporte en SAP">Grupo <span class="code">${esc(e.grupo)}</span></span>` : e.anulada ? '' : '<span class="tag">Sin grupo</span>'}
        ${facturada || e.factura ? `<span class="tag ${facturada ? 'ok' : ''}" title="N° de factura">Factura <span class="code">${esc(e.factura || '—')}</span></span>` : ''}
        ${estado}</div>
      <span class="spacer"></span>
      ${verCam}
      <details class="menu-acc"><summary class="btn quiet sm icon" aria-label="Más acciones de la entrega ${esc(e.entrega)}">${ICON.more}</summary>
        <div class="menu-acc-lista" role="menu">
          <button role="menuitem" data-act="editarEntrega" data-ent="${esc(id)}">Editar entrega</button>
          ${!e.anulada && !facturada ? `<button role="menuitem" data-paso="facturada" data-ent="${esc(id)}">Registrar factura</button>` : ''}
          ${(e.log || []).length ? `<button role="menuitem" data-act="logEntrega" data-ent="${esc(id)}">${UI.entLog.has(id) ? 'Ocultar' : 'Ver'} historial</button>` : ''}
          ${e.anulada ? `<button role="menuitem" data-act="reactivar" data-ent="${esc(id)}">Reactivar</button>` :
            `<button role="menuitem" class="peligro" data-act="anular" data-ent="${esc(id)}">Anular entrega</button>
             <button role="menuitem" class="peligro" data-act="borrarEntregaSap" data-ent="${esc(e.entrega)}" title="Borra la entrega en VL06 y la quita de la plataforma">Borrar en SAP</button>`}
        </div></details>
    </div>
    ${plegada ? '' : `<div class="ent-detalle ${lineas.length > 8 ? 'tabla-corta' : ''}"><table class="tbl ent-tbl"><thead><tr><th>SKU</th><th>Descripción</th>${bultosSku ? '<th class="n">Bultos</th>' : ''}<th class="n">Unidades</th></tr></thead><tbody>
      ${lineas.map(l => `<tr><td class="code">${esc(l.sku)}</td><td>${esc(l.desc || descDe(e.pedido, l.sku))}</td>${bultosSku ? `<td class="n">${bultosSku[normSku(l.sku)] !== undefined ? fmt(bultosSku[normSku(l.sku)]) : '—'}</td>` : ''}<td class="n">${fmt(l.qty)}</td></tr>`).join('')}</tbody></table></div>`}
    ${e.obs ? `<p class="dk-obs">${esc(e.obs)}</p>` : ''}
    ${UI.entLog.has(id) && (e.log || []).length ? `<ul class="log">${e.log.map(x => `<li>${new Date(x.at).toLocaleString('es-CL')} — ${esc(x.txt)}</li>`).join('')}</ul>` : ''}
    ${abierta ? cubicajeDeEntrega(p, e, idx) : ''}
  </article>`;
}

/* Notas del grupo: una línea con la última (o «Agregar nota»); se despliega para ver el historial y escribir otra */
UI.notasAbiertas = new Set(); UI.notaBorrador = {};
const fechaCorta = iso => { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString('es-CL', {day: '2-digit', month: '2-digit'}) + ' ' + d.toTimeString().slice(0, 5); };
function notasHTML(g){
  const ns = notasDe(g.key), abierta = UI.notasAbiertas.has(g.key), ult = ns[ns.length - 1];
  const llave = esc(g.key);
  return `<div class="grp-notas ${abierta ? 'abierta' : ''}">
    <button class="grp-notas-t" data-act="notasGrupo" data-grupo="${llave}" aria-expanded="${abierta}" title="Notas del grupo: por qué llegó hasta aquí">
      ${ICON.nota}<span class="n-tit">Notas${ns.length ? ` <b class="num">${ns.length}</b>` : ''}</span>
      ${!abierta ? (ult ? `<span class="n-ult">${esc(ult.texto)}</span><span class="n-ref">${esc(ult.usuario ? ult.usuario + ' · ' : '')}${fechaCorta(ult.at)}</span>` : '<span class="n-ult vacia">Agregar nota</span>') : ''}
      <span class="n-flecha" aria-hidden="true">${ICON.chevronAbajo}</span></button>
    ${abierta ? `<div class="grp-notas-c">
      ${ns.length ? `<ul class="notas-lista">${ns.map(n => `<li><span class="n-ref">${esc(n.usuario ? n.usuario + ' · ' : '')}${fechaCorta(n.at)}</span><span class="n-txt">${esc(n.texto)}</span>
        <button class="btn quiet sm icon" data-act="borrarNota" data-id="${n.id}" title="Borrar nota" aria-label="Borrar nota">${ICON.x}</button></li>`).join('')}</ul>` : ''}
      <div class="nota-nueva"><input type="text" maxlength="300" data-nota="${llave}" value="${esc(UI.notaBorrador[g.key] || '')}" placeholder="Escribe una nota corta y presiona Enter" aria-label="Nueva nota del grupo" autocomplete="off">
        <button class="btn sm" data-act="agregarNota" data-grupo="${llave}">Agregar</button></div></div>` : ''}
  </div>`;
}
function grupoHTML(g){
  const c = g.cita || {};
  const otros = g.pedidos.length > 1;
  const camion = gruposDelCamion(g);
  const estado = g.next ? `<span class="tag warn">Falta ${esc(g.next.t)}</span>` : '<span class="tag ok">Entregado</span>';
  const pedActual = (Store.get('pedidos', UI.sel) || {}).pedido;
  const k = g.next && g.next.k;
  const falta = g.next ? g.entregas.filter(e => !pasoOk(e, k)) : [];
  const llave = esc(g.key), ents = esc(g.entregas.map(e => e.entrega).join(','));
  // lo que sigue, con el botón que lo hace: no hay que adivinar qué tocar
  const siguiente = !g.next ? '<b>Camión completo.</b> Todos los pasos están hechos.'
    : `<b>Siguiente:</b> ${esc(g.next.t)}${falta.length && falta.length < g.entregas.length ? ` <span class="muted">· falta en ${falta.map(e => esc(e.entrega)).join(', ')}</span>` : ''}
      <span class="grp-acc">${k === 'confirmada' ? `<button class="btn primary sm" data-gpaso="${k}" data-grupo="${llave}" data-forzar="1" title="Pide fecha, hora y referencia del grupo y las lleva a SAP">Confirmar cita</button>`
        : k === 'sap' ? `<button class="btn primary sm" data-act="citaGrupo" data-grupo="${llave}" title="Pone la fecha, la hora y la referencia en SAP">Actualizar en SAP</button>
          <button class="btn quiet sm" data-gpaso="${k}" data-grupo="${llave}" data-forzar="1" title="Si ya lo hiciste a mano en SAP">Ya está hecho</button>`
        : POR_ENTREGA.includes(k) ? `<button class="btn primary sm" data-act="irEntrega" data-ent="${esc(safeId((falta[0] || g.entregas[0]).entrega))}">Registrar facturas</button>`
        : `<button class="btn primary sm" data-gpaso="${k}" data-grupo="${llave}" data-forzar="1">Marcar hecho</button>`}</span>`;
  return `<article class="docket grp" data-k="g-${llave}">
    <div class="grp-h">
      <div class="ent-id"><span class="cap">${g.sinGrupo ? 'Camión' : 'Grupo'}</span><span class="code ${g.sinGrupo ? 'sin' : ''}">${g.sinGrupo ? 'Sin grupo' : esc(g.grupo)}</span></div>
      <div class="ent-stats"><span class="ent-stat"><b class="num">${fmt(g.unidades)}</b> un.</span><span class="ent-stat"><b class="num">${g.entregas.length}</b> entrega${g.entregas.length === 1 ? '' : 's'}</span></div>
      <div class="ent-tags">${estado}
        ${g.parcial ? '<span class="tag err" title="Hay pasos marcados en unas entregas del camión y en otras no">Entregas desalineadas</span>' : ''}
        ${otros ? '<span class="tag info">Camión compartido</span>' : ''}
        ${g.camionRef && camion.length > 1 ? `<span class="tag info" title="Los pedidos de distinta categoría viajan en el mismo camión pero van en grupos de SAP separados; comparten la cita">Categoría ${esc(g.categoria || 'A')} · camión de ${camion.length} grupos</span>` : ''}
        ${(() => { const ps = Store.get('pedidos', UI.sel); const sm = [...new Set(g.entregas.map(e => e.suministro || 1))];
          return ps && resumen(ps).sums.length > 1 ? `<span class="tag">Suministro ${sm.join(' y ')}</span>` : ''; })()}</div>
      <span class="spacer"></span>
      <div class="grp-cita ${c.fecha ? '' : 'sin'}">${c.fecha ? `<span class="cap">Cita</span><b class="num">${fmtFecha(c.fecha)}${c.hora ? ' · ' + esc(c.hora) : ''}</b>` : '<span class="cap">Cita</span><span class="muted">Sin fecha</span>'}
        ${c.numero ? `<span class="code small" title="Referencia del grupo">${esc(c.numero)}</span>` : ''}</div>
    </div>
    <div class="grp-ents" aria-label="Entregas de este camión"><span class="cap">Entregas</span>${g.entregas.map(e => `<button class="ent-chip ${pasoOk(e, 'facturada') ? 'fac' : ''}" data-act="irEntrega" data-ent="${esc(safeId(e.entrega))}" title="Ver el detalle de la entrega ${esc(e.entrega)}">
        <span class="code">${esc(e.entrega)}</span><span class="num">${fmt(unidades(e))} un. · ${(e.lineas || []).length} SKU</span>${e.pedido !== pedActual ? `<span class="tag">pedido ${esc(e.pedido)}</span>` : ''}${pasoOk(e, 'facturada') ? `<span class="tag ok">Factura ${esc(e.factura || '')}</span>` : ''}</button>`).join('')}</div>
    ${rutaHTML(g)}
    <p class="grp-sig">${siguiente}</p>
    <p class="grp-meta small muted">${esc([g.vehiculo, g.carga, g.un, g.tipo, g.region].filter(Boolean).join(' · '))}</p>
    ${notasHTML(g)}
    <div class="dk-act">
      <button class="btn sm" data-act="editarGrupo" data-grupo="${llave}">Editar camión</button>
      <button class="btn sm" data-act="reprogGrupo" data-grupo="${llave}" ${g.pasos.confirmada ? '' : 'disabled title="Solo para citas confirmadas"'}>Reprogramar cita</button>
      ${g.sinGrupo
        ? `<span class="spacer"></span><button class="btn quiet sm" data-act="ensayoGrupo" data-cam="${llave}" data-ents="${ents}">Ensayo del grupo</button>
           <button class="btn sm" data-act="crearGrupoSap" data-cam="${llave}" data-ents="${ents}" title="Crea el grupo de transporte en VL06">Crear grupo en SAP</button>`
        : `<button class="btn sm" data-act="citaGrupo" data-grupo="${llave}" title="Pone en SAP la fecha, la hora y la referencia completa de este grupo (VG02); si falta la cita, la pide">Actualizar cita en SAP</button>
           <span class="spacer"></span>
           <button class="btn danger sm" data-act="borrarGrupoSap" data-num="${esc(g.grupo)}" title="Borra el grupo en VG02; las entregas quedan sin grupo">Borrar grupo en SAP</button>`}
    </div>
    ${listaArchivos(g.entregas[0].pedido, g.grupo)}
  </article>`;
}

/* ---- Cubicaje propio (port del cubicador del Excel) ---- */
UI.cubicaje = {}; UI.verVisorCub = true; UI.autoCub = {}; UI.predist = {}; UI.verPredist = false;
UI.cubOpts = {modo:'', caja_master:'', piso_pallet:''};   // lo que eligió el usuario, no se pierde al redibujar
const modoElegido = cb => UI.cubOpts.modo || (cb && cb.modo) || 'MDA';
async function cargarPredist(pedido){
  try { UI.predist[pedido] = await api('GET', `/predistribuido/${encodeURIComponent(pedido)}`); }
  catch(e){ UI.predist[pedido] = {filas:[]}; }
  render();
}
async function guardarPredist(pedido, texto){
  try {
    UI.predist[pedido] = await api('PUT', `/predistribuido/${encodeURIComponent(pedido)}`, {texto});
    const d = UI.predist[pedido];
    toast(`${d.filas.length} líneas · ${d.sucursales.length} sucursales${d.errores.length ? ' · ' + d.errores.length + ' con problema' : ''}`);
  } catch(e){ toast(e.message); }
  render();
}
async function importarPredist(input, pedido){
  const f = input.files[0]; if (!f) return;
  const fd = new FormData(); fd.append('file', f);
  try {
    const r = await fetch(`/api/predistribuido/${encodeURIComponent(pedido)}/importar`, {method:'POST', body:fd,
      headers: cab()});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'No se pudo importar el reparto');
    UI.predist[pedido] = d;
    Avisos.agregar(d.errores.length ? 'info' : 'ok',
      `Reparto del pedido ${pedido}: ${fmt(d.filas.length)} líneas en ${d.sucursales.length} sucursales`,
      `${fmt(d.unidades)} unidades. Vuelve a cubicar para aplicarlo.`, (d.errores || []).slice(0, 8));
  } catch(e){ toast(e.message); }
  render();
}
function seccionPredist(p, modo){
  if (!/PREDISTRIBUIDO/.test(modo || '')) return '';
  const d = UI.predist[p.pedido];
  if (!d) { setTimeout(() => cargarPredist(p.pedido), 0); return '<p class="small muted">Cargando reparto…</p>'; }
  return `<div class="panel" style="margin:12px 0"><div class="panel-b stack">
    <div class="row">
      <div><b>Reparto por sucursal</b> <span class="small muted">${d.filas.length ? `${fmt(d.filas.length)} líneas · ${d.sucursales.length} sucursales · ${fmt(d.unidades)} unidades` : 'sin datos'}</span></div>
      <div class="row" style="gap:6px">
        <a class="btn quiet small" href="/api/predistribuido/plantilla" title="Excel para armar el reparto: sucursal, SKU y unidades">Plantilla</a>
        <label class="btn quiet small" title="Carga el reparto desde la plantilla. Reemplaza el que hay.">Importar Excel
          <input type="file" accept=".xlsx,.xlsm,.xls,.csv" data-predistimport="${esc(p.pedido)}" style="display:none"></label>
        <button class="btn quiet small" data-act="verPredist">${UI.verPredist ? 'Ocultar' : (d.filas.length ? 'Editar' : 'Pegar reparto')}</button>
      </div>
    </div>
    ${(d.errores || []).length ? `<p class="small"><span class="tag err">Revisar</span> ${esc(d.errores.slice(0,3).join(' · '))}</p>` : ''}
    ${UI.verPredist ? `<label class="f" style="margin-top:10px">Pega desde el Excel del cliente: sucursal, SKU y unidades (una línea por fila)
      <textarea data-predist placeholder="SUC-01\t900081624\t20">${esc((d.filas || []).map(f => `${f.sucursal}\t${f.sku}\t${f.unidades}`).join('\n'))}</textarea></label>
      <button class="btn primary" data-act="guardarPredist">Guardar reparto</button>` : ''}
  </div></div>`;
}
async function cargarCubicaje(pedido){
  UI.cubicaje[pedido] = {cargando:true}; render();
  try { UI.cubicaje[pedido] = await api('GET', `/cubicaje/${encodeURIComponent(pedido)}`); }
  catch(e){ UI.cubicaje[pedido] = {error:e.message}; }
  render();
}
async function cubicar(pedido, opts){
  const previo = UI.cubicaje[pedido];
  // con un resultado a la vista se conserva (y su visor): solo se marca que se está recalculando
  UI.cubicaje[pedido] = previo && previo.camiones ? {...previo, recalculando:true} : {cargando:true}; render();
  try {
    UI.cubicaje[pedido] = await api('POST', `/cubicaje/${encodeURIComponent(pedido)}`, opts || {});
    if (UI.cubicaje[pedido].visor) UI.verVisorCub = true;      // el visor nuevo queda a la vista
    toast(`Cubicado en ${UI.cubicaje[pedido].camiones.length} camión(es)`);
  } catch(e){ UI.cubicaje[pedido] = {error:e.message}; toast(e.message); }
  render();
  Store.refresh();                  // el indicador de flujo (cubicaje hecho) llega sin esperar la próxima consulta
}
/* El camión se rearma solo cada vez que cambias una cantidad */
/* El camión de un pedido usa el mismo visor de dirección fija que el cubicador:
   se abre una vez y recibe cada cálculo por mensaje (ver visor.js). */
UI.pedCam = {};
function visorPedido(p, cb, alto, clave = p.pedido){
  if (!cb.visor) return '';
  const vivo = cb.visor_json && cb.visor_vivo;
  return `<div class="visor-caja" style="min-height:${alto}px;flex:none;height:${alto}px">
    ${vivo ? `<iframe data-k="visor-ped" data-visor="pedido:${esc(clave)}" src="${esc(cb.visor_vivo)}#solo3d" title="Visor 3D del pedido ${esc(p.pedido)}"></iframe>`
           : `<iframe data-k="visor-ped" src="${esc(cb.visor)}" title="Visor 3D del pedido ${esc(p.pedido)}"></iframe>`}
    ${herramientasVisor()}
    <a class="btn sm abrir" href="${esc(cb.visor)}" target="_blank" rel="noopener" style="position:absolute;right:10px;bottom:10px">${ICON.external} Aparte</a></div>`;
}
/* PDF del cubicaje sin entrar al visor aparte: el visor 3D genera el PDF, así que se le pide desde aquí (aunque esté oculto, se muestra un momento). */
const pausa = ms => new Promise(r => setTimeout(r, ms));
async function pedirPdfAlVisor(buscar, listo){
  for (let i = 0; i < 100; i++){                                  // hasta ~10 s a que el visor cargue sus datos
    const f = buscar();
    if (f && f.contentWindow && listo(f)){ f.contentWindow.postMessage({tipo: 'od-visor-pdf', soloActual: false}, location.origin); return true; }
    await pausa(100);
  }
  toast('El visor 3D no alcanzó a cargar. Intenta de nuevo.');
  return false;
}
async function pdfPedido(pedido){
  const cb = UI.cubicaje[pedido]; if (!cb || !cb.visor) return toast('Este cubicaje no tiene visor 3D.');
  const n = (cb.camiones || []).length;
  toast(n > 1 ? `Se descargarán ${n} PDF, uno por camión. Si el navegador pregunta, permite las descargas múltiples.` : 'Generando el PDF…');
  if (!UI.verVisorCub){ UI.verVisorCub = true; render(); }
  await pedirPdfAlVisor(() => document.querySelector('iframe[data-k="visor-ped"]'),
    f => f.dataset.visor ? Visor.listos.has(f) && !!Visor.enviado.get(f) : f.contentDocument && f.contentDocument.readyState === 'complete');
}
async function pdfConjunto(){
  const n = (UI.conjunto && UI.conjunto.camiones || []).length;
  toast(n > 1 ? `Se descargarán ${n} PDF, uno por camión. Si el navegador pregunta, permite las descargas múltiples.` : 'Generando el PDF…');
  await pedirPdfAlVisor(() => document.querySelector('iframe[data-k="visor-conj"]'), f => f.contentDocument && f.contentDocument.readyState === 'complete');
}
function fichasCamion(p, cb){
  const porCamion = {};
  for (const f of cb.filas) porCamion[f.camion] = f.ocup_acum;
  const sel = UI.pedCam[p.pedido] || 0;
  return `<div class="chips">${cb.camiones.map((c, i) => {
    const o = porCamion[c.numero] || 0, tono = o > 0.92 ? 'err' : o > 0.7 ? 'warn' : 'ok';
    return `<button class="chip-cam" data-ped-cam="${esc(p.pedido)}|${i}" aria-pressed="${i === sel}">
      <span class="l1"><b>${esc(c.tipo)} · n.º ${c.numero}</b></span>
      <span class="barra"><span class="${tono}" style="width:${Math.min(100, 100 * o).toFixed(1)}%"></span></span>
      <span class="l2"><span class="num">${pctCub(o)}</span><span class="num">${m3(c.vol_m3)} m³</span></span></button>`; }).join('')}</div>`;
}
document.addEventListener('click', ev => {
  const b = ev.target.closest('[data-ped-cam]'); if (!b) return;
  const [ped, i] = b.dataset.pedCam.split('|');
  UI.pedCam[ped] = +i;
  Visor.camion(+i, document.querySelector(`iframe[data-visor="pedido:${CSS.escape(ped)}"]`));
  render();
});

function vistaCubicaje(p){
  const cb = UI.cubicaje[p.pedido];
  if (!cb) { setTimeout(() => cargarCubicaje(p.pedido), 0); return '<div class="stack"><span class="skel" style="width:30%"></span><span class="skel"></span></div>'; }
  if (cb.cargando) return '<p class="small muted">Cubicando… (puede tardar unos segundos)</p>';
  const modos = ['MDA', 'MDA PREDISTRIBUIDO', 'SDA STOCK', 'SDA PREDISTRIBUIDO'];
  const sel3 = (attr, opciones, valor) => `<select ${attr}>${opciones.map(o =>
    `<option value="${esc(o.v)}" ${o.v === valor ? 'selected' : ''}>${esc(o.t)}</option>`).join('')}</select>`;
  const form = `<div class="row" style="gap:12px;align-items:flex-end">
      <label class="f">Modo${sel3('data-cubmodo', modos.map(m => ({v:m, t:m})), modoElegido(cb))}</label>
      <label class="f">Caja master${sel3('data-cubcm', [{v:'', t:''}, {v:'CON CAJA MASTER', t:'CON CAJA MASTER'}, {v:'SIN CAJA MASTER', t:'SIN CAJA MASTER'}], UI.cubOpts.caja_master || cb.caja_master || '')}</label>
      <label class="f">Piso / pallet${sel3('data-cubh2', [{v:'', t:'Default del modo'}, {v:'PISO', t:'PISO'}, {v:'PALLET', t:'PALLET'}], UI.cubOpts.piso_pallet || cb.piso_pallet || '')}</label>
      ${/SDA/.test(modoElegido(cb)) || (UI.cubOpts.piso_pallet || cb.piso_pallet) === 'PALLET' ? marcaMix(UI.cubOpts.mix ?? cb.mezclar_pallets, 'data-act="cubMix"') : ''}
      <button class="btn primary" data-act="cubicar">${cb.error || !cb.camiones ? 'Cubicar' : 'Volver a cubicar'}</button>
    </div>`;
  if (cb.error || !cb.camiones){
    const falta = /analizar el pedido/.test(cb.error || '');
    if (!falta && /todavía no está cubicado/.test(cb.error || '') && flujoDe(p).an && !UI.autoCub[p.pedido]){
      UI.autoCub[p.pedido] = true; setTimeout(() => cubicar(p.pedido, {}), 0);       // la carga sale del análisis: no hay nada que pedir
      return '<div class="stack"><span class="skel" style="width:30%"></span><span class="skel"></span></div>';
    }
    return `<div class="empty"><h3>${cb.error && !/todavía no está cubicado/.test(cb.error) ? 'No se pudo cubicar' : 'Este pedido todavía no está cubicado'}</h3>
      <p>${esc(cb.error && !/todavía no está cubicado/.test(cb.error) ? cb.error : 'El cubicaje usa la carga del análisis, con tus ajustes manuales.')}</p>
      ${falta ? '<button class="btn primary" data-act="abrirAnalisis">Analizar pedido</button>' : form + seccionPredist(p, modoElegido(cb))}</div>`;
  }
  const porCamion = {};
  for (const f of cb.filas) (porCamion[f.camion] = porCamion[f.camion] || []).push(f);
  const camiones = cb.camiones.map(c => {
    const fs = porCamion[c.numero] || [];
    const ocup = fs.length ? fs[fs.length - 1].ocup_acum : 0;
    const m = (cap, v) => `<div class="m"><span class="cap">${cap}</span><span class="v">${v}</span></div>`;
    return `<article class="docket" data-k="cam-${c.numero}">
      <div class="dk-h"><div class="dk-id">Camión ${c.numero} <span class="tag">${esc(c.tipo)}</span>
        <span class="tag ${fs[0] && fs[0].tipo_carga === 'Mono-pedido' ? 'ok' : 'warn'}">${esc(fs[0] ? fs[0].tipo_carga : '')}</span></div>
        <div class="dk-qty">${fmt(fs.reduce((a, f) => a + f.unidades, 0))} <small>un.${(cb.carga_por_camion || []).find(x => x.camion === c.numero) ? ` · ${fmt(cb.carga_por_camion.find(x => x.camion === c.numero).bultos)} bultos` : ''} · ${pctCub(ocup)} ocupado${kgTxt((cb.carga_por_camion.find(x => x.camion === c.numero) || {}).kilos) ? ` · ${kgTxt(cb.carga_por_camion.find(x => x.camion === c.numero).kilos)}` : ''}</small></div></div>
      <div class="meta">${m('Medidas', `${fmt(c.L)} × ${fmt(c.w)} × ${fmt(c.h)} cm`)}${m('Capacidad', `${m3(c.vol_m3, 2)} m³`)}${m('Libre', `${m3(fs.length ? fs[fs.length - 1].libre_m3 : c.vol_m3, 2)} m³`)}</div>
      </article>`;
  }).join('');
  const problemas = [
    ...(cb.no_encontrados || []).map(x => `<span class="tag err">Sin descripción: ${esc(x)}</span>`),
    ...Object.entries(cb.sin_ubicar || {}).map(([k, v]) => `<span class="tag err">No cupo: ${esc(k)} (${fmt(v)})</span>`),
  ].join(' ');
  const banner = cb.conjunto ? `<div class="aviso info"><div class="aviso-cuerpo"><b>Cubicado junto con ${cb.conjunto.pedidos.filter(x => x !== p.pedido).map(esc).join(', ')}.</b>
      <span class="small">Los camiones se comparten: aquí ves solo la parte de este pedido. Las entregas y los grupos se crean desde el cubicaje conjunto.</span></div>
      <button class="btn sm" data-act="verConjunto" data-cid="${esc(cb.conjunto.id)}">Abrir cubicaje conjunto</button></div>` : '';
  return banner + `<div class="row" style="margin-bottom:10px">
      <div class="small muted">Cubicaje ${esc(cb.modo)} del ${fmtFecha(cb.generado)} · pallet del cliente ${cb.pallet.join(' × ')} cm</div>
      <span class="spacer"></span>
      ${cb.visor ? `<button class="btn sm" data-act="ensayoEntregas" title="Recorre VL01N sin guardar, para revisar antes de crear">Ensayo en SAP</button>
        <button class="btn primary sm" data-act="crearEntregas" title="Crea una entrega por camión en VL01N">Crear entregas en SAP</button>
        <a class="btn sm" href="/api/cubicaje/${encodeURIComponent(p.pedido)}/excel">Exportar a Excel</a>
        <button class="btn sm" data-act="pdfPedido" data-ped="${esc(p.pedido)}" title="PDF para operaciones, un archivo por camión (a color, pensado para imprimirse en blanco y negro; con vista desde arriba)">${ICON.descargar} Descargar PDF</button>
        <button class="btn sm" data-act="verVisorCub" aria-pressed="${!!UI.verVisorCub}">${UI.verVisorCub ? 'Ocultar visor 3D' : 'Ver visor 3D aquí'}</button>` : ''}</div>
    ${cb.camiones.length ? fichasCamion(p, cb) : ''}
    ${cb.visor && UI.verVisorCub ? `<div style="margin:10px 0 14px">${visorPedido(p, cb, 640)}</div>` : ''}
    <div class="legend" style="margin:12px 0"><span>Camiones <b class="num">${cb.camiones.length}</b></span><span>Unidades <b class="num">${fmt(cb.unidades)}</b></span>${cb.bultos ? `<span>Bultos <b class="num">${fmt(cb.bultos)}</b></span>` : ''}
      <span>SKU <b class="num">${new Set(cb.filas.map(f => f.sku)).size}</b></span>
      ${(cb.pallets_detalle || []).length ? `<span>Pallets <b class="num">${cb.pallets_detalle.length}</b></span>` : ''}
      ${(cb.filas04 || []).some(f => f.tipo === 'Piso') ? `<span>A piso <b class="num">${fmt(cb.filas04.filter(f => f.tipo === 'Piso').reduce((a, f) => a + f.unidades, 0))}</b></span>` : ''}</div>
    ${alertaFaltantes(cb.faltantes, `/api/cubicaje/${encodeURIComponent(p.pedido)}/faltantes.xlsx`, (cb.unidades || 0) + (cb.faltantes || []).reduce((a, x) => a + x.unidades, 0))}
    ${form}
    ${seccionPredist(p, modoElegido(cb))}
    ${problemas ? `<p class="small" style="margin-top:10px">${problemas}</p>` : ''}
    ${(cb.avisos || []).map(a => `<p class="small"><span class="tag warn">Aviso</span> ${esc(a)}</p>`).join('')}
    ${(cb.kits || []).length ? `<p class="small muted" style="margin:6px 0"><span class="tag info">Kits</span> ${cb.kits.map(k => `<b>${esc(k.sku)}</b> × ${fmt(k.unidades)} (${k.componentes.map(c => esc(c.sku) + (c.por_kit > 1 ? ' ×' + c.por_kit : '')).join(' + ')})`).join(' · ')} — sus cajas viajan juntas.</p>` : ''}
    <div class="camiones-lista tabla-larga" style="margin-top:12px">${camiones}</div>
    ${detalleCarga(cb, UI.pedCam[p.pedido] || 0)}`;
}

function descDe(ped, sku){ const p = Store.get('pedidos', safeId(ped)); const l = p && (p.lineas || []).find(x => normSku(x.sku) === normSku(sku)); return l ? l.desc : ''; }

/* El menú de acciones del pedido se cierra al elegir algo o al tocar fuera */
document.addEventListener('click', ev => {
  document.querySelectorAll('.menu-acc[open]').forEach(d => { if (!d.contains(ev.target) || ev.target.closest('.menu-acc-lista > *')) d.open = false; });
});
