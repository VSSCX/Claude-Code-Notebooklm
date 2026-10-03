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
function vistaPedidos(){
  const q = normH(UI.q);
  let peds = Store.list('pedidos')
    .filter(p => !UI.cliente || p.cliente === UI.cliente)
    .filter(p => !q || normH([p.pedido, p.oc, p.cliente, ...(p.lineas||[]).map(l => l.sku + ' ' + l.desc), ...entregasDe(p.pedido).map(e => e.entrega + ' ' + e.grupo + ' ' + (e.cita?.numero||''))].join(' ')).includes(q))
    .filter(p => !UI.soloAbiertos || !cerrado(p))
    .sort((a, b) => urgencia(a).localeCompare(urgencia(b)));
  if (UI.sel && !Store.get('pedidos', UI.sel)) UI.sel = null;
  if (!UI.sel && peds.length && window.innerWidth > 960) UI.sel = safeId(peds[0].pedido);

  const lista = peds.length ? `<ul class="plist">${peds.map(p => {
      const {tot} = resumen(p); const id = safeId(p.pedido);
      return `<li><button data-sel="${esc(id)}" aria-current="${UI.sel === id}">
        <div class="l1"><span class="ped">${esc(p.pedido)}</span><span class="small muted num">${pct(tot.agendado + tot.entregado, tot.pedida)} agendado</span></div>
        <div class="l2">${esc(p.cliente || 'Sin cliente')} · OC ${esc(p.oc || '—')} · <span class="num">${fmt(tot.pedida)}</span> un.${tot.pendiente ? ` · <span class="num">${fmt(tot.pendiente)}</span> por suministrar` : ''}</div>
        ${barHTML(tot)}</button></li>`; }).join('')}</ul>`
    : `<div class="empty"><h3>${Store.list('pedidos').length ? 'Ningún pedido coincide' : 'Aún no hay pedidos'}</h3><p>${Store.list('pedidos').length ? 'Cambia el filtro o la búsqueda.' : 'Crea uno a mano o importa un Excel exportado de SAP.'}</p></div>`;

  return `<div class="layout">
    <section class="panel">
      <div class="panel-h">
        <input type="search" placeholder="Pedido, OC, SKU, entrega… y Enter" value="${esc(UI.q)}" data-q style="flex:1;min-width:160px" aria-label="Buscar">
        <button class="btn primary" data-act="abrirAnalisis">Analizar pedido de SAP</button>
        <button class="btn" data-act="nuevoPedido">Cargar a mano</button>
        <div class="row" style="width:100%">${filtroCliente()}
          <label class="row small"><input type="checkbox" data-abiertos ${UI.soloAbiertos ? 'checked' : ''}> Ocultar cerrados</label></div>
      </div>
      ${lista}
    </section>
    <section>${UI.sel ? detallePedido(Store.get('pedidos', UI.sel)) : `<div class="panel empty"><h3>Selecciona un pedido</h3><p>Verás su avance por producto y cada entrega con sus pasos.</p></div>`}</section>
  </div>`;
}

