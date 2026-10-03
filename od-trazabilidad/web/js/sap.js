/* Acciones en SAP, clientes, Base de Medidas y archivos.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Acciones en SAP (todo nativo: la plataforma no abre Excel) ============ */
function estadoJob(){
  const j = UI.job; if (!j) return '';
  if (j.estado === 'en_curso') return `<p class="small"><span class="tag warn">En curso</span> ${esc(j.label)}${j.progreso ? ' · <b>' + esc(j.progreso) + '</b>' : ''} desde ${esc(j.inicio.slice(11, 16))}. ${['analizar_pedido','sap_leer_pedido'].includes(j.accion) ? 'No uses el mouse ni el teclado sobre SAP hasta que termine.' : 'Si Excel muestra un mensaje, ciérralo para que termine.'}</p>`;
  if (j.estado === 'ok') return `<p class="small"><span class="tag ok">Listo</span> ${esc(j.label)}: ${esc(j.archivo ? 'archivo guardado en el pedido' : j.resultado || 'terminó')}</p>`;
  return `<p class="small"><span class="tag err">Error</span> ${esc(j.label)}: ${esc(j.error)}</p>`;
}
async function seguirJob(){
  while (UI.job && UI.job.estado === 'en_curso'){
    await new Promise(r => setTimeout(r, 1500));
    try { UI.job = await api('GET', '/acciones/trabajos/' + UI.job.id); } catch(e){ break; }
    render();
  }
  render();
  if (UI.job && UI.job.estado === 'ok') await Store.refresh();
  else if (UI.job && UI.job.estado === 'error') toast(UI.job.error);
}
function abrirLecturaSap(modo){
  const p = UI.sel && Store.get('pedidos', UI.sel);
  const cfg = config();
  const analizar = modo === 'analizar';
  abrirDlg(analizar ? 'Analizar pedido (VL01N + ZSD001_03 + MMBE)' : 'Leer pedido desde SAP (directo, sin Excel)', `
    <p style="margin-top:0" class="small">${analizar
      ? 'Hace en un solo paso lo del botón 01 del Excel: lee el pedido en VL01N, trae la Qty en entrega de ZSD001_03, calcula saldo SOP, carga y alertas, y consulta MMBE solo para los SKU con alerta. Sin mensajes que aceptar.'
      : 'Abre VL01N con tu sesión de SAP y trae las posiciones del pedido.'} <b>Solo lee</b>: no crea ni modifica nada en SAP. Mientras corre, no uses el mouse ni el teclado sobre SAP.</p>
    <div class="fgrid">
      <label class="f">N° de pedido<input type="text" name="lsPedido" value="${esc(p ? p.pedido : '')}"></label>
      <label class="f">…o la orden de compra<input type="text" name="lsOc" placeholder="OC del cliente y Enter"></label>
      <label class="f">Puesto de expedición<input type="text" name="lsPuesto" value="${esc(cfg.puesto || 'PN01')}"></label>
      <label class="f">Fecha de picking<input type="date" name="lsFecha" value="${new Date().toISOString().slice(0,10)}"></label>
      <label class="f">Cliente<input type="text" name="lsCliente" list="dl-cli2" value="${esc(p ? p.cliente : (UI.cliente || 'PARIS'))}"></label>
    </div>
    <datalist id="dl-cli2">${[...new Set([...clientes(), 'PARIS', 'HITES'])].map(c => `<option value="${esc(c)}">`).join('')}</datalist>`,
    `<button class="btn primary" data-act="${analizar ? 'analizarSap' : 'leerSap'}">${analizar ? 'Analizar' : 'Leer desde SAP'}</button>`);
}
async function analizarSap(){
  const body = {puesto:dval('lsPuesto').toUpperCase(), fecha:dval('lsFecha'), cliente:dval('lsCliente')};
  const pedido = dval('lsPedido');
  if (!pedido) return dErr('Ingresa el N° de pedido.');
  if (!body.cliente) return dErr('Ingresa el cliente.');
  dlg.close();
  const cfg = clone(config()); if (cfg.puesto !== body.puesto){ cfg.puesto = body.puesto; save('config', 'app', cfg); }
  await lanzarAnalisis(pedido, body);
}
async function lanzarAnalisis(pedido, body){
  try { UI.job = await api('POST', `/analisis/${encodeURIComponent(pedido)}`, body); render(); }
  catch(e){ toast(e.message); return; }
  await seguirJob();
  if (UI.job && UI.job.estado === 'ok' && UI.job.datos){
    const d = UI.job.datos;
    UI.job.resultado = `${d.posiciones} productos analizados · ${d.limitadas} limitados por el plan · ${d.alertadas} con alerta`;
    if (d.aviso_sap) toast(d.aviso_sap);
    delete UI.analisis[d.pedido]; delete UI.cubicaje[d.pedido]; UI.autoCub[d.pedido] = false;
    UI.sel = safeId(d.pedido); UI.sub = 'analisis'; UI.view = 'pedidos';
    render();
  }
}

