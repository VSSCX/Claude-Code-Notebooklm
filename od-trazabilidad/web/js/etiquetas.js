/* Etiquetas (pack list): cuadrar las etiquetas que manda el cliente con lo que se despachó.
   Cada cliente manda sus etiquetas de una forma, así que lo primero es elegir el cliente. Hoy está DIMARSA
   (archivo ZPL .prn o .txt por correo); los demás muestran que la integración está en camino.
   Parte de la interfaz de Trazabilidad Order Desk. */

const ETQ_LISTOS = ['DIMARSA'];
UI.etq = {cliente: '', archivo: '', res: null, filas: [], orig: new Map(), bajando: false, leyendo: false, error: '', sel: new Set(), cuadre: null, cuadrando: false, arrastrando: false, cargandoClientes: false};

const etqListo = c => ETQ_LISTOS.includes(String(c || '').toUpperCase());
const etqIniciales = n => String(n).replace(/[^A-Za-zÁÉÍÓÚÑ0-9 ]/g, '').trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase() || '?';
function etqClientes(){
  const todos = new Set(ETQ_LISTOS);
  for (const c of UI.clientes || []) if (c && c.nombre) todos.add(String(c.nombre).toUpperCase());
  return [...todos].sort((a, b) => (etqListo(b) - etqListo(a)) || a.localeCompare(b, 'es'));
}

/* ---- Vista ---- */
function vistaEtiquetas(){
  const q = UI.etq;
  if (!UI.clientes && !q.cargandoClientes){ q.cargandoClientes = true; cargarClientes().finally(() => { q.cargandoClientes = false; }); }
  if (!q.cliente) return etqElegir();
  return etqListo(q.cliente) ? etqDimarsa() : etqEnIntegracion();
}

/* Cargando: nunca una pantalla en blanco */
const etqCargando = txt => `<div class="etq-carga" role="status" aria-live="polite"><i class="etq-giro" aria-hidden="true"></i><span>${esc(txt)}</span></div>`;

function etqElegir(){
  const cuerpo = UI.clientes
    ? `<div class="etq-grid" id="etq-grid">${etqClientes().map((c, i) => `
        <button type="button" class="etq-card ${etqListo(c) ? 'listo' : ''}" data-etq-cliente="${esc(c)}" style="--i:${i}">
          <span class="etq-ini" aria-hidden="true">${esc(etqIniciales(c))}</span>
          <b>${esc(c)}</b>
          <small>${etqListo(c) ? '<span class="tag ok">Disponible</span>' : '<span class="etq-pronto">En integración</span>'}</small>
        </button>`).join('')}</div>`
    : etqCargando('Cargando clientes…');
  return `<div class="etq-centro" data-k="etq-elegir">
    <i class="etq-logo" aria-hidden="true">${ICON.etiquetas}</i>
    <h1>Etiquetas</h1>
    <p class="etq-sub">¿De qué cliente son las etiquetas? Cada cliente las manda de una forma distinta.</p>
    ${cuerpo}</div>`;
}

function etqEnIntegracion(){
  const c = UI.etq.cliente;
  return `<div class="etq-centro" data-k="etq-integracion">
    <i class="etq-logo grande integra" aria-hidden="true">${ICON.integracion}</i>
    <h1>Estamos trabajando en la integración con ${esc(c)}</h1>
    <p class="etq-sub">Todavía no se pueden cuadrar aquí las etiquetas de este cliente. Cuando esté lista, vas a poder cargarlas y compararlas con la factura desde esta misma pantalla.</p>
    <div class="etq-puntos" aria-hidden="true"><i></i><i></i><i></i></div>
    <button type="button" class="btn" data-etq="volver">${ICON.undo} Elegir otro cliente</button></div>`;
}