function detallePedido(p){
  const {filas, tot} = resumen(p); const ents = entregasDe(p.pedido);
  const activas = ents.filter(e => !e.anulada);
  let cuerpo = '';
  if (UI.sub === 'analisis'){
    cuerpo = vistaAnalisis(p);
  } else if (UI.sub === 'cubicaje'){
    cuerpo = vistaCubicaje(p);
  } else if (UI.sub === 'grupos'){
    const gs = gruposDe(p.pedido);
    cuerpo = gs.length ? gs.map(grupoHTML).join('') :
      `<div class="empty"><h3>Todavía no hay camiones</h3><p>Aparecen cuando la entrega tiene grupo. Las entregas sin grupo se muestran igual, como camión pendiente.</p></div>`;
  } else if (UI.sub === 'entregas'){
    cuerpo = ents.length ? ents.map(entregaHTML).join('') :
      `<div class="empty"><h3>Este pedido no tiene entregas</h3><p>Crea la primera con las cantidades que suministraste en VL01N.</p><button class="btn primary" data-act="nuevaEntrega">Nueva entrega</button></div>`;
  } else if (UI.sub === 'pendientes'){
    const pen = filas.filter(r => r.pendiente > 0);
    cuerpo = pen.length ? `<div class="scroll"><table class="t"><thead><tr><th>SKU</th><th>Descripción</th><th class="n">Pedido</th><th class="n">En entregas</th><th class="n">Por suministrar</th></tr></thead><tbody>
      ${pen.map(r => `<tr><td class="num">${esc(r.sku)}</td><td>${esc(r.desc)}</td><td class="n">${fmt(r.pedida)}</td><td class="n">${fmt(r.enEntrega + r.externa)}</td><td class="n"><b>${fmt(r.pendiente)}</b></td></tr>`).join('')}
      </tbody></table></div><div class="row" style="margin-top:14px"><button class="btn primary" data-act="nuevaEntrega">Crear entrega con estos pendientes</button></div>`
      : `<div class="empty"><h3>Nada por suministrar</h3><p>Todas las unidades del pedido ya están en alguna entrega.</p></div>`;
  } else {
    cuerpo = tablaProductos(p, filas, tot);
  }
  return `<div class="panel">
    <div class="panel-b">
      <div class="dhead">
        <div><div class="dtitle">${esc(p.pedido)}</div>
          <div class="meta" style="margin-top:6px"><span>Cliente <b>${esc(p.cliente || '—')}</b></span><span>OC <b>${esc(p.oc || '—')}</b></span><span>Canal <b>${esc(p.canal || '—')}</b></span>${p.fechaOC ? `<span>Recibido <b>${fmtFecha(p.fechaOC)}</b></span>` : ''}</div>
          ${p.obs ? `<p class="small" style="margin:8px 0 0">${esc(p.obs)}</p>` : ''}</div>
        <div class="row"><button class="btn" data-act="editarPedido">Editar pedido</button><button class="btn primary" data-act="nuevaEntrega">Nueva entrega</button></div>
      </div>
      <div class="row" style="margin-top:10px">
        <button class="btn primary" data-act="abrirAnalisis" ${UI.job && UI.job.estado === 'en_curso' ? 'disabled' : ''} title="Vuelve a leer el pedido en SAP y actualiza cantidades, saldo y stock">Actualizar desde SAP</button>
        ${botonAccion('leer_pedido')}${botonAccion('cubicar')}${botonAccion('crear_entregas')}${botonAccion('crear_grupos')}${botonAccion('visor')}
      </div>
      ${estadoJob()}
      ${listaArchivos(p.pedido, '')}
      <div style="display:none">
      </div>
      <div style="margin-top:18px">${barHTML(tot, true)}</div>
      <div class="legend">
        <div>Solicitado<b>${fmt(tot.pedida)}</b></div>
        <div><span class="sw s-age"></span>En entrega<b>${fmt(tot.enEntrega)}</b></div>
        <div><span class="sw s-pen"></span>Pendiente<b>${fmt(tot.pendiente)}</b></div>
        <div class="muted">Agendado<b>${pct(tot.agendado + tot.entregado, tot.pedida)}</b></div>
        <div class="muted"><span class="sw s-ent"></span>Entregado<b>${fmt(tot.entregado)}</b></div>
        ${tot.externa ? `<div class="muted">Otras entregas SAP<b>${fmt(tot.externa)}</b></div>` : ''}
        ${tot.exceso ? `<div class="warn-t">Exceso en entregas<b>${fmt(tot.exceso)}</b></div>` : ''}
      </div>
    </div>
    <div class="subtabs" role="tablist">
      <button role="tab" data-sub="entregas" aria-selected="${UI.sub === 'entregas'}">Entregas (${activas.length})</button>
      <button role="tab" data-sub="grupos" aria-selected="${UI.sub === 'grupos'}">Grupos / camiones (${gruposDe(p.pedido).length})</button>
      <button role="tab" data-sub="analisis" aria-selected="${UI.sub === 'analisis'}">Análisis</button>
      <button role="tab" data-sub="cubicaje" aria-selected="${UI.sub === 'cubicaje'}">Cubicaje</button>
      <button role="tab" data-sub="pendientes" aria-selected="${UI.sub === 'pendientes'}">Pendientes (${fmt(tot.pendiente)} un.)</button>
      <button role="tab" data-sub="productos" aria-selected="${UI.sub === 'productos'}">Productos, plan y stock</button>
    </div>
    <div class="panel-b">${cuerpo}</div>
  </div>`;
}