/* ---- Pestaña Análisis (igual a la hoja 02_Posiciones) ---- */
UI.analisis = {};
async function cargarAnalisis(pedido){
  UI.analisis[pedido] = {cargando:true}; render();
  try { UI.analisis[pedido] = await api('GET', `/analisis/${encodeURIComponent(pedido)}`); }
  catch(e){ UI.analisis[pedido] = {error:e.message}; }
  render();
}
async function ajustarCarga(pedido, sku, valor){ return ajustarLote(pedido, {[sku]: valor === '' ? null : valor}); }
async function ajustarLote(pedido, ajustes){
  try {
    const r = await api('PUT', `/analisis/${encodeURIComponent(pedido)}/carga`, {ajustes});
    UI.analisis[pedido] = r;
    if (r.cubicaje) UI.cubicaje[pedido] = r.cubicaje;      // cubicaje y visor en vivo
    render();
    Store.refresh();
  } catch(e){ toast(e.message); render(); }
}
const TAG_ALERTA = {'Sin stock':'err', 'Stock parcial':'warn', 'Limitado SOP':'warn', 'Completo':'ok'};
const PIP_ALERTA = {'Sin stock':'err', 'Stock parcial':'warn', 'Limitado SOP':'lim', 'Completo':'ok'};
const ICONO_ALERTA = Object.fromEntries(Object.entries(PIP_ALERTA).map(([k, t]) => [k, `<span class="pip ${t}"></span>`]));
/* Lo primero que se ve al analizar: qué productos limitó el plan SOP y si se puede exceder */
function avisosAnalisis(p, a, r){
  const out = [];
  if ((a.cliente || '').toUpperCase() !== (p.cliente || '').toUpperCase())
    out.push(`<div class="aviso warn"><div><b>Este análisis es de ${esc(a.cliente)}, pero el pedido ahora es de ${esc(p.cliente || 'sin cliente')}.</b>
      El plan SOP, lo facturado y la Qty en entrega siguen siendo los del cliente anterior.</div>
      <button class="btn primary sm" data-act="reanalizarCliente">Analizar con ${esc(p.cliente || 'el cliente')}</button></div>`);
  const lim = r.filas.filter(f => f.carga_calculada < f.qty_entrega);
  if (!lim.length){
    out.push(`<div class="aviso ok"><div><b>El plan SOP cubre todo lo pedido.</b> Se carga lo que pide el pedido, sin recortes.</div></div>`);
  } else {
    const pedidas = lim.reduce((x, f) => x + f.qty_entrega, 0), limite = lim.reduce((x, f) => x + f.carga_calculada, 0);
    const cargadas = lim.reduce((x, f) => x + f.carga, 0);
    const recortadas = lim.filter(f => f.carga < f.qty_entrega);
    out.push(`<div class="aviso warn"><div><b>El plan SOP limita ${lim.length} producto${lim.length === 1 ? '' : 's'}.</b>
      Se piden <b class="num">${fmt(pedidas)}</b> un. y el saldo del plan deja <b class="num">${fmt(limite)}</b>${cargadas > limite ? `; con la autorización, la carga queda en <b class="num">${fmt(cargadas)}</b>` : ': la carga ya está recortada a ese saldo'}.
      Si tienes autorización para exceder el plan, súbela por producto en la columna Carga o para todos a la vez.</div>
      <div class="row tight">${recortadas.length ? '<button class="btn sm" data-act="autorizarExceso">Autorizar exceder el plan</button>' : ''}
        ${cargadas > limite ? '<button class="btn sm" data-act="limitarAlPlan">Volver al límite del plan</button>' : ''}</div></div>`);
  }
  return out.join('');
}
function vistaAnalisis(p){
  const a = UI.analisis[p.pedido];
  if (!a) { setTimeout(() => cargarAnalisis(p.pedido), 0); return '<p class="small muted">Cargando análisis…</p>'; }
  if (a.cargando) return '<p class="small muted">Cargando análisis…</p>';
  if (a.error) return `<div class="empty"><h3>Este pedido todavía no tiene análisis</h3>
    <p>El análisis hace en un clic lo del botón 01 del Excel: VL01N, Qty en entrega, saldo SOP, alertas y stock MMBE.</p>
    <button class="btn primary" data-act="abrirAnalisis">Analizar pedido</button></div>`;
  const r = a.resultado, pct = x => x == null ? '—' : (100 * x).toFixed(1) + '%';
  let prev = '';
  const filas = r.filas.map(f => {
    const corte = f.alerta !== prev; prev = f.alerta;
    const st = f.stock || {};
    const aut = (a.autorizaciones || {})[f.sku], limitada = f.carga_calculada < f.qty_entrega && !aut && f.carga < f.qty_entrega;
    return `<tr class="${corte ? 'corte' : ''} ${limitada ? 'limitada' : ''}">
      <td><span class="tag ${TAG_ALERTA[f.alerta]}">${ICONO_ALERTA[f.alerta]} ${esc(f.alerta)}</span></td>
      <td class="num">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td>
      <td class="n">${fmt(f.qty_entrega)}</td><td class="n">${fmt(f.pendiente)}</td>
      <td class="n">${fmt(f.plan)}</td><td class="n">${fmt(f.real)}</td><td class="n">${fmt(f.en_entrega)}</td>
      <td class="n"><b${f.saldo < f.pendiente ? ' class="warn-t"' : ''}>${fmt(f.saldo)}</b></td>
      <td class="n"><input class="qty" type="number" min="0" step="1" value="${Math.round(f.carga)}" data-carga="${esc(f.sku)}" aria-label="Carga ${esc(f.sku)}" style="width:80px${f.ajustada ? ';border-color:var(--accent);font-weight:600' : ''}">
        ${f.ajustada ? `<button class="btn quiet sm" data-act="resetCarga" data-sku="${esc(f.sku)}" title="Volver a ${fmt(f.carga_calculada)} (calculado)" aria-label="Volver al valor calculado">${ICON.undo}</button>` : ''}
        ${aut ? `<span class="tag ink" title="Superó el plan SOP (calculado ${fmt(aut.calculada)}). Autorizó ${esc(aut.por)} el ${esc(aut.at.slice(0, 16).replace('T', ' '))}">Autorizado · ${esc(aut.por)}</span>` : ''}
        ${limitada ? `<span class="tag warn" title="El pedido pide ${fmt(f.qty_entrega)} y el saldo del plan deja ${fmt(f.carga_calculada)}">de ${fmt(f.qty_entrega)}</span>` : ''}</td>
      <td class="n">${pct(f.ocupacion)}</td><td class="n">${pct(f.acumulado)}</td>
      <td class="small">${esc(f.disponibilidad)}</td>
      <td class="n">${f.stock ? fmt(st.cd30) : ''}</td><td class="n">${f.stock ? fmt(st.reserva_cd30) : ''}</td>
      <td class="n">${f.stock ? fmt(st.ec01) : ''}</td><td class="n">${f.stock ? fmt(st.tp01) : ''}</td></tr>`;
  }).join('');
  const cuenta = k => r.filas.filter(f => f.alerta === k).length;
  return `${avisosAnalisis(p, a, r)}<div class="row" style="justify-content:space-between;margin-bottom:10px">
      <div class="small muted">Análisis del ${fmtFecha(a.generado)} · cliente ${esc(a.cliente)} · grupo SOP ${esc(a.grupo_sop)} · puesto ${esc(a.puesto)} · Saldo SOP = plan − real − Qty en entrega (igual que el Excel)</div>
      <div class="row tight"><button class="btn" data-act="abrirAnalisis">Volver a analizar</button>
        <button class="btn primary" data-flujo="cubicaje">Continuar a cubicaje</button></div></div>
    <div class="legend" style="margin:0 0 12px">
      <div>Ocupación total<b>${pct(r.ocupacion_total)}</b></div>
      <div>Carga total<b>${fmt(r.filas.reduce((s, f) => s + f.carga, 0))}</b></div>
      ${['Sin stock','Stock parcial','Limitado SOP','Completo'].map(k => `<div>${ICONO_ALERTA[k]} ${k}<b>${cuenta(k)}</b></div>`).join('')}
    </div>
    <div class="scroll"><table class="tbl"><thead><tr>
      <th>Alerta</th><th>SKU</th><th>Descripción</th><th class="n">Qty entrega</th><th class="n">Pendiente</th>
      <th class="n">Plan SOP</th><th class="n">Real</th><th class="n">En entrega</th><th class="n">Saldo SOP</th>
      <th class="n">Carga</th><th class="n">% ocup.</th><th class="n">Acumulado</th><th>Disponibilidad</th>
      <th class="n">Stock CD30</th><th class="n">Reserva CD30</th><th class="n">Stock EC01</th><th class="n">Stock TP01</th>
    </tr></thead><tbody>${filas}</tbody></table></div>
    <p class="small muted">La <b>Carga</b> se puede ajustar a mano: escribe la cantidad y presiona Enter o sal del campo. El botón de deshacer la devuelve al valor calculado. Subirla por sobre el plan SOP queda registrado a tu nombre.</p>`;
}
async function buscarPorOc(valor){
  if (!valor) return;
  const campo = dlg.querySelector('[name="lsPedido"]');
  try {
    const r = await api('GET', '/pedidos-sap?q=' + encodeURIComponent(valor));
    if (!r.ok) return dErr('No se pudo consultar los pedidos ingresados: ' + r.error);
    if (!r.resultados.length) return dErr(`No se encontró un pedido con la OC ${valor}.`);
    if (r.resultados.length > 1) return dErr(`Hay ${r.resultados.length} pedidos con esa OC: ` +
      r.resultados.slice(0, 5).map(x => x.pedido).join(', '));
    campo.value = r.resultados[0].pedido;
    dErr('');
  } catch(e){ dErr(e.message); }
}
async function leerSap(){
  const body = {pedido:dval('lsPedido'), puesto:dval('lsPuesto').toUpperCase(), fecha:dval('lsFecha'), cliente:dval('lsCliente')};
  if (!body.pedido) return dErr('Ingresa el N° de pedido.');
  dlg.close();
  const cfg = clone(config()); if (cfg.puesto !== body.puesto){ cfg.puesto = body.puesto; save('config', 'app', cfg); }
  try { UI.job = await api('POST', '/sap/leer_pedido', body); render(); }
  catch(e){ toast(e.message); return; }
  await seguirJob();
  if (UI.job && UI.job.estado === 'ok' && UI.job.datos){
    const d = UI.job.datos;
    UI.job.resultado = `${d.posiciones} productos leídos · ${d.agregadas} nuevos · ${d.actualizadas} actualizados`;
    UI.sel = safeId(d.pedido); UI.sub = 'pendientes'; UI.view = 'pedidos';
    render();
  }
}