/* ---- DIMARSA ---- */
function etqZona(){
  const q = UI.etq;
  if (q.leyendo) return `<div class="etq-zona leyendo" aria-busy="true">${etqCargando(`Leyendo ${q.archivo || 'el archivo'}…`)}<i class="etq-barra" aria-hidden="true"></i></div>`;
  const msg = q.error ? `<div class="aviso error" role="alert" style="margin:0 0 12px"><div class="aviso-cuerpo">${esc(q.error)}</div></div>` : '';
  if (q.res) return `<div class="etq-zona hecho"><span class="etq-arch">${ICON.file}<b>${esc(q.res.archivo || q.archivo)}</b><small>${esc(q.res.formato)} · ${fmt(q.res.total_etiquetas)} etiquetas</small></span>
      <button type="button" class="btn sm" data-etq="elegir">Cambiar archivo</button></div>${msg}`;
  return `${msg}<div class="etq-zona ${q.arrastrando ? 'sobre' : ''}" data-etq-zona>
    <i class="etq-subir" aria-hidden="true">${ICON.descargar}</i>
    <b>Arrastra aquí el archivo de etiquetas</b>
    <span class="small muted">El TXT o el PRN que manda DIMARSA por correo</span>
    <button type="button" class="btn primary" data-etq="elegir">Elegir archivo</button></div>`;
}

/* La tabla editable: una fila por producto, con las columnas del Excel de impresión (más Local y Cantidad) */
const ETQ_COLS = [['cod_interno', 'Cód. DIMARSA', 104], ['nombre', 'Descripción', 280], ['marca', 'Marca', 118], ['atributo', 'Atributo', 84],
  ['orden_compra', 'N° OC', 92], ['serie', 'Serie', 88], ['cod_proveedor', 'Cód. proveedor', 130], ['precio', 'Precio', 76], ['cod_usuario', 'Cód. usuario', 90],
  ['rubro', 'Rubro', 76], ['linea', 'Línea', 76], ['familia', 'Familia', 80], ['local', 'Local', 66], ['cantidad', 'Cantidad', 86]];
const ETQ_AYUDA = {local: 'El 1006 que viene en el TXT', cantidad: 'Cuántas etiquetas se imprimen de este producto', cod_proveedor: 'Código Electrolux (o el modelo, si el archivo no trae código)',
  rubro: 'Ej. 00002', linea: 'Ej. 00010', familia: 'Ej. 00030'};
let _etqId = 0;
const etqTotal = () => UI.etq.filas.reduce((a, f) => a + (+f.cantidad || 0), 0);
const etqIgual = (a, b) => String(a ?? '') === String(b ?? '');
const etqCambiada = (f, c) => { const o = UI.etq.orig.get(f._id); return !o || !etqIgual(o[c], f[c]); };
const etqNCambios = () => UI.etq.filas.reduce((n, f) => n + (UI.etq.orig.has(f._id) ? ETQ_COLS.filter(([c]) => etqCambiada(f, c)).length : 1), 0)
  + [...UI.etq.orig.keys()].filter(id => !UI.etq.filas.some(f => f._id === id)).length;

