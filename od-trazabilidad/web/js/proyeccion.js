/* Vistas de Proyección y de SAP y archivos.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Vista: Proyección ============ */
function camiones(){
  const out = new Map();
  for (const e of Store.list('entregas')){
    if (e.anulada || !e.cita || !e.cita.fecha) continue;
    if (e.cita.fecha < UI.pDesde || (UI.pHasta && e.cita.fecha > UI.pHasta)) continue;
    const conf = pasoOk(e, 'confirmada'); if (!conf && !UI.pPorConf) continue;
    const key = e.cita.numero ? 'C' + e.cita.numero : 'G' + (e.grupo || e.entrega);
    const p = Store.get('pedidos', safeId(e.pedido)) || {};
    const t = out.get(key) || {key, fecha:e.cita.fecha, hora:e.cita.hora || '', cliente:p.cliente || '', canal:p.canal || '', region:e.region || '',
      vehiculo:e.vehiculo || '', carga:e.carga || '', un:e.un || '', qty:0, grupos:new Set(), ents:[], conf:true, cita:e.cita.numero || ''};
    t.qty += unidades(e); if (e.grupo) t.grupos.add(e.grupo); t.ents.push(e); t.conf = t.conf && conf;
    out.set(key, t);
  }
  return [...out.values()].sort((a,b) => (a.fecha + a.hora).localeCompare(b.fecha + b.hora));
}
function vistaProyeccion(){
  const cams = camiones(); const cfg = config();
  return `<div class="panel"><div class="panel-h" style="justify-content:space-between">
    <h2>Proyección de despacho</h2>
    <div class="row">
      <label class="f">Analista<input type="text" data-analista value="${esc(cfg.analista || '')}" placeholder="Tu nombre como en 2026.xlsx"></label>
      <label class="f">Desde<input type="date" data-pdesde value="${UI.pDesde}"></label>
      <label class="f">Hasta<input type="date" data-phasta value="${UI.pHasta}"></label>
      <label class="row small" style="align-self:flex-end;margin-bottom:8px"><input type="checkbox" data-pporconf ${UI.pPorConf ? 'checked' : ''}> Incluir por confirmar</label>
    </div></div>
    <div class="panel-b">
    ${cams.length ? `<p class="small muted" style="margin-top:0">Un camión = entregas con el mismo N° de cita (o el mismo grupo si no hay cita). Las columnas calzan con las hojas de 2026.xlsx para pegar directo.</p>
    <div class="scroll"><table class="t"><thead><tr><th>Fecha</th><th>Hora</th><th class="n">Sem.</th><th>Cliente</th><th>Región</th><th>Estado</th><th>Vehículo</th><th>Carga</th><th>UN</th><th class="n">QTY</th><th>Grupo(s)</th><th>Cita</th><th>Proyección</th></tr></thead><tbody>
    ${cams.map(t => { const cargado = t.ents.every(e => pasoOk(e, 'proyeccion'));
      return `<tr><td>${fmtFecha(t.fecha)}</td><td class="num">${esc(t.hora || '—')}</td><td class="n">${isoWeek(t.fecha)}</td><td>${esc(t.cliente)}</td><td>${esc(t.region)}</td>
      <td>${t.conf ? '<span class="tag green">Confirmado</span>' : '<span class="tag amber">Por confirmar</span>'} ${esc(ampm(t.hora))}</td>
      <td>${esc(t.vehiculo)}</td><td>${esc(t.carga)}</td><td>${esc(t.un)}</td><td class="n">${fmt(t.qty)}</td><td class="num">${esc([...t.grupos].join(', '))}</td><td class="num">${esc(t.cita)}</td>
      <td>${cargado ? '<span class="tag green">Cargado</span>' : '<span class="tag">Pendiente</span>'}</td></tr>`; }).join('')}
    </tbody></table></div>
    <div class="row" style="margin-top:14px"><button class="btn primary" data-act="exportProy">Descargar Excel para 2026.xlsx</button>
      <button class="btn" data-act="marcarProy">Marcar estos camiones como cargados en proyección</button></div>`
    : `<div class="empty"><h3>No hay camiones en este rango</h3><p>Aparecen aquí las entregas con fecha de cita. Ajusta el rango o agrega la fecha en la entrega.</p></div>`}
    </div></div>`;
}
const ampm = h => !h ? '' : (+h.split(':')[0] < 12 ? 'AM' : 'PM');