function entregaHTML(e){
  const id = safeId(e.entrega), open = UI.open.has(id), c = e.cita || {};
  const g = grupos().find(x => x.entregas.some(y => y.entrega === e.entrega));
  const estado = e.anulada ? '<span class="tag red">Anulada</span>'
    : pasoOk(e, 'entregado') ? '<span class="tag green">Entregada</span>'
    : g && g.next ? `<span class="tag amber">Camión: falta ${esc(g.next.t)}</span>` : '';
  return `<article class="ent ${e.anulada ? 'anulada' : ''}">
    <div class="top">
      <div><span class="id">Entrega ${esc(e.entrega)}</span> ${estado}</div>
      <div class="num" style="font-size:19px">${fmt(unidades(e))} <span class="muted small">un.</span> <span class="muted small">· ${(e.lineas || []).length} SKU</span></div>
    </div>
    <div class="meta" style="margin-top:4px">
      <span>Grupo <b>${esc(e.grupo || 'sin grupo')}</b></span><span>${esc(e.tipo || '—')} · ${esc(e.un || '')}</span>
      <span>Cita <b>${esc(c.numero || '—')}</b></span>
      <span>Fecha <b>${c.fecha ? fmtFecha(c.fecha) : '—'}${c.hora ? ' ' + esc(c.hora) : ''}</b></span>
      <span>Factura <b>${esc(e.factura || '—')}</b> ${pasoOk(e, 'facturada') ? '<span class="tag green">Facturada</span>' : ''}</span>
    </div>
    ${e.obs ? `<p class="small" style="margin:6px 0 0">${esc(e.obs)}</p>` : ''}
    <div class="act">
      <button class="btn" data-act="editarEntrega" data-ent="${esc(id)}">Editar</button>
      ${e.anulada ? `<button class="btn" data-act="reactivar" data-ent="${esc(id)}">Reactivar</button>` :
        `<button class="btn" data-paso="facturada" data-ent="${esc(id)}">${pasoOk(e, 'facturada') ? 'Desmarcar factura' : 'Marcar facturada'}</button>
         <button class="btn danger ghost" data-act="anular" data-ent="${esc(id)}">Anular</button>
         <button class="btn danger ghost" data-act="borrarEntregaSap" data-ent="${esc(e.entrega)}" title="Borra la entrega en VL06 y la quita de la plataforma">Borrar en SAP</button>`}
      <button class="btn ghost" data-act="toggle" data-ent="${esc(id)}" aria-expanded="${open}">${open ? 'Ocultar productos' : `Ver productos (${(e.lineas || []).length})`}</button>
    </div>
    ${open ? `<div class="scroll" style="margin-top:10px"><table class="t"><thead><tr><th>SKU</th><th>Descripción</th><th class="n">Cantidad</th></tr></thead><tbody>
      ${(e.lineas || []).map(l => `<tr><td class="num">${esc(l.sku)}</td><td>${esc(l.desc || descDe(e.pedido, l.sku))}</td><td class="n">${fmt(l.qty)}</td></tr>`).join('')}</tbody></table></div>
      ${(e.log || []).length ? `<details><summary>Historial</summary><ul class="log">${e.log.map(x => `<li>${new Date(x.at).toLocaleString('es-CL')} — ${esc(x.txt)}</li>`).join('')}</ul></details>` : ''}` : ''}
  </article>`;
}

