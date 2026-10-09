/* Cuentas por analista: pantalla de entrada, menú de la cuenta, cambio de clave, "Mi actividad"
   y el aviso al servidor de los errores que ocurren en el navegador.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Utilidades de fecha y copia ============ */
const _fh = new Intl.DateTimeFormat('es-CL', {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false});
const aFecha = iso => iso ? new Date(iso) : null;
const horaDe = iso => { const d = aFecha(iso); return d ? d.toTimeString().slice(0, 5) : ''; };
const fechaHoraDe = iso => { const d = aFecha(iso); return d ? _fh.format(d).replace(',', '') : ''; };
function diaDe(iso){
  const d = aFecha(iso); if (!d) return '';
  const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
  const dd = new Date(d); dd.setHours(0, 0, 0, 0);
  const n = Math.round((hoy - dd) / 864e5);
  if (n === 0) return 'Hoy'; if (n === 1) return 'Ayer';
  return d.toLocaleDateString('es-CL', {weekday: 'long', day: 'numeric', month: 'long'});
}
function haceDe(iso){
  const d = aFecha(iso); if (!d) return 'nunca';
  const s = Math.max(0, (Date.now() - d) / 1000);
  if (s < 45) return 'ahora'; if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`; if (s < 86400 * 30) return `hace ${Math.round(s / 86400)} d`;
  return fechaHoraDe(iso).slice(0, 10);
}
async function copiarTexto(texto, aviso = 'Copiado'){
  try { await navigator.clipboard.writeText(texto); toast(aviso); }
  catch(e){
    const t = document.createElement('textarea'); t.value = texto; t.style.cssText = 'position:fixed;opacity:0'; document.body.append(t); t.select();
    try { document.execCommand('copy'); toast(aviso); } catch(e2){ toast('No se pudo copiar'); } t.remove();
  }
}
const iniciales = n => String(n || '?').trim().split(/\s+/).slice(0, 2).map(x => x[0]).join('').toUpperCase() || '?';
const ROL = {admin: 'Administrador', analista: 'Analista'};

/* ============ Sesión ============ */
const Sesion = {
  modo: 'abierto', cuenta: null, puedeConfigurar: false, _espera: null,
  /* Administración solo existe con cuentas: en modo abierto (cada PC con su nombre) no se muestra */
  esAdmin(){ return !!(this.cuenta && this.cuenta.rol === 'admin'); },
  conCuentas(){ return this.modo === 'cuentas'; },
  quien(){ return this.cuenta ? this.cuenta.nombre : Usuario.get(); },

  async iniciar(){
    let est = null;
    try { est = await fetch('/api/sesion', {headers: {'X-Requested-With': 'od'}}).then(r => r.json()); } catch(e){ return true; }
    this.modo = est.modo || 'abierto'; this.puedeConfigurar = !!est.puede_configurar;
    if (this.modo === 'abierto'){ document.body.classList.remove('entrando'); $('.app').inert = false; if (est.requiere_clave && !est.abierta) await pedirSesion(); return true; }
    if (est.abierta && est.cuenta){
      this.cuenta = est.cuenta;
      if (this.cuenta.debe_cambiar_clave) return this.pantalla(est.configuracion_inicial ? 'inicial' : 'cambio');
      return true;
    }
    return this.pantalla(est.configuracion_inicial ? 'inicial' : 'login');
  },
  /* La sesión caducó (o se cerró en otro lado) con la plataforma abierta */
  expirada(){
    if (this._espera) return this._espera;
    this.cuenta = null; renderFoot();
    this._espera = this.pantalla('login', 'Tu sesión terminó. Entra de nuevo; lo que estabas haciendo sigue en pantalla.').then(ok => { this._espera = null; return ok; });
    return this._espera;
  },
  pantalla(modo, aviso = ''){
    return new Promise(res => {
      E.modo = modo; E.error = aviso; E.ocupado = false; E.exito = false; E.res = res;
      document.body.classList.add('entrando'); $('.app').inert = true;
      pintarEntrada();
      setTimeout(() => { const f = $('#entrada [autofocus]') || $('#entrada input'); if (f) f.focus(); }, 30);
    });
  },
  async salir(){
    try { await api('DELETE', '/sesion'); } catch(e){}
    location.reload();
  },
};

/* ============ Pantalla de entrada ============ */
const E = {modo: 'login', error: '', ocupado: false, exito: false, res: null, ver: false, mayus: false, actual: '', nueva: '', usuario: ''};

function reglasClave(clave, usuario){
  return [
    {ok: clave.length >= 8, t: '8 caracteres o más'},
    {ok: /[A-Za-zÁÉÍÓÚÑáéíóúñ]/.test(clave) && /\d/.test(clave), t: 'Letras y números'},
    {ok: !!clave && !(usuario && clave.toLowerCase().includes(usuario.toLowerCase())), t: 'Sin tu usuario dentro'},
  ];
}
function fuerza(clave){
  let p = 0;
  if (clave.length >= 8) p++; if (clave.length >= 12) p++;
  if (/[a-z]/.test(clave) && /[A-Z]/.test(clave)) p++;
  if (/\d/.test(clave) && /[^A-Za-z0-9]/.test(clave)) p++;
  return Math.min(4, p);
}
function campoClave(nombre, etiqueta, valor, auto, {ayuda = ''} = {}){
  return `<label class="ecampo"><span class="cap">${etiqueta}</span>
    <span class="eclave"><input type="${E.ver ? 'text' : 'password'}" name="${nombre}" value="${esc(valor)}" autocomplete="${auto}" spellcheck="false" autocapitalize="off" ${ayuda ? `placeholder="${esc(ayuda)}"` : ''} data-clave>
    <button type="button" class="ver" data-ver aria-label="${E.ver ? 'Ocultar' : 'Mostrar'} la clave" aria-pressed="${E.ver}">${E.ver ? ICON.ojoNo : ICON.ojo}</button></span></label>`;
}
function pintarEntrada(){
  const el = $('#entrada'); if (!el) return;
  const m = E.modo, forzado = m === 'cambio';
  const titulo = m === 'login' ? 'Entrar' : m === 'inicial' ? 'Crear el primer administrador' : 'Elige tu clave nueva';
  const sub = m === 'login' ? 'Cada analista entra con su cuenta; lo que hagas queda a tu nombre.'
    : m === 'inicial' ? 'Todavía no hay cuentas. Esta persona administra a las demás.'
    : 'La clave que recibiste es temporal. Cámbiala para seguir.';
  let campos = '', reglas = '';
  if (m === 'login'){
    campos = `<label class="ecampo"><span class="cap">Usuario</span>
        <input type="text" name="usuario" value="${esc(E.usuario)}" autocomplete="username" autocapitalize="off" spellcheck="false" autofocus></label>` +
      campoClave('clave', 'Clave', '', 'current-password');
  } else if (m === 'inicial'){
    const cl = E.nueva || '';
    campos = `<label class="ecampo"><span class="cap">Nombre</span><input type="text" name="nombre" value="${esc(E.nombre || '')}" autocomplete="name" autofocus></label>
      <label class="ecampo"><span class="cap">Usuario</span><input type="text" name="usuario" value="${esc(E.usuario)}" autocomplete="username" autocapitalize="off" spellcheck="false" placeholder="ej. vsoto"></label>` +
      campoClave('nueva', 'Clave', cl, 'new-password');
    reglas = reglasHTML(cl, E.usuario);
  } else {
    const cl = E.nueva || '';
    campos = (E.actual ? '' : campoClave('actual', 'Clave temporal (la que recibiste)', '', 'current-password')) +
      campoClave('nueva', 'Clave nueva', cl, 'new-password');
    reglas = reglasHTML(cl, Sesion.cuenta ? Sesion.cuenta.usuario : '');
  }
  const alto = (E.mayus && m !== 'cambio') ? `<p class="emayus" role="status">${ICON.alerta}<span>Bloq Mayús está activado</span></p>` : '';
  const pie = m === 'inicial' && !Sesion.puedeConfigurar
    ? `<p class="enota">Esta pantalla solo crea la primera cuenta desde el propio servidor. Si estás en otro equipo, pídele a TI que ponga <code>ADMIN_INICIAL=usuario:clave:Nombre</code> en el <code>.env</code> y reinicie.</p>` : '';
  const horizonte = codigoBarrasSVG('ORDER DESK TRAZABILIDAD DE PEDIDOS', {modulo: 3, alto: 100, silencio: 2, etiqueta: ''}).replace('<svg ', '<svg preserveAspectRatio="none" ');
  el.innerHTML = `<div class="horizonte" aria-hidden="true">${horizonte}</div>
    <div class="etiqueta-entrada ${E.exito ? 'ok' : ''}" role="dialog" aria-modal="true" aria-labelledby="eTitulo">
      <div class="ee-top"><span class="ee-marca">Order Desk</span><span class="ee-sub">Trazabilidad de pedidos</span></div>
      <form class="ee-cuerpo" data-entrada novalidate>
        <h1 id="eTitulo">${titulo}</h1>
        <p class="ee-lead">${sub}</p>
        <div class="ee-campos ${E.sacudir ? 'sacude' : ''}">${campos}</div>
        ${reglas}
        ${alto}
        <p class="ee-error" role="alert" id="eError">${esc(E.error)}</p>
        ${pie}
        <button class="btn primary ee-ir" type="submit" ${E.ocupado || (m === 'inicial' && !Sesion.puedeConfigurar) ? 'disabled' : ''}>
          ${E.ocupado ? 'Revisando…' : m === 'login' ? 'Entrar' : m === 'inicial' ? 'Crear cuenta y entrar' : 'Guardar y entrar'}</button>
      </form>
      <div class="ee-pie"><span class="ee-barras">${codigoBarrasSVG('OD-TRAZ', {modulo: 1.5, alto: 34, silencio: 4, etiqueta: 'Código decorativo'})}<i class="ee-scan" aria-hidden="true"></i></span>
        <span class="ee-nota">${esc(location.hostname)} · ${new Date().toLocaleDateString('es-CL')}</span></div>
    </div>`;
  E.sacudir = false;
}
function reglasHTML(clave, usuario){
  const f = fuerza(clave), rs = reglasClave(clave, usuario);
  return `<div class="reglas" aria-live="polite"><div class="fuerza f${clave ? f : 0}" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
    <ul>${rs.map(r => `<li class="${r.ok ? 'ok' : ''}">${r.ok ? ICON.check : '<span class="pt"></span>'}<span>${r.t}</span></li>`).join('')}</ul></div>`;
}
function entradaError(msg){
  E.error = msg; E.ocupado = false; E.sacudir = true; pintarEntrada();
  const f = $('#entrada input[name="clave"], #entrada input[name="nueva"]') || $('#entrada input'); if (f){ f.focus(); f.select(); }
}
function entradaListo(){
  E.exito = true; E.ocupado = false; pintarEntrada();           // un barrido de luz sobre el código: confirma que entró
  setTimeout(() => {
    document.body.classList.remove('entrando'); $('.app').inert = false; $('#entrada').innerHTML = '';
    E.nueva = E.actual = ''; E.usuario = ''; const r = E.res; E.res = null; renderFoot(); if (r) r(true);
  }, matchMedia('(prefers-reduced-motion: reduce)').matches ? 80 : 520);
}
function leerCampos(){
  const v = n => ($(`#entrada [name="${n}"]`) || {}).value || '';
  E.usuario = v('usuario') || E.usuario; if ($('#entrada [name="nombre"]')) E.nombre = v('nombre');
  if ($('#entrada [name="nueva"]')) E.nueva = v('nueva');
}
async function enviarEntrada(){
  if (E.ocupado) return;
  leerCampos();
  const vals = {};
  document.querySelectorAll('#entrada input[name]').forEach(i => { vals[i.name] = i.value; });      // se leen antes de redibujar
  const v = n => vals[n] || '';
  E.ocupado = true; E.error = ''; pintarEntrada();
  try {
    if (E.modo === 'login'){
      const usuario = v('usuario').trim(), clave = v('clave');
      if (!usuario || !clave) return entradaError('Escribe tu usuario y tu clave.');
      const r = await api('POST', '/sesion', {usuario, clave});
      Sesion.cuenta = r.cuenta; E.actual = clave;
      if (r.cuenta.debe_cambiar_clave){ E.modo = 'cambio'; E.ocupado = false; E.error = ''; E.nueva = ''; pintarEntrada(); setTimeout(() => $('#entrada input')?.focus(), 30); return; }
      entradaListo();
    } else if (E.modo === 'inicial'){
      const r = await api('POST', '/sesion/configuracion-inicial', {usuario: E.usuario.trim(), nombre: (E.nombre || '').trim(), clave: E.nueva});
      Sesion.cuenta = r.cuenta; Sesion.modo = 'cuentas'; entradaListo();
    } else {
      const falta = reglasClave(E.nueva, Sesion.cuenta.usuario).find(r => !r.ok);
      if (falta) return entradaError('La clave nueva necesita: ' + falta.t.toLowerCase() + '.');
      await api('POST', '/sesion/clave', {actual: E.actual || v('actual'), nueva: E.nueva});
      Sesion.cuenta.debe_cambiar_clave = false; entradaListo();
    }
  } catch(e){ entradaError(e.message); }
}
document.addEventListener('submit', ev => { if (ev.target.matches('[data-entrada]')){ ev.preventDefault(); enviarEntrada(); } });
document.addEventListener('input', ev => {
  const t = ev.target; if (!t.closest || !t.closest('#entrada')) return;
  if (t.name === 'nueva' || t.name === 'usuario' && E.modo === 'inicial'){
    leerCampos();
    const r = $('#entrada .reglas'); if (r){                                   // se actualiza solo el medidor, sin redibujar los campos
      const cl = E.nueva, us = E.modo === 'inicial' ? E.usuario : (Sesion.cuenta || {}).usuario || '';
      r.outerHTML = reglasHTML(cl, us);
    }
  }
  if (E.error){ E.error = ''; const p = $('#eError'); if (p) p.textContent = ''; }
});
document.addEventListener('click', ev => {
  const b = ev.target.closest && ev.target.closest('#entrada [data-ver]'); if (!b) return;
  leerCampos(); E.ver = !E.ver; pintarEntrada();
  const i = $('#entrada [data-clave]'); if (i){ i.focus(); const n = i.value.length; i.setSelectionRange(n, n); }
});
document.addEventListener('keydown', ev => {
  if (!ev.target.closest || !ev.target.closest('#entrada')) return;
  if (ev.key === 'Escape'){ ev.preventDefault(); return; }                      // no se puede cerrar sin entrar
  if (ev.getModifierState){
    const m = ev.getModifierState('CapsLock');
    if (m !== E.mayus && ev.target.matches('[data-clave]')){ E.mayus = m; leerCampos(); const c = ev.target.name; pintarEntrada(); const i = $(`#entrada [name="${c}"]`); if (i){ i.focus(); const n = i.value.length; i.setSelectionRange(n, n); } }
  }
});