async function exportarProyeccion(){
  const cfg = config();
  const rows = camiones().map(t => {
    const am = ampm(t.hora) !== 'PM';
    return {'Fecha de Cita': new Date(t.fecha + 'T00:00:00'), 'Hora Cliente': t.hora || '', 'Semana': isoWeek(t.fecha), 'Analista': cfg.analista || '',
      'Cliente': t.cliente, 'Región': t.region,
      'Confirmado AM': t.conf && am ? 1 : '', 'Confirmado PM': t.conf && !am ? 1 : '',
      'Por Confirmar AM': !t.conf && am ? 1 : '', 'Por Confirmar PM': !t.conf && !am ? 1 : '',
      'Tipo Vehículo': t.vehiculo, 'Tipo Carga': t.carga, 'Unidad de Negocio': t.un, 'QTY': t.qty,
      'Grupo Optativo': [...t.grupos].join(', '), 'Canal': t.canal};
  });
  if (!rows.length) return toast('No hay camiones para exportar');
  const ws = XLSX.utils.json_to_sheet(rows, {cellDates:true, dateNF:'dd-mm-yyyy'});
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Proyección');
  await descargar(`proyeccion_${UI.pDesde}.xlsx`, XLSX.write(wb, {bookType:'xlsx', type:'array'}));
}
async function descargar(filename, arr){
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([arr], {type:'application/octet-stream'}));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  toast('Archivo descargado');
}
async function marcarProyeccion(){
  const ents = camiones().flatMap(t => t.ents).filter(e => !pasoOk(e, 'proyeccion'));
  if (!ents.length) return toast('Todos ya estaban cargados');
  for (const e of ents) await marcarPaso(safeId(e.entrega), 'proyeccion', true);
  toast(`${ents.length} entregas marcadas en proyección`);
}