function grupoHTML(g){
  const c = g.cita || {};
  const estado = g.next ? `<span class="tag amber">Falta: ${esc(g.next.t)}</span>` : '<span class="tag green">Entregado</span>';
  const otros = g.pedidos.length > 1;
  return `<article class="ent">
    <div class="top">
      <div><span class="id">${g.sinGrupo ? 'Sin grupo' : 'Grupo ' + esc(g.grupo)}</span> ${estado}
        ${g.parcial ? '<span class="tag red" title="Hay pasos marcados en unas entregas del camión y en otras no">Entregas desalineadas</span>' : ''}
        ${otros ? '<span class="tag">Camión compartido</span>' : ''}</div>
      <div class="num" style="font-size:19px">${fmt(g.unidades)} <span class="muted small">un. · ${g.entregas.length} entrega(s)</span></div>
    </div>
    <div class="meta" style="margin-top:4px">
      <span>Cita <b>${esc(c.numero || '—')}</b></span>
      <span>Fecha <b>${c.fecha ? fmtFecha(c.fecha) : '—'}${c.hora ? ' ' + esc(c.hora) : ''}</b></span>
      <span>${esc(g.vehiculo || '')} · ${esc(g.carga || '')} · ${esc(g.un || '')} · ${esc(g.tipo || '')}</span>
      <span>Región <b>${esc(g.region || '—')}</b></span>
    </div>
    <div class="track">${STEPS.map((s, i) => {
      const d = g.pasos[s.k], n = g.next && g.next.k === s.k, fijo = POR_ENTREGA.includes(s.k);
      const tit = fijo ? `${s.t} · se marca en cada entrega` : s.t;
      return `<button class="stp ${d ? 'done' : ''} ${n ? 'next' : ''}" ${fijo ? 'disabled style="cursor:default"' : `data-gpaso="${s.k}" data-grupo="${esc(g.key)}"`} aria-pressed="${d}" title="${esc(tit)}">
        <span class="k">${d ? '✓' : i + 1}</span><span class="t">${esc(s.t)}</span></button>`; }).join('')}</div>
    <div class="scroll" style="margin-top:6px"><table class="t"><thead><tr><th>Entrega</th><th>Pedido</th><th class="n">Unidades</th><th class="n">SKU</th><th>Factura</th></tr></thead><tbody>
      ${g.entregas.map(e => `<tr><td class="num">${esc(e.entrega)}</td><td class="num">${esc(e.pedido)}${e.pedido !== (Store.get('pedidos', UI.sel) || {}).pedido ? ' <span class="tag">otro pedido</span>' : ''}</td>
      <td class="n">${fmt(unidades(e))}</td><td class="n">${(e.lineas || []).length}</td><td class="num">${esc(e.factura || '—')}${pasoOk(e, 'facturada') ? ' ✓' : ''}</td></tr>`).join('')}
    </tbody></table></div>
    <div class="act">
      <button class="btn" data-act="editarGrupo" data-grupo="${esc(g.key)}">Editar camión</button>
      <button class="btn" data-act="reprogGrupo" data-grupo="${esc(g.key)}" ${g.pasos.confirmada ? '' : 'disabled title="Solo para citas confirmadas"'}>Reprogramar cita</button>
      ${g.sinGrupo
        ? `<button class="btn ghost" data-act="ensayoGrupo" data-cam="${esc(g.key)}" data-ents="${esc(g.entregas.map(e => e.entrega).join(','))}">Ensayo del grupo</button>
           <button class="btn" data-act="crearGrupoSap" data-cam="${esc(g.key)}" data-ents="${esc(g.entregas.map(e => e.entrega).join(','))}" title="Crea el grupo de transporte en VL06">Crear grupo en SAP</button>`
        : `<button class="btn" data-act="citaGrupo" data-num="${esc(g.grupo)}" title="Fecha, hora y referencia de la cita en VG02">Cita en SAP</button>
           <button class="btn danger ghost" data-act="borrarGrupoSap" data-num="${esc(g.grupo)}" title="Borra el grupo en VG02; las entregas quedan sin grupo">Borrar grupo en SAP</button>`}
    </div>
    ${listaArchivos(g.entregas[0].pedido, g.grupo)}
  </article>`;
}