/* ============ Menú de la cuenta (pie de la barra lateral) ============ */
let _pieSync = {estado: 'ok', texto: ''};
function cuentaHTML(){
  const c = Sesion.cuenta;
  if (!c) return '';                            // sin cuentas no hay nada de usuario en pantalla: el nombre sale del PC
  return `<div class="cuenta-w"><button class="cuenta" data-act="menuCuenta" aria-haspopup="menu" aria-expanded="${!!UI.menuCuenta}" title="Tu cuenta">
      <span class="avatar" aria-hidden="true">${esc(iniciales(c.nombre))}</span>
      <span class="cuenta-t"><b>${esc(c.nombre)}</b><small>${ROL[c.rol] || c.rol}</small></span>${ICON.chevron}</button>
    ${UI.menuCuenta ? `<div class="menu-cuenta" role="menu" id="menuCuenta">
      <button role="menuitem" data-act="miActividad">${ICON.historial}<span>Mi actividad</span></button>
      <button role="menuitem" data-act="cambiarClave">${ICON.llave}<span>Cambiar mi clave</span></button>
      <hr><button role="menuitem" data-act="cerrarSesion">${ICON.salir}<span>Cerrar sesión</span></button></div>` : ''}</div>`;
}
function renderFoot(){
  const el = $('#sync'); if (!el) return;
  const html = `<span class="sync-linea"><span class="dot ${_pieSync.estado}" aria-hidden="true"></span><span>${esc(_pieSync.texto)}</span></span>` + cuentaHTML();
  if (el.innerHTML !== html) el.innerHTML = html;
  renderNav();
}
function menuCuenta(abrir){
  UI.menuCuenta = abrir === undefined ? !UI.menuCuenta : abrir; renderFoot();
  if (UI.menuCuenta) $('#menuCuenta [role="menuitem"]')?.focus();
}
document.addEventListener('click', ev => {
  if (UI.menuCuenta && !ev.target.closest('.cuenta-w')) menuCuenta(false);
});
document.addEventListener('keydown', ev => {
  if (!UI.menuCuenta) return;
  if (ev.key === 'Escape'){ menuCuenta(false); $('.cuenta')?.focus(); }
  else if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp'){
    const it = [...document.querySelectorAll('#menuCuenta [role="menuitem"]')], i = it.indexOf(document.activeElement);
    if (it.length){ ev.preventDefault(); it[(i + (ev.key === 'ArrowDown' ? 1 : -1) + it.length) % it.length].focus(); }
  }
});
function cambiarClave(){
  dlg.classList.add('angosto');
  abrirDlg('Cambiar mi clave', `<div class="stack">
      <label class="f">Clave actual<input type="password" name="actual" autocomplete="current-password"></label>
      <label class="f">Clave nueva<input type="password" name="nueva" autocomplete="new-password"></label>
      <div data-reglas>${reglasHTML('', (Sesion.cuenta || {}).usuario)}</div>
      <label class="f">Repite la clave nueva<input type="password" name="repite" autocomplete="new-password"></label>
      <p class="small muted">Al cambiarla se cierran tus otras sesiones abiertas.</p></div>`,
    `<button class="btn primary" data-act="guardarClave">Cambiar clave</button>`);
  dlg.querySelector('[name="actual"]').focus();
}
document.addEventListener('input', ev => {
  if (ev.target.matches && ev.target.matches('#dlg [name="nueva"]')){
    const r = dlg.querySelector('[data-reglas]'); if (r) r.innerHTML = reglasHTML(ev.target.value, (Sesion.cuenta || {}).usuario);
  }
});
async function guardarClave(){
  const actual = dval('actual'), nueva = dlg.querySelector('[name="nueva"]').value, repite = dlg.querySelector('[name="repite"]').value;
  if (!actual || !nueva) return dErr('Completa los campos.');
  if (nueva !== repite) return dErr('Las dos claves nuevas no coinciden.');
  try { await api('POST', '/sesion/clave', {actual: dlg.querySelector('[name="actual"]').value, nueva}); dlg.close(); toast('Clave cambiada'); }
  catch(e){ dErr(e.message); }
}