/* ============ Vista: Importar ============ */
const ALIAS = {
  pedido:['pedido','docventas','documentodeventas','pedidosap','documentoventas'],
  oc:['oc','ordendecompra','pedidocliente','nrooc','noc','numerooc'],
  cliente:['cliente','solicitante','nombresolicitante','nombrecliente'],
  canal:['canal'],
  fechaOC:['fechaoc','fecharecepcion','fechapedido','creadoel'],
  sku:['material','sku','codigo','codmaterial','articulo'],
  desc:['descripcion','denominacion','textobreve','desc','textobrevedematerial'],
  qty:['cantidad','cantpedido','cantidadpedido','qty','ctdpedido','cantidadentrega','ctdentrega','unidades'],
  entrega:['entrega','nentrega','noentrega','nroentrega','numeroentrega'],
  grupo:['grupo','grupooptativo','nrogrupo'],
  tipo:['tipo','stockpredistribuido','modalidad'],
  cita:['cita','ncita','nrocita','nodecita','numerocita','referenciagrupo'],
  fechaCita:['fecha','fechacita'],
  horaCita:['hora','horacita'],
};
function mapCols(headers){
  const m = {}; const hs = headers.map(normH);
  for (const [k, al] of Object.entries(ALIAS)){ const i = hs.findIndex(h => al.includes(h)); if (i >= 0) m[k] = headers[i]; }
  return m;
}
function analizarLibro(wb){
  const res = {pedidos:new Map(), entregas:new Map(), errores:[], hojas:[]};
  for (const name of wb.SheetNames){
    const rows = XLSX.utils.sheet_to_json(wb.Sheets[name], {defval:'', raw:true});
    if (!rows.length) continue;
    const m = mapCols(Object.keys(rows[0]));
    const esEnt = !!m.entrega;
    const faltan = (esEnt ? ['entrega','pedido','sku','qty'] : ['pedido','sku','qty']).filter(k => !m[k]);
    if (faltan.length){ res.errores.push(`Hoja "${name}": faltan columnas ${faltan.join(', ')}.`); continue; }
    res.hojas.push(`${name} → ${esEnt ? 'entregas' : 'pedidos'} (${rows.length} filas)`);
    rows.forEach((r, i) => {
      const ped = String(r[m.pedido]).trim(), sku = normSku(r[m.sku]), qty = +String(r[m.qty]).replace(/\./g,'').replace(',','.');
      if (!ped || !sku){ return; }
      if (!isFinite(qty)){ res.errores.push(`Hoja "${name}", fila ${i + 2}: cantidad no numérica.`); return; }
      const desc = m.desc ? String(r[m.desc]).trim() : '';
      if (esEnt){
        const ent = String(r[m.entrega]).trim(); if (!ent) return;
        const o = res.entregas.get(ent) || {entrega:ent, pedido:ped, grupo: m.grupo ? String(r[m.grupo]).trim() : '', tipo: m.tipo ? normTipo(r[m.tipo]) : '',
          cita: m.cita ? String(r[m.cita]).trim() : '', fecha: m.fechaCita ? toDateISO(r[m.fechaCita]) : '', hora: m.horaCita ? toHora(r[m.horaCita]) : '', lineas:new Map()};
        const l = o.lineas.get(sku) || {sku, desc, qty:0}; l.qty += qty; o.lineas.set(sku, l); res.entregas.set(ent, o);
      } else {
        const o = res.pedidos.get(ped) || {pedido:ped, oc: m.oc ? String(r[m.oc]).trim() : '', cliente: m.cliente ? String(r[m.cliente]).trim() : '',
          canal: m.canal ? String(r[m.canal]).trim() : '', fechaOC: m.fechaOC ? toDateISO(r[m.fechaOC]) : '', lineas:new Map()};
        const l = o.lineas.get(sku) || {sku, desc, qty:0}; l.qty += qty; o.lineas.set(sku, l); res.pedidos.set(ped, o);
      }
    });
  }
  return res;
}
function vistaImportar(){
  const imp = UI.imp;
  const pk = UI.pkg;
  const seccionScript = `<div class="panel" style="margin-bottom:20px"><div class="panel-h"><h2>Paquetes del script</h2></div><div class="panel-b">
    <p style="margin-top:0;max-width:72ch">Con la plataforma abierta, cada macro envía sus datos sola al terminar. Si no pudo conectarse, deja el paquete copiado: presiona <b>Ctrl+V</b> en esta página, o carga el .json de la carpeta <b>Trazabilidad_Web</b> con el selector de abajo.</p>
    <textarea data-pkg placeholder="…o pégalo aquí" style="min-height:70px"></textarea>
    ${pk ? `<div style="margin-top:14px">
      <p style="margin:0 0 6px"><b>${esc(EVENTOS[pk.evento] || pk.evento)}</b> · ${esc(pk.cliente || 'sin cliente')} · ${esc(pk.analista || '')} · ${esc(pk.at || '')}</p>
      <div class="scroll"><table class="t"><thead><tr><th>Entrega</th><th>Pedido</th><th>Grupo</th><th>Cita</th><th>Fecha</th><th>Vehículo</th><th>Carga</th><th class="n">Unid.</th><th></th></tr></thead><tbody>
      ${(pk.entregas || []).map(e => `<tr><td class="num">${esc(e.entrega)}</td><td class="num">${esc(e.pedido)}</td><td class="num">${esc(e.grupo || '—')}</td><td class="num">${esc(e.cita || '—')}</td>
        <td>${e.fecha ? fmtFecha(e.fecha) + ' ' + esc(e.hora || '') : '—'}</td><td>${esc(normVeh(e.vehiculo))}</td><td>${esc(e.carga || '')}</td>
        <td class="n">${fmt((e.lineas || []).reduce((a, l) => a + (+l.qty || 0), 0))}</td>
        <td>${Store.get('entregas', safeId(e.entrega)) ? '<span class="tag">Actualiza</span>' : '<span class="tag green">Nueva</span>'}${(pk.sapOk || []).map(String).includes(String(e.grupo)) ? ' <span class="tag green">Fecha en SAP</span>' : ''}</td></tr>`).join('')
        || '<tr><td colspan="9" class="muted">Sin entregas en este paquete</td></tr>'}
      </tbody></table></div>
      <p class="small muted">${(pk.pedidos || []).length} pedido(s) con ${(pk.pedidos || []).reduce((a, p) => a + (p.lineas || []).length, 0)} líneas de producto.</p>
      <div class="row"><button class="btn primary" data-act="cargarPkg">Cargar paquete</button><button class="btn ghost" data-act="descartarPkg">Descartar</button></div>
    </div>` : ''}
  </div></div>`;
  return seccionAcciones() + seccionScript + `<div class="panel"><div class="panel-h"><h2>Importar desde Excel</h2></div><div class="panel-b">
    <p style="margin-top:0;max-width:72ch">Sube un Excel exportado de SAP. Cada hoja se lee sola: si tiene columna <b>Entrega</b> se carga como entregas; si no, como líneas de pedido. Los encabezados se reconocen aunque cambien tildes o mayúsculas (Material/SKU, Cantidad/Qty, Doc. ventas/Pedido…). Si el registro ya existe, se actualizan sus productos y se conservan los pasos marcados.</p>
    <div class="row"><input type="file" accept=".xlsx,.xls,.csv,.json" data-file aria-label="Archivo Excel o paquete JSON"><button class="btn" data-act="plantilla">Descargar plantilla</button></div>
    ${imp ? `<div style="margin-top:18px">
      ${imp.hojas.length ? `<p class="small">${imp.hojas.map(esc).join('<br>')}</p>` : ''}
      <p><b class="num" style="font-size:22px">${imp.pedidos.size}</b> pedidos · <b class="num" style="font-size:22px">${imp.entregas.size}</b> entregas listos para cargar</p>
      ${imp.errores.length ? `<ul class="err">${imp.errores.slice(0, 12).map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${[...imp.entregas.values()].filter(e => !Store.get('pedidos', safeId(e.pedido)) && !imp.pedidos.has(e.pedido)).length ?
        `<p class="err">Hay entregas cuyo pedido no existe; se crearán pedidos vacíos que debes completar.</p>` : ''}
      <button class="btn primary" data-act="cargarImp" ${imp.pedidos.size + imp.entregas.size ? '' : 'disabled'}>Cargar datos</button>
    </div>` : ''}
  </div></div>`;
}
async function cargarImportacion(){
  const imp = UI.imp; let n = 0;
  const btn = document.querySelector('[data-act="cargarImp"]'); if (btn) btn.disabled = true;
  const pedidos = new Map(imp.pedidos);
  for (const e of imp.entregas.values()) if (!pedidos.has(e.pedido) && !Store.get('pedidos', safeId(e.pedido))) pedidos.set(e.pedido, {pedido:e.pedido, lineas:new Map()});
  try {
    for (const [ped, o] of pedidos){
      const id = safeId(ped); const cur = clone(Store.get('pedidos', id) || {pedido:ped, creado:nowISO(), lineas:[]});
      for (const k of ['oc','cliente','canal','fechaOC']) if (o[k]) cur[k] = o[k];
      const lm = new Map((cur.lineas || []).map(l => [normSku(l.sku), l]));
      for (const l of o.lineas.values()) lm.set(l.sku, {sku:l.sku, desc:l.desc || lm.get(l.sku)?.desc || '', qty:l.qty});
      cur.lineas = [...lm.values()];
      await Store.set('pedidos', id, cur); n++; 
    }
    for (const [ent, o] of imp.entregas){
      const id = safeId(ent); const prevEnt = Store.get('entregas', id); const cur = clone(prevEnt || {entrega:ent, creado:nowISO(), pasos:{}, ...DEF_ENT});
      cur.pedido = o.pedido; if (o.grupo) cur.grupo = o.grupo; if (o.tipo) cur.tipo = o.tipo;
      if (!prevEnt) cur.region = patron((pedidos.get(o.pedido) || {}).cliente || (Store.get('pedidos', safeId(o.pedido)) || {}).cliente).region;
      cur.cita = cur.cita || {};
      if (o.cita) cur.cita.numero = o.cita; if (o.fecha) cur.cita.fecha = o.fecha; if (o.hora) cur.cita.hora = o.hora;
      cur.lineas = [...o.lineas.values()].map(l => ({sku:l.sku, qty:l.qty}));
      addLog(cur, 'Importado desde Excel');
      await Store.set('entregas', id, cur); n++; 
    }
    toast(`${n} registros cargados`); UI.imp = null; UI.view = 'pedidos'; render();
  } catch(e){ toast(dbErr(e) + ` (${n} alcanzaron a cargarse)`); render(); }
}
function parsePaquete(txt){
  try {
    const o = JSON.parse(String(txt || '').replace(/^\uFEFF/, '').trim());
    if (o && o.tipo === 'od-traz' && Array.isArray(o.entregas)) return o;
  } catch(e) {}
  return null;
}
function recibirPaquete(txt){
  const pk = parsePaquete(txt);
  if (!pk){ toast('Eso no es un paquete del script de trazabilidad'); return false; }
  UI.pkg = pk; UI.view = 'importar'; render(); return true;
}
async function cargarPaquete(){
  const pk = UI.pkg; if (!pk) return;
  const btn = document.querySelector('[data-act="cargarPkg"]'); if (btn) btn.disabled = true;
  try {
    const r = await api('POST', '/paquetes', pk);
    toast(`Paquete cargado: ${r.pedidos} pedido(s), ${r.entregas} entrega(s)`);
    const primero = (pk.entregas || [])[0] || (pk.pedidos || [])[0];
    UI.pkg = null; UI.view = 'pedidos'; if (primero){ UI.sel = safeId(primero.pedido); UI.sub = 'entregas'; }
    await Store.refresh();
  } catch(e){ toast(e.message); if (btn) btn.disabled = false; }
}