function seccionAcciones(){
  const ocupado = UI.job && UI.job.estado === 'en_curso' ? 'disabled' : '';
  return `<div class="panel" style="margin-bottom:20px"><div class="panel-h"><h2>SAP y bases</h2></div><div class="panel-b">
    <p style="margin-top:0;max-width:72ch"><b>Analizar pedido</b> lee el pedido en VL01N, trae la Qty en entrega de ZSD001_03, calcula el saldo SOP y la carga, y consulta MMBE solo para los productos con alerta. Todo desde la plataforma: no abre Excel. Solo lee.</p>
    <div class="row"><button class="btn primary" data-act="abrirAnalisis" ${ocupado}>Analizar pedido</button>
    <button class="btn" data-act="abrirLecturaSap" ${ocupado}>Solo leer VL01N</button>
    <button class="btn" data-act="actualizarBases" title="Vuelve a consultar el plan de ventas y los saldos en SQL Server">Actualizar bases</button></div>
    ${estadoJob()}</div></div>`;
}

/* ============ Clientes y sus reglas de cubicaje ============ */
UI.clientes = null; UI.cliEdit = null;
async function cargarClientes(){
  try { UI.clientes = (await api('GET', '/clientes')).filas; }
  catch(e){ UI.clientes = []; toast(e.message); }
  render();
}
async function guardarCliente(nombre, datos){
  try {
    await api('PUT', '/clientes/' + encodeURIComponent(nombre), datos);
    UI.cliEdit = null; await cargarClientes(); toast('Cliente guardado');
  } catch(e){ toast(e.message); }
}
function seccionClientes(){
  const cs = UI.clientes;
  if (!cs) setTimeout(cargarClientes, 0);
  const filas = cs || [];
  const ed = UI.cliEdit;
  return `<div class="panel" style="margin-bottom:20px"><div class="panel-h" style="justify-content:space-between">
      <h2>Clientes y reglas de cubicaje</h2>
      <div class="row"><span class="small muted">${filas.length} clientes</span>
        <button class="btn" data-act="nuevoCliente">Agregar cliente</button></div>
    </div><div class="panel-b">
    <p style="margin-top:0;max-width:72ch">Cada cliente tiene su pallet, su grupo SOP, su código de solicitante y sus reglas: separar calefones en camiones aparte (HITES) o mandar los conchos a piso en vez de armar pallets mix (SODIMAC, RIPLEY).</p>
    ${ed ? `<div class="panel" style="margin-bottom:12px"><div class="panel-b">
      <div class="fgrid">
        <label class="f">Cliente<input type="text" name="cliNombre" value="${esc(ed.nombre || '')}" ${ed.nuevo ? '' : 'readonly'}></label>
        <label class="f">Grupo SOP<input type="text" name="cliGrupo" value="${esc(ed.grupo_sop || '')}"></label>
        <label class="f">Código solicitante<input type="text" name="cliCodigo" value="${esc(ed.codigo || '')}"></label>
        <label class="f">Canal<input type="text" name="cliCanal" value="${esc(ed.canal || 'RETAIL')}"></label>
        <label class="f">Región<input type="text" name="cliRegion" value="${esc(ed.region || 'RM')}"></label>
        <label class="f">Pallet largo<input type="number" step="1" name="cliPL" value="${(ed.pallet || [120,100,140])[0]}"></label>
        <label class="f">Pallet ancho<input type="number" step="1" name="cliPW" value="${(ed.pallet || [120,100,140])[1]}"></label>
        <label class="f">Pallet alto<input type="number" step="1" name="cliPH" value="${(ed.pallet || [120,100,140])[2]}"></label>
        <label class="f">Caja master por defecto<select name="cliCM"><option value=""></option>
          <option ${ed.caja_master === 'CON CAJA MASTER' ? 'selected' : ''}>CON CAJA MASTER</option>
          <option ${ed.caja_master === 'SIN CAJA MASTER' ? 'selected' : ''}>SIN CAJA MASTER</option></select></label>
      </div>
      <div class="row" style="margin-top:10px">
        <label class="row small"><input type="checkbox" name="cliCalefon" ${ed.calefon_aparte ? 'checked' : ''}> Calefones en camión aparte</label>
        <label class="row small"><input type="checkbox" name="cliHibrido" ${ed.hibrido ? 'checked' : ''}> Conchos a piso (sin pallets mix)</label>
      </div>
      <label class="f" style="margin-top:10px">Notas<input type="text" name="cliNotas" value="${esc(ed.notas || '')}"></label>
      <div class="row" style="margin-top:10px"><button class="btn primary" data-act="guardarCliente">Guardar</button>
        <button class="btn quiet" data-act="cancelarCliente">Cancelar</button></div>
    </div></div>` : ''}
    <div class="scroll"><table class="tbl"><thead><tr><th>Cliente</th><th>Grupo SOP</th><th>Código</th>
      <th>Pallet (L × A × Alto)</th><th>Caja master</th><th>Reglas</th><th></th></tr></thead><tbody>
      ${filas.map(f => `<tr><td><b>${esc(f.nombre)}</b></td><td>${esc(f.grupo_sop)}</td><td class="num">${esc(f.codigo)}</td>
        <td class="num">${f.pallet.map(x => fmt(x)).join(' × ')}</td><td class="small">${esc(f.caja_master || '—')}</td>
        <td>${f.calefon_aparte ? '<span class="tag">calefones aparte</span> ' : ''}${f.hibrido ? '<span class="tag">conchos a piso</span>' : ''}</td>
        <td><button class="btn quiet sm" data-act="editarCliente" data-nombre="${esc(f.nombre)}">Editar</button></td></tr>`).join('')}
    </tbody></table></div>
  </div></div>`;
}

