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

  const lista = peds.length ? `<ul class="olist">${peds.map(p => {
      const {tot} = resumen(p); const id = safeId(p.pedido); const nx = proximaAccion(p);
      return `<li data-k="p-${esc(id)}"><button class="orow" data-sel="${esc(id)}" aria-current="${UI.sel === id}">
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
      </div>
      ${lista}
    </section>
    <section aria-label="Detalle del pedido">${UI.sel ? detallePedido(Store.get('pedidos', UI.sel)) : `<div class="panel empty"><h3>Selecciona un pedido</h3><p>Verás su avance por producto y cada entrega con sus pasos.</p></div>`}</section>
  </div>`;
}

const TABS_PEDIDO = [['analisis', 'Análisis'], ['cubicaje', 'Cubicador'], ['entregas', 'Entregas'], ['grupos', 'Grupos'], ['pendientes', 'Pendientes']];

/* Cambiar de pestaña: el contenido entra desde el lado hacia el que se avanza y la barra se desliza hasta la nueva */
function cambiarSub(nueva){
  const orden = TABS_PEDIDO.map(t => t[0]), dir = Math.sign(orden.indexOf(nueva) - orden.indexOf(UI.sub));
  if (nueva === UI.sub) return;
  UI.sub = nueva;
  document.documentElement.classList.add('anim-tabs');          // solo en clics de pestaña: elegir otro pedido no anima la barra
  clearTimeout(cambiarSub._t); cambiarSub._t = setTimeout(() => document.documentElement.classList.remove('anim-tabs'), 300);
  render();
  entrar(document.querySelector('.tab-body'), 10 * dir, dir ? 0 : 4);
}
function flujoHTML(f){
  return `<div class="ruta flujo" role="group" aria-label="Flujo del pedido">${f.pasos.map((s, i) =>
    `<button class="paso ${s.hecho ? 'done' : ''} ${s.sig ? 'next' : ''} ${s.omit ? 'fixed' : ''}" data-flujo="${s.k}" aria-current="${!!s.sig}"
      title="${esc(s.t + (s.hecho ? ' · hecho' : s.sig ? ' · siguiente' : s.omit ? ' · no aplica' : ''))}"><span class="k">${s.hecho ? ICON.check : i + 1}</span>
      <span class="t">${esc(s.t)}</span>${s.det ? `<span class="d">${esc(s.det)}</span>` : ''}</button>`).join('')}</div>`;
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
    cuerpo = ents.length ? ents.map(entregaHTML).join('') :
      `<div class="empty"><h3>Este pedido no tiene entregas</h3><p>Crea la primera con las cantidades que suministraste en VL01N.</p><button class="btn primary" data-act="nuevaEntrega">Nueva entrega</button></div>`;
  } else if (UI.sub === 'pendientes'){
    const pen = filas.filter(r => r.pendiente > 0);
    cuerpo = pen.length ? `<div class="scroll"><table class="tbl"><thead><tr><th>SKU</th><th>Descripción</th><th class="n">Pedido</th><th class="n">En entregas</th><th class="n">Por suministrar</th></tr></thead><tbody>
      ${pen.map(r => `<tr><td class="code">${esc(r.sku)}</td><td>${esc(r.desc)}</td><td class="n">${fmt(r.pedida)}</td><td class="n">${fmt(r.enEntrega + r.externa)}</td><td class="n"><b>${fmt(r.pendiente)}</b></td></tr>`).join('')}
      </tbody></table></div><div class="row" style="margin-top:14px"><button class="btn primary" data-act="nuevaEntrega">Crear entrega con estos pendientes</button></div>`
      : `<div class="empty"><h3>Nada por suministrar</h3><p>Todas las unidades del pedido ya están en alguna entrega.</p></div>`;
  }
  const cuenta = {entregas: activas.length, grupos: gs.length, pendientes: tot.pendiente ? fmt(tot.pendiente) + ' un.' : ''};
  const enCurso = UI.job && UI.job.estado === 'en_curso';
  const celda = (cap, val, extra = '') => `<div class="cell ${extra}"><span class="cap">${cap}</span><span class="val">${val}</span></div>`;
  return `<div class="label" data-k="label-${esc(safeId(p.pedido))}">
    <div class="label-top">
      <h2 class="lab-num"><span class="lab-pre">Pedido</span> ${esc(p.pedido)}</h2>
      <div class="label-act"><button class="btn sm" data-act="editarPedido">Editar pedido</button>
        <button class="btn primary sm" data-act="nuevaEntrega">${ICON.plus} Nueva entrega</button></div>
      <div class="label-code">${codigoBarrasSVG(p.pedido, {etiqueta: `Código de barras del pedido ${p.pedido}`})}<span class="code">${esc(p.pedido)}</span></div>
    </div>
    <div class="cells">
      ${celda('Cliente', esc(p.cliente || '—'))}${celda('OC', `<span class="code">${esc(p.oc || '—')}</span>`)}${celda('Canal', esc(p.canal || '—'))}${p.fechaOC ? celda('Recibido', fmtFecha(p.fechaOC)) : ''}
    </div>
    <div class="cells" style="border-top:1px solid var(--hair)">
      ${celda('Solicitado', fmt(tot.pedida))}${celda('En entrega', fmt(tot.enEntrega))}${celda('Pendiente', fmt(tot.pendiente))}
      ${celda('Agendado', pct(tot.agendado + tot.entregado, tot.pedida))}${celda('Entregado', fmt(tot.entregado))}
      ${tot.externa ? celda('Otras entregas SAP', fmt(tot.externa)) : ''}${tot.exceso ? celda('Exceso en entregas', fmt(tot.exceso), 'alert') : ''}
    </div>
    <div class="label-bar">${barHTML(tot, true)}
      <div class="legend" style="margin-top:8px"><span><span class="sw s-ent"></span>Entregado</span><span><span class="sw s-age"></span>Agendado</span><span><span class="sw s-sin"></span>Sin cita</span><span><span class="sw s-pen"></span>Pendiente</span></div></div>
    ${p.obs ? `<p class="label-obs small">${esc(p.obs)}</p>` : ''}
    <div class="label-flujo">${flujoHTML(flujo)}</div>
    <div class="label-foot">
      <button class="btn sm" data-act="abrirAnalisis" ${enCurso ? 'disabled' : ''} title="Vuelve a leer el pedido en SAP y actualiza cantidades, saldo y stock">${flujo.an ? 'Volver a analizar' : 'Analizar pedido'}</button>
      <span class="spacer"></span>
      ${flujo.sig ? `<button class="btn primary sm" data-flujo="${flujo.sig.k}">${esc(FLUJO_ACCION[flujo.sig.k])}</button>` : ''}
    </div>
    ${estadoJob()}
    <div class="label-files">${listaArchivos(p.pedido, '')}</div>
  </div>
  <div class="tabs" role="tablist" aria-label="Secciones del pedido">${TABS_PEDIDO.map(([k, t]) =>
    `<button role="tab" data-sub="${k}" aria-selected="${UI.sub === k}">${t}${cuenta[k] !== undefined && cuenta[k] !== '' ? `<span class="tcount">${cuenta[k]}</span>` : ''}</button>`).join('')}<i class="tab-ind" aria-hidden="true"${UI.tabInd ? ` style="transform:${UI.tabInd}"` : ''}></i></div>
  <div class="tab-body">${cuerpo}</div>`;
}

function entregaHTML(e){
  const id = safeId(e.entrega), open = UI.open.has(id), c = e.cita || {};
  const g = grupos().find(x => x.entregas.some(y => y.entrega === e.entrega));
  const estado = e.anulada ? '<span class="tag void">Anulada</span>'
    : pasoOk(e, 'entregado') ? '<span class="tag ok">Entregada</span>'
    : g && g.next ? `<span class="tag warn">Falta ${esc(g.next.t)}</span>` : '';
  const m = (cap, v) => `<div class="m"><span class="cap">${cap}</span><span class="v">${v}</span></div>`;
  return `<article class="docket ${e.anulada ? 'void' : ''}" data-k="e-${esc(id)}">
    <div class="dk-h">
      <div class="dk-id">Entrega <span class="code">${esc(e.entrega)}</span> ${estado}</div>
      <div class="dk-qty">${fmt(unidades(e))} <small>un. · ${(e.lineas || []).length} SKU</small></div>
    </div>
    <div class="meta">
      ${m('Grupo', `<span class="code">${esc(e.grupo || 'sin grupo')}</span>`)}${m('Tipo', `${esc(e.tipo || '—')} · ${esc(e.un || '')}`)}${m('Cita', `<span class="code">${esc(c.numero || '—')}</span>`)}
      ${m('Fecha', `${c.fecha ? fmtFecha(c.fecha) : '—'}${c.hora ? ' ' + esc(c.hora) : ''}`)}${m('Factura', `<span class="code">${esc(e.factura || '—')}</span>`)}
    </div>
    ${g && !e.anulada ? rutaHTML(g, {entrega: e}) : ''}
    ${e.obs ? `<p class="dk-obs">${esc(e.obs)}</p>` : ''}
    <div class="dk-act">
      <button class="btn sm" data-act="editarEntrega" data-ent="${esc(id)}">Editar</button>
      ${e.anulada ? `<button class="btn sm" data-act="reactivar" data-ent="${esc(id)}">Reactivar</button>` :
        `<button class="btn danger sm" data-act="anular" data-ent="${esc(id)}">Anular</button>
         <button class="btn danger sm" data-act="borrarEntregaSap" data-ent="${esc(e.entrega)}" title="Borra la entrega en VL06 y la quita de la plataforma">Borrar en SAP</button>`}
      <span class="spacer"></span>
      <button class="btn quiet sm" data-act="toggle" data-ent="${esc(id)}" aria-expanded="${open}">${open ? 'Ocultar productos' : `Ver productos (${(e.lineas || []).length})`}</button>
    </div>
    ${open ? `<div class="scroll" style="margin-top:10px"><table class="tbl"><thead><tr><th>SKU</th><th>Descripción</th><th class="n">Cantidad</th></tr></thead><tbody>
      ${(e.lineas || []).map(l => `<tr><td class="code">${esc(l.sku)}</td><td>${esc(l.desc || descDe(e.pedido, l.sku))}</td><td class="n">${fmt(l.qty)}</td></tr>`).join('')}</tbody></table></div>
      ${(e.log || []).length ? `<details><summary>Historial</summary><ul class="log">${e.log.map(x => `<li>${new Date(x.at).toLocaleString('es-CL')} — ${esc(x.txt)}</li>`).join('')}</ul></details>` : ''}` : ''}
  </article>`;
}

function grupoHTML(g){
  const c = g.cita || {};
  const estado = g.next ? `<span class="tag warn">Falta ${esc(g.next.t)}</span>` : '<span class="tag ok">Entregado</span>';
  const otros = g.pedidos.length > 1;
  const m = (cap, v) => `<div class="m"><span class="cap">${cap}</span><span class="v">${v}</span></div>`;
  return `<article class="docket" data-k="g-${esc(g.key)}">
    <div class="dk-h">
      <div class="dk-id">${g.sinGrupo ? 'Sin grupo' : `Grupo <span class="code">${esc(g.grupo)}</span>`} ${estado}
        ${g.parcial ? '<span class="tag err" title="Hay pasos marcados en unas entregas del camión y en otras no">Entregas desalineadas</span>' : ''}
        ${otros ? '<span class="tag info">Camión compartido</span>' : ''}</div>
      <div class="dk-qty">${fmt(g.unidades)} <small>un. · ${g.entregas.length} entrega(s)</small></div>
    </div>
    <div class="meta">
      ${m('Cita', `<span class="code">${esc(c.numero || '—')}</span>`)}${m('Fecha', `${c.fecha ? fmtFecha(c.fecha) : '—'}${c.hora ? ' ' + esc(c.hora) : ''}`)}
      ${m('Vehículo', `${esc(g.vehiculo || '')} · ${esc(g.carga || '')}`)}${m('Tipo', `${esc(g.un || '')} · ${esc(g.tipo || '')}`)}${m('Región', esc(g.region || '—'))}
    </div>
    ${rutaHTML(g)}
    <div class="scroll"><table class="tbl"><thead><tr><th>Entrega</th><th>Pedido</th><th class="n">Unidades</th><th class="n">SKU</th><th>Factura</th></tr></thead><tbody>
      ${g.entregas.map(e => `<tr><td class="code">${esc(e.entrega)}</td><td class="code">${esc(e.pedido)}${e.pedido !== (Store.get('pedidos', UI.sel) || {}).pedido ? ' <span class="tag">otro pedido</span>' : ''}</td>
      <td class="n">${fmt(unidades(e))}</td><td class="n">${(e.lineas || []).length}</td><td class="code">${esc(e.factura || '—')}${pasoOk(e, 'facturada') ? ` <span class="tag ok">${ICON.check}</span>` : ''}</td></tr>`).join('')}
    </tbody></table></div>
    <div class="dk-act">
      <button class="btn sm" data-act="editarGrupo" data-grupo="${esc(g.key)}">Editar camión</button>
      <button class="btn sm" data-act="reprogGrupo" data-grupo="${esc(g.key)}" ${g.pasos.confirmada ? '' : 'disabled title="Solo para citas confirmadas"'}>Reprogramar cita</button>
      ${g.sinGrupo
        ? `<button class="btn quiet sm" data-act="ensayoGrupo" data-cam="${esc(g.key)}" data-ents="${esc(g.entregas.map(e => e.entrega).join(','))}">Ensayo del grupo</button>
           <button class="btn sm" data-act="crearGrupoSap" data-cam="${esc(g.key)}" data-ents="${esc(g.entregas.map(e => e.entrega).join(','))}" title="Crea el grupo de transporte en VL06">Crear grupo en SAP</button>`
        : `<button class="btn sm" data-act="citaGrupo" data-num="${esc(g.grupo)}" title="Fecha, hora y referencia de la cita en VG02">Cita en SAP</button>
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
      headers: Usuario.get() ? {'X-Usuario': Usuario.get()} : {}});
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
          <input type="file" accept=".xlsx,.xlsm" data-predistimport="${esc(p.pedido)}" style="display:none"></label>
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
function visorPedido(p, cb, alto){
  if (!cb.visor) return '';
  const vivo = cb.visor_json && cb.visor_vivo;
  return `<div class="visor-caja" style="min-height:${alto}px;flex:none;height:${alto}px">
    ${vivo ? `<iframe data-k="visor-ped" data-visor="pedido:${esc(p.pedido)}" src="${esc(cb.visor_vivo)}#solo3d" title="Visor 3D del pedido ${esc(p.pedido)}"></iframe>`
           : `<iframe data-k="visor-ped" src="${esc(cb.visor)}" title="Visor 3D del pedido ${esc(p.pedido)}"></iframe>`}
    ${herramientasVisor()}
    <a class="btn sm abrir" href="${esc(cb.visor)}" target="_blank" rel="noopener" style="position:absolute;right:10px;bottom:10px">${ICON.external} Aparte</a></div>`;
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
        <div class="dk-qty">${fmt(fs.reduce((a, f) => a + f.unidades, 0))} <small>un. · ${pctCub(ocup)} ocupado</small></div></div>
      <div class="meta">${m('Medidas', `${fmt(c.L)} × ${fmt(c.w)} × ${fmt(c.h)} cm`)}${m('Capacidad', `${m3(c.vol_m3, 2)} m³`)}${m('Libre', `${m3(fs.length ? fs[fs.length - 1].libre_m3 : c.vol_m3, 2)} m³`)}</div>
      <div class="scroll" style="margin-top:8px"><table class="tbl"><thead><tr>${fs.some(f => f.sucursal) ? '<th>Sucursal</th>' : ''}<th>SKU</th><th>Descripción</th><th class="n">Unidades</th></tr></thead><tbody>
        ${fs.map(f => `<tr>${fs.some(x => x.sucursal) ? `<td>${esc(f.sucursal)}</td>` : ''}<td class="code">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td><td class="n">${fmt(f.unidades)}</td></tr>`).join('')}
      </tbody></table></div></article>`;
  }).join('');
  const problemas = [
    ...(cb.no_encontrados || []).map(x => `<span class="tag err">Sin descripción: ${esc(x)}</span>`),
    ...Object.entries(cb.sin_ubicar || {}).map(([k, v]) => `<span class="tag err">No cupo: ${esc(k)} (${fmt(v)})</span>`),
  ].join(' ');
  return `<div class="row" style="margin-bottom:10px">
      <div class="small muted">Cubicaje ${esc(cb.modo)} del ${fmtFecha(cb.generado)} · pallet del cliente ${cb.pallet.join(' × ')} cm</div>
      <span class="spacer"></span>
      ${cb.visor ? `<button class="btn sm" data-act="ensayoEntregas" title="Recorre VL01N sin guardar, para revisar antes de crear">Ensayo en SAP</button>
        <button class="btn primary sm" data-act="crearEntregas" title="Crea una entrega por camión en VL01N">Crear entregas en SAP</button>
        <a class="btn sm" href="/api/cubicaje/${encodeURIComponent(p.pedido)}/excel">Exportar a Excel</a>
        <button class="btn sm" data-act="verVisorCub" aria-pressed="${!!UI.verVisorCub}">${UI.verVisorCub ? 'Ocultar visor 3D' : 'Ver visor 3D aquí'}</button>` : ''}</div>
    ${cb.camiones.length ? fichasCamion(p, cb) : ''}
    ${cb.visor && UI.verVisorCub ? `<div style="margin:10px 0 14px">${visorPedido(p, cb, 640)}</div>` : ''}
    <div class="legend" style="margin:12px 0"><span>Camiones <b class="num">${cb.camiones.length}</b></span><span>Unidades <b class="num">${fmt(cb.unidades)}</b></span>
      <span>SKU <b class="num">${new Set(cb.filas.map(f => f.sku)).size}</b></span>
      ${(cb.pallets_detalle || []).length ? `<span>Pallets <b class="num">${cb.pallets_detalle.length}</b></span>` : ''}
      ${(cb.filas04 || []).some(f => f.tipo === 'Piso') ? `<span>A piso <b class="num">${fmt(cb.filas04.filter(f => f.tipo === 'Piso').reduce((a, f) => a + f.unidades, 0))}</b></span>` : ''}</div>
    ${alertaFaltantes(cb.faltantes, `/api/cubicaje/${encodeURIComponent(p.pedido)}/faltantes.xlsx`, (cb.unidades || 0) + (cb.faltantes || []).reduce((a, x) => a + x.unidades, 0))}
    ${form}
    ${seccionPredist(p, modoElegido(cb))}
    ${problemas ? `<p class="small" style="margin-top:10px">${problemas}</p>` : ''}
    ${(cb.avisos || []).map(a => `<p class="small"><span class="tag warn">Aviso</span> ${esc(a)}</p>`).join('')}
    <div style="margin-top:12px">${camiones}</div>
    ${(cb.filas04 || []).length ? `<div class="panel" style="margin-top:14px"><div class="panel-h"><h3>Detalle por pallet</h3></div>
      <div class="scroll"><table class="tbl"><thead><tr><th class="n">Camión</th><th>Tipo vehículo</th><th class="n">Pallet</th>
        ${cb.filas04.some(f => f.sucursal) ? '<th>Sucursal</th>' : ''}<th>SKU</th><th>Descripción</th>
        <th class="n">Cajas</th><th class="n">Bultos</th><th class="n">Unidades</th><th>Tipo</th></tr></thead><tbody>
        ${cb.filas04.map(f => `<tr><td class="n">${f.vehiculo}</td><td>${esc(f.tipo_vehiculo)}</td>
          <td class="n">${f.pallet || '—'}</td>${cb.filas04.some(x => x.sucursal) ? `<td>${esc(f.sucursal)}</td>` : ''}
          <td class="code">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td><td class="n">${fmt(f.cajas)}</td>
          <td class="n">${fmt(f.bultos)}</td><td class="n">${fmt(f.unidades)}</td>
          <td><span class="tag ${f.tipo === 'Piso' ? 'warn' : ''}">${esc(f.tipo)}</span></td></tr>`).join('')}
      </tbody></table></div></div>` : ''}`;
}

function descDe(ped, sku){ const p = Store.get('pedidos', safeId(ped)); const l = p && (p.lineas || []).find(x => normSku(x.sku) === normSku(sku)); return l ? l.desc : ''; }