function etqResumen(r){
  const q = UI.etq, nc = etqNCambios();
  return `<section class="panel etq-res" data-k="etq-res">
    <div class="panel-h"><h2>2. Cómo quedan las etiquetas</h2><span class="spacer"></span>
      <button type="button" class="btn sm" data-etq="agregar">${ICON.plus} Agregar fila</button>
      <button type="button" class="btn sm" data-etq="restaurar" ${nc ? '' : 'disabled'} title="Vuelve a lo que traía el archivo">${ICON.undo} Deshacer cambios</button>
      <button type="button" class="btn primary" data-etq="excel" ${q.bajando ? 'disabled' : ''} title="Baja la tabla en el Excel que se usa para imprimir">${q.bajando ? '<i class="etq-giro chico" aria-hidden="true"></i> Preparando…' : `${ICON.descargar} Descargar Excel`}</button></div>
    <div class="panel-b">
      <div class="etq-stats">
        <div><b class="num" data-etq-total>${fmt(etqTotal())}</b><span>etiquetas</span></div>
        <div><b class="num">${fmt(q.filas.length)}</b><span>productos</span></div>
        <div><b class="num">${esc(r.orden_compra || '—')}</b><span>orden de compra · ${esc(r.formato)}</span></div>
        <div class="${nc ? 'edit' : ''}"><b class="num" data-etq-cambios>${nc ? fmt(nc) : 'Sin'}</b><span>${nc === 1 ? 'cambio tuyo' : 'cambios tuyos'}</span></div>
      </div>
      ${(r.avisos || []).map(a => `<div class="aviso warn" role="status" style="margin:0 0 8px"><div class="aviso-cuerpo">${esc(a)}</div></div>`).join('')}
      <div class="scroll etq-scroll"><table class="tbl etq-tbl"><thead><tr>${ETQ_COLS.map(([c, t, w]) => `<th style="min-width:${w}px" ${ETQ_AYUDA[c] ? `title="${esc(ETQ_AYUDA[c])}"` : ''} class="${c === 'cantidad' ? 'n' : ''}">${t}</th>`).join('')}<th></th></tr></thead><tbody>
      ${q.filas.map(f => `<tr data-k="etq-f${f._id}">${ETQ_COLS.map(([c, t]) => {
        const cod = c === 'cod_proveedor' && !/^\d{6,}$/.test(String(f[c]).trim());
        return `<td><input class="${c === 'cantidad' ? 'n num' : ''} ${etqCambiada(f, c) ? 'edit' : ''} ${cod ? 'modelo' : ''}" data-etq-celda="${f._id}:${c}" value="${esc(f[c])}" aria-label="${esc(t)}" ${c === 'cantidad' ? 'inputmode="numeric"' : ''} spellcheck="false" autocomplete="off"></td>`; }).join('')}
        <td><button type="button" class="btn quiet sm icon" data-etq-borrar="${f._id}" aria-label="Quitar esta fila" title="Quitar esta fila">${ICON.x}</button></td></tr>`).join('')}
      </tbody></table></div></div></section>`;
}

/* Entregas de DIMARSA que se pueden cuadrar: las de los pedidos de ese cliente (si no hay, las de todos, con aviso) */
function etqEntregas(){
  const todos = Store.list('pedidos');
  const prop = todos.filter(p => /dimarsa/i.test(p.cliente || ''));
  const peds = prop.length ? prop : todos;
  const por = new Map(peds.map(p => [p.pedido, []]));
  for (const e of Store.list('entregas')) if (!e.anulada && por.has(e.pedido)) por.get(e.pedido).push(e);
  return {propios: prop.length > 0, grupos: [...por].filter(([, es]) => es.length).map(([pedido, es]) => ({pedido, entregas: es.sort((a, b) => String(a.entrega).localeCompare(String(b.entrega)))}))};
}
function etqCuadre(){
  const q = UI.etq, {propios, grupos} = etqEntregas();
  const lista = grupos.length ? grupos.map(g => {
    const todas = g.entregas.every(e => q.sel.has(e.entrega));
    return `<div class="etq-ped"><label class="etq-ped-h"><input type="checkbox" data-etq-ped="${esc(g.pedido)}" ${todas ? 'checked' : ''}> <b>Pedido ${esc(g.pedido)}</b>
        <span class="small muted">${g.entregas.length} ${g.entregas.length === 1 ? 'entrega' : 'entregas'}</span></label>
      <div class="etq-ents">${g.entregas.map(e => `<label class="etq-ent ${q.sel.has(e.entrega) ? 'on' : ''}"><input type="checkbox" data-etq-ent="${esc(e.entrega)}" ${q.sel.has(e.entrega) ? 'checked' : ''}>
        <span class="num">${esc(e.entrega)}</span><small>${fmt(unidades(e))} un.${e.grupo ? ` · grupo ${esc(e.grupo)}` : ''}</small></label>`).join('')}</div></div>`;
  }).join('') : `<div class="empty"><h3>No hay entregas para cuadrar</h3><p>Crea las entregas del pedido para poder compararlas con las etiquetas.</p></div>`;
  return `<section class="panel" data-k="etq-cuadre">
    <div class="panel-h"><h2>3. Cuadrar con la factura (opcional)</h2><span class="spacer"></span>
      <button type="button" class="btn primary" data-etq="cuadrar" ${q.sel.size && !q.cuadrando ? '' : 'disabled'}>${q.cuadrando ? '<i class="etq-giro chico" aria-hidden="true"></i> Cuadrando…' : 'Cuadrar'}</button></div>
    <div class="panel-b">
      <p class="small muted" style="margin-top:0">Elige las entregas que van con estas etiquetas. Se compara, producto por producto, cuántas etiquetas hay contra cuántas unidades se despacharon.</p>
      ${grupos.length && !propios ? '<div class="aviso warn" style="margin:0 0 12px"><div class="aviso-cuerpo">No hay pedidos de DIMARSA: se muestran los de todos los clientes.</div></div>' : ''}
      ${lista}
      ${q.cuadrando ? etqCargando('Comparando etiquetas y entregas…') : q.cuadre ? etqResultado(q.cuadre) : ''}
    </div></section>`;
}
const ETQ_ESTADO = {ok: ['ok', 'Cuadra'], faltan: ['warn', 'Faltan etiquetas'], sobran: ['warn', 'Sobran etiquetas'],
                    sin_entrega: ['err', 'Sin entrega'], sin_etiqueta: ['err', 'Sin etiqueta']};