/* ---- Plan SOP, saldo y disponibilidad (SQL Server) ---- */
UI.plan = {};
async function cargarPlan(pedido, refrescar){
  UI.plan[pedido] = {cargando:true};
  render();
  try { UI.plan[pedido] = await api('GET', `/plan/${encodeURIComponent(pedido)}${refrescar ? '?refrescar=true' : ''}`); }
  catch(e){ UI.plan[pedido] = {ok:false, error:e.message, productos:{}}; }
  render();
}
function tablaProductos(p, filas, tot){
  const pl = UI.plan[p.pedido];
  if (!pl) setTimeout(() => cargarPlan(p.pedido), 0);
  // La "en entrega" (ZSD001_03) viene del último análisis del pedido
  const an = UI.analisis[p.pedido];
  if (!an) setTimeout(() => cargarAnalisis(p.pedido), 0);
  const conAnalisis = an && an.resultado;
  const enEntZsd = {};
  if (conAnalisis) for (const f of an.resultado.filas) enEntZsd[f.sku] = f.en_entrega;
  let aviso = '';
  if (!pl || pl.cargando) aviso = '<p class="small muted">Consultando plan y stock en SQL Server…</p>';
  else if (!pl.ok) aviso = `<p class="small"><span class="tag red">Sin plan</span> No se pudo consultar SQL Server: ${esc(pl.error)}</p>`;
  else if (!pl.grupo_encontrado) aviso = `<p class="small"><span class="tag amber">Atención</span> El grupo SOP <b>${esc(pl.grupo)}</b> no tiene plan cargado este mes. Revisa que el cliente del pedido se llame igual que el grupo SOP.</p>`;
  else aviso = `<p class="small muted">Plan ${esc(pl.tipo_plan)} del mes · grupo SOP ${esc(pl.grupo)} · <b>Saldo SOP = plan − real − en entrega</b>${conAnalisis ? ` (en entrega según el análisis del ${fmtFecha(an.generado)})` : ''}. <button class="btn ghost small" data-act="refrescarPlan">Actualizar plan</button></p>
    ${conAnalisis ? '' : `<p class="small"><span class="tag amber">Falta la Qty en entrega</span> El saldo se calcula con la Qty en entrega de ZSD001_03, que se obtiene al analizar el pedido. <button class="btn small" data-act="abrirAnalisis">Analizar pedido</button></p>`}`;
  const prod = (pl && pl.productos) || {};
  const alertas = {sinPlan:0, sinStock:0};
  const cuerpo = filas.map(r => {
    const x = prod[r.sku] || {}, plan = x.plan, disp = x.disponible;
    // Regla oficial (igual que el Excel): saldo SOP = plan − real − en entrega
    const enZsd = conAnalisis ? (enEntZsd[r.sku] ?? 0) : null;
    const saldoPed = plan && enZsd !== null ? plan.plan - plan.vendido - enZsd : null;
    const puede = saldoPed !== null ? Math.max(0, Math.min(r.pendiente, saldoPed)) : null;
    let marcas = '';
    if (pl && pl.ok && pl.grupo_encontrado){
      if (!plan) marcas += ' <span class="tag" title="Este código no aparece en el plan del grupo">no está en el plan</span>';
      else if (saldoPed !== null && r.pendiente > saldoPed){ marcas += ` <span class="tag red" title="El saldo del plan no alcanza para todo lo pendiente">sin saldo · alcanza ${fmt(puede)} de ${fmt(r.pendiente)}</span>`; alertas.sinPlan++; }
      if (disp && r.pendiente > disp.cantidad){ marcas += ' <span class="tag amber" title="Lo pendiente supera el stock disponible">sin stock</span>'; alertas.sinStock++; }
    }
    return `<tr><td class="num">${esc(r.sku)}${r.fuera ? ' <span class="tag red">no está en el pedido</span>' : ''}</td><td>${esc(r.desc)}${marcas}</td>
      <td class="n">${fmt(r.pedida)}</td><td class="n">${fmt(r.enEntrega + r.externa)}</td><td class="n">${fmt(r.pendiente)}</td>
      <td class="n">${plan ? fmt(plan.plan) : '—'}</td><td class="n">${plan ? fmt(plan.vendido) : '—'}</td>
      <td class="n">${enZsd !== null ? fmt(enZsd) : '—'}</td>
      <td class="n">${saldoPed !== null ? `<b${saldoPed < r.pendiente ? ' class="warn-t"' : ''}>${fmt(saldoPed)}</b>` : '—'}</td>
      <td class="n">${disp ? fmt(disp.cantidad) : '—'}${disp && disp.fecha ? `<div class="small muted">${fmtFecha(disp.fecha)}</div>` : ''}</td></tr>`;
  }).join('');
  const resumen = (alertas.sinPlan || alertas.sinStock)
    ? `<p class="small">${alertas.sinPlan ? `<span class="tag red">${alertas.sinPlan} SKU sin saldo suficiente</span> ` : ''}${alertas.sinStock ? `<span class="tag amber">${alertas.sinStock} SKU sin stock suficiente</span>` : ''}</p>` : '';
  return `${aviso}${resumen}<div class="scroll"><table class="t"><thead><tr><th>SKU</th><th>Descripción</th>
    <th class="n">Pedido</th><th class="n" title="Unidades de este pedido que ya están en entregas registradas en la plataforma">En entrega (pedido)</th><th class="n">Pendiente</th>
    <th class="n">Plan mes</th><th class="n">Real</th><th class="n" title="Qty en entrega de ZSD001_03 (todas las entregas del cliente de ese producto)">En entrega (SAP)</th><th class="n" title="Plan − real − en entrega">Saldo SOP</th><th class="n">Disponible</th></tr></thead>
    <tbody>${cuerpo}</tbody>
    <tfoot><tr><td></td><td class="muted">Total</td><td class="n">${fmt(tot.pedida)}</td><td class="n">${fmt(tot.enEntrega + tot.externa)}</td><td class="n">${fmt(tot.pendiente)}</td><td colspan="5"></td></tr></tfoot></table></div>`;
}

