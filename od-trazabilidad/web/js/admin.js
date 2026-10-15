/* Administración: resumen, historial por analista, errores, cuentas y estado del servidor.
   Parte de la interfaz de Trazabilidad Order Desk. */

const ADM_TABS = [['resumen', 'Resumen'], ['actividad', 'Actividad'], ['errores', 'Errores'], ['usuarios', 'Cuentas'], ['servidor', 'Servidor']];
const bytes = n => n == null ? '—' : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : n < 1073741824 ? `${(n / 1048576).toFixed(1).replace('.', ',')} MB` : `${(n / 1073741824).toFixed(1).replace('.', ',')} GB`;
function duracion(seg){
  const d = Math.floor(seg / 86400), h = Math.floor(seg % 86400 / 3600), m = Math.floor(seg % 3600 / 60);
  return d ? `${d} d ${h} h` : h ? `${h} h ${m} min` : `${m} min`;
}
const ADM = () => UI.adm = UI.adm || {
  tab: 'resumen', horas: 24, vivo: true, hora: null,
  resumen: null,
  act: {f: {usuario: '', categoria: '', resultado: '', q: '', desde: '', hasta: ''}, limite: 100, d: null, nuevas: new Set(), max: 0},
  err: {estado: 'abiertos', origen: '', q: '', d: null, sel: null, det: null},
  usr: {d: null}, srv: null, error: '',
};

/* ---------- carga de datos (cada pestaña pide solo lo suyo) ---------- */
async function admCargar(tab, {silencioso = false} = {}){
  const A = ADM(); tab = tab || A.tab;
  try {
    if (tab === 'resumen') A.resumen = await api('GET', `/admin/resumen?horas=${A.horas}`);
    else if (tab === 'actividad'){
      const f = A.act.f, p = new URLSearchParams({limite: A.act.limite});
      Object.entries(f).forEach(([k, v]) => v && p.set(k, v));
      const d = await api('GET', '/admin/actividad?' + p);
      const previa = A.act.max;
      A.act.nuevas = new Set(previa ? d.filas.filter(a => a.id > previa).map(a => a.id) : []);
      A.act.max = Math.max(previa, ...d.filas.map(a => a.id), 0); A.act.d = d;
    } else if (tab === 'errores'){
      const e = A.err, p = new URLSearchParams({limite: 200});
      if (e.estado) p.set('estado', e.estado); if (e.origen) p.set('origen', e.origen); if (e.q) p.set('q', e.q);
      e.d = await api('GET', '/admin/errores?' + p);
      UI.erroresNuevos = (e.d.cuentas || {}).nuevo || 0;
      if (e.sel && !silencioso) await admDetalleError(e.sel, true);
      else if (e.sel && e.det) await admDetalleError(e.sel, true);
    } else if (tab === 'usuarios') A.usr.d = await api('GET', '/admin/usuarios');
    else if (tab === 'servidor') A.srv = await api('GET', '/admin/servidor');
    A.error = ''; A.hora = new Date();
  } catch(e){ if (!silencioso || !A.resumen) A.error = e.message; }
  renderSoon();
}
async function admDetalleError(id, sinRender){
  const A = ADM();
  try { A.err.det = await api('GET', '/admin/errores/' + id); A.err.sel = id; } catch(e){ toast(e.message); }
  if (!sinRender) renderSoon();
}
function admTab(k){
  const A = ADM(); if (A.tab === k) return;
  const orden = ADM_TABS.map(t => t[0]), dir = Math.sign(orden.indexOf(k) - orden.indexOf(A.tab));
  A.tab = k;
  document.documentElement.classList.add('anim-tabs');
  clearTimeout(admTab._t); admTab._t = setTimeout(() => document.documentElement.classList.remove('anim-tabs'), 300);
  render(); entrar(document.querySelector('.tab-body'), 10 * dir, 0);
  admCargar(k);
}
/* Refresco en vivo mientras se mira: no pisa lo que se está escribiendo */
setInterval(() => {
  if (UI.view !== 'admin' || document.hidden || !ADM().vivo || (dlg && dlg.open)) return;
  if (document.activeElement && document.activeElement.closest('#app input, #app textarea, #app select')) return;
  admCargar(null, {silencioso: true});
}, 15000);
setInterval(async () => {                                   // la insignia de errores nuevos en la barra lateral
  if (document.hidden || !Sesion.esAdmin() || (Sesion.conCuentas() && !Sesion.cuenta)) return;
  try { const d = await api('GET', '/admin/errores?estado=nuevo&limite=1'); const n = (d.cuentas || {}).nuevo || 0; if (n !== UI.erroresNuevos){ UI.erroresNuevos = n; renderNav(); } } catch(e){}
}, 60000);

/* ---------- piezas ---------- */
const kpi = (cap, valor, nota, {tono = '', ir = ''} = {}) =>
  `<${ir ? 'button data-admir="' + ir + '"' : 'div'} class="kpi ${tono}"><span class="cap">${cap}</span><b class="num">${valor}</b><small>${nota}</small></${ir ? 'button' : 'div'}>`;
const avatar = (n, cl = '') => `<span class="avatar ${cl}" aria-hidden="true">${esc(iniciales(n))}</span>`;
const estadoTag = e => e === 'nuevo' ? '<span class="tag err">Nuevo</span>' : e === 'visto' ? '<span class="tag warn">Visto</span>' : '<span class="tag ok">Resuelto</span>';
const origenTag = o => `<span class="tag ${o === 'servidor' ? 'ink' : o === 'sap' ? 'warn' : 'info'}">${esc({servidor: 'Servidor', navegador: 'Navegador', sap: 'SAP', sql: 'SQL'}[o] || o)}</span>`;
const salir = html => `<div class="panel empty">${html}</div>`;