/* ============ Base de Medidas cargada en la plataforma ============ */
UI.medidas = null; UI.medidasBuscar = '';
async function cargarMedidas(){
  try { UI.medidas = await api('GET', '/medidas' + (UI.medidasBuscar ? `?buscar=${encodeURIComponent(UI.medidasBuscar)}` : '')); }
  catch(e){ UI.medidas = {error:e.message, filas:[]}; }
  render();
}
async function importarMedidas(input){
  const f = input.files[0]; if (!f) return;
  const fd = new FormData(); fd.append('file', f);
  toast('Cargando medidas…');
  try {
    const r = await fetch('/api/medidas/importar', {method:'POST', body:fd});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'No se pudo importar');
    toast(`${d.nuevos} nuevos · ${d.actualizados} actualizados · ${d.sin_cambios} sin cambios`);
    UI.medidas = null; await cargarMedidas();
  } catch(e){ toast(e.message); }
}
function seccionMedidas(){
  const m = UI.medidas;
  if (!m) setTimeout(cargarMedidas, 0);
  const filas = (m && m.filas) || [];
  return `<div class="panel" style="margin-bottom:20px"><div class="panel-h" style="justify-content:space-between">
      <h2>Base de Medidas</h2>
      <div class="small muted">${m ? `${fmt(m.productos)} productos${m.ultima_carga ? ' · última carga ' + fmtFecha(m.ultima_carga.slice(0,10)) : ''}` : 'Cargando…'}</div>
    </div><div class="panel-b">
    <p style="margin-top:0;max-width:72ch">El cubicaje usa estas medidas. Sube <b>Base de Medidas.xlsm</b> cuando cambie: agrega los productos nuevos, actualiza los que cambiaron y deja el resto igual. Si un producto aparece repetido, manda el primero, como en el Excel.</p>
    <div class="row">
      <label class="btn primary">Cargar archivo de medidas<input type="file" accept=".xlsm,.xlsx" data-medidas style="display:none"></label>
      <input type="search" placeholder="Buscar SKU o descripción y Enter" value="${esc(UI.medidasBuscar)}" data-buscarmed style="min-width:220px">
    </div>
    ${m && m.error ? `<p class="small"><span class="tag err">Error</span> ${esc(m.error)}</p>` : ''}
    ${filas.length ? `<div class="scroll" style="margin-top:12px"><table class="tbl"><thead><tr><th>SKU</th><th>Descripción</th>
      <th class="n">Largo</th><th class="n">Ancho</th><th class="n">Alto</th><th class="n">Peso</th>
      <th>Apilar</th><th>Inclinar</th><th>Rotar</th><th class="n">Máx camión</th><th class="n">Máx pallet</th></tr></thead><tbody>
      ${filas.map(f => `<tr><td class="num">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td>
        <td class="n">${f.largo}</td><td class="n">${f.ancho}</td><td class="n">${f.alto}</td><td class="n">${f.peso}</td>
        <td>${esc(f.apilar)}</td><td>${esc(f.inclinar)}</td><td>${esc(f.rotar)}</td>
        <td class="n">${fmt(f.max_camion)}</td><td class="n">${fmt(f.max_pallet)}</td></tr>`).join('')}
    </tbody></table></div>${filas.length >= 50 ? '<p class="small muted">Se muestran los primeros 50. Usa el buscador para encontrar un producto.</p>' : ''}`
    : (m && !m.error ? '<p class="small muted" style="margin-top:12px">Todavía no hay medidas cargadas.</p>' : '')}
  </div></div>`;
}