function etqResultado(c){
  const bien = c.cuadra;
  return `<div class="etq-resultado" data-k="etq-resultado">
    <div class="aviso ${bien ? 'ok' : 'warn'}" role="status" style="margin:16px 0 12px"><div class="aviso-cuerpo"><b>${bien ? 'Cuadra: etiquetas y entregas son iguales.' : `Hay ${fmt(c.con_diferencia + (c.sin_codigo ? 1 : 0))} ${c.con_diferencia + (c.sin_codigo ? 1 : 0) === 1 ? 'diferencia' : 'diferencias'} por revisar.`}</b>
      <span class="small"> ${fmt(c.etiquetas)} etiquetas · ${fmt(c.unidades)} unidades despachadas${c.sin_codigo ? ` · ${fmt(c.sin_codigo)} etiquetas sin código Electrolux` : ''}</span></div></div>
    <div class="scroll"><table class="tbl"><thead><tr><th>Código</th><th>Descripción</th><th class="n">Etiquetas</th><th class="n">Entregas</th><th class="n">Diferencia</th><th>Estado</th></tr></thead><tbody>
    ${c.filas.map(f => { const [t, txt] = ETQ_ESTADO[f.estado] || ['', f.estado];
      return `<tr class="${f.estado === 'ok' ? '' : 'etq-dif'}"><td class="num">${esc(f.sku)}</td><td>${esc(f.descripcion)}</td><td class="n num">${fmt(f.etiquetas)}</td><td class="n num">${fmt(f.unidades)}</td>
        <td class="n num">${f.diferencia > 0 ? '+' : ''}${fmt(f.diferencia)}</td><td><span class="tag ${t}">${txt}</span></td></tr>`; }).join('')}
    </tbody></table></div></div>`;
}

function etqDimarsa(){
  const q = UI.etq;
  return `<div class="etq-dim" data-k="etq-dimarsa">
    <div class="etq-top"><button type="button" class="btn quiet sm" data-etq="volver">${ICON.undo} Otro cliente</button>
      <h1>Etiquetas · <span>DIMARSA</span></h1></div>
    <input type="file" data-etq-archivo accept=".prn,.txt,.zpl,text/plain" hidden>
    <section class="panel"><div class="panel-h"><h2>1. Archivo de DIMARSA</h2></div><div class="panel-b">${etqZona()}</div></section>
    ${q.res ? etqResumen(q.res) : ''}
    ${q.res ? etqCuadre() : ''}
  </div>`;
}