/* ---------- vista ---------- */
function vistaAdmin(){
  const A = ADM();
  if (!A.cargado){ A.cargado = true; admCargar(); admCargar('errores', {silencioso: true}); }
  const abiertos = A.err.d ? (A.err.d.cuentas.nuevo || 0) + (A.err.d.cuentas.visto || 0) : (A.resumen ? A.resumen.errores_abiertos : 0);
  const cuerpo = {resumen: admResumen, actividad: admActividad, errores: admErrores, usuarios: admUsuarios, servidor: admServidor}[A.tab]();
  return `<div class="page-head"><h2>Administración</h2>
      ${A.hora ? `<span class="small muted">Actualizado ${A.hora.toTimeString().slice(0, 8)}</span>` : ''}
      <span class="spacer"></span>
      <label class="chk" title="Se actualiza solo cada 15 segundos"><input type="checkbox" data-admvivo ${A.vivo ? 'checked' : ''}><span class="vivo-p ${A.vivo ? 'on' : ''}" aria-hidden="true"></span>En vivo</label>
      <button class="btn sm" data-act="admRefrescar">${ICON.refrescar}Actualizar</button></div>
    ${A.error ? `<div class="aviso error"><div class="aviso-cuerpo"><b>No se pudo cargar</b> <span class="small">${esc(A.error)}</span></div></div>` : ''}
    <div class="tabs" role="tablist" aria-label="Administración">${ADM_TABS.map(([k, t]) =>
      `<button role="tab" data-admtab="${k}" aria-selected="${A.tab === k}">${t}${k === 'errores' && abiertos ? `<span class="tcount ${A.err.d && A.err.d.cuentas.nuevo ? 'hot' : ''}">${abiertos}</span>` : ''}</button>`).join('')}<i class="tab-ind" aria-hidden="true"${UI.tabInd ? ` style="transform:${UI.tabInd}"` : ''}></i></div>
    <div class="tab-body">${cuerpo}</div>`;
}

/* ===== Resumen ===== */
function graficoActividad(r){
  const s = r.serie, max = Math.max(1, ...s.map(x => x.acciones), ...s.map(x => x.errores));
  const etiqueta = x => r.por_dia ? aFecha(x.t).toLocaleDateString('es-CL', {day: 'numeric', month: 'short'}) : horaDe(x.t);
  const marcas = s.length <= 1 ? [0] : [0, Math.floor((s.length - 1) / 2), s.length - 1];
  return `<div class="chart" role="img" aria-label="Acciones y errores en el tiempo">
      <div class="chart-bars" style="--n:${s.length}">${s.map((x, i) => `<button class="col" data-admcol="${i}" aria-label="${esc(etiqueta(x))}: ${x.acciones} acciones, ${x.errores} errores">
        <i class="a" style="height:${x.acciones ? Math.max(3, x.acciones / max * 100) : 0}%"></i><i class="e" style="height:${x.errores ? Math.max(3, x.errores / max * 100) : 0}%"></i></button>`).join('')}</div>
      <div class="chart-x">${marcas.map(i => `<span>${esc(etiqueta(s[i]))}</span>`).join('')}</div>
      <div class="chart-tip" id="chartTip" hidden></div></div>`;
}
function admResumen(){
  const A = ADM(), r = A.resumen;
  if (!r) return `<div class="panel" style="padding:16px"><span class="skel" style="width:30%"></span><span class="skel" style="margin-top:12px"></span><span class="skel" style="margin-top:12px;width:60%"></span></div>`;
  const maxU = Math.max(1, ...r.por_usuario.map(u => u.acciones));
  const totCat = r.por_categoria.reduce((a, c) => a + c.n, 0) || 1;
  const periodo = {24: 'últimas 24 h', 168: 'últimos 7 días', 720: 'últimos 30 días'}[r.horas] || `últimas ${r.horas} h`;
  return `<div class="adm-barra"><div class="seg sm" role="group" aria-label="Período">${[[24, '24 horas'], [168, '7 días'], [720, '30 días']].map(([h, t]) => `<button data-admhoras="${h}" aria-pressed="${A.horas === h}">${t}</button>`).join('')}</div>
      <span class="muted small">${periodo}</span></div>
    <div class="kpis">
      ${kpi('Acciones', fmt(r.acciones), 'de los analistas')}
      ${kpi('Analistas activos', fmt(r.analistas_activos), r.en_linea.length ? `${r.en_linea.length} en línea ahora` : 'ninguno en línea')}
      ${kpi('Errores', fmt(r.errores_periodo), 'en el período', {tono: r.errores_periodo ? 'alerta' : ''})}
      ${kpi('Errores abiertos', fmt(r.errores_abiertos), r.errores_nuevos ? `${r.errores_nuevos} sin revisar` : 'al día', {tono: r.errores_nuevos ? 'alerta' : '', ir: 'errores'})}
      ${kpi('Rechazadas', fmt(r.ingresos_rechazados), 'acciones que el sistema no aceptó', {ir: 'rechazadas'})}</div>
    <div class="panel"><div class="panel-h"><h3>Actividad en el tiempo</h3><span class="spacer"></span>
        <span class="leyenda-mini"><i class="sw a"></i>Acciones <i class="sw e"></i>Errores</span></div>
      <div class="panel-b">${graficoActividad(r)}</div></div>
    <div class="adm-2">
      <div class="panel"><div class="panel-h"><h3>Por analista</h3><span class="spacer"></span><span class="small muted">Toca uno para ver su historial</span></div>
        ${r.por_usuario.length ? `<ul class="rank">${r.por_usuario.map(u => `<li><button data-admusuario="${esc(u.usuario)}">
          ${avatar(u.nombre)}<span class="rk-n"><b>${esc(u.nombre)}</b><small>${haceDe(u.ultima)}</small></span>
          <span class="rk-b"><i style="transform:scaleX(${(u.acciones / maxU).toFixed(3)})"></i></span><b class="num rk-v">${fmt(u.acciones)}</b></button></li>`).join('')}</ul>`
        : `<div class="empty"><h3>Sin actividad en este período</h3><p>Cuando los analistas trabajen, aparecerán aquí.</p></div>`}
        ${r.en_linea.length ? `<div class="en-linea"><span class="cap">En línea</span>${r.en_linea.map(u => `<span class="chip-on"><i class="dot ok"></i>${esc(u.nombre)}<small>${haceDe(u.visto)}</small></span>`).join('')}</div>` : ''}</div>
      <div class="panel"><div class="panel-h"><h3>Por tipo de acción</h3></div><div class="panel-b">
        <div class="barra-cat" role="img" aria-label="Distribución por categoría">${r.por_categoria.map(c => `<i style="flex:${c.n};background:${(CATS[c.categoria] || CATS.sistema)[1]}" title="${esc((CATS[c.categoria] || [c.categoria])[0])}: ${c.n}"></i>`).join('')}</div>
        <ul class="leyenda-cat">${r.por_categoria.map(c => `<li><button data-admcat="${esc(c.categoria)}">${catChip(c.categoria)}<b class="num">${fmt(c.n)}</b><small>${Math.round(c.n / totCat * 100)}%</small></button></li>`).join('')}</ul></div></div></div>
    <div class="panel"><div class="panel-h"><h3>Errores que más se repiten</h3><span class="spacer"></span><button class="btn sm quiet" data-admir="errores">Ver todos</button></div>
      ${r.top_errores.length ? `<ul class="err-top">${r.top_errores.map(e => `<li><button data-admerr="${e.id}"><span class="x num">×${e.cuenta}</span>
        <span class="et"><b>${esc(e.mensaje)}</b><small>${esc(e.ruta || '—')} · ${haceDe(e.ultima)}${e.ultimo_usuario ? ' · ' + esc(e.ultimo_usuario) : ''}</small></span>${origenTag(e.origen)}${estadoTag(e.estado)}</button></li>`).join('')}</ul>`
      : `<div class="empty"><h3>Sin errores en este período</h3><p>Todo funcionó. Si algo falla, aparece aquí con su código de seguimiento.</p></div>`}</div>`;
}