/* ============ Archivos (visor 3D y PDFs) ============ */
function archivosDe(pedido, grupo){
  return (Store.archivos || []).filter(a => (grupo ? a.grupo === grupo : a.pedido === pedido && !a.grupo));
}
UI.verArchivo = null;
function listaArchivos(pedido, grupo){
  const arch = archivosDe(pedido, grupo);
  const camiones = grupo ? [] : gruposDe(pedido).filter(g => !g.sinGrupo);
  const visible = arch.find(a => a.id === UI.verArchivo);
  return `<div class="row" style="margin-top:10px;gap:8px">
    ${arch.map(a => `<span class="tag">${a.tipo === 'visor' ? ICON.cube : ICON.file} <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.nombre)}</a>
      <button class="btn quiet sm" data-act="verArchivo" data-id="${a.id}" style="padding:0 4px">${UI.verArchivo === a.id ? 'Ocultar' : 'Ver aquí'}</button>
      ${camiones.length ? `<select data-asignar="${a.id}" aria-label="Asignar a camión" style="padding:1px 4px;font-size:12px"><option value="">Asignar a camión…</option>${camiones.map(g => `<option value="${esc(g.grupo)}">Grupo ${esc(g.grupo)}</option>`).join('')}</select>` : ''}
      ${grupo ? `<button class="btn quiet sm" data-act="desasignar" data-id="${a.id}" title="Volver al pedido" aria-label="Volver al pedido">${ICON.undo}</button>` : ''}
      <button class="btn quiet sm" data-act="borrarArchivo" data-id="${a.id}" title="Quitar" aria-label="Quitar archivo">${ICON.x}</button></span>`).join('') || '<span class="small muted">Sin archivos</span>'}
    <label class="btn quiet sm">Subir PDF<input type="file" accept=".pdf,.png,.jpg,.html" data-subir data-pedido="${esc(pedido)}" data-grupo="${esc(grupo || '')}" style="display:none"></label>
  </div>
  ${visible ? `<iframe src="${esc(visible.url)}" title="${esc(visible.nombre)}" style="width:100%;height:560px;border:1px solid var(--hair);border-radius:8px;margin-top:10px;background:#fff"></iframe>` : ''}`;
}
async function asignarArchivo(id, grupo){
  try { await api('PATCH', '/archivos/' + id, {grupo}); await Store.refresh(); toast(grupo ? `Asignado al grupo ${grupo}` : 'Devuelto al pedido'); }
  catch(e){ toast(e.message); }
}
async function subirArchivo(input){
  const f = input.files[0]; if (!f) return;
  const fd = new FormData();
  fd.append('file', f); fd.append('pedido', input.dataset.pedido || '');
  fd.append('grupo', input.dataset.grupo || ''); fd.append('tipo', f.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'adjunto');
  try {
    const r = await fetch('/api/archivos', {method:'POST', body:fd});
    if (!r.ok) throw new Error((await r.json()).detail || 'No se pudo subir');
    toast('Archivo guardado'); await Store.refresh();
  } catch(e){ toast(e.message); }
}