/* ---- Cubicaje propio (port del cubicador del Excel) ---- */
UI.cubicaje = {}; UI.verVisorCub = true; UI.visorVivo = true; UI.predist = {}; UI.verPredist = false;
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
  return `<div class="panel" style="margin:12px 0"><div class="panel-b">
    <div class="row" style="justify-content:space-between">
      <div><b>Reparto por sucursal</b> <span class="small muted">${d.filas.length ? `${fmt(d.filas.length)} líneas · ${d.sucursales.length} sucursales · ${fmt(d.unidades)} unidades` : 'sin datos'}</span></div>
      <div class="row" style="gap:6px">
        <a class="btn ghost small" href="/api/predistribuido/plantilla" title="Excel para armar el reparto: sucursal, SKU y unidades">Plantilla</a>
        <label class="btn ghost small" title="Carga el reparto desde la plantilla. Reemplaza el que hay.">Importar Excel
          <input type="file" accept=".xlsx,.xlsm" data-predistimport="${esc(p.pedido)}" style="display:none"></label>
        <button class="btn ghost small" data-act="verPredist">${UI.verPredist ? 'Ocultar' : (d.filas.length ? 'Editar' : 'Pegar reparto')}</button>
      </div>
    </div>
    ${(d.errores || []).length ? `<p class="small"><span class="tag red">Revisar</span> ${esc(d.errores.slice(0,3).join(' · '))}</p>` : ''}
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
  UI.cubicaje[pedido] = {cargando:true}; render();
  try {
    UI.cubicaje[pedido] = await api('POST', `/cubicaje/${encodeURIComponent(pedido)}`, opts || {});
    if (UI.cubicaje[pedido].visor) UI.verVisorCub = true;      // el visor nuevo queda a la vista
    toast(`Cubicado en ${UI.cubicaje[pedido].camiones.length} camión(es)`);
  } catch(e){ UI.cubicaje[pedido] = {error:e.message}; toast(e.message); }
  render();
}
/* El camión se rearma solo cada vez que cambias una cantidad */
function panelVisorVivo(p){
  const cb = UI.cubicaje[p.pedido];
  if (!cb){ setTimeout(() => cubicar(p.pedido, {}), 0); return '<p class="small muted">Armando el camión…</p>'; }
  if (cb.cargando) return '<p class="small muted">Recalculando el camión…</p>';
  if (cb.error || !cb.camiones) return `<p class="small"><span class="tag amber">Camión</span> ${esc(cb.error || 'sin cubicaje')}</p>`;
  const pct = x => (100 * x).toFixed(1) + '%';
  const porCamion = {};
  for (const f of cb.filas) porCamion[f.camion] = f.ocup_acum;
  const chips = cb.camiones.map(c => `<span class="tag">${esc(c.tipo)} #${c.numero}: ${pct(porCamion[c.numero] || 0)}</span>`).join(' ');
  return `<div class="panel" style="margin-bottom:16px"><div class="panel-b">
    <div class="row" style="justify-content:space-between">
      <div><b>Camión en vivo</b> <span class="small muted">se rearma al cambiar la carga</span></div>
      <div class="row">${chips || '<span class="tag">Sin unidades</span>'}
        ${cb.visor ? `<a class="btn ghost small" href="${esc(cb.visor)}" target="_blank" rel="noopener">Abrir aparte</a>` : ''}
        <button class="btn ghost small" data-act="ocultarVivo">${UI.visorVivo === false ? 'Mostrar' : 'Ocultar'}</button></div>
    </div>
    ${cb.visor && UI.visorVivo !== false
      ? `<iframe src="${esc(cb.visor)}" title="Visor 3D en vivo" style="width:100%;height:460px;border:1px solid var(--line);border-radius:8px;margin-top:10px;background:#fff"></iframe>`
      : ''}
    ${(cb.avisos || []).length ? `<p class="small muted" style="margin:8px 0 0">${esc(cb.avisos[0])}</p>` : ''}
  </div></div>`;
}

