/* Vistas de Por hacer y del Cubicador libre.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Vista: Por hacer ============ */
function vistaBandeja(){
  const gs = grupos().filter(g => g.next).filter(g => {
    if (!UI.cliente) return true;
    return g.entregas.some(e => (Store.get('pedidos', safeId(e.pedido)) || {}).cliente === UI.cliente);
  });
  const cols = STEPS.map(s => ({s, items: gs.filter(g => g.next.k === s.k)
    .sort((a, b) => (a.cita.fecha || '9').localeCompare(b.cita.fecha || '9'))})).filter(c => c.items.length);
  return `<div class="row" style="margin-bottom:14px;justify-content:space-between"><h2>Por hacer</h2><div class="row">${filtroCliente()}</div></div>
  ${cols.length ? `<div class="inbox">${cols.map(({s, items}) => `<section class="col"><h3>${esc(s.t)} <span class="num">${items.length}</span></h3>
    ${items.map(g => { const p = Store.get('pedidos', safeId(g.entregas[0].pedido)) || {};
      return `<div class="card"><div class="c1"><b>${g.sinGrupo ? 'Entrega ' + esc(g.entregas[0].entrega) : 'Grupo ' + esc(g.grupo)}</b><span class="num">${fmt(g.unidades)} un.</span></div>
      <div class="c2">${esc(p.cliente || '—')} · ${g.pedidos.length > 1 ? g.pedidos.length + ' pedidos' : 'Pedido ' + esc(g.pedidos[0])} · ${g.entregas.length} entrega(s)${g.cita.fecha ? ` · ${fmtFecha(g.cita.fecha)} ${esc(g.cita.hora || '')}` : ''}</div>
      <div class="row">${POR_ENTREGA.includes(s.k) ? '' : `<button class="btn primary" data-gpaso="${s.k}" data-grupo="${esc(g.key)}" data-forzar="1">Marcar hecho</button>`}
      <button class="btn ghost" data-abrir="${esc(safeId(g.pedidos[0]))}" data-sub="${POR_ENTREGA.includes(s.k) ? 'entregas' : 'grupos'}">Ver pedido</button></div></div>`; }).join('')}</section>`).join('')}</div>`
  : `<div class="panel empty"><h3>No hay tareas pendientes</h3><p>Aquí aparece el próximo paso de cada camión.</p></div>`}`;
}

/* ============ Vista: Cubicador libre ============ */
UI.cub = null; UI.cubSug = []; UI.cubBuscando = ''; UI.ajustes = null; UI.verAjustes = false;
UI.vistaCamion = 'rampla';   // a qué camión volver desde la vista de un solo pallet UI.verAjustes = false;
async function cargarAjustes(){
  try { UI.ajustes = await api('GET', '/ajustes-cubicaje'); } catch(e){ UI.ajustes = null; }
}
async function guardarAjustes(datos){
  try { UI.ajustes = await api('PUT', '/ajustes-cubicaje', {...(UI.ajustes || {}), ...datos}); }
  catch(e){ return toast(e.message); }
  if (UI.cub) await calcularCubLibre({});
  if (UI.sel){ const p = Store.get('pedidos', UI.sel); if (p) delete UI.cubicaje[p.pedido]; }
  render();
}
const VISTAS = [['rampla','Rampla 53'], ['camion50','Camión 50'], ['pallet','Un solo pallet']];
const PALETA_CUB = ['#E8534E','#F2C94C','#56A3D9','#27AE60','#9B59B6','#E67E22',
                    '#1ABC9C','#E84393','#3498DB','#F39C12','#7F8C8D','#16A085'];