async function borrarArchivo(id){
  if (!await preguntar({titulo: 'Quitar archivo', texto: 'El archivo se quita del pedido.', ok: 'Quitar', peligro: true})) return;
  try { await api('DELETE', '/archivos/' + id); await Store.refresh(); toast('Archivo quitado'); }
  catch(e){ toast(e.message); }
}
async function plantilla(){
  if (!await asegurarXLSX()) return toast('No se pudo cargar el lector de Excel');
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['Pedido','OC','Cliente','Canal','Fecha OC','Material','Descripción','Cantidad']]), 'Pedidos');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['Entrega','Pedido','Grupo','Tipo','Material','Cantidad']]), 'Entregas');
  await descargar('plantilla_trazabilidad.xlsx', XLSX.write(wb, {bookType:'xlsx', type:'array'}));
}


/* ---- Conexión a SQL Server: cada quien la suya, desde la plataforma ---- */
UI.conexion = null;
async function cargarConexion(){
  try { UI.conexion = await api('GET', '/conexion'); } catch(e){ UI.conexion = {url:'', usuario:'', tiene_clave:false}; }
  render();
}
async function guardarConexion(){
  const v = n => (document.querySelector(`[name="${n}"]`) || {}).value || '';
  try {
    await api('PUT', '/conexion', {url: v('cxUrl').trim(), usuario: v('cxUsuario').trim(), clave: v('cxClave')});
    UI.conexion = null; await cargarConexion();
    toast('Conexión guardada');
  } catch(e){ toast(e.message); }
}
async function probarConexion(){
  UI.cxProbando = true; render();
  try {
    const r = await api('POST', '/conexion/probar');
    UI.cxResultado = r;
  } catch(e){ UI.cxResultado = {ok:false, mensaje:e.message}; }
  UI.cxProbando = false; render();
}
function seccionConexion(){
  const cx = UI.conexion;
  if (!cx) { setTimeout(cargarConexion, 0); return ''; }
  const r = UI.cxResultado;
  return `<div class="panel" style="margin-bottom:20px"><div class="panel-h"><h2>Conexión a las bases (SQL Server)</h2></div><div class="panel-b">
    <p style="margin-top:0;max-width:72ch">De aquí salen el plan SOP, la disponibilidad y los pedidos ingresados. Si dejas el usuario en blanco, la plataforma entra con tu cuenta de Windows. Estos datos quedan <b>solo en este equipo</b>: no se comparten ni viajan a ningún lado.</p>
    <div class="fgrid">
      <label class="f" style="grid-column:1 / -1">Servidor y base
        <input type="text" name="cxUrl" value="${esc(cx.url || '')}" placeholder="mssql+pyodbc://clws0156/161221_TS_ODS?driver=ODBC+Driver+17+for+SQL+Server&amp;trusted_connection=yes&amp;TrustServerCertificate=yes"></label>
      <label class="f">Usuario de SQL Server<input type="text" name="cxUsuario" value="${esc(cx.usuario || '')}" placeholder="vacío = cuenta de Windows"></label>
      <label class="f">Clave<input type="password" name="cxClave" placeholder="${cx.tiene_clave ? 'guardada · escribe solo si la cambias' : 'sin clave'}"></label>
    </div>
    <div class="row" style="margin-top:10px">
      <button class="btn primary" data-act="guardarConexion">Guardar</button>
      <button class="btn" data-act="probarConexion" ${UI.cxProbando ? 'disabled' : ''}>${UI.cxProbando ? 'Probando…' : 'Probar conexión'}</button>
      ${cx.desde_env ? '<span class="tag">viene del archivo .env</span>' : ''}
      ${cx.tiene_clave ? '<span class="tag ok">clave guardada</span>' : ''}
    </div>
    ${r ? `<p class="small"><span class="tag ${r.ok ? 'ok' : 'err'}">${r.ok ? 'Conecta' : 'No conecta'}</span> ${esc(r.mensaje)}</p>` : ''}
  </div></div>`;
}

/* ============ Vista: Configuración ============
   Lo que antes estaba mezclado en "SAP y archivos": clientes, medidas y ajustes. */
function vistaConfiguracion(){
  return `<div class="panel" style="margin-bottom:20px"><div class="panel-b">
      <h2 style="margin:0 0 6px">Configuración</h2>
      <p class="small muted" style="margin:0;max-width:72ch">Los datos que usa el cubicaje y el análisis: las reglas de cada cliente y la Base de Medidas. Se cargan una vez y quedan guardados.</p>
    </div></div>` + seccionConexion() + seccionClientes() + seccionMedidas();
}