/* ---- Acciones ---- */
function etqElegirCliente(c){ Object.assign(UI.etq, {cliente: c, archivo: '', res: null, filas: [], orig: new Map(), bajando: false, error: '', sel: new Set(), cuadre: null, leyendo: false, cuadrando: false}); render(); }
async function etqLeer(archivo){
  const q = UI.etq; if (!archivo || q.leyendo) return;
  Object.assign(q, {leyendo: true, archivo: archivo.name, error: '', cuadre: null}); render();
  const fd = new FormData(); fd.append('archivo', archivo);
  try {
    const r = await fetch('/api/etiquetas/dimarsa/analizar', {method: 'POST', body: fd, headers: cab()});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'No se pudo leer el archivo.');
    q.res = d; q.sel = new Set(); q.filas = d.filas.map(f => ({...f, _id: ++_etqId})); q.orig = new Map(q.filas.map(f => [f._id, {...f}]));
  } catch(e){ q.res = null; q.filas = []; q.error = e.message === 'Failed to fetch' ? 'Sin conexión con el servidor. Revisa que run.bat siga abierto.' : e.message; }
  q.leyendo = false; render();
}
async function etqCuadrar(){
  const q = UI.etq; if (!q.res || !q.filas.length || !q.sel.size || q.cuadrando) return;
  Object.assign(q, {cuadrando: true, cuadre: null}); render();
  try { q.cuadre = await api('POST', '/etiquetas/dimarsa/cuadrar', {filas: q.filas, entregas: [...q.sel]}); }
  catch(e){ toast(e.message); }
  q.cuadrando = false; render();
}

document.addEventListener('click', ev => {
  if (UI.view !== 'etiquetas') return;
  const t = ev.target.closest && ev.target.closest('[data-etq], [data-etq-cliente], [data-etq-borrar]'); if (!t) return;
  if (t.dataset.etqCliente){ etqElegirCliente(t.dataset.etqCliente); return; }
  if (t.dataset.etqBorrar){ UI.etq.filas = UI.etq.filas.filter(f => String(f._id) !== t.dataset.etqBorrar); UI.etq.cuadre = null; render(); return; }
  const a = t.dataset.etq;
  if (a === 'volver') etqElegirCliente('');
  else if (a === 'agregar'){
    const f = {...etqFilaNueva(), _id: ++_etqId}; UI.etq.filas.push(f); UI.etq.cuadre = null; render();
    const i = document.querySelector(`[data-etq-celda="${f._id}:cod_interno"]`); if (i){ i.scrollIntoView({block: 'center'}); i.focus(); }
  }
  else if (a === 'restaurar'){ UI.etq.filas = [...UI.etq.orig.values()].map(f => ({...f})); UI.etq.cuadre = null; render(); }
  else if (a === 'excel') etqDescargar();
  else if (a === 'elegir'){ const i = document.querySelector('[data-etq-archivo]'); if (i){ i.value = ''; i.click(); } }
  else if (a === 'cuadrar') etqCuadrar();
});
document.addEventListener('change', ev => {
  if (UI.view !== 'etiquetas') return;
  const t = ev.target;
  if (t.matches && t.matches('[data-etq-archivo]')){ etqLeer(t.files[0]); return; }
  if (t.dataset && t.dataset.etqEnt !== undefined){
    t.checked ? UI.etq.sel.add(t.dataset.etqEnt) : UI.etq.sel.delete(t.dataset.etqEnt);
    UI.etq.cuadre = null; render(); return;
  }
  if (t.dataset && t.dataset.etqPed !== undefined){
    for (const e of Store.list('entregas')) if (!e.anulada && e.pedido === t.dataset.etqPed) t.checked ? UI.etq.sel.add(e.entrega) : UI.etq.sel.delete(e.entrega);
    UI.etq.cuadre = null; render();
  }
});
/* Arrastrar el archivo sobre la zona */
document.addEventListener('dragover', ev => {
  const z = ev.target.closest && ev.target.closest('[data-etq-zona]'); if (!z || UI.view !== 'etiquetas') return;
  ev.preventDefault(); if (!UI.etq.arrastrando){ UI.etq.arrastrando = true; z.classList.add('sobre'); }
});
document.addEventListener('dragleave', ev => {
  const z = ev.target.closest && ev.target.closest('[data-etq-zona]'); if (!z || z.contains(ev.relatedTarget)) return;
  UI.etq.arrastrando = false; z.classList.remove('sobre');
});
document.addEventListener('drop', ev => {
  const z = ev.target.closest && ev.target.closest('[data-etq-zona]'); if (!z || UI.view !== 'etiquetas') return;
  ev.preventDefault(); UI.etq.arrastrando = false;
  const f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0]; if (f) etqLeer(f);
});
/* Un resalte que se desliza de un cliente al otro, como el del menú de la izquierda (solo con mouse) */
document.addEventListener('pointerover', ev => {
  if (ev.pointerType && ev.pointerType !== 'mouse') return;
  const g = document.getElementById('etq-grid'), c = ev.target.closest && ev.target.closest('.etq-card'); if (!g || !c || !g.contains(c)) return;
  g.style.setProperty('--gx', c.offsetLeft + 'px'); g.style.setProperty('--gy', c.offsetTop + 'px');
  g.style.setProperty('--gw', c.offsetWidth + 'px'); g.style.setProperty('--gh', c.offsetHeight + 'px'); g.classList.add('hover');
});
document.addEventListener('pointerout', ev => {
  const g = document.getElementById('etq-grid'); if (g && !g.contains(ev.relatedTarget)) g.classList.remove('hover');
});