/* ============ Mi actividad ============ */
const CATS = {
  pedido: ['Pedidos', 'var(--accent)'], sap: ['SAP', 'var(--warn-solid)'], cubicaje: ['Cubicaje', 'var(--ok-solid)'],
  datos: ['Datos', 'var(--sched)'], cuenta: ['Cuenta', 'var(--muted)'], sistema: ['Sistema', 'var(--edge)'],
};
const catChip = c => `<span class="cat"><i style="background:${(CATS[c] || CATS.sistema)[1]}"></i>${esc((CATS[c] || [c])[0])}</span>`;
const resTag = r => r === 'ok' ? '' : `<span class="tag ${r === 'error' ? 'err' : 'warn'}">${r === 'error' ? 'Falló' : 'Rechazada'}</span>`;

/* Una fila del historial. `admin` agrega a quién pertenece; el número de pedido abre ese pedido */
function filaActividad(a, {admin = false} = {}){
  const ent = a.entidad && /^\d{6,}$/.test(a.entidad) && Store.get('pedidos', safeId(a.entidad));
  return `<li class="act ${a.resultado !== 'ok' ? 'mala' : ''}" data-k="act-${a.id}">
    <time class="act-h num" datetime="${esc(a.at)}" title="${esc(fechaHoraDe(a.at))}">${horaDe(a.at)}</time>
    <span class="act-c">${catChip(a.categoria)}</span>
    <span class="act-t">${admin ? `<b class="act-u">${esc(a.nombre || a.usuario || 'sin nombre')}</b> ` : ''}${esc(a.accion)}${ent ? ` <button class="enlace" data-abrir="${esc(safeId(a.entidad))}">Abrir</button>` : ''}
      ${a.detalle ? `<span class="act-d small muted">${esc(a.detalle)}</span>` : ''}</span>
    <span class="act-r">${resTag(a.resultado)}${a.ms >= 1500 ? `<span class="small muted num">${(a.ms / 1000).toFixed(1).replace('.', ',')} s</span>` : ''}
      ${a.request_id ? `<button class="cod" data-copiar="${esc(a.request_id)}" title="Copiar código de seguimiento">${esc(a.request_id)}</button>` : ''}</span></li>`;
}
function agruparPorDia(filas, pintar){
  let ult = '', html = '';
  for (const a of filas){
    const d = diaDe(a.at);
    if (d !== ult){ html += `${ult ? '</ul>' : ''}<h4 class="act-dia">${esc(d)}</h4><ul class="acts">`; ult = d; }
    html += pintar(a);
  }
  return html ? html + '</ul>' : '';
}
async function cargarMiActividad(){
  UI.mia = UI.mia || {filas: [], total: 0, cat: '', q: '', cargando: true};
  try { const d = await api('GET', '/mi/actividad?limite=500'); Object.assign(UI.mia, {filas: d.filas, total: d.total, usuario: d.usuario, cargando: false, error: ''}); }
  catch(e){ UI.mia.cargando = false; UI.mia.error = e.message; }
  renderSoon();
}
function vistaMiActividad(){
  const m = UI.mia = UI.mia || {filas: [], total: 0, cat: '', q: '', cargando: true};
  if (m.cargando && !m.pedida) { m.pedida = true; cargarMiActividad(); }
  const hoy0 = new Date(); hoy0.setHours(0, 0, 0, 0);
  const sem0 = new Date(hoy0); sem0.setDate(sem0.getDate() - 6);
  const nHoy = m.filas.filter(a => a.categoria !== 'cuenta' && aFecha(a.at) >= hoy0).length;
  const nSem = m.filas.filter(a => a.categoria !== 'cuenta' && aFecha(a.at) >= sem0).length;
  const nErr = m.filas.filter(a => a.resultado !== 'ok' && aFecha(a.at) >= sem0).length;
  const q = (m.q || '').toLowerCase();
  const filas = m.filas.filter(a => (!m.cat || a.categoria === m.cat) && (!q || (a.accion + ' ' + a.entidad + ' ' + a.detalle).toLowerCase().includes(q)));
  const quien = Sesion.cuenta ? Sesion.cuenta.nombre : (m.usuario || Usuario.get() || 'tú');
  return `<div class="page-head"><h2>Mi actividad</h2><span class="muted small">${esc(quien)}</span><span class="spacer"></span>
      <button class="btn sm" data-act="recargarMia">${ICON.refrescar}Actualizar</button></div>
    <div class="kpis">
      <div class="kpi"><span class="cap">Hoy</span><b class="num">${fmt(nHoy)}</b><small>acciones</small></div>
      <div class="kpi"><span class="cap">Últimos 7 días</span><b class="num">${fmt(nSem)}</b><small>acciones</small></div>
      <div class="kpi ${nErr ? 'alerta' : ''}"><span class="cap">Con problemas</span><b class="num">${fmt(nErr)}</b><small>${nErr ? 'rechazadas o con error' : 'todo bien'}</small></div>
      <div class="kpi"><span class="cap">Guardado</span><b class="num">${fmt(m.total)}</b><small>registros tuyos</small></div></div>
    <div class="panel">
      <div class="panel-h"><div class="seg sm" role="group" aria-label="Categoría">
          ${[['', 'Todo'], ['pedido', 'Pedidos'], ['sap', 'SAP'], ['cubicaje', 'Cubicaje'], ['datos', 'Datos'], ['cuenta', 'Cuenta']].map(([k, t]) => `<button data-miacat="${k}" aria-pressed="${m.cat === k}">${t}</button>`).join('')}</div>
        <span class="spacer"></span>
        <label class="searchbox">${ICON.search}<input type="search" data-miaq placeholder="Buscar en mi historial" value="${esc(m.q || '')}" aria-label="Buscar en mi historial"></label></div>
      <div class="panel-b act-lista">${m.cargando ? '<span class="skel" style="width:40%"></span><span class="skel" style="margin-top:10px"></span><span class="skel" style="margin-top:10px;width:70%"></span>'
        : m.error ? `<p class="err">${esc(m.error)}</p>`
        : filas.length ? agruparPorDia(filas, a => filaActividad(a))
        : `<div class="empty"><h3>${m.filas.length ? 'Nada con ese filtro' : 'Todavía no hay actividad'}</h3><p>${m.filas.length ? 'Prueba con otra categoría o borra la búsqueda.' : 'Aquí aparecerá lo que hagas: guardar pedidos, analizar en SAP, cubicar…'}</p></div>`}</div>
      ${filas.length >= 500 ? '<p class="small muted" style="padding:0 16px 14px">Se muestran los últimos 500 movimientos.</p>' : ''}</div>`;
}
document.addEventListener('click', ev => {
  const b = ev.target.closest && ev.target.closest('button'); if (!b) return;
  if (b.dataset.copiar !== undefined){ ev.preventDefault(); copiarTexto(b.dataset.copiar, 'Código copiado: ' + b.dataset.copiar); return; }
  if (b.dataset.miacat !== undefined){ UI.mia.cat = b.dataset.miacat; render(); return; }
  switch (b.dataset.act){
    case 'menuCuenta': menuCuenta(); break;
    case 'miActividad': menuCuenta(false); UI.mia = null; go('miactividad'); break;
    case 'cambiarClave': menuCuenta(false); cambiarClave(); break;
    case 'guardarClave': guardarClave(); break;
    case 'cerrarSesion': menuCuenta(false); Sesion.salir(); break;
    case 'recargarMia': UI.mia.cargando = true; UI.mia.pedida = false; render(); break;
  }
});
document.addEventListener('input', ev => {
  if (ev.target.matches && ev.target.matches('[data-miaq]')){ UI.mia.q = ev.target.value; renderSoon(); }
});