const letraItem = i => String.fromCharCode(65 + (i % 26)) + (i >= 26 ? Math.floor(i / 26) : '');
async function cargarCubLibre(){
  try { UI.cub = await api('GET', '/cubicaje-libre'); }
  catch(e){ UI.cub = {lineas:[], cliente:'', modo:'MDA', vista:'rampla'}; }
  if (!UI.clientes) await cargarClientes();
  if (!UI.ajustes) await cargarAjustes();
  render();
}
async function calcularCubLibre(extra){
  const c = {...(UI.cub || {}), ...(extra || {})};
  UI.cub = {...c, calculando:true}; render();
  try { UI.cub = await api('POST', '/cubicaje-libre', c); }
  catch(e){ UI.cub = {...c, error:e.message}; toast(e.message); }
  render();
}
async function importarCarga(input){
  const f = input.files[0]; if (!f) return;
  const fd = new FormData(); fd.append('file', f);
  UI.cub = {...(UI.cub || {}), calculando:true}; render();
  try {
    const r = await fetch('/api/cubicaje-libre/importar', {method:'POST', body:fd,
      headers: Usuario.get() ? {'X-Usuario': Usuario.get()} : {}});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'No se pudo importar');
    UI.cub = d;
    const avisos = [];
    if ((d.sin_medidas_archivo || []).length) avisos.push('Sin medidas: ' + d.sin_medidas_archivo.slice(0,5).join(', '));
    if ((d.errores_archivo || []).length) avisos.push(d.errores_archivo.slice(0,3).join(' · '));
    const reparto = d.predistribuido || [];
    const sucs = new Set(reparto.map(x => x.sucursal)).size;
    Avisos.agregar(avisos.length ? 'info' : 'ok',
                   `${d.importadas} producto(s) importados` + (reparto.length ? ` · reparto en ${sucs} sucursales` : ''),
                   avisos.join(' | '), []);
  } catch(e){ UI.cub = {...(UI.cub || {}), calculando:false}; toast(e.message); }
  render();
}