function vistaCubicaje(p){
  const cb = UI.cubicaje[p.pedido];
  const an = UI.analisis[p.pedido];
  if (!cb) { setTimeout(() => cargarCubicaje(p.pedido), 0); return '<p class="small muted">Cargando cubicaje…</p>'; }
  if (cb.cargando) return '<p class="small muted">Cubicando… (puede tardar unos segundos)</p>';
  const modos = ['MDA', 'MDA PREDISTRIBUIDO', 'SDA STOCK', 'SDA PREDISTRIBUIDO'];
  const sel3 = (attr, opciones, valor) => `<select ${attr}>${opciones.map(o =>
    `<option value="${esc(o.v)}" ${o.v === valor ? 'selected' : ''}>${esc(o.t)}</option>`).join('')}</select>`;
  const form = `<div class="row" style="gap:10px">
      <label class="f">Modo${sel3('data-cubmodo', modos.map(m => ({v:m, t:m})), modoElegido(cb))}</label>
      <label class="f">Caja master${sel3('data-cubcm', [{v:'', t:''}, {v:'CON CAJA MASTER', t:'CON CAJA MASTER'}, {v:'SIN CAJA MASTER', t:'SIN CAJA MASTER'}], UI.cubOpts.caja_master || cb.caja_master || '')}</label>
      <label class="f">Piso / pallet${sel3('data-cubh2', [{v:'', t:'Default del modo'}, {v:'PISO', t:'PISO'}, {v:'PALLET', t:'PALLET'}], UI.cubOpts.piso_pallet || cb.piso_pallet || '')}</label>
      <button class="btn primary" data-act="cubicar" style="align-self:flex-end;margin-bottom:2px">${cb.error || !cb.camiones ? 'Cubicar' : 'Volver a cubicar'}</button>
    </div>`;
  if (cb.error || !cb.camiones){
    const falta = /analizar el pedido/.test(cb.error || '');
    return `<div class="empty"><h3>${cb.error && !/todavía no está cubicado/.test(cb.error) ? 'No se pudo cubicar' : 'Este pedido todavía no está cubicado'}</h3>
      <p>${esc(cb.error && !/todavía no está cubicado/.test(cb.error) ? cb.error : 'El cubicaje usa la carga del análisis, con tus ajustes manuales.')}</p>
      ${falta ? '<button class="btn primary" data-act="abrirAnalisis">Analizar pedido</button>' : form + seccionPredist(p, modoElegido(cb))}</div>`;
  }
  const porCamion = {};
  for (const f of cb.filas) (porCamion[f.camion] = porCamion[f.camion] || []).push(f);
  const pct = x => (100 * x).toFixed(1) + '%';
  const camiones = cb.camiones.map(c => {
    const fs = porCamion[c.numero] || [];
    const ocup = fs.length ? fs[fs.length - 1].ocup_acum : 0;
    return `<article class="ent">
      <div class="top"><div><span class="id">Camión ${c.numero}</span> <span class="tag">${esc(c.tipo)}</span>
        <span class="tag ${fs[0] && fs[0].tipo_carga === 'Mono-pedido' ? 'green' : 'amber'}">${esc(fs[0] ? fs[0].tipo_carga : '')}</span></div>
        <div class="num" style="font-size:19px">${fmt(fs.reduce((a, f) => a + f.unidades, 0))} <span class="muted small">un. · ${pct(ocup)} ocupado</span></div></div>
      <div class="meta" style="margin-top:4px"><span>${fmt(c.L)} × ${fmt(c.w)} × ${fmt(c.h)} cm</span><span>Capacidad <b>${c.vol_m3.toFixed(2)} m³</b></span>
        <span>Libre <b>${(fs.length ? fs[fs.length - 1].libre_m3 : c.vol_m3).toFixed(2)} m³</b></span></div>
      <div class="scroll" style="margin-top:8px"><table class="t"><thead><tr>${fs.some(f => f.sucursal) ? '<th>Sucursal</th>' : ''}<th>SKU</th><th>Descripción</th><th class="n">Unidades</th></tr></thead><tbody>
        ${fs.map(f => `<tr>${fs.some(x => x.sucursal) ? `<td>${esc(f.sucursal)}</td>` : ''}<td class="num">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td><td class="n">${fmt(f.unidades)}</td></tr>`).join('')}
      </tbody></table></div></article>`;
  }).join('');
  const problemas = [
    ...(cb.sin_medidas || []).map(x => `<span class="tag red">Sin medidas: ${esc(x)}</span>`),
    ...(cb.no_encontrados || []).map(x => `<span class="tag red">Sin descripción: ${esc(x)}</span>`),
    ...Object.entries(cb.sin_ubicar || {}).map(([k, v]) => `<span class="tag red">No cupo: ${esc(k)} (${fmt(v)})</span>`),
  ].join(' ');
  return `<div class="row" style="justify-content:space-between;margin-bottom:10px">
      <div class="small muted">Cubicaje ${esc(cb.modo)} del ${fmtFecha(cb.generado)} · pallet del cliente ${cb.pallet.join(' × ')} cm</div>
      ${cb.visor ? `<div class="row"><button class="btn" data-act="ensayoEntregas" title="Recorre VL01N sin guardar, para revisar antes de crear">Ensayo en SAP</button>
        <button class="btn primary" data-act="crearEntregas" title="Crea una entrega por camión en VL01N">Crear entregas en SAP</button>
        <a class="btn ghost" href="/api/cubicaje/${encodeURIComponent(p.pedido)}/excel">Exportar a Excel</a>
        <button class="btn primary" data-act="verVisorCub">${UI.verVisorCub ? 'Ocultar visor 3D' : 'Ver visor 3D aquí'}</button>
        <a class="btn" href="${esc(cb.visor)}" target="_blank" rel="noopener">Abrir en otra pestaña</a></div>` : ''}</div>
    ${cb.visor && UI.verVisorCub ? `<iframe src="${esc(cb.visor)}" title="Visor 3D del pedido ${esc(p.pedido)}" style="width:100%;height:640px;border:1px solid var(--line);border-radius:8px;margin-bottom:14px;background:#fff"></iframe>` : ''}
    <div class="legend" style="margin:0 0 12px">
      <div>Camiones<b>${cb.camiones.length}</b></div><div>Unidades<b>${fmt(cb.unidades)}</b></div>
      <div>SKU<b>${new Set(cb.filas.map(f => f.sku)).size}</b></div>
      ${(cb.pallets_detalle || []).length ? `<div>Pallets<b>${cb.pallets_detalle.length}</b></div>` : ''}
      ${(cb.filas04 || []).some(f => f.tipo === 'Piso') ? `<div>A piso<b>${fmt(cb.filas04.filter(f => f.tipo === 'Piso').reduce((a, f) => a + f.unidades, 0))}</b></div>` : ''}</div>
    ${form}
    ${seccionPredist(p, modoElegido(cb))}
    ${problemas ? `<p class="small" style="margin-top:10px">${problemas}</p>` : ''}
    ${(cb.avisos || []).map(a => `<p class="small"><span class="tag amber">Aviso</span> ${esc(a)}</p>`).join('')}
    <div style="margin-top:12px">${camiones}</div>
    ${(cb.filas04 || []).length ? `<div class="panel" style="margin-top:14px"><div class="panel-h"><h3>Detalle por pallet</h3></div><div class="panel-b">
      <div class="scroll"><table class="t"><thead><tr><th class="n">Camión</th><th>Tipo vehículo</th><th class="n">Pallet</th>
        ${cb.filas04.some(f => f.sucursal) ? '<th>Sucursal</th>' : ''}<th>SKU</th><th>Descripción</th>
        <th class="n">Cajas</th><th class="n">Bultos</th><th class="n">Unidades</th><th>Tipo</th></tr></thead><tbody>
        ${cb.filas04.map(f => `<tr><td class="n">${f.vehiculo}</td><td>${esc(f.tipo_vehiculo)}</td>
          <td class="n">${f.pallet || '—'}</td>${cb.filas04.some(x => x.sucursal) ? `<td>${esc(f.sucursal)}</td>` : ''}
          <td class="num">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td><td class="n">${fmt(f.cajas)}</td>
          <td class="n">${fmt(f.bultos)}</td><td class="n">${fmt(f.unidades)}</td>
          <td><span class="tag ${f.tipo === 'Piso' ? 'amber' : ''}">${esc(f.tipo)}</span></td></tr>`).join('')}
      </tbody></table></div></div></div>` : ''}`;
}

function descDe(ped, sku){ const p = Store.get('pedidos', safeId(ped)); const l = p && (p.lineas || []).find(x => normSku(x.sku) === normSku(sku)); return l ? l.desc : ''; }