/* ============ Errores del navegador → servidor ============
   Una pantalla en blanco o un fallo de script también queda en el registro, con el código de seguimiento. */
const Reporte = {
  vistos: new Set(), tiempos: [],
  enviar(mensaje, pila, extra){
    mensaje = String(mensaje || 'Error').slice(0, 300);
    if (/ResizeObserver loop|^Script error\.?$/i.test(mensaje)) return;
    const k = mensaje + '|' + String(pila || '').slice(0, 120);
    const t = Date.now(); this.tiempos = this.tiempos.filter(x => t - x < 60000);
    if (this.vistos.has(k) || this.tiempos.length >= 5) return;
    this.vistos.add(k); this.tiempos.push(t);
    try {
      fetch('/api/log/cliente', {method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json', 'X-Requested-With': 'od', ...(Usuario.get() ? {'X-Usuario': Usuario.get()} : {})},
        body: JSON.stringify({mensaje, pila: String(pila || ''), url: location.pathname, vista: (typeof UI !== 'undefined' ? UI.view : ''), extra})}).catch(() => {});
    } catch(e){}
  },
};
window.addEventListener('error', ev => Reporte.enviar(ev.message, ev.error && ev.error.stack, {archivo: `${(ev.filename || '').split('/').pop()}:${ev.lineno}:${ev.colno}`}));
window.addEventListener('unhandledrejection', ev => {
  const r = ev.reason; if (r && r.api) return; Reporte.enviar(r && r.message ? 'Promesa rechazada: ' + r.message : 'Promesa rechazada', r && r.stack);
});