async function sugerirSku(texto){
  UI.cubBuscando = texto;
  if (texto.trim().length < 2){ UI.cubSug = []; return render(); }
  try { UI.cubSug = (await api('GET', '/medidas/sugerir?q=' + encodeURIComponent(texto))).sugerencias; }
  catch(e){ UI.cubSug = []; }
  render();
}
async function traerPedido(numero){
  if (!numero) return;
  UI.cub = {...(UI.cub || {}), calculando:true}; render();
  try {
    UI.cub = await api('POST', '/cubicaje-libre/desde-pedido', {pedido: String(numero).trim()});
    toast(`Pedido ${numero} cargado en el cubicador`);
  } catch(e){ UI.cub = {...(UI.cub || {}), calculando:false}; toast(e.message); }
  render();
}
function agregarSku(sku, qty){
  const c = UI.cub || {lineas:[]};
  const lineas = [...(c.lineas || [])];
  const ya = lineas.find(l => l.sku === sku);
  if (ya) ya.qty = (+ya.qty || 0) + (+qty || 1); else lineas.push({sku, qty: +qty || 1});
  UI.cubSug = []; UI.cubBuscando = '';
  calcularCubLibre({lineas});
}
/* El modo del motor son dos preguntas: cómo va la carga y a quién va. */
function modoDe(tipo, destino){
  if (tipo === 'SDA') return destino === 'sucursal' ? 'SDA PREDISTRIBUIDO' : 'SDA STOCK';
  return destino === 'sucursal' ? 'MDA PREDISTRIBUIDO' : 'MDA';
}
function segmentado(campo, actual, opciones){
  return `<div class="seg" role="group">${opciones.map(([v, t, ayuda]) =>
    `<button type="button" data-cubopt="${campo}" data-valor="${esc(v)}" aria-pressed="${v === actual}"${ayuda ? ` title="${esc(ayuda)}"` : ''}>${esc(t)}</button>`).join('')}</div>`;
}
function cambiarOpcionCub(campo, valor){
  const c = UI.cub || {};
  let tipo = /SDA/.test(c.modo || '') ? 'SDA' : 'MDA';
  let destino = /PREDISTRIBUIDO/.test(c.modo || '') ? 'sucursal' : 'stock';
  const cambios = {};
  if (campo === 'tipo') tipo = valor;
  else if (campo === 'destino') destino = valor;
  else if (campo === 'caja_master') cambios.caja_master = valor;
  else if (campo === 'vista'){
    cambios.vista = valor;
    if (valor !== 'pallet') UI.vistaCamion = valor;          // a qué camión volver desde un pallet
  }
  if (campo === 'tipo' || campo === 'destino'){
    cambios.modo = modoDe(tipo, destino);
    // fuera de MDA el motor exige indicar caja master: se parte en "sin" en vez de fallar
    if (cambios.modo !== 'MDA' && !c.caja_master) cambios.caja_master = 'SIN CAJA MASTER';
    // la vista de un pallet solo existe con pallets
    if (tipo === 'MDA' && c.vista === 'pallet') cambios.vista = UI.vistaCamion || 'rampla';
  }
  if (Object.keys(cambios).length) calcularCubLibre(cambios);
}
function quitarRepartoCub(){
  const tipo = /SDA/.test((UI.cub || {}).modo || '') ? 'SDA' : 'MDA';
  calcularCubLibre({predistribuido: [], modo: modoDe(tipo, 'stock')});
}
function seccionAjustes(){
  const a = UI.ajustes || {orientacion_pallet:'largo', celda_cm:1, capacidad_pallet:'geometria'};
  const op = [['largo','Largo del pallet (como EasyCargo)'],
              ['excel','Ancho del pallet (como el Excel)']];
  const cap = [['geometria','Calcularla con las medidas reales'],
               ['tabla','Usar la columna Máx Pallet de la base']];
  return `<details style="margin-top:12px" ${UI.verAjustes ? 'open' : ''} data-ajustes><summary>Ajustes del motor</summary>
    <div class="grid-form" style="margin-top:10px">
      <label class="f">Cómo se acomodan las cajas en el pallet
        <select data-ajorient>${op.map(([v, t]) => `<option value="${v}" ${v === a.orientacion_pallet ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label class="f">Capacidad del pallet
        <select data-ajcap>${cap.map(([v, t]) => `<option value="${v}" ${v === a.capacidad_pallet ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label class="f">Precisión al acomodar en el camión
        <select data-ajcelda><option value="1" ${a.celda_cm === 1 ? 'selected' : ''}>1 cm</option>
          <option value="2" ${a.celda_cm === 2 ? 'selected' : ''}>2 cm (como el Excel, más rápido)</option></select></label>
    </div>
    <p class="small muted">Con los valores de arriba, la capacidad del pallet coincide con EasyCargo en 543 de 545 productos de la Base de Medidas. Valen para todo el cubicaje, también el de los pedidos.</p>
  </details>`;
}

function vistaCubicador(){
  const c = UI.cub;
  if (!c) { setTimeout(cargarCubLibre, 0); return '<div class="panel empty"><h3>Cargando cubicador…</h3></div>'; }
  const modos = ['MDA', 'MDA PREDISTRIBUIDO', 'SDA STOCK', 'SDA PREDISTRIBUIDO'];
  const cls = (UI.clientes || []).map(x => x.nombre);
  const lineas = c.lineas || [];
  const det = c.detalle_lineas || {};
  const unidades = lineas.reduce((a, l) => a + (+l.qty || 0), 0);
  const camiones = c.camiones || [];
  const pct = x => (100 * (x || 0)).toFixed(1) + '%';
  const unidPorCam = {}, ocupPorCam = {};
  for (const f of (c.filas || [])){
    unidPorCam[f.camion] = (unidPorCam[f.camion] || 0) + f.unidades;
    ocupPorCam[f.camion] = f.ocup_acum;
  }
  const ocupMax = camiones.length ? Math.max(0, ...Object.values(ocupPorCam)) : 0;
  const pallets = (c.pallets_detalle || []).length;
  const aPiso = (c.filas04 || []).filter(f => f.tipo === 'Piso').reduce((a, f) => a + f.unidades, 0);
  const faltaMedidas = /Base de Medidas/.test(c.error || '');
  const enPallet = c.vista === 'pallet';

  /* --- cabecera: las cifras que importan, siempre a la vista --- */
  const cifras = `<div class="resumen">
      <div class="dato"><span>${enPallet ? 'Pallets' : 'Camiones'}</span><b>${(enPallet ? pallets : camiones.length) || '—'}</b></div>
      <div class="dato"><span>Unidades</span><b>${fmt(c.unidades || 0)}</b></div>
      <div class="dato"><span>Ocupación máx.</span><b>${camiones.length ? pct(ocupMax) : '—'}</b></div>
      ${!enPallet && pallets ? `<div class="dato"><span>Pallets</span><b>${pallets}</b></div>` : ''}
      ${aPiso ? `<div class="dato"><span>A piso</span><b>${fmt(aPiso)}</b></div>` : ''}
      <div class="dato"><span>Pallet</span><b class="chico">${(c.pallet || []).join(' × ')} cm</b></div>
      ${c.pedido ? `<div class="dato"><span>Pedido</span><b class="chico">${esc(c.pedido)}</b></div>` : ''}
    </div>`;

  /* --- ítems --- */
  const items = `<div class="items">
      ${lineas.map((l, i) => {
        const d = det[l.sku] || {};
        return `<div class="item">
          <span class="letra" style="background:${esc(d.color || PALETA_CUB[i % PALETA_CUB.length])}">${esc(d.letra || letraItem(i))}</span>
          <div class="cuerpo">
            <div class="l1">${esc(l.sku)}${(c.desconocidos || []).includes(l.sku) ? ' <span class="tag red">sin medidas</span>' : ''}</div>
            <div class="l2">${esc(d.descripcion || '')}${d.medidas ? ' · ' + esc(d.medidas) : ''}</div>
          </div>
          <label class="mini">unid.<input class="qty" type="number" min="0" step="1" value="${l.qty}" data-cubqty="${i}"></label>
          <button class="btn ghost small" data-quitar="${i}" title="Quitar este ítem">✕</button>
        </div>`;
      }).join('')}
      <div class="item nuevo">
        <span class="letra vacia">+</span>
        <div class="cuerpo" style="position:relative">
          <input type="text" data-cubsku placeholder="Agregar ítem: escribe el SKU o parte de la descripción" value="${esc(UI.cubBuscando)}" autocomplete="off" style="width:100%">
          ${UI.cubSug.length ? `<div class="sugerencias">
            ${UI.cubSug.map(x => `<button data-agregar="${esc(x.sku)}">
              <div class="l1"><span class="ped">${esc(x.sku)}</span>${x.caja_master ? '<span class="tag amber">caja master ×' + x.piezas + '</span>' : ''}</div>
              <div class="l2">${esc(x.descripcion)} · ${esc(x.medidas)}</div></button>`).join('')}
          </div>` : ''}
        </div>
      </div>
    </div>`;

  /* --- opciones: una pregunta por fila, con botones --- */
  const tipo = /SDA/.test(c.modo || '') ? 'SDA' : 'MDA';
  const destino = /PREDISTRIBUIDO/.test(c.modo || '') ? 'sucursal' : 'stock';
  const reparto = c.predistribuido || [];
  const opciones = `<div class="cub-opts">
      <label class="op"><span>Cliente</span><select data-cubcliente><option value="">Sin cliente</option>
        ${cls.map(n => `<option ${n === c.cliente ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>
      <div class="op"><span>Carga</span>${segmentado('tipo', tipo, [
        ['MDA', 'A piso', 'Las cajas van directo al piso del camión (MDA)'],
        ['SDA', 'En pallets', 'Las cajas se arman en pallets (SDA)']])}</div>
      <div class="op"><span>Destino</span>${segmentado('destino', destino, [
        ['stock', 'Stock', 'Toda la carga va junta'],
        ['sucursal', 'Por sucursal', 'Se separa por sucursal según el reparto (predistribuido)']])}</div>
      ${destino === 'sucursal' && !reparto.length
        ? '<p class="ayuda">Falta el reparto: importa la plantilla llenando la columna Sucursal.</p>' : ''}
      ${(c.modo || 'MDA') !== 'MDA' ? `<div class="op"><span>Caja master</span>${segmentado('caja_master', c.caja_master || '', [
        ['CON CAJA MASTER', 'Con'], ['SIN CAJA MASTER', 'Sin']])}</div>` : ''}
      <div class="op"><span>Ver</span>${segmentado('vista', c.vista || 'rampla', VISTAS)}</div>
      ${enPallet && (c.pallets_disponibles || []).length > 1 ? `<label class="op"><span>Pallet</span>
        <select data-cubpallet>${c.pallets_disponibles.map(n => `<option value="${n}" ${n === c.pallet_visto ? 'selected' : ''}>Pallet ${n} de ${c.pallets_disponibles.length}</option>`).join('')}</select></label>` : ''}
    </div>`;

  /* --- reparto por sucursal cargado (predistribuido) --- */
  const sucs = [...new Set(reparto.map(x => x.sucursal))];
  const bloqueReparto = reparto.length ? `<div class="reparto">
      <div class="row" style="justify-content:space-between;gap:6px">
        <span><b>Reparto por sucursal</b> · ${sucs.length} sucursales · ${fmt(reparto.reduce((a, x) => a + (+x.qty || 0), 0))} un.</span>
        <button class="btn ghost small" data-act="cubQuitarReparto" title="Quitar el reparto y volver a Stock">Quitar</button>
      </div>
      <details><summary class="small muted">Ver detalle</summary><table>
        ${reparto.slice(0, 300).map(x => `<tr><td>${esc(x.sucursal)}</td><td>${esc(x.sku)}</td><td class="num">${fmt(x.qty)}</td></tr>`).join('')}
      </table>${reparto.length > 300 ? `<p class="small muted">…y ${reparto.length - 300} líneas más</p>` : ''}</details>
    </div>` : '';

  /* --- camiones, como tira de tarjetas --- */
  const tarjetas = camiones.map(v => {
    const o = ocupPorCam[v.numero] || 0;
    const color = o > 0.92 ? 'var(--err)' : o > 0.7 ? 'var(--warn)' : 'var(--ok)';
    return `<div class="camion">
      <div class="row" style="justify-content:space-between;gap:6px">
        <b>${esc(v.tipo)} ${v.numero}</b><span class="num">${fmt(unidPorCam[v.numero] || 0)}<span class="small muted"> un.</span></span>
      </div>
      <div class="barra"><span style="width:${Math.min(100, 100 * o).toFixed(1)}%;background:${color}"></span></div>
      <div class="meta small muted"><span>${pct(o)}</span><span>${v.vol_m3.toFixed(1)} m³</span></div>
    </div>`;
  }).join('');

  const mensajes = `
    ${faltaMedidas ? `<div class="empty"><h3>Falta la Base de Medidas</h3>
        <p>El cubicaje necesita las medidas de los productos. Se cargan una vez y quedan guardadas.</p>
        <button class="btn primary" data-go="config">Ir a Configuración</button></div>`
      : (c.error ? `<p class="small"><span class="tag red">Error</span> ${esc(c.error)}</p>` : '')}
    ${(c.sin_medidas || []).length ? `<p class="small"><span class="tag red">Sin medidas</span> ${esc(c.sin_medidas.join(', '))}</p>` : ''}
    ${enPallet && c.modo_usado && c.modo_usado !== c.modo
      ? `<p class="small muted">Para ver pallets se cubicó en ${esc(c.modo_usado)}: en ${esc(c.modo)} la carga va a piso.</p>` : ''}
    ${(c.avisos || []).map(a => `<p class="small"><span class="tag amber">Aviso</span> ${esc(a)}</p>`).join('')}`;

  return `<section class="panel cubicador">
    <div class="panel-h">
      <h2>Cubicador</h2>
      ${cifras}
      <div class="row" style="margin-left:auto;gap:6px">
        <a class="btn ghost small" href="/api/cubicaje-libre/plantilla" title="Excel para armar la carga fuera de la plataforma">Plantilla</a>
        <label class="btn ghost small" title="Cargar productos desde un Excel">Importar
          <input type="file" accept=".xlsx,.xlsm" data-cubimport style="display:none"></label>
        ${lineas.length ? `<a class="btn ghost small" href="/api/cubicaje-libre/excel">Exportar</a>
          <button class="btn ghost small" data-act="cubLimpiar">Vaciar</button>` : ''}
      </div>
    </div>

    <div class="cub-cuerpo">
      <div class="cub-izq">
        <div class="bloque-t">Opciones</div>
        ${opciones}
        <div class="bloque-t">Carga <span class="small muted" style="font-weight:400;text-transform:none">${fmt(unidades)} un. · ${lineas.length} SKU</span></div>
        ${items}
        ${bloqueReparto}
        <div class="row" style="margin-top:8px;gap:6px">
          <input type="text" data-cubped placeholder="…o trae un pedido analizado" style="flex:1;min-width:120px">
          <button class="btn ghost small" data-act="traerPedido">Traer</button>
        </div>
        ${seccionAjustes()}
      </div>

      <div class="cub-der">
        ${mensajes}
        ${!lineas.length && !c.error ? `<div class="empty"><h3>Arma una carga</h3>
            <p>Busca un producto a la izquierda, trae un pedido analizado o importa un Excel.
               El camión se rearma con cada cambio.</p></div>` : ''}
        ${c.visor ? `<div class="visor-caja">
            <iframe src="${esc(c.visor)}#compacto" title="Visor 3D del cubicador"></iframe>
            <a class="btn ghost small abrir" href="${esc(c.visor)}" target="_blank" rel="noopener">Abrir aparte</a>
          </div>` : ''}
        ${camiones.length ? `<div class="camiones">${tarjetas}</div>` : ''}
      </div>
    </div>
  </section>`;
}