/* ---- Editar la tabla ---- */
const etqFilaNueva = () => ({cod_interno: '', nombre: '', marca: '', atributo: '000000', orden_compra: (UI.etq.res || {}).orden_compra || '', serie: '', cod_proveedor: '',
  precio: '', cod_usuario: 1588, rubro: '', linea: '', familia: '', local: '1006', cantidad: 0});
/* Cada tecla se guarda al momento y solo se actualizan los totales: la tabla no se vuelve a dibujar mientras escribes */
document.addEventListener('input', ev => {
  const i = ev.target; if (UI.view !== 'etiquetas' || !i.dataset || !i.dataset.etqCelda) return;
  const [id, campo] = i.dataset.etqCelda.split(':'), f = UI.etq.filas.find(x => String(x._id) === id); if (!f) return;
  f[campo] = campo === 'cantidad' ? Math.max(0, parseInt(String(i.value).replace(/\D/g, ''), 10) || 0) : i.value;
  UI.etq.cuadre = null;
  i.classList.toggle('edit', etqCambiada(f, campo));
  if (campo === 'cod_proveedor') i.classList.toggle('modelo', !/^\d{6,}$/.test(String(f[campo]).trim()));
  const tot = document.querySelector('[data-etq-total]'), nc = document.querySelector('[data-etq-cambios]');
  if (tot) tot.textContent = fmt(etqTotal());
  if (nc){ const n = etqNCambios(); nc.textContent = n ? fmt(n) : 'Sin'; nc.parentElement.classList.toggle('edit', n > 0); }
});
/* Enter baja a la misma columna de la fila siguiente, como en una planilla */
document.addEventListener('keydown', ev => {
  const i = ev.target; if (ev.key !== 'Enter' || UI.view !== 'etiquetas' || !i.dataset || !i.dataset.etqCelda) return;
  const campo = i.dataset.etqCelda.split(':')[1], fila = i.closest('tr'), sig = ev.shiftKey ? fila.previousElementSibling : fila.nextElementSibling;
  const dest = sig && sig.querySelector(`[data-etq-celda$=":${campo}"]`); if (dest){ ev.preventDefault(); dest.focus(); dest.select(); }
});

/* ---- Descargar el Excel de impresión ---- */
async function etqDescargar(){
  const q = UI.etq; if (!q.filas.length || q.bajando) return;
  if (q.filas.some(f => !String(f.cod_interno).trim())) return toast('Hay filas sin código DIMARSA: complétalas o quítalas antes de descargar.');
  q.bajando = true; render();
  try {
    const r = await fetch('/api/etiquetas/dimarsa/excel', {method: 'POST', headers: cab({'Content-Type': 'application/json'}),
      body: JSON.stringify({filas: q.filas.map(({_id, ...f}) => f), archivo: q.res ? q.res.archivo : ''})});
    if (!r.ok){ const d = await r.json().catch(() => ({})); throw new Error(typeof d.detail === 'string' ? d.detail : 'No se pudo preparar el Excel.'); }
    const nombre = ((r.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/) || [])[1] || 'Etiquetas_DIMARSA.xlsx';
    const url = URL.createObjectURL(await r.blob()), a = document.createElement('a');
    a.href = url; a.download = nombre; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 4000);
    toast(`Excel descargado: ${nombre}`);
  } catch(e){ toast(e.message === 'Failed to fetch' ? 'Sin conexión con el servidor. Revisa que run.bat siga abierto.' : e.message); }
  q.bajando = false; render();
}