/* ===== Actividad ===== */
function admActividad(){
  const A = ADM(), a = A.act, f = a.f, d = a.d;
  const url = '/api/admin/actividad.csv?' + new URLSearchParams(Object.entries(f).filter(([, v]) => v));
  const filtrado = Object.values(f).some(Boolean);
  const hay = d ? d.total : 0;
  return `<div class="panel"><div class="panel-h filtros">
      <label class="f">Analista<select data-admf="usuario"><option value="">Todos</option>${(d ? d.usuarios : []).map(u => `<option value="${esc(u.usuario)}" ${f.usuario === u.usuario ? 'selected' : ''}>${esc(u.nombre)}</option>`).join('')}</select></label>
      <label class="f">Tipo<select data-admf="categoria"><option value="">Todos</option>${Object.entries(CATS).map(([k, [t]]) => `<option value="${k}" ${f.categoria === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label class="f">Resultado<select data-admf="resultado">${[['', 'Todos'], ['ok', 'Correctas'], ['rechazada', 'Rechazadas'], ['error', 'Con error']].map(([k, t]) => `<option value="${k}" ${f.resultado === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label class="f">Desde<input type="datetime-local" data-admf="desde" value="${esc(f.desde)}"></label>
      <label class="f">Hasta<input type="datetime-local" data-admf="hasta" value="${esc(f.hasta)}"></label>
      <label class="f grow">Buscar<span class="searchbox">${ICON.search}<input type="search" data-admq placeholder="Pedido, acción o código de seguimiento" value="${esc(f.q)}"></span></label></div>
    <div class="panel-h sub"><span class="small muted num">${d ? `${fmt(hay)} movimiento${hay === 1 ? '' : 's'}${filtrado ? ' con estos filtros' : ''}` : 'Cargando…'}</span><span class="spacer"></span>
      ${filtrado ? `<button class="btn sm quiet" data-act="admLimpiar">Quitar filtros</button>` : ''}
      <a class="btn sm" href="${esc(url)}" download>${ICON.descargar}Descargar CSV</a></div>
    <div class="panel-b act-lista">${!d ? '<span class="skel" style="width:40%"></span><span class="skel" style="margin-top:10px"></span>'
      : d.filas.length ? agruparPorDia(d.filas, x => filaActividad(x, {admin: true}).replace('class="act ', `class="act ${a.nuevas.has(x.id) ? 'nueva ' : ''}`))
      : `<div class="empty"><h3>Nada que mostrar</h3><p>${filtrado ? 'Ningún movimiento coincide con los filtros.' : 'Cuando alguien haga algo en la plataforma, queda aquí.'}</p></div>`}</div>
    ${d && d.filas.length < hay ? `<div class="panel-b" style="padding-top:0"><button class="btn" data-act="admMas">Mostrar más (${fmt(hay - d.filas.length)} restantes)</button></div>` : ''}</div>`;
}

/* ===== Errores ===== */
function informeError(e){
  const o = (e.ocurrencias || [])[0] || {};
  return [`ERROR #${e.id} · ${e.origen} · ${e.estado}`, `Mensaje: ${e.mensaje}`, `Ruta: ${e.ruta || '—'}`,
    `Ocurrencias: ${e.cuenta} (primera ${fechaHoraDe(e.primera)}, última ${fechaHoraDe(e.ultima)})`,
    `Última vez: ${o.nombre || o.usuario || '—'} · código ${o.codigo || '—'} · ${o.metodo || ''} ${o.ruta || ''} · HTTP ${o.status || '—'}`,
    o.contexto && Object.keys(o.contexto).length ? `Contexto: ${JSON.stringify(o.contexto)}` : '', e.nota ? `Nota: ${e.nota}` : '',
    '', 'Traza:', e.traza || '(sin traza)'].filter(x => x !== '').join('\n');
}
function admErrores(){
  const A = ADM(), e = A.err, d = e.d, c = d ? d.cuentas : {};
  const n = k => c[k] || 0;
  const filtros = [['abiertos', 'Abiertos', n('nuevo') + n('visto')], ['nuevo', 'Nuevos', n('nuevo')], ['resuelto', 'Resueltos', n('resuelto')], ['', 'Todos', n('nuevo') + n('visto') + n('resuelto')]];
  const lista = !d ? '<div style="padding:14px"><span class="skel"></span><span class="skel" style="margin-top:10px;width:70%"></span></div>'
    : d.filas.length ? `<ul class="elist">${d.filas.map(x => `<li><button class="erow ${x.estado}" data-admerr="${x.id}" aria-current="${e.sel === x.id}" data-k="er-${x.id}">
        <span class="x num" title="Veces que ocurrió">×${x.cuenta}</span>
        <span class="et"><b>${esc(x.mensaje)}</b><small>${esc(x.ruta || '—')}</small>
          <span class="em">${origenTag(x.origen)}${estadoTag(x.estado)}<span class="small muted">${haceDe(x.ultima)}${x.ultimo_usuario ? ' · ' + esc(x.ultimo_usuario) : ''}</span></span></span></button></li>`).join('')}</ul>`
    : `<div class="empty"><h3>${e.estado === 'abiertos' ? 'Sin errores abiertos' : 'Sin resultados'}</h3><p>${e.estado === 'abiertos' ? 'Todo en orden. Los errores nuevos aparecen aquí solos.' : 'Prueba con otro filtro.'}</p></div>`;
  return `<div class="split err-split">
    <div class="panel list-col"><div class="list-tools">
        <div class="seg sm" role="group" aria-label="Estado">${filtros.map(([k, t, q]) => `<button data-admestado="${k}" aria-pressed="${e.estado === k}">${t}${q ? ` <span class="num">${q}</span>` : ''}</button>`).join('')}</div>
        <div class="row"><select data-admorigen aria-label="Origen"><option value="">Cualquier origen</option>${[['servidor', 'Servidor'], ['navegador', 'Navegador'], ['sap', 'SAP'], ['sql', 'SQL']].map(([k, t]) => `<option value="${k}" ${e.origen === k ? 'selected' : ''}>${t}</option>`).join('')}</select>
          <label class="searchbox">${ICON.search}<input type="search" data-admeq placeholder="Mensaje, ruta o código" value="${esc(e.q)}" aria-label="Buscar errores"></label></div></div>
      ${lista}</div>
    <div class="err-det">${detalleError(e)}</div></div>`;
}
function detalleError(e){
  const x = e.det;
  if (!x) return salir(`<h3>Elige un error</h3><p>Verás cuántas veces ocurrió, quién lo vio, qué hacía justo antes y la traza técnica para repararlo.</p>`);
  return `<div class="label">
    <div class="label-top"><div style="min-width:0;flex:1"><div class="row tight" style="margin-bottom:6px">${origenTag(x.origen)}${estadoTag(x.estado)}<span class="tag">×${x.cuenta}</span><span class="code muted small">#${x.id}</span></div>
        <h3 class="err-msg">${esc(x.mensaje)}</h3><p class="small muted code">${esc(x.ruta || '—')}</p></div></div>
    <div class="cells"><div class="cell"><span class="cap">Primera vez</span><span class="val">${esc(fechaHoraDe(x.primera))}</span></div>
      <div class="cell"><span class="cap">Última vez</span><span class="val">${esc(fechaHoraDe(x.ultima))}</span></div>
      <div class="cell"><span class="cap">Veces</span><span class="val">${x.cuenta}</span></div>
      <div class="cell"><span class="cap">Último afectado</span><span class="val">${esc((x.ocurrencias[0] || {}).nombre || '—')}</span></div></div>
    <div class="label-foot">
      ${x.estado !== 'resuelto' ? `<button class="btn primary sm" data-admestadoerr="resuelto" data-id="${x.id}">${ICON.check}Marcar resuelto</button>` : `<button class="btn sm" data-admestadoerr="nuevo" data-id="${x.id}">Reabrir</button>`}
      <button class="btn sm" data-admcopiar="${x.id}">${ICON.copiar}Copiar informe para TI</button><span class="spacer"></span>
      <label class="nota-e"><span class="sr">Nota</span><input type="text" data-admnota="${x.id}" value="${esc(x.nota)}" placeholder="Nota (qué se hizo, quién lo ve…)" maxlength="400"></label></div></div>
    <div class="panel"><div class="panel-h"><h3>Cómo se llegó aquí</h3><span class="small muted">Las últimas ${x.ocurrencias.length} veces</span></div>
      <ol class="ocs">${x.ocurrencias.map(o => `<li class="oc"><div class="oc-1"><time class="num">${esc(fechaHoraDe(o.at))}</time><b>${esc(o.nombre || o.usuario || 'sin usuario')}</b>
          ${o.status ? `<span class="tag ${o.status >= 500 ? 'err' : 'warn'}">HTTP ${o.status}</span>` : ''}<span class="code small muted">${esc((o.metodo + ' ' + o.ruta).trim())}</span>
          ${o.codigo ? `<button class="cod" data-copiar="${esc(o.codigo)}" title="Copiar código de seguimiento">${esc(o.codigo)}</button><button class="enlace" data-admbuscar="${esc(o.codigo)}">Ver su rastro</button>` : ''}</div>
        ${o.antes.length ? `<details><summary>Lo que hizo justo antes (${o.antes.length})</summary><ul class="antes">${o.antes.map(a => `<li><time class="num">${horaDe(a.at)}</time> ${esc(a.accion)}</li>`).join('')}</ul></details>` : ''}
        ${Object.keys(o.contexto || {}).length ? `<dl class="ctx">${Object.entries(o.contexto).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(typeof v === 'object' ? JSON.stringify(v) : v)}</dd>`).join('')}</dl>` : ''}</li>`).join('')}</ol></div>
    <div class="panel"><div class="panel-h"><h3>Traza técnica</h3><span class="spacer"></span><button class="btn sm quiet" data-admcopiartraza="${x.id}">${ICON.copiar}Copiar</button></div>
      ${x.traza ? `<pre class="traza">${trazaHTML(x.traza)}</pre>` : '<div class="panel-b"><p class="muted small">Este error no trajo traza.</p></div>'}</div>`;
}
/* Resalta los archivos propios de la plataforma entre las líneas de la traza */
function trazaHTML(t){
  return t.split('\n').map(l => {
    const propia = /\/app\/|\\app\\|\/web\/js\//.test(l) && !/site-packages|dist-packages/.test(l);
    return `<span class="${propia ? 'mia' : /^\s*File |^\s+at /.test(l) ? 'lib' : ''}">${esc(l)}</span>`;
  }).join('\n');
}

/* ===== Cuentas ===== */
function admUsuarios(){
  const A = ADM(), d = A.usr.d;
  if (!d) return `<div class="panel" style="padding:16px"><span class="skel" style="width:30%"></span><span class="skel" style="margin-top:12px"></span></div>`;
  if (d.modo === 'abierto') return `<div class="panel activar"><div class="panel-b">
      <div class="activar-i">${ICON.escudo}</div>
      <h3>Activa las cuentas por analista</h3>
      <p>Ahora la plataforma está en <b>modo abierto</b>: cada persona escribe su nombre al entrar y no hay clave. Cuando la publiques en un servidor, crea cuentas para que cada analista entre con su usuario y clave, y el historial y los errores queden a su nombre.</p>
      <ul class="check-l"><li>Claves protegidas (no se guardan en claro) y bloqueo tras 5 intentos fallidos</li><li>Sesión que se cierra sola tras ${Sesion.modo === 'cuentas' ? '' : 'varias '}horas sin uso</li><li>Historial por analista y errores con código de seguimiento</li></ul>
      ${Sesion.puedeConfigurar ? `<div class="fgrid" style="margin-top:14px;max-width:760px">
        <label class="f">Tu nombre<input type="text" name="aNombre" autocomplete="name"></label>
        <label class="f">Usuario<input type="text" name="aUsuario" autocapitalize="off" autocomplete="off" placeholder="ej. vsoto"></label>
        <label class="f">Clave<input type="password" name="aClave" autocomplete="new-password"></label></div>
        <p class="err" id="activarErr" role="alert"></p>
        <button class="btn primary" data-act="admActivar">Crear administrador y activar cuentas</button>`
      : `<p class="enota">La primera cuenta se crea desde el propio servidor o con <code>ADMIN_INICIAL=usuario:clave:Nombre</code> en el <code>.env</code>.</p>`}</div></div>`;
  const yo = Sesion.cuenta ? Sesion.cuenta.id : 0;
  return `<div class="adm-barra"><span class="muted small">${d.filas.filter(u => u.activo).length} cuentas activas · ${d.filas.length} en total</span><span class="spacer"></span>
      <button class="btn primary sm" data-act="admNuevaCuenta">${ICON.plus}Nueva cuenta</button></div>
    <div class="usrs">${d.filas.map(u => `<article class="usr ${u.activo ? '' : 'off'}" data-k="u-${u.id}">
      ${avatar(u.nombre, u.rol === 'admin' ? 'adm' : '')}
      <div class="usr-n"><b>${esc(u.nombre)}${u.id === yo ? ' <span class="tag info">Tú</span>' : ''}</b><span class="code small muted">${esc(u.usuario)}</span></div>
      <div class="usr-t"><span class="tag ${u.rol === 'admin' ? 'ink' : ''}">${ROL[u.rol]}</span>${u.activo ? '' : '<span class="tag void">Desactivada</span>'}${u.debe_cambiar_clave ? '<span class="tag warn">Clave temporal</span>' : ''}</div>
      <div class="usr-m"><span><small>Último acceso</small><b>${u.ultimo_acceso ? haceDe(u.ultimo_acceso) : 'nunca'}</b></span><span><small>Sesiones</small><b class="num">${u.sesiones}</b></span><span><small>Acciones</small><b class="num">${fmt(u.acciones)}</b></span></div>
      <div class="usr-a"><button class="btn sm" data-admusuario="${esc(u.usuario)}">${ICON.historial}Historial</button>
        <button class="btn sm" data-act="admClave" data-id="${u.id}">${ICON.llave}Restablecer clave</button>
        ${u.sesiones ? `<button class="btn sm" data-act="admCerrarSes" data-id="${u.id}">Cerrar sesiones</button>` : ''}
        <button class="btn sm" data-act="admRol" data-id="${u.id}" data-rol="${u.rol === 'admin' ? 'analista' : 'admin'}">${u.rol === 'admin' ? 'Quitar admin' : 'Hacer admin'}</button>
        ${u.id === yo ? '' : `<button class="btn sm ${u.activo ? 'danger' : ''}" data-act="admActivo" data-id="${u.id}" data-activo="${u.activo ? '' : '1'}">${u.activo ? 'Desactivar' : 'Activar'}</button>`}</div></article>`).join('')}</div>`;
}
function claveTemporalDlg(titulo, usuario, clave){
  dlg.classList.add('angosto');
  abrirDlg(titulo, `<p class="prose">Entrégale esta clave a <b>${esc(usuario)}</b>. Es temporal: al entrar tendrá que elegir la suya.</p>
    <div class="clave-t"><code id="claveT">${esc(clave)}</code><button class="btn sm" data-copiar="${esc(clave)}">${ICON.copiar}Copiar</button></div>
    <p class="small muted">Se muestra una sola vez; el servidor no la guarda en claro. Si se pierde, restablece la clave.</p>`, '');
  dlg.querySelector('.dlg-f .btn[data-close]').textContent = 'Listo';
}

/* ===== Servidor ===== */
function admServidor(){
  const s = ADM().srv;
  if (!s) return `<div class="panel" style="padding:16px"><span class="skel" style="width:30%"></span><span class="skel" style="margin-top:12px"></span></div>`;
  const chequeos = [
    [s.autenticacion === 'cuentas' ? 'ok' : 'warn', 'Cuentas por analista', s.autenticacion === 'cuentas' ? 'Activas: cada analista entra con su usuario y clave.' : 'Modo abierto: cualquiera que llegue a la dirección puede usar la plataforma. Actívalas antes de publicar.'],
    [s.cookie_segura ? 'ok' : 'warn', 'HTTPS (cookie segura)', s.cookie_segura ? 'La sesión solo viaja cifrada.' : 'Sin COOKIE_SEGURA. Si la plataforma queda detrás de HTTPS, actívalo en el .env.'],
    [s.disco_libre > 5 * 1073741824 ? 'ok' : s.disco_libre > 1073741824 ? 'warn' : 'err', 'Espacio en disco', `${bytes(s.disco_libre)} libres.`],
    [s.base.tipo === 'sqlite' ? 'info' : 'ok', 'Base de datos', s.base.tipo === 'sqlite' ? 'SQLite: sirve para un equipo o pocos analistas. Para uso simultáneo intenso, apunta DATABASE_URL a SQL Server.' : `${s.base.tipo}: apta para varios analistas a la vez.`],
  ];
  return `<div class="cells cells-s">
      <div class="cell"><span class="cap">Versión</span><span class="val">${esc(s.version)}</span></div>
      <div class="cell"><span class="cap">Activo hace</span><span class="val">${duracion(s.activo_seg)}</span></div>
      <div class="cell"><span class="cap">Python</span><span class="val">${esc(s.python)}</span></div>
      <div class="cell"><span class="cap">Base de datos</span><span class="val">${esc(s.base.tipo)}${s.base.tamano != null ? ' · ' + bytes(s.base.tamano) : ''}</span></div>
      <div class="cell"><span class="cap">Registro en archivo</span><span class="val">${bytes(s.logs.tamano)}</span></div>
      <div class="cell"><span class="cap">Sesiones abiertas</span><span class="val">${s.sesiones}</span></div></div>
    <div class="panel" style="margin-top:16px"><div class="panel-h"><h3>Estado</h3></div>
      <ul class="salud">${chequeos.map(([t, n, d]) => `<li><span class="pip ${t === 'info' ? 'lim' : t}"></span><div><b>${n}</b><span class="small muted">${esc(d)}</span></div></li>`).join('')}</ul></div>
    <div class="panel"><div class="panel-h"><h3>Registros guardados</h3></div><div class="panel-b">
      <div class="meta" style="margin:0 0 12px"><div class="m"><span class="cap">Actividad</span><span class="v">${fmt(s.registros.actividad)} movimientos · se borran a los ${s.retencion.actividad_dias} días</span></div>
        <div class="m"><span class="cap">Errores</span><span class="v">${fmt(s.registros.errores)} agrupados · los resueltos se borran a los ${s.retencion.errores_dias} días</span></div>
        <div class="m"><span class="cap">Sesión</span><span class="v">se cierra tras ${s.sesion_horas} h sin uso</span></div></div>
      <div class="row"><button class="btn" data-act="admPurgar">Borrar lo que ya pasó el plazo</button>
        <button class="btn" data-act="admCopiarSrv">${ICON.copiar}Copiar resumen para TI</button></div>
      <p class="small muted" style="margin-top:10px">Archivo de registro: <span class="code">${esc(s.logs.carpeta)}</span> (una línea JSON por petición y por error; rota solo).</p></div></div>`;
}

/* morphdom no siempre vuelve a marcar la opción elegida cuando cambian las opciones de un select */
function admPostRender(){
  const f = ADM().act.f;
  document.querySelectorAll('select[data-admf]').forEach(s => {
    const i = [...s.options].findIndex(o => o.value === (f[s.dataset.admf] || ''));
    if (i >= 0 && s.selectedIndex !== i) s.selectedIndex = i;
  });
}

/* ============ Eventos ============ */
document.addEventListener('click', async ev => {
  const b = ev.target.closest && ev.target.closest('button'); if (!b) return;
  const A = UI.adm;
  if (b.dataset.admtab){ admTab(b.dataset.admtab); return; }
  if (b.dataset.admhoras){ ADM().horas = +b.dataset.admhoras; ADM().resumen = null; render(); admCargar('resumen'); return; }
  if (b.dataset.admir){                                                      // atajos desde las tarjetas
    const k = b.dataset.admir;
    if (k === 'rechazadas'){ ADM().act.f = {usuario: '', categoria: '', resultado: 'rechazada', q: '', desde: '', hasta: ''}; ADM().act.d = null; admTab('actividad'); admCargar('actividad'); }
    else admTab(k);
    return;
  }
  if (b.dataset.admusuario !== undefined){ const a = ADM(); a.act.f = {usuario: b.dataset.admusuario, categoria: '', resultado: '', q: '', desde: '', hasta: ''}; a.act.d = null; a.act.max = 0; a.act.limite = 100; admTab('actividad'); admCargar('actividad'); return; }
  if (b.dataset.admcat !== undefined){ const a = ADM(); a.act.f = {usuario: '', categoria: b.dataset.admcat, resultado: '', q: '', desde: '', hasta: ''}; a.act.d = null; a.act.max = 0; admTab('actividad'); admCargar('actividad'); return; }
  if (b.dataset.admcol !== undefined){                                       // una barra del gráfico → ese tramo en Actividad
    const r = ADM().resumen, x = r.serie[+b.dataset.admcol], ini = new Date(x.t), fin = new Date(+ini + (r.por_dia ? 864e5 : 36e5));
    const loc = d => new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
    const a = ADM(); a.act.f = {usuario: '', categoria: '', resultado: '', q: '', desde: loc(ini), hasta: loc(fin)}; a.act.d = null; a.act.max = 0; admTab('actividad'); admCargar('actividad'); return;
  }
  if (b.dataset.admerr){ const id = +b.dataset.admerr; if (ADM().tab !== 'errores'){ ADM().err.sel = id; ADM().err.det = null; ADM().err.estado = ''; admTab('errores'); admCargar('errores'); } else { ADM().err.sel = id; await admDetalleError(id); } return; }
  if (b.dataset.admestado !== undefined){ const e = ADM().err; e.estado = b.dataset.admestado; e.d = null; render(); admCargar('errores'); return; }
  if (b.dataset.admestadoerr){
    try { await api('PUT', '/admin/errores/' + b.dataset.id, {estado: b.dataset.admestadoerr}); toast(b.dataset.admestadoerr === 'resuelto' ? 'Marcado como resuelto' : 'Reabierto'); } catch(e){ toast(e.message); }
    await admCargar('errores'); return;
  }
  if (b.dataset.admcopiar){ const x = ADM().err.det; if (x) copiarTexto(informeError(x), 'Informe copiado'); return; }
  if (b.dataset.admcopiartraza){ const x = ADM().err.det; if (x) copiarTexto(x.traza, 'Traza copiada'); return; }
  if (b.dataset.admbuscar){ const a = ADM(); a.act.f = {usuario: '', categoria: '', resultado: '', q: b.dataset.admbuscar, desde: '', hasta: ''}; a.act.d = null; a.act.max = 0; admTab('actividad'); admCargar('actividad'); return; }
  switch (b.dataset.act){
    case 'admRefrescar': admCargar(); break;
    case 'admLimpiar': A.act.f = {usuario: '', categoria: '', resultado: '', q: '', desde: '', hasta: ''}; A.act.limite = 100; A.act.d = null; A.act.max = 0; render(); admCargar('actividad'); break;
    case 'admMas': A.act.limite += 200; admCargar('actividad'); break;
    case 'admNuevaCuenta': admNuevaCuenta(); break;
    case 'admCrearCuenta': admCrearCuenta(); break;
    case 'admClave': { const u = A.usr.d.filas.find(x => x.id === +b.dataset.id);
      const r = await preguntar({titulo: 'Restablecer clave', texto: `Se genera una clave temporal nueva para <b>${esc(u.nombre)}</b> y se cierran sus sesiones abiertas.`, ok: 'Restablecer'});
      if (!r) break;
      try { const d = await api('POST', `/admin/usuarios/${u.id}/clave`); claveTemporalDlg('Clave temporal', u.nombre, d.clave_temporal); admCargar('usuarios'); } catch(e){ toast(e.message); } break; }
    case 'admCerrarSes': try { const d = await api('POST', `/admin/usuarios/${b.dataset.id}/cerrar-sesiones`); toast(`${d.cerradas} sesión(es) cerradas`); admCargar('usuarios'); } catch(e){ toast(e.message); } break;
    case 'admRol': try { await api('PUT', '/admin/usuarios/' + b.dataset.id, {rol: b.dataset.rol}); toast('Rol cambiado'); admCargar('usuarios'); } catch(e){ toast(e.message); } break;
    case 'admActivo': try { await api('PUT', '/admin/usuarios/' + b.dataset.id, {activo: !!b.dataset.activo}); toast(b.dataset.activo ? 'Cuenta activada' : 'Cuenta desactivada'); admCargar('usuarios'); } catch(e){ toast(e.message); } break;
    case 'admActivar': {
      const v = n => (document.querySelector(`[name="${n}"]`) || {}).value || '';
      const err = $('#activarErr');
      try { await api('POST', '/sesion/configuracion-inicial', {nombre: v('aNombre'), usuario: v('aUsuario'), clave: v('aClave')}); toast('Cuentas activadas'); location.reload(); }
      catch(e){ if (err) err.textContent = e.message; } break; }
    case 'admPurgar': try { const d = await api('POST', '/admin/purgar'); toast(`Borrado: ${d.actividad || 0} movimientos y ${d.errores || 0} errores`); admCargar('servidor'); } catch(e){ toast(e.message); } break;
    case 'admCopiarSrv': { const s = ADM().srv; if (s) copiarTexto([`Order Desk ${s.version}`, `Python ${s.python} · ${s.sistema}`, `Activo hace ${duracion(s.activo_seg)}`, `Base: ${s.base.tipo}${s.base.tamano != null ? ' ' + bytes(s.base.tamano) : ''}`,
      `Autenticación: ${s.autenticacion} · cookie segura: ${s.cookie_segura ? 'sí' : 'no'} · sesión ${s.sesion_horas} h`, `Disco libre: ${bytes(s.disco_libre)}`, `Logs: ${s.logs.carpeta} (${bytes(s.logs.tamano)})`].join('\n'), 'Resumen copiado'); break; }
  }
});
function admNuevaCuenta(){
  abrirDlg('Nueva cuenta', `<div class="fgrid">
      <label class="f">Nombre<input type="text" name="cNombre" autocomplete="off" placeholder="Andrea Rojas"></label>
      <label class="f">Usuario<input type="text" name="cUsuario" autocomplete="off" autocapitalize="off" placeholder="arojas"></label>
      <label class="f">Rol<select name="cRol"><option value="analista">Analista</option><option value="admin">Administrador</option></select></label>
      <label class="f">Clave (opcional)<input type="text" name="cClave" autocomplete="off" placeholder="Se genera una temporal"></label></div>
    <p class="small muted" style="margin-top:12px">La persona tendrá que cambiar la clave la primera vez que entre. El usuario se escribe en minúsculas, sin espacios.</p>`,
    `<button class="btn primary" data-act="admCrearCuenta">Crear cuenta</button>`);
  dlg.querySelector('[name="cNombre"]').focus();
}
async function admCrearCuenta(){
  const v = n => (dlg.querySelector(`[name="${n}"]`) || {}).value || '';
  try {
    const d = await api('POST', '/admin/usuarios', {nombre: v('cNombre').trim(), usuario: v('cUsuario').trim(), rol: v('cRol'), clave: v('cClave')});
    dlg.close(); claveTemporalDlg('Cuenta creada', d.nombre, d.clave_temporal); admCargar('usuarios');
  } catch(e){ dErr(e.message); }
}
let _admT;
document.addEventListener('input', ev => {
  const el = ev.target; if (!el.matches) return;
  if (el.matches('[data-admq]')){ clearTimeout(_admT); _admT = setTimeout(() => { const a = ADM(); a.act.f.q = el.value.trim(); a.act.max = 0; admCargar('actividad'); }, 300); }
  else if (el.matches('[data-admeq]')){ clearTimeout(_admT); _admT = setTimeout(() => { const e = ADM().err; e.q = el.value.trim(); admCargar('errores'); }, 300); }
});
document.addEventListener('change', async ev => {
  const el = ev.target; if (!el.matches) return;
  if (el.matches('[data-admf]')){ const a = ADM(); a.act.f[el.dataset.admf] = el.value; a.act.max = 0; a.act.limite = 100; admCargar('actividad'); }
  else if (el.matches('[data-admorigen]')){ ADM().err.origen = el.value; admCargar('errores'); }
  else if (el.matches('[data-admvivo]')){ ADM().vivo = el.checked; render(); }
  else if (el.matches('[data-admnota]')){ try { await api('PUT', '/admin/errores/' + el.dataset.admnota, {nota: el.value}); toast('Nota guardada'); } catch(e){ toast(e.message); } }
});
/* Etiqueta flotante del gráfico: sigue al puntero sin redibujar nada */
document.addEventListener('pointerover', ev => {
  const c = ev.target.closest && ev.target.closest('[data-admcol]'), tip = $('#chartTip');
  if (!tip) return;
  if (!c){ tip.hidden = true; return; }
  const r = ADM().resumen; if (!r) return;
  const x = r.serie[+c.dataset.admcol], d = aFecha(x.t);
  tip.innerHTML = `<b>${r.por_dia ? d.toLocaleDateString('es-CL', {weekday: 'short', day: 'numeric', month: 'short'}) : horaDe(x.t) + ' h'}</b><span>${x.acciones} acciones</span><span class="${x.errores ? 'e' : ''}">${x.errores} errores</span>`;
  tip.hidden = false;
  const caja = tip.parentElement.getBoundingClientRect(), col = c.getBoundingClientRect();
  tip.style.left = Math.min(Math.max(col.left - caja.left + col.width / 2, 60), caja.width - 60) + 'px';
});
document.addEventListener('pointerleave', ev => { const tip = $('#chartTip'); if (tip && ev.target.closest && ev.target.closest('.chart-bars')) tip.hidden = true; }, true);
