/* Etiquetas (pack list): cuadrar las etiquetas que manda el cliente con lo que se despachó.
   Cada cliente manda sus etiquetas de una forma, así que lo primero es elegir el cliente. Hoy está DIMARSA
   (archivo ZPL .prn o .txt por correo); los demás muestran que la integración está en camino.
   Parte de la interfaz de Trazabilidad Order Desk. */

const ETQ_LISTOS = ['DIMARSA'];
UI.etq = {cliente: '', archivo: '', res: null, leyendo: false, error: '', sel: new Set(), cuadre: null, cuadrando: false, arrastrando: false, cargandoClientes: false};

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
  if (q.res) return `<div class="etq-zona hecho"><span class="etq-arch">${ICON.file}<b>${esc(q.res.archivo || q.archivo)}</b><small>${fmt(q.res.total_etiquetas)} etiquetas</small></span>
      <button type="button" class="btn sm" data-etq="elegir">Cambiar archivo</button></div>${msg}`;
  return `${msg}<div class="etq-zona ${q.arrastrando ? 'sobre' : ''}" data-etq-zona>
    <i class="etq-subir" aria-hidden="true">${ICON.descargar}</i>
    <b>Arrastra aquí el archivo de etiquetas</b>
    <span class="small muted">El que manda DIMARSA por correo (.prn o .txt)</span>
    <button type="button" class="btn primary" data-etq="elegir">Elegir archivo</button></div>`;
}

function etqResumen(r){
  const sinSku = r.productos.filter(p => !p.sku).length;
  return `<section class="panel etq-res" data-k="etq-res">
    <div class="panel-h"><h2>Lo que trae el archivo</h2><span class="spacer"></span><span class="small muted">Lote ${esc(r.lote || '—')}</span></div>
    <div class="panel-b">
      <div class="etq-stats">
        <div><b class="num">${fmt(r.total_etiquetas)}</b><span>etiquetas</span></div>
        <div><b class="num">${fmt(r.productos.length)}</b><span>productos</span></div>
        <div><b class="num">${fmt(r.filas_impresas)}</b><span>filas de 2 etiquetas</span></div>
        <div class="${sinSku ? 'mal' : 'bien'}"><b class="num">${sinSku ? fmt(sinSku) : 'Todos'}</b><span>${sinSku ? 'sin código Electrolux' : 'con código Electrolux'}</span></div>
      </div>
      ${(r.avisos || []).map(a => `<div class="aviso warn" role="status" style="margin:0 0 8px"><div class="aviso-cuerpo">${esc(a)}</div></div>`).join('')}
      <div class="scroll"><table class="tbl"><thead><tr><th>Cód. DIMARSA</th><th>Descripción</th><th>Cód. Electrolux</th><th>Ubicación</th><th class="n">Etiquetas</th></tr></thead><tbody>
      ${r.productos.map(p => `<tr><td class="num">${esc(p.cod_cliente)}</td><td>${esc(p.descripcion)}</td>
        <td>${p.sku ? `<span class="num">${esc(p.sku)}</span>${p.origen_sku === 'homologacion' ? ' <span class="tag" title="Sale de la maestra de homologación">homologado</span>' : ''}`
                    : `<span class="tag warn" title="La etiqueta trae «${esc(p.sku_etiqueta)}» y la maestra no lo conoce">sin código</span>`}</td>
        <td class="num">${esc(p.ubicacion)}</td><td class="n num">${fmt(p.etiquetas)}</td></tr>`).join('')}
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
    <div class="panel-h"><h2>Cuadrar con la factura</h2><span class="spacer"></span>
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
    <section class="panel"><div class="panel-h"><h2>1. Archivo de etiquetas</h2></div><div class="panel-b">${etqZona()}</div></section>
    ${q.res ? etqResumen(q.res) : ''}
    ${q.res ? etqCuadre() : ''}
  </div>`;
}

/* ---- Acciones ---- */
function etqElegirCliente(c){ Object.assign(UI.etq, {cliente: c, archivo: '', res: null, error: '', sel: new Set(), cuadre: null, leyendo: false, cuadrando: false}); render(); }
async function etqLeer(archivo){
  const q = UI.etq; if (!archivo || q.leyendo) return;
  Object.assign(q, {leyendo: true, archivo: archivo.name, error: '', cuadre: null}); render();
  const fd = new FormData(); fd.append('archivo', archivo);
  try {
    const r = await fetch('/api/etiquetas/dimarsa/analizar', {method: 'POST', body: fd, headers: cab()});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'No se pudo leer el archivo.');
    q.res = d; q.sel = new Set();
  } catch(e){ q.res = null; q.error = e.message === 'Failed to fetch' ? 'Sin conexión con el servidor. Revisa que run.bat siga abierto.' : e.message; }
  q.leyendo = false; render();
}
async function etqCuadrar(){
  const q = UI.etq; if (!q.res || !q.sel.size || q.cuadrando) return;
  Object.assign(q, {cuadrando: true, cuadre: null}); render();
  try { q.cuadre = await api('POST', '/etiquetas/dimarsa/cuadrar', {productos: q.res.productos, entregas: [...q.sel]}); }
  catch(e){ toast(e.message); }
  q.cuadrando = false; render();
}

document.addEventListener('click', ev => {
  if (UI.view !== 'etiquetas') return;
  const t = ev.target.closest && ev.target.closest('[data-etq], [data-etq-cliente]'); if (!t) return;
  if (t.dataset.etqCliente){ etqElegirCliente(t.dataset.etqCliente); return; }
  const a = t.dataset.etq;
  if (a === 'volver') etqElegirCliente('');
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
