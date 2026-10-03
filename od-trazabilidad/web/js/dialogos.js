/* Diálogos, render y manejo de eventos.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Diálogos ============ */
const dlg = $('#dlg');
function abrirDlg(titulo, cuerpo, pie){
  dlg.innerHTML = `<div class="dlg-h"><h3>${esc(titulo)}</h3><button class="btn ghost" data-close aria-label="Cerrar">✕</button></div>
    <div class="dlg-b">${cuerpo}</div><div class="dlg-f"><span class="err" id="dlgErr" style="margin-right:auto"></span><button class="btn" data-close>Cancelar</button>${pie}</div>`;
  if (!dlg.open) dlg.showModal();
}
const sel = (name, opts, val) => `<select name="${name}">${opts.map(o => `<option ${o === val ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
const dval = n => dlg.querySelector(`[name="${n}"]`)?.value?.trim() ?? '';
const dErr = m => { $('#dlgErr').textContent = m; };

function abrirPedido(id){
  const p = id ? Store.get('pedidos', id) : {};
  const lineas = (p.lineas || []).map(l => [l.sku, l.desc, l.qty].join('\t')).join('\n');
  abrirDlg(id ? `Editar pedido ${p.pedido}` : 'Nuevo pedido', `
    <div class="grid-form">
      <label class="f">N° pedido SAP<input type="text" name="pedido" value="${esc(p.pedido || '')}" ${id ? 'readonly' : ''}></label>
      <label class="f">OC cliente<input type="text" name="oc" value="${esc(p.oc || '')}"></label>
      <label class="f">Cliente<input type="text" name="cliente" list="dl-cli" value="${esc(p.cliente || UI.cliente || '')}"></label>
      <label class="f">Canal${sel('canal', CAT.canal, p.canal || patron(UI.cliente).canal)}</label>
      <label class="f">Recibido<input type="date" name="fechaOC" value="${esc(p.fechaOC || new Date().toISOString().slice(0,10))}"></label>
    </div>
    <datalist id="dl-cli">${[...new Set([...clientes(), 'PARIS', 'PARIS FULL', 'HITES'])].map(c => `<option value="${esc(c)}">`).join('')}</datalist>
    <label class="f" style="margin-top:14px">Productos: pega desde Excel o SAP una línea por producto (SKU, descripción, cantidad separados por tabulación o ;)
      <textarea name="lineas" placeholder="955117816&#9;Exprimidor MJP10&#9;120">${esc(lineas)}</textarea></label>
    <label class="f" style="margin-top:12px">Observaciones<input type="text" name="obs" value="${esc(p.obs || '')}"></label>
    ${id ? `<p style="margin:16px 0 0"><button class="btn danger" data-act="borrarPedido" data-id="${esc(id)}">Eliminar pedido y sus entregas</button></p>` : ''}`,
    `<button class="btn primary" data-act="guardarPedido" data-id="${esc(id || '')}">${id ? 'Guardar cambios' : 'Crear pedido'}</button>`);
}
function parseLineas(txt){
  const out = new Map(), errs = [];
  txt.split(/\r?\n/).forEach((raw, i) => {
    if (!raw.trim()) return;
    const c = raw.split(/\t|;/).map(s => s.trim());
    const sku = normSku(c[0]); const qtyTxt = c.length >= 3 ? c[c.length - 1] : c[1];
    const desc = c.length >= 3 ? c.slice(1, -1).join(' ') : '';
    const qty = +String(qtyTxt ?? '').replace(/\./g,'').replace(',','.');
    if (!sku || !isFinite(qty) || qty <= 0){ errs.push(i + 1); return; }
    const l = out.get(sku) || {sku, desc, qty:0}; l.qty += qty; if (!l.desc) l.desc = desc; out.set(sku, l);
  });
  return {lineas:[...out.values()], errs};
}
async function guardarPedido(id){
  const ped = dval('pedido'); if (!ped) return dErr('Ingresa el N° de pedido.');
  const nid = safeId(ped);
  if (!id && Store.get('pedidos', nid)) return dErr('Ese pedido ya existe. Búscalo en la lista para editarlo.');
  const {lineas, errs} = parseLineas(dval('lineas'));
  if (errs.length) return dErr(`Revisa las líneas ${errs.join(', ')}: falta SKU o cantidad válida.`);
  const cur = clone(Store.get('pedidos', nid) || {pedido:ped, creado:nowISO()});
  Object.assign(cur, {oc:dval('oc'), cliente:dval('cliente').toUpperCase(), canal:dval('canal'), fechaOC:dval('fechaOC'), obs:dval('obs'), lineas});
  dlg.close(); UI.sel = nid; UI.view = 'pedidos';
  if (await save('pedidos', nid, cur)) toast(id ? 'Pedido actualizado' : 'Pedido creado');
}
async function borrarPedido(id){
  const p = Store.get('pedidos', id); const ents = entregasDe(p.pedido);
  if (!confirm(`¿Eliminar el pedido ${p.pedido} y sus ${ents.length} entregas? No se puede deshacer.`)) return;
  dlg.close();
  try { await Store.del('pedidos', id); UI.sel = null; toast('Pedido eliminado'); }
  catch(e){ toast(dbErr(e)); }
}

function abrirEntrega(pedId, entId, opts = {}){
  const p = Store.get('pedidos', safeId(pedId)); const e = entId ? Store.get('entregas', entId) : {...DEF_ENT, region: patron(p.cliente).region};
  const {filas} = resumen(p);
  const actual = new Map((e.lineas || []).map(l => [normSku(l.sku), +l.qty]));
  const filasForm = filas.filter(r => entId ? (r.pedida > 0 || actual.has(r.sku)) : r.pendiente > 0);
  const c = e.cita || {};
  abrirDlg(entId ? `Entrega ${e.entrega}` : `Nueva entrega · pedido ${p.pedido}`, `
    <div class="grid-form">
      <label class="f">N° entrega (VL01N)<input type="text" name="entrega" value="${esc(e.entrega || '')}" ${entId ? 'readonly' : ''}></label>
      <label class="f">Grupo<input type="text" name="grupo" value="${esc(e.grupo || '')}"></label>
      <label class="f">Tipo${sel('tipo', CAT.tipo, e.tipo)}</label>
      <label class="f">N° cita cliente<input type="text" name="citaNum" value="${esc(c.numero || '')}"></label>
      <label class="f">Fecha cita<input type="date" name="citaFecha" value="${esc(c.fecha || '')}"></label>
      <label class="f">Hora cita<input type="time" name="citaHora" value="${esc(c.hora || '')}"></label>
      <label class="f">Vehículo${sel('vehiculo', CAT.vehiculo, e.vehiculo)}</label>
      <label class="f">Carga${sel('carga', CAT.carga, e.carga)}</label>
      <label class="f">Unidad de negocio${sel('un', CAT.un, e.un)}</label>
      <label class="f">Región${sel('region', CAT.region, e.region)}</label>
      <label class="f">N° factura<input type="text" name="factura" value="${esc(e.factura || '')}"></label>
    </div>
    <label class="f" style="margin-top:12px">Observaciones<input type="text" name="obs" value="${esc(e.obs || '')}"></label>
    <h3 style="margin:18px 0 6px">Productos en esta entrega</h3>
    ${filasForm.length ? `<div class="scroll"><table class="t"><thead><tr><th>SKU</th><th>Descripción</th><th class="n">Pedido</th><th class="n">Disponible</th><th class="n">Cantidad</th></tr></thead><tbody>
    ${filasForm.map(r => { const mia = actual.get(r.sku) || 0; const disp = r.pedida - r.externa - (r.enEntrega - mia);
      return `<tr><td class="num">${esc(r.sku)}</td><td>${esc(r.desc)}</td><td class="n">${fmt(r.pedida)}</td><td class="n">${fmt(Math.max(0, disp))}</td>
      <td class="n"><input class="qty" type="number" min="0" step="1" data-sku="${esc(r.sku)}" data-disp="${disp}" value="${entId ? mia : Math.max(0, disp)}" aria-label="Cantidad ${esc(r.sku)}"></td></tr>`; }).join('')}
    </tbody></table></div>` : `<p class="muted">El pedido no tiene productos por suministrar. Edita el pedido para agregarlos.</p>`}
    ${opts.msg ? `<p class="err" style="margin-top:10px">${esc(opts.msg)}</p>` : ''}`,
    `<button class="btn primary" data-act="guardarEntrega" data-ped="${esc(safeId(pedId))}" data-id="${esc(entId || '')}" data-marcar="${esc(opts.marcar || '')}">${entId ? 'Guardar cambios' : 'Crear entrega'}</button>`);
  if (opts.marcar === 'confirmada') dlg.querySelector('[name="citaFecha"]').focus();
  if (opts.marcar === 'facturada') dlg.querySelector('[name="factura"]').focus();
}
async function guardarEntrega(pedId, id, marcar){
  const num = dval('entrega'); if (!num) return dErr('Ingresa el N° de entrega.');
  const nid = safeId(num);
  if (!id && Store.get('entregas', nid)) return dErr('Esa entrega ya existe.');
  const lineas = [], exceso = [];
  dlg.querySelectorAll('input.qty').forEach(inp => {
    const q = Math.round(+inp.value || 0); if (q > 0) lineas.push({sku:inp.dataset.sku, qty:q});
    if (q > +inp.dataset.disp) exceso.push(inp.dataset.sku);
  });
  if (!lineas.length) return dErr('La entrega debe tener al menos un producto con cantidad.');
  if (exceso.length && !confirm(`Superas lo disponible del pedido en ${exceso.join(', ')}. ¿Guardar igual?`)) return;
  const p = Store.get('pedidos', pedId);
  const e = clone(Store.get('entregas', nid) || {entrega:num, pedido:p.pedido, creado:nowISO(), pasos:{}});
  const antes = JSON.stringify(e.cita || {});
  Object.assign(e, {grupo:dval('grupo'), tipo:dval('tipo'), vehiculo:dval('vehiculo'), carga:dval('carga'), un:dval('un'), region:dval('region'),
    factura:dval('factura'), obs:dval('obs'), lineas, cita:{numero:dval('citaNum'), fecha:dval('citaFecha'), hora:dval('citaHora')}});
  if (marcar === 'confirmada' && !(e.cita.fecha && e.cita.hora)) return dErr('Falta fecha u hora de la cita.');
  if (marcar === 'facturada' && !e.factura) return dErr('Falta el N° de factura.');
  if (marcar){ e.pasos[marcar] = {ok:true, at:nowISO()}; addLog(e, `Hecho: ${STEPS.find(s => s.k === marcar).t}`); }
  if (marcar === 'confirmada') e.pasos.solicitada = e.pasos.solicitada?.ok ? e.pasos.solicitada : {ok:true, at:nowISO()};
  addLog(e, id ? (antes !== JSON.stringify(e.cita) ? 'Datos de cita editados' : 'Entrega editada') : 'Entrega creada');
  dlg.close(); UI.open.add(nid);
  if (await save('entregas', nid, e)) toast(id ? 'Entrega actualizada' : 'Entrega creada');
}

function abrirGrupo(key, opts = {}){
  const g = grupo1(key); if (!g) return;
  const c = g.cita || {};
  abrirDlg(g.sinGrupo ? `Camión de la entrega ${g.entregas[0].entrega}` : `Camión · grupo ${g.grupo}`, `
    <p style="margin-top:0" class="small">Se aplica a ${g.entregas.length} entrega(s): ${esc(g.entregas.map(e => e.entrega).join(', '))}${g.pedidos.length > 1 ? ' (de más de un pedido)' : ''}.</p>
    <div class="grid-form">
      <label class="f">N° cita cliente<input type="text" name="citaNum" value="${esc(c.numero || '')}"></label>
      <label class="f">Fecha cita<input type="date" name="citaFecha" value="${esc(c.fecha || '')}"></label>
      <label class="f">Hora cita<input type="time" name="citaHora" value="${esc(c.hora || '')}"></label>
      <label class="f">Vehículo${sel('vehiculo', CAT.vehiculo, g.vehiculo)}</label>
      <label class="f">Carga${sel('carga', CAT.carga, g.carga)}</label>
      <label class="f">Unidad de negocio${sel('un', CAT.un, g.un)}</label>
      <label class="f">Región${sel('region', CAT.region, g.region)}</label>
      <label class="f">Tipo${sel('tipo', CAT.tipo, g.tipo)}</label>
    </div>
    ${opts.msg ? `<p class="err" style="margin-top:10px">${esc(opts.msg)}</p>` : ''}`,
    `<button class="btn primary" data-act="guardarGrupo" data-grupo="${esc(key)}" data-marcar="${esc(opts.marcar || '')}">Guardar en todo el camión</button>`);
  if (opts.marcar === 'confirmada') dlg.querySelector('[name="citaFecha"]').focus();
}
async function guardarGrupo(key, marcar){
  const g = grupo1(key); if (!g) return;
  const cita = {numero:dval('citaNum'), fecha:dval('citaFecha'), hora:dval('citaHora')};
  if (marcar === 'confirmada' && !(cita.fecha && cita.hora)) return dErr('Falta fecha u hora de la cita.');
  const campos = {vehiculo:dval('vehiculo'), carga:dval('carga'), un:dval('un'), region:dval('region'), tipo:dval('tipo')};
  dlg.close();
  for (const orig of g.entregas){
    const e = clone(orig);
    Object.assign(e, campos); e.cita = cita;
    if (marcar){
      e.pasos = e.pasos || {};
      if (!pasoOk(e, 'solicitada')) e.pasos.solicitada = {ok:true, at:nowISO()};
      e.pasos[marcar] = {ok:true, at:nowISO()};
      addLog(e, `Hecho: ${STEPS.find(s => s.k === marcar).t} (camión)`);
    } else addLog(e, 'Datos del camión editados');
    if (!await save('entregas', safeId(e.entrega), e)) return;
  }
  toast('Camión actualizado');
}

function abrirReprogramar(key){
  const g = grupo1(key); if (!g) return;
  const c = g.cita || {};
  abrirDlg(g.sinGrupo ? `Reprogramar entrega ${g.entregas[0].entrega}` : `Reprogramar grupo ${g.grupo}`, `
    <p style="margin-top:0">Se reabren: ${REABRE_AL_REPROGRAMAR.map(k => STEPS.find(s => s.k === k).t).join(', ')}. Cita actual: <b>${c.fecha ? fmtFecha(c.fecha) + ' ' + (c.hora || '') : '—'}</b>.</p>
    <div class="grid-form">
      <label class="f">Nueva fecha (si ya la tienes)<input type="date" name="f" value=""></label>
      <label class="f">Nueva hora<input type="time" name="h" value=""></label>
      <label class="f">N° cita nuevo<input type="text" name="n" value="${esc(c.numero || '')}"></label>
    </div>
    <label class="f" style="margin-top:12px">Motivo<input type="text" name="motivo" placeholder="Ej.: cliente sin capacidad en andén"></label>`,
    `<button class="btn primary" data-act="guardarReprog" data-grupo="${esc(key)}">Reprogramar</button>`);
}
async function guardarReprog(key){
  const g = grupo1(key); if (!g) return;
  const motivo = dval('motivo');
  if (!motivo) return dErr('Indica el motivo; queda en el historial.');
  const antes = g.cita || {};
  const cita = {numero:dval('n'), fecha:dval('f') || antes.fecha || '', hora:dval('h') || antes.hora || ''};
  dlg.close();
  for (const orig of g.entregas){
    const e = clone(orig);
    for (const k of REABRE_AL_REPROGRAMAR) e.pasos[k] = {ok:false, at:nowISO()};
    e.cita = cita;
    if (dval('f') && dval('h')) e.pasos.confirmada = {ok:true, at:nowISO()};
    e.reprog = (e.reprog || 0) + 1;
    addLog(e, `Reprogramada (antes ${antes.fecha ? fmtFecha(antes.fecha) : '—'} ${antes.hora || ''}): ${motivo}`);
    if (!await save('entregas', safeId(e.entrega), e)) return;
  }
  toast('Cita reprogramada en el camión');
}
/* ---- Crear en SAP: primero ensayo, después de verdad ---- */
async function crearEntregasSap(pedido, ensayo){
  const cb = UI.cubicaje[pedido];
  if (!cb || !cb.camiones || !cb.camiones.length) return toast('Primero hay que cubicar el pedido');
  let confirmar = '';
  if (!ensayo){
    const txt = prompt(`Se van a CREAR ${cb.camiones.length} entrega(s) en SAP para el pedido ${pedido}.\n\nEscribe ${pedido} para confirmar:`);
    if (txt !== String(pedido)) return toast('Cancelado');
    confirmar = txt;
  }
  try { UI.job = await api('POST', '/sap/crear_entregas', {pedido, ensayo, confirmar}); render(); }
  catch(e){ return toast(e.message); }
  await seguirJob();
  if (UI.job && UI.job.estado === 'ok'){
    const d = UI.job.datos || {};
    const hechas = (d.resultados || []).filter(x => x.entrega).map(x => x.entrega);
    const incid = (d.resultados || []).flatMap(x => x.incidencias || []);
    Avisos.agregar('ok', ensayo ? `Ensayo del pedido ${pedido} terminado` : `Entregas creadas en SAP`,
      ensayo ? 'Se recorrió VL01N sin guardar. Revisa la pantalla de SAP.'
             : `Pedido ${pedido}: ${hechas.join(', ') || 'sin número'}`, incid);
    await Store.refresh();
  } else if (UI.job) Avisos.agregar('error', 'No se pudieron crear las entregas', UI.job.error || '');
  render();
}
async function crearGrupoSap(entregas, ensayo, camion){
  if (!entregas.length) return toast('No hay entregas para agrupar');
  let confirmar = '';
  if (!ensayo){
    const txt = prompt(`Se van a agrupar ${entregas.length} entrega(s) en SAP.\n\nEscribe agrupar para confirmar:`);
    if ((txt || '').toLowerCase() !== 'agrupar') return toast('Cancelado');
    confirmar = 'agrupar';
  }
  const p = Store.get('pedidos', UI.sel) || {};
  try { UI.job = await api('POST', '/sap/crear_grupo',
      {entregas, ensayo, confirmar, camion: camion || '1', cliente: p.cliente || ''}); render(); }
  catch(e){ return toast(e.message); }
  await seguirJob();
  if (UI.job && UI.job.estado === 'ok'){
    const d = UI.job.datos || {};
    Avisos.agregar('ok', ensayo ? 'Ensayo del grupo terminado' : `Grupo ${d.grupo} creado en SAP`,
                   d.mensaje || '', d.incidencias || []);
    await Store.refresh();
  } else if (UI.job) Avisos.agregar('error', 'No se pudo crear el grupo', UI.job.error || '');
  render();
}
async function citaGrupoSap(grupo, ensayo){
  const f = prompt('Fecha de la cita (dd.mm.aaaa):');
  if (f === null) return;
  const h = prompt('Hora (hh:mm), opcional:') || '';
  const ref = prompt('Referencia o N° de cita, opcional:') || '';
  if (!f && !h && !ref) return toast('No indicaste nada que cambiar');
  try { UI.job = await api('POST', '/sap/fecha_grupo', {grupo, fecha: f.trim(),
      hora: h.trim() ? h.trim() + ':00' : '', referencia: ref.trim(), ensayo}); render(); }
  catch(e){ return toast(e.message); }
  await seguirJob();
  if (UI.job && UI.job.estado === 'ok'){
    const d = UI.job.datos || {};
    Avisos.agregar('ok', ensayo ? 'Ensayo de la cita terminado' : `Cita del grupo ${grupo} actualizada`,
                   d.mensaje || '', d.incidencias || []);
    await Store.refresh();
  } else if (UI.job) Avisos.agregar('error', 'No se pudo actualizar la cita', UI.job.error || '');
  render();
}

async function borrarEnSap(tipo, numero){
  const que = tipo === 'entrega' ? 'la entrega' : 'el grupo';
  const txt = prompt(`Esto BORRA ${que} ${numero} en SAP y no se puede deshacer.\n\nEscribe ${numero} para confirmar:`);
  if (txt !== String(numero)) return toast('Cancelado');
  try { UI.job = await api('POST', `/sap/borrar_${tipo}`, {[tipo]: numero, confirmar: txt}); render(); }
  catch(e){ toast(e.message); return; }
  await seguirJob();
  if (UI.job && UI.job.estado === 'ok'){
    Avisos.agregar('ok', `${que.charAt(0).toUpperCase() + que.slice(1)} ${numero} borrado en SAP`, '');
    await Store.refresh();
  } else if (UI.job) Avisos.agregar('error', `No se pudo borrar ${que} ${numero}`, UI.job.error || '');
}
async function anular(id, valor){
  const e = clone(Store.get('entregas', id));
  let motivo = '';
  if (valor){ motivo = prompt(`Motivo para anular la entrega ${e.entrega}:`); if (!motivo) return; }
  e.anulada = valor; addLog(e, valor ? `Anulada: ${motivo}` : 'Reactivada');
  if (await save('entregas', id, e)) toast(valor ? 'Entrega anulada' : 'Entrega reactivada');
}

/* ---- Entrada: nombre de quien usa la plataforma y clave si está configurada ---- */
async function pedirSesion(forzar){
  let est = {requiere_clave:false, abierta:true};
  try { est = await api('GET', '/sesion'); } catch(e){}
  if (!forzar && est.abierta && Usuario.get()) return true;
  const nombre = prompt('¿Quién eres? Tu nombre queda en el historial de cada entrega:',
                        Usuario.get() || '');
  if (nombre === null) return false;
  Usuario.set(nombre);
  if (!est.requiere_clave) return true;
  const clave = prompt('Clave de acceso:') || '';
  try {
    await api('POST', '/sesion', {clave, usuario: Usuario.get()});
    toast(`Hola ${Usuario.get()}`);
    await Store.refresh(); render();
    return true;
  } catch(e){ toast(e.message); return false; }
}

/* ============ Render y eventos ============ */
function render(){
  renderNav();
  const app = $('#app');
  // Se recuerda en qué campo estabas escribiendo para devolverte ahí tras redibujar
  const act = document.activeElement;
  const campo = act && act.matches && act.matches('[data-q], [data-cubsku], [data-buscarmed]')
    ? {sel: act.matches('[data-q]') ? '[data-q]' : act.matches('[data-cubsku]') ? '[data-cubsku]' : '[data-buscarmed]',
       pos: act.selectionStart, val: act.value} : null;
  if (!Store.loaded.size){ app.innerHTML = Store.offline ? `<div class="panel empty"><h3>No hay conexión con el servidor</h3><p>Abre <b>run.bat</b> y recarga esta página.</p></div>` : `<div class="panel empty"><h3>Cargando datos…</h3></div>`; return; }
  app.innerHTML = Avisos.html() + (UI.view === 'bandeja' ? vistaBandeja()
    : UI.view === 'cubicador' ? vistaCubicador()
    : UI.view === 'proyeccion' ? vistaProyeccion()
    : UI.view === 'importar' ? vistaImportar()
    : UI.view === 'config' ? vistaConfiguracion()
    : vistaPedidos());
  if (campo){
    const el = $(campo.sel);
    if (el){ el.value = campo.val; el.focus(); try { el.setSelectionRange(campo.pos, campo.pos); } catch(e){} }
  }
}

document.addEventListener('click', ev => {
  const t = ev.target.closest('button'); if (!t) return;
  if (t.dataset.go){ go(t.dataset.go); return; }
  if (t.hasAttribute('data-close')){ dlg.close(); return; }
  if (t.dataset.sel){ UI.sel = t.dataset.sel; UI.sub = 'entregas'; render(); if (window.innerWidth <= 960) document.querySelector('.layout > section:last-child')?.scrollIntoView(); return; }
  if (t.dataset.sub){ UI.sub = t.dataset.sub; render(); return; }
  if (t.closest && t.closest('[data-ajustes]')) UI.verAjustes = true;   // no se cierra al recalcular
  if (t.dataset.cerrarAviso){ Avisos.cerrar(t.dataset.cerrarAviso); return; }
  if (t.dataset.cubopt){ cambiarOpcionCub(t.dataset.cubopt, t.dataset.valor); return; }
  if (t.dataset.agregar){ agregarSku(t.dataset.agregar, 1); return; }
  if (t.dataset.quitar){ const l = [...(UI.cub.lineas || [])]; l.splice(+t.dataset.quitar, 1); calcularCubLibre({lineas: l}); return; }
  if (t.dataset.abrir){ UI.sel = t.dataset.abrir; UI.sub = t.dataset.sub || 'entregas'; go('pedidos'); return; }
  if (t.dataset.gpaso){ marcarPasoGrupo(t.dataset.grupo, t.dataset.gpaso, t.dataset.forzar ? true : undefined); return; }
  if (t.dataset.accion){
    const id = t.dataset.accion;
    const args = t.dataset.args ? [t.dataset.args] : [];
    const p = UI.sel && Store.get('pedidos', UI.sel);
    if (!args.length && p && (accion1(id) || {}).args.length) args.push(p.pedido);
    correrAccion(id, args); return;
  }
  if (t.dataset.paso){ marcarPaso(t.dataset.ent, t.dataset.paso, t.dataset.forzar ? true : undefined); return; }
  const a = t.dataset.act; const ent = t.dataset.ent;
  const ped = UI.sel && Store.get('pedidos', UI.sel);
  switch (a){
    case 'nuevoPedido': abrirPedido(null); break;
    case 'editarPedido': abrirPedido(UI.sel); break;
    case 'guardarPedido': guardarPedido(t.dataset.id); break;
    case 'borrarPedido': borrarPedido(t.dataset.id); break;
    case 'nuevaEntrega': if (ped) abrirEntrega(ped.pedido, null); break;
    case 'editarEntrega': abrirEntrega(Store.get('entregas', ent).pedido, ent); break;
    case 'guardarEntrega': guardarEntrega(t.dataset.ped, t.dataset.id, t.dataset.marcar); break;
    case 'editarGrupo': abrirGrupo(t.dataset.grupo); break;
    case 'guardarGrupo': guardarGrupo(t.dataset.grupo, t.dataset.marcar); break;
    case 'reprogGrupo': abrirReprogramar(t.dataset.grupo); break;
    case 'guardarReprog': guardarReprog(t.dataset.grupo); break;
    case 'anular': anular(ent, true); break;
    case 'borrarEntregaSap': borrarEnSap('entrega', t.dataset.ent); break;
    case 'ensayoEntregas': { const p = Store.get('pedidos', UI.sel); if (p) crearEntregasSap(p.pedido, true); break; }
    case 'crearEntregas': { const p = Store.get('pedidos', UI.sel); if (p) crearEntregasSap(p.pedido, false); break; }
    case 'crearGrupoSap': crearGrupoSap((t.dataset.ents || '').split(',').filter(Boolean), false, t.dataset.cam); break;
    case 'citaGrupo': citaGrupoSap(t.dataset.num, false); break;
    case 'ensayoGrupo': crearGrupoSap((t.dataset.ents || '').split(',').filter(Boolean), true, t.dataset.cam); break;
    case 'borrarGrupoSap': borrarEnSap('grupo', t.dataset.num); break;
    case 'reactivar': anular(ent, false); break;
    case 'toggle': UI.open.has(ent) ? UI.open.delete(ent) : UI.open.add(ent); render(); break;
    case 'exportProy': exportarProyeccion(); break;
    case 'marcarProy': marcarProyeccion(); break;
    case 'plantilla': plantilla(); break;
    case 'cargarImp': cargarImportacion(); break;
    case 'cargarPkg': cargarPaquete(); break;
    case 'borrarArchivo': borrarArchivo(t.dataset.id); break;
    case 'guardarConexion': guardarConexion(); break;
    case 'probarConexion': probarConexion(); break;
    case 'nuevoCliente': UI.cliEdit = {nuevo:true, pallet:[120,100,140], canal:'RETAIL', region:'RM'}; render(); break;
    case 'editarCliente': UI.cliEdit = (UI.clientes || []).find(x => x.nombre === t.dataset.nombre); render(); break;
    case 'cancelarCliente': UI.cliEdit = null; render(); break;
    case 'guardarCliente': {
      const v = n => (document.querySelector(`[name="${n}"]`) || {}).value;
      const chk = n => !!(document.querySelector(`[name="${n}"]`) || {}).checked;
      guardarCliente(v('cliNombre').trim().toUpperCase(), {
        grupo_sop: v('cliGrupo'), codigo: v('cliCodigo'), canal: v('cliCanal'), region: v('cliRegion'),
        pallet: [+v('cliPL'), +v('cliPW'), +v('cliPH')], caja_master: v('cliCM'),
        calefon_aparte: chk('cliCalefon'), hibrido: chk('cliHibrido'), notas: v('cliNotas')});
      break; }
    case 'abrirLecturaSap': abrirLecturaSap(); break;
    case 'abrirAnalisis': abrirLecturaSap('analizar'); break;
    case 'cambiarUsuario': pedirSesion(true); break;
    case 'verVisorCub': UI.verVisorCub = !UI.verVisorCub; render(); break;
    case 'cubLimpiar': calcularCubLibre({lineas: [], pedido: '', predistribuido: []}); break;
    case 'cubQuitarReparto': quitarRepartoCub(); break;
    case 'traerPedido': { const el = document.querySelector('[data-cubped]');
      traerPedido(el ? el.value : ''); break; }
    case 'verPredist': UI.verPredist = !UI.verPredist; render(); break;
    case 'guardarPredist': { const p = Store.get('pedidos', UI.sel);
      const ta = document.querySelector('[data-predist]');
      if (p && ta) guardarPredist(p.pedido, ta.value); break; }
    case 'ocultarVivo': UI.visorVivo = UI.visorVivo === false; render(); break;
    case 'cubicar': { const p = Store.get('pedidos', UI.sel);
      if (p) cubicar(p.pedido, {modo: modoElegido(UI.cubicaje[p.pedido]),
                                caja_master: UI.cubOpts.caja_master,
                                piso_pallet: UI.cubOpts.piso_pallet}); break; }
    case 'analizarSap': analizarSap(); break;
    case 'resetCarga': { const p = Store.get('pedidos', UI.sel); if (p) ajustarCarga(p.pedido, t.dataset.sku, ''); break; }
    case 'leerSap': leerSap(); break;
    case 'verArchivo': UI.verArchivo = UI.verArchivo === +t.dataset.id ? null : +t.dataset.id; render(); break;
    case 'desasignar': asignarArchivo(t.dataset.id, ''); break;
    case 'refrescarPlan': { const p = Store.get('pedidos', UI.sel); if (p) cargarPlan(p.pedido, true); break; }
    case 'descartarPkg': UI.pkg = null; render(); break;
  }
});
document.addEventListener('paste', ev => {
  const txt = ev.clipboardData ? ev.clipboardData.getData('text') : '';
  const enCampo = ev.target.closest && ev.target.closest('input, textarea:not([data-pkg])');
  if (enCampo || !txt || !txt.includes('"od-traz"')) return;
  ev.preventDefault();
  if (dlg.open) dlg.close();
  recibirPaquete(txt);
});
// Los buscadores no se disparan mientras escribes: hay que presionar Enter
document.addEventListener('keydown', ev => {
  const el = ev.target;
  if (ev.key !== 'Enter') return;
  if (el.matches && el.matches('[name="lsOc"]')){ ev.preventDefault(); buscarPorOc(el.value.trim()); return; }
  if (el.matches && el.matches('[data-cubsku]')){
    ev.preventDefault();
    const v = el.value.trim();
    // si lo escrito es exactamente un SKU sugerido, se agrega; si no, se busca
    const exacta = (UI.cubSug || []).find(x => x.sku.toLowerCase() === v.toLowerCase());
    if (exacta) agregarSku(exacta.sku, 1);
    else if (UI.cubSug.length === 1 && UI.cubBuscando === v) agregarSku(UI.cubSug[0].sku, 1);
    else sugerirSku(v);
    return;
  }
  if (el.matches && el.matches('[data-cubped]')){ ev.preventDefault(); traerPedido(el.value); return; }
  if (el.matches && el.matches('[data-cubqty]')){
    ev.preventDefault(); el.blur(); return;      // Enter confirma la cantidad, como salir del campo
  }
  if (el.matches && el.matches('[data-q]')){ ev.preventDefault(); UI.q = el.value; render(); }
  else if (el.matches && el.matches('[data-buscarmed]')){ ev.preventDefault(); UI.medidasBuscar = el.value; cargarMedidas(); }
});
document.addEventListener('toggle', ev => {
  if (ev.target.matches && ev.target.matches('[data-ajustes]')) UI.verAjustes = ev.target.open;
}, true);
/* Mientras escribes solo se muestran sugerencias: nada se agrega ni se recalcula.
   Agregar un producto necesita hacer clic en la sugerencia o presionar Enter. */
let sugTimer;
document.addEventListener('input', ev => {
  if (!ev.target.matches || !ev.target.matches('[data-cubsku]')) return;
  const v = ev.target.value;
  UI.cubBuscando = v;
  clearTimeout(sugTimer);
  sugTimer = setTimeout(() => sugerirSku(v), 300);
});
document.addEventListener('change', async ev => {
  const el = ev.target;
  if (el.matches('[data-cliente]')){ UI.cliente = el.value; render(); }
  else if (el.matches('[data-abiertos]')){ UI.soloAbiertos = el.checked; render(); }
  else if (el.matches('[data-pdesde]')){ UI.pDesde = el.value || '0000-00-00'; render(); }
  else if (el.matches('[data-phasta]')){ UI.pHasta = el.value; render(); }
  else if (el.matches('[data-pporconf]')){ UI.pPorConf = el.checked; render(); }
  else if (el.matches('[data-analista]')){ const c = clone(config()); c.analista = el.value.trim(); if (await save('config', 'app', c)) toast('Analista guardado'); }
  else if (el.matches('[data-cubimport]') && el.files[0]){ await importarCarga(el); el.value = ''; }
  else if (el.matches('[data-predistimport]') && el.files[0]){ await importarPredist(el, el.dataset.predistimport); el.value = ''; }
  else if (el.matches('[data-medidas]') && el.files[0]){ await importarMedidas(el); el.value = ''; }
  else if (el.matches('[data-subir]') && el.files[0]){ await subirArchivo(el); el.value = ''; }
  else if (el.matches('[data-asignar]') && el.value){ await asignarArchivo(el.dataset.asignar, el.value); }
  else if (el.matches('[data-cubmodo]')){ UI.cubOpts.modo = el.value; render(); }
  else if (el.matches('[data-cubcliente]')){ await calcularCubLibre({cliente: el.value}); }
  else if (el.matches('[data-cubpallet]')){ await calcularCubLibre({pallet_n: +el.value}); }
  else if (el.matches('[data-ajorient]')){ await guardarAjustes({orientacion_pallet: el.value}); }
  else if (el.matches('[data-ajcelda]')){ await guardarAjustes({celda_cm: +el.value}); }
  else if (el.matches('[data-ajcap]')){ await guardarAjustes({capacidad_pallet: el.value}); }
  else if (el.matches('[data-cubqty]')){
    const l = [...(UI.cub.lineas || [])];
    l[+el.dataset.cubqty].qty = Math.max(0, +el.value || 0);
    await calcularCubLibre({lineas: l});
  }
  else if (el.matches('[data-cubcm]')){ UI.cubOpts.caja_master = el.value; }
  else if (el.matches('[data-cubh2]')){ UI.cubOpts.piso_pallet = el.value; }
  else if (el.matches('[data-carga]')){ const p = Store.get('pedidos', UI.sel); if (p) await ajustarCarga(p.pedido, el.dataset.carga, el.value); }
  else if (el.matches('[data-file]') && el.files[0] && /\.json$/i.test(el.files[0].name)){
    recibirPaquete(await el.files[0].text());
  }
  else if (el.matches('[data-file]') && el.files[0]){
    if (typeof XLSX === 'undefined') return toast('No se pudo cargar el lector de Excel');
    try { const buf = await el.files[0].arrayBuffer(); UI.imp = analizarLibro(XLSX.read(buf, {type:'array', cellDates:true})); render(); }
    catch(e){ toast('No se pudo leer el archivo. ¿Es un Excel válido?'); }
  }
});

render();
pedirSesion().then(() => Store.init());   // primero quién eres, después se carga todo
cargarAcciones();
