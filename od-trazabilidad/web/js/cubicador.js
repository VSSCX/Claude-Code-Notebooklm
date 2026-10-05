/* Por hacer y la mesa de carga del Cubicador.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Vista: Por hacer ============ */
function vistaBandeja(){
  const gs = grupos().filter(g => g.next).filter(g => {
    if (!UI.cliente) return true;
    return g.entregas.some(e => (Store.get('pedidos', safeId(e.pedido)) || {}).cliente === UI.cliente);
  });
  // pedidos analizados en la plataforma que todavía no terminan el flujo: análisis → cubicaje → entregas → grupos
  const COLS_FLUJO = [['ajuste', 'Revisar la carga'], ['cubicaje', 'Por cubicar'], ['entregas', 'Crear entregas'], ['grupos', 'Crear grupos'], ['analisis', 'Volver a analizar']];
  const delFlujo = Store.list('pedidos').filter(p => !UI.cliente || p.cliente === UI.cliente)
    .map(p => ({p, f: flujoDe(p)})).filter(x => x.f.enPlataforma && x.f.sig)
    .sort((a, b) => (b.p.actualizado || '').localeCompare(a.p.actualizado || ''));
  const colsFlujo = COLS_FLUJO.map(([k, t]) => ({k, t, items: delFlujo.filter(x => x.f.sig.k === k)})).filter(c => c.items.length);
  const tarjetaFlujo = ({p, f}, k) => {
    const {tot} = resumen(p);
    const det = k === 'ajuste' ? `${f.an.limitadas} producto(s) limitados por el plan SOP`
      : k === 'cubicaje' ? `${fmt(f.an.carga)} un. a cargar`
      : k === 'entregas' ? `${f.ents.length} de ${f.cb.camiones} entregas`
      : k === 'grupos' ? `${f.ents.filter(e => e.grupo).length} de ${f.ents.length} con grupo` : `era de ${f.an.cliente}`;
    return `<div class="tarea" data-k="f-${esc(safeId(p.pedido))}-${k}"><div class="c1"><b>Pedido ${esc(p.pedido)}</b><span class="num">${fmt(f.an.pedida)} un.</span></div>
      <div class="c2">${esc(p.cliente || '—')} · ${esc(det)}</div>
      <div class="row tight"><button class="btn primary sm" data-abrir="${esc(safeId(p.pedido))}" data-sub="${f.tab[k]}">${esc(FLUJO_ACCION[k])}</button></div></div>`;
  };
  const cols = STEPS.map(s => ({s, items: gs.filter(g => g.next.k === s.k)
    .sort((a, b) => (a.cita.fecha || '9').localeCompare(b.cita.fecha || '9'))})).filter(c => c.items.length);
  return `<div class="page-head"><h2>Por hacer</h2><span class="spacer"></span>${filtroCliente()}</div>
  ${colsFlujo.length ? `<div class="inbox">${colsFlujo.map(c => `<section class="col"><h3>${esc(c.t)} <span class="num">${c.items.length}</span></h3>${c.items.map(x => tarjetaFlujo(x, c.k)).join('')}</section>`).join('')}</div>` : ''}
  ${cols.length ? `<div class="inbox">${cols.map(({s, items}) => `<section class="col"><h3>${esc(s.t)} <span class="num">${items.length}</span></h3>
    ${items.map(g => { const p = Store.get('pedidos', safeId(g.entregas[0].pedido)) || {};
      return `<div class="tarea" data-k="t-${esc(g.key)}-${s.k}"><div class="c1"><b>${g.sinGrupo ? 'Entrega ' + esc(g.entregas[0].entrega) : 'Grupo ' + esc(g.grupo)}</b><span class="num">${fmt(g.unidades)} un.</span></div>
      <div class="c2">${esc(p.cliente || '—')} · ${g.pedidos.length > 1 ? g.pedidos.length + ' pedidos' : 'Pedido ' + esc(g.pedidos[0])} · ${g.entregas.length} entrega(s)${g.cita.fecha ? ` · ${fmtFecha(g.cita.fecha)} ${esc(g.cita.hora || '')}` : ''}</div>
      <div class="row tight">${POR_ENTREGA.includes(s.k) ? '' : `<button class="btn primary sm" data-gpaso="${s.k}" data-grupo="${esc(g.key)}" data-forzar="1">Marcar hecho</button>`}
      <button class="btn quiet sm" data-abrir="${esc(safeId(g.pedidos[0]))}" data-sub="${POR_ENTREGA.includes(s.k) ? 'entregas' : 'grupos'}">Ver pedido</button></div></div>`; }).join('')}</section>`).join('')}</div>`
  : (colsFlujo.length ? '' : `<div class="panel empty"><h3>No hay tareas pendientes</h3><p>Aquí aparece el próximo paso de cada pedido analizado y de cada camión.</p></div>`)}`;
}

/* ============ Cubicador: mesa de carga ============
   Dos estados separados, para que un cálculo nunca pise lo que la persona está escribiendo:
     UI.cubIn  lo que la persona edita (productos, cliente, modo…). Se ve al instante.
     UI.cub    lo último que calculó el servidor (camiones, ocupación, datos del visor).
   Cada edición pide un cálculo; mientras hay uno en curso, las ediciones nuevas se juntan y se
   calcula una sola vez más con lo último: gana siempre la edición más reciente. */
UI.cubIn = null; UI.cub = null; UI.cubError = ''; UI.cubCalculando = false; UI.cubSucio = false;
UI.cubSug = []; UI.cubQ = ''; UI.cubSugQ = ''; UI.cubSel = 0; UI.cubInfo = {}; UI.cubFoco = null; UI.cubCam = 0;
UI.cubIniciado = false; UI.cubFiltro = null; UI.cubFalta = false; UI.cubGen = 0; UI.cubOcupado = false; UI.ajustes = null; UI.verAjustes = false; UI.vistaCamion = 'rampla';

const VISTAS = [['rampla', 'Rampla 53'], ['camion50', 'Camión 50'], ['pallet', 'Un pallet']];
const PALETA_CUB = ['#E8534E','#F2C94C','#56A3D9','#27AE60','#9B59B6','#E67E22',
                    '#1ABC9C','#E84393','#3498DB','#F39C12','#7F8C8D','#16A085'];
const letraItem = i => String.fromCharCode(65 + (i % 26)) + (i >= 26 ? Math.floor(i / 26) : '');
/* Texto oscuro sobre colores claros y blanco sobre oscuros: la letra siempre se lee */
function tintaSobre(hex){
  const h = String(hex).replace('#', ''); const v = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) || 0);
  return (0.299 * v[0] + 0.587 * v[1] + 0.114 * v[2]) > 150 ? '#12171C' : '#FFFFFF';
}
const pctCub = x => (100 * (x || 0)).toFixed(1).replace('.', ',') + '%';

function entradaDe(doc){
  return {cliente: doc.cliente || '', modo: doc.modo || 'MDA', vista: doc.vista || 'rampla',
          caja_master: doc.caja_master || '', piso_pallet: doc.piso_pallet || '', destino: doc.destino || '',
          predistribuido: doc.predistribuido || [], grupos: doc.grupos || [], pedido: doc.pedido || '',
          lineas: (doc.lineas || []).map(l => ({sku: String(l.sku), qty: +l.qty || 0})),
          pallet_n: doc.pallet_visto || 0, pallet_camion: !!doc.pallet_camion};
}
async function cargarCubLibre(){
  UI.cubIniciado = true;
  // todo lo que la vista necesita se pide a la vez, no uno tras otro
  const [doc] = await Promise.all([
    api('GET', '/cubicaje-libre').catch(() => ({})),
    UI.clientes ? null : cargarClientes(),
    UI.ajustes ? null : cargarAjustes(),
  ]);
  UI.cubIn = entradaDe(doc);
  UI.cub = doc.camiones ? doc : null;
  render();
}
async function cargarAjustes(){
  try { UI.ajustes = await api('GET', '/ajustes-cubicaje'); } catch(e){ UI.ajustes = null; }
}
async function guardarAjustes(datos){
  try { UI.ajustes = await api('PUT', '/ajustes-cubicaje', {...(UI.ajustes || {}), ...datos}); }
  catch(e){ return toast(e.message); }
  pedirCalculo();
  if (UI.sel){ const p = Store.get('pedidos', UI.sel); if (p) delete UI.cubicaje[p.pedido]; }
  render();
}

function pedirCalculo(){
  UI.cubSucio = true;
  if (!UI.cubCalculando) correrCalculos();
  else renderSoon();
}
async function correrCalculos(){
  UI.cubCalculando = true; renderSoon();
  try {
    while (UI.cubSucio){
      UI.cubSucio = false;
      // sin reparto, un modo predistribuido calcula una carga vacía: el panel pide el archivo
      UI.cubFalta = efectivoCub(UI.cubIn).pred && !(UI.cubIn.predistribuido || []).length && !(UI.cubIn.grupos || []).length;
      const gen = UI.cubGen;
      try {
        const r = await api('POST', '/cubicaje-libre', clone(UI.cubIn));
        // si hay una edición más nueva, o se importó otra carga mientras tanto, este resultado ya no vale
        if (!UI.cubSucio && gen === UI.cubGen){ UI.cub = r; UI.cubError = ''; camionDelPallet(); }
      } catch(e){ if (!UI.cubSucio && gen === UI.cubGen) UI.cubError = e.message; }
      renderSoon();
    }
  } finally { UI.cubCalculando = false; renderSoon(); }
}
/* Con "pallets en el camión", el 3D arranca en el camión donde va el pallet elegido */
function camionDelPallet(){
  const c = UI.cub, inp = UI.cubIn;
  if (!c || !inp || inp.vista !== 'pallet' || !inp.pallet_camion || !c.pallet_vehiculo) return;
  const i = (c.camiones || []).findIndex(v => v.numero === c.pallet_vehiculo);
  if (i >= 0 && i !== UI.cubCam){ UI.cubCam = i; Visor.camion(i); }
}
/* Importar y "traer pedido" reemplazan toda la carga: el servidor devuelve el documento completo */
function adoptarDoc(doc){ UI.cubGen++; UI.cubSucio = false; UI.cubIn = entradaDe(doc); UI.cub = doc; UI.cubError = ''; UI.cubCam = 0; UI.cubFiltro = null; }

/* ---- Agregar productos ---- */
let _sugSeq = 0, _sugTimer = 0, _qtyTimer = 0;
function pedirSugerencias(q){
  clearTimeout(_sugTimer);
  UI.cubQ = q;
  if (q.trim().length < 2){ UI.cubSug = []; UI.cubSugQ = ''; UI.cubSel = 0; ++_sugSeq; return renderSoon(); }
  _sugTimer = setTimeout(async () => {
    const mi = ++_sugSeq;
    try {
      const r = (await api('GET', '/medidas/sugerir?q=' + encodeURIComponent(q))).sugerencias;
      if (mi !== _sugSeq) return;                                // llegó tarde: ya se escribió otra cosa
      UI.cubSug = r; UI.cubSugQ = q.trim(); UI.cubSel = 0;
      r.forEach(x => UI.cubInfo[x.sku] = x);
    } catch(e){ if (mi === _sugSeq) UI.cubSug = []; }
    renderSoon();
  }, 140);
}
/* Enter con lo escrito: si las sugerencias ya son de este texto se usan; si no (se tecleó o escaneó
   más rápido que la red) se piden ahora, sin esperar el retardo, y se agrega el SKU exacto o el primero. */
async function agregarConEnter(v){
  clearTimeout(_sugTimer);
  if (v.length < 2) return;
  let lista = UI.cubSugQ === v ? UI.cubSug : null, sel = UI.cubSel;
  if (!lista){
    const mi = ++_sugSeq;
    try { lista = (await api('GET', '/medidas/sugerir?q=' + encodeURIComponent(v))).sugerencias; }
    catch(e){ return toast(e.message); }
    if (mi !== _sugSeq) return;                                  // se siguió escribiendo: manda lo último
    lista.forEach(x => UI.cubInfo[x.sku] = x); sel = 0;
  }
  const exacto = lista.find(x => x.sku.toLowerCase() === v.toLowerCase());
  const elegido = sel > 0 ? lista[sel] : (exacto || lista[0]);
  if (elegido) agregarSku(elegido.sku, 1); else toast(`No encontré «${v}» en la Base de Medidas`);
}
function agregarSku(sku, qty){
  const l = UI.cubIn.lineas;
  const ya = l.find(x => x.sku === sku);
  if (ya) ya.qty = (+ya.qty || 0) + (+qty || 1); else l.push({sku, qty: +qty || 1});
  UI.cubQ = ''; UI.cubSug = []; UI.cubSel = 0; UI.cubFoco = sku; ++_sugSeq;
  vaciarBuscador();
  pedirCalculo();
  render();                       // la fila y el foco en sus unidades aparecen ya, sin esperar al cálculo
}
/* El campo enfocado manda sobre el redibujado: hay que vaciarlo a mano */
function vaciarBuscador(){ const q = document.querySelector('[data-cub-q]'); if (q) q.value = ''; }
/* Pegar una lista desde Excel: "SKU  unidades" por línea */
function pegarLista(texto){
  let n = 0;
  for (const raw of texto.split(/\r?\n/)){
    const c = raw.split(/\t|;|,|\s{2,}/).map(x => x.trim()).filter(Boolean);
    if (c.length < 2) continue;
    const sku = normSku(c[0]), qty = +String(c[1]).replace(/\./g, '').replace(',', '.');
    if (!sku || !isFinite(qty) || qty <= 0) continue;
    const ya = UI.cubIn.lineas.find(x => x.sku === sku);
    if (ya) ya.qty += qty; else UI.cubIn.lineas.push({sku, qty});
    n++;
  }
  if (!n) return toast('No encontré líneas con SKU y unidades');
  UI.cubQ = ''; UI.cubSug = []; vaciarBuscador();
  toast(`${n} producto(s) agregados`);
  pedirCalculo();
}
function cambiarQty(i, v){
  const l = UI.cubIn.lineas[i]; if (!l) return;
  l.qty = Math.max(0, Math.round(+v || 0));
  pedirCalculo();
}
function quitarLinea(i){
  const [q] = UI.cubIn.lineas.splice(i, 1);
  if (q && q.sku === UI.cubFiltro) UI.cubFiltro = null;
  pedirCalculo();
}

/* ---- Opciones: el modo del motor decide cómo se arma la carga ---- */
/* Lo que de verdad se cubica: el modo elegido, con Destino y Carga mandando sobre él (como H2 en el Excel):
   MDA + "en pallets" se cubica en pallets, y SDA + "a piso" va directo al camión sin armar pallets. */
/* Bultos: una caja master (C + SKU) es un bulto con varias unidades (50 cajas de 2 = 50 bultos y 100 unidades);
   con "con caja master" en SDA, las unidades de un SKU se agrupan en cajas de a `caja` y las sueltas cuentan una a una. */
function bultosDe(l, d, conCaja){
  const q = +l.qty || 0;
  if (d && (d.master || /^C\d/i.test(l.sku)) && d.piezas > 1) return {bultos: q, un: q * d.piezas, caja: d.piezas};
  if (conCaja && d && d.caja > 1) return {bultos: Math.floor(q / d.caja) + q % d.caja, un: q, caja: d.caja};
  return {bultos: q, un: q, caja: 0};
}
function efectivoCub(inp){
  const base = inp.modo || 'MDA', sda = /SDA/.test(base);
  const grupos = (inp.grupos || []).length > 0 && !(inp.predistribuido || []).length && inp.destino !== 'STOCK';
  const pred = inp.destino === 'SUCURSAL' || (inp.destino !== 'STOCK' && /PREDISTRIBUIDO/.test(base)) || grupos;
  const pallets = inp.piso_pallet === 'PALLET' || (inp.piso_pallet !== 'PISO' && sda);
  const modo = (pallets ? 'SDA ' : 'MDA') + (pallets ? (pred ? 'PREDISTRIBUIDO' : 'STOCK') : (pred ? ' PREDISTRIBUIDO' : ''));
  return {modo, pallets, pred, pideCaja: base !== 'MDA' || inp.piso_pallet === 'PALLET' || inp.destino === 'SUCURSAL',
          grupos, texto: `${pallets ? 'En pallets' : 'A piso'} · ${grupos ? 'por grupos' : pred ? 'por sucursal' : 'stock'}`};
}
function cambiarOpcionCub(campo, valor){
  const c = UI.cubIn;
  if (campo === 'caja_master') c.caja_master = valor;
  else if (campo === 'vista'){
    c.vista = valor;
    if (valor !== 'pallet') UI.vistaCamion = valor;             // a qué camión volver desde un pallet
  } else if (campo === 'modo') c.modo = valor;
  else if (campo === 'carga') c.piso_pallet = valor;
  else if (campo === 'destino') c.destino = valor;
  else if (campo === 'pallet_modo') c.pallet_camion = valor === 'camion';
  if (campo === 'pallet_modo'){ UI.cubCam = 0; pedirCalculo(); return; }
  if (campo === 'modo' || campo === 'carga' || campo === 'destino'){
    // fuera de MDA el motor exige indicar caja master: se parte en "sin" en vez de fallar
    if (efectivoCub(c).pideCaja && !c.caja_master) c.caja_master = 'SIN CAJA MASTER';
    // la vista de un solo pallet solo existe con pallets
    if (!efectivoCub(c).pallets && c.vista === 'pallet') c.vista = UI.vistaCamion || 'rampla';
  }
  UI.cubCam = 0;
  pedirCalculo();
}
function quitarRepartoCub(){
  UI.cubIn.predistribuido = []; UI.cubIn.grupos = []; UI.cubIn.destino = ''; UI.cubIn.modo = /SDA/.test(UI.cubIn.modo) ? 'SDA STOCK' : 'MDA';
  pedirCalculo();
}
function vaciarCub(){
  const previo = {lineas: clone(UI.cubIn.lineas), pedido: UI.cubIn.pedido, predistribuido: UI.cubIn.predistribuido, grupos: UI.cubIn.grupos};
  Object.assign(UI.cubIn, {lineas: [], pedido: '', predistribuido: [], grupos: []});
  UI.cubCam = 0; pedirCalculo();
  if (previo.lineas.length) toast('Carga vaciada', {texto: 'Deshacer', fn: () => { Object.assign(UI.cubIn, previo); pedirCalculo(); render(); }});
}

/* ---- Importar / traer un pedido ---- */
async function importarCarga(input){
  const f = input.files[0]; if (!f) return;
  const fd = new FormData(); fd.append('file', f);
  fd.append('modo', UI.cubIn.modo || ''); fd.append('caja_master', UI.cubIn.caja_master || '');
  fd.append('piso_pallet', UI.cubIn.piso_pallet || ''); fd.append('destino', UI.cubIn.destino || '');
  UI.cubOcupado = true; renderSoon();
  try {
    const r = await fetch('/api/cubicaje-libre/importar', {method: 'POST', body: fd,
      headers: Usuario.get() ? {'X-Usuario': Usuario.get()} : {}});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'No se pudo importar');
    adoptarDoc(d);
    const avisos = [];
    const lec = d.lectura || {}, col = lec.columnas || {};
    const mapa = [['sucursal', 'Sucursal'], ['sku', 'SKU'], ['unidades', 'Unidades'], ['grupo', 'Grupo']].filter(([k]) => col[k]).map(([k, n]) => `${col[k]} → ${n}`);
    if (mapa.length) avisos.push('Leído: ' + mapa.join(' · '));
    avisos.push(...(lec.notas || []));
    if ((d.errores_archivo || []).length) avisos.push(d.errores_archivo.slice(0, 3).join(' · '));
    const reparto = d.predistribuido || [];
    const sucs = new Set(reparto.map(x => x.sucursal)).size;
    Avisos.agregar(avisos.length > 1 || (d.errores_archivo || []).length ? 'info' : 'ok',
      `${d.importadas} producto(s) importados` + (reparto.length ? ` · reparto en ${sucs} sucursales` : ''), avisos.join(' | '), []);
  } catch(e){ toast(e.message); }
  UI.cubOcupado = false; render();
}
async function traerPedido(numero){
  if (!numero) return;
  UI.cubOcupado = true; renderSoon();
  try { adoptarDoc(await api('POST', '/cubicaje-libre/desde-pedido', {pedido: String(numero).trim()})); toast(`Pedido ${numero} cargado`); }
  catch(e){ toast(e.message); }
  UI.cubOcupado = false; render();
}

/* ---- Tras cada render: foco de la carga producto por producto ---- */
function postRenderCub(){
  if (UI.view !== 'cubicador') return;
  // el render no toca el campo enfocado: su estado de combobox se pone a mano
  const campo = document.querySelector('[data-cub-q]');
  if (campo){
    campo.setAttribute('aria-expanded', UI.cubSug.length > 0);
    if (UI.cubSug.length) campo.setAttribute('aria-activedescendant', 'sug-' + UI.cubSel); else campo.removeAttribute('aria-activedescendant');
  }
  if (!UI.cubFoco) return;
  const fila = document.querySelector(`[data-cubsku="${CSS.escape(UI.cubFoco)}"]`);
  UI.cubFoco = null;
  if (!fila) return;
  const q = fila.querySelector('input.qty');
  if (q){ q.focus(); q.select(); }
  fila.scrollIntoView({block: 'nearest'});
  fila.classList.add('flash');
}

/* ---- Vista ---- */
const MODOS_CUB = [
  ['MDA', 'MDA', 'A piso, toda la carga junta: las cajas van directo al camión'],
  ['MDA PREDISTRIBUIDO', 'MDA predistribuido', 'A piso, separado por sucursal según el reparto del cliente'],
  ['SDA STOCK', 'SDA', 'En pallets, toda la carga junta'],
  ['SDA PREDISTRIBUIDO', 'SDA predistribuido', 'En pallets, separado por sucursal según el reparto del cliente']];
function seg(campo, actual, opciones){
  return `<div class="seg" role="group">${opciones.map(([v, t, ayuda]) =>
    `<button type="button" data-cub-opt="${campo}" data-valor="${esc(v)}" aria-pressed="${v === actual}"${ayuda ? ` title="${esc(ayuda)}"` : ''}>${esc(t)}</button>`).join('')}</div>`;
}
function seccionAjustes(){
  const a = UI.ajustes || {orientacion_pallet: 'largo', celda_cm: 1, capacidad_pallet: 'geometria'};
  const sel = (clave, opciones, valor) => `<select data-cub-aj="${clave}">${opciones.map(([v, t]) =>
    `<option value="${v}" ${String(v) === String(valor) ? 'selected' : ''}>${t}</option>`).join('')}</select>`;
  return `<details class="ajustes" ${UI.verAjustes ? 'open' : ''} data-ajustes><summary>Ajustes del motor</summary>
    <div class="stack">
      <label class="f">Cómo se acomodan las cajas en el pallet
        ${sel('orientacion_pallet', [['largo', 'Largo del pallet (como EasyCargo)'], ['excel', 'Ancho del pallet (como el Excel)']], a.orientacion_pallet)}</label>
      <label class="f">Capacidad del pallet
        ${sel('capacidad_pallet', [['geometria', 'Calcularla con las medidas reales'], ['tabla', 'Usar la columna Máx Pallet de la base']], a.capacidad_pallet)}</label>
      <label class="f">Precisión al acomodar en el camión
        ${sel('celda_cm', [[1, '1 cm (más fiel a la carga real)'], [2, '2 cm (como el Excel, más rápido)']], a.celda_cm)}</label>
      <p class="small muted">Con estos valores la capacidad del pallet coincide con EasyCargo en 543 de 545 productos de la Base de Medidas. Valen para todo el cubicaje, también el de los pedidos.</p>
    </div></details>`;
}

function vistaCubicador(){
  if (!UI.cubIn){
    if (!UI.cubIniciado) setTimeout(cargarCubLibre, 0);
    return `<div class="mesa"><div class="panel mesa-carga"><div class="panel-b stack"><span class="skel" style="width:40%"></span><span class="skel"></span><span class="skel" style="width:80%"></span></div></div><div class="mesa-vista"><div class="visor-caja"><i class="calc-bar"></i></div></div></div>`;
  }
  const inp = UI.cubIn, c = UI.cub || {};
  const lineas = inp.lineas;
  const det = c.detalle_lineas || {};
  const camiones = c.camiones || [];
  const unidades = lineas.reduce((a, l) => a + (+l.qty || 0), 0);
  const conCaja = inp.caja_master === 'CON CAJA MASTER' && /SDA/.test(efectivoCub(inp).modo);
  const resB = lineas.map(l => bultosDe(l, det[l.sku], conCaja));
  const totBultos = resB.reduce((a, x) => a + x.bultos, 0), totUnidades = resB.reduce((a, x) => a + x.un, 0);
  const unidPorCam = {}, ocupPorCam = {};
  for (const f of (c.filas || [])){
    unidPorCam[f.camion] = (unidPorCam[f.camion] || 0) + f.unidades;
    ocupPorCam[f.camion] = f.ocup_acum;
  }
  const ocupMax = camiones.length ? Math.max(0, ...Object.values(ocupPorCam)) : 0;
  const pallets = (c.pallets_detalle || []).length;
  const aPiso = (c.filas04 || []).filter(f => f.tipo === 'Piso').reduce((a, f) => a + f.unidades, 0);
  const faltaMedidas = /Base de Medidas/.test(UI.cubError || c.error || '');
  const enPallet = inp.vista === 'pallet';
  const soloPallet = enPallet && !inp.pallet_camion;       // un pallet aislado; si no, los pallets dentro del camión
  const ef = efectivoCub(inp), porSucursal = ef.pred;
  if (UI.cubCam >= camiones.length) UI.cubCam = 0;

  /* --- productos: uno por fila, con letra y color iguales a los del visor --- */
  const filas = lineas.map((l, i) => {
    const d = det[l.sku] || {}, info = UI.cubInfo[l.sku] || {};
    const color = d.color || PALETA_CUB[i % PALETA_CUB.length];
    const sinMedidas = (c.desconocidos || []).includes(l.sku);
    return `<li class="item ${sinMedidas ? 'faltante' : ''}" data-k="it-${esc(l.sku)}" data-cubsku="${esc(l.sku)}">
      <button class="letra" style="background:${esc(color)};color:${tintaSobre(color)}" data-cub-filtro="${esc(l.sku)}" aria-pressed="${UI.cubFiltro === l.sku}" title="Aislar este producto en el 3D" aria-label="Aislar ${esc(l.sku)} en el 3D">${esc(d.letra || letraItem(i))}</button>
      <div class="cuerpo">
        <div class="l1"><span class="code">${esc(l.sku)}</span>${sinMedidas ? '<span class="tag err" title="No se cubica hasta que tenga medidas">no se carga · sin medidas</span>' : ''}</div>
        <div class="l2" title="${esc(d.descripcion || info.descripcion || '')}">${esc(d.descripcion || info.descripcion || '')}</div>
        ${(d.medidas || info.medidas) ? `<div class="l3 num">${esc(d.medidas || info.medidas)}${resB[i].caja ? ` · ${fmt(resB[i].bultos)} bultos de ${resB[i].caja} un.` : ''}</div>` : ''}
      </div>
      <div class="step">
        <button class="btn quiet icon sm" data-cub-menos="${i}" aria-label="Una unidad menos">${ICON.minus}</button>
        <input class="qty" type="number" inputmode="numeric" min="0" step="1" value="${l.qty}" data-cubqty="${i}" aria-label="Unidades de ${esc(l.sku)}">
        <button class="btn quiet icon sm" data-cub-mas="${i}" aria-label="Una unidad más">${ICON.plus}</button>
      </div>
      <button class="btn quiet icon sm" data-cub-quitar="${i}" aria-label="Quitar ${esc(l.sku)}" title="Quitar">${ICON.x}</button>
    </li>`;
  }).join('');

  const sugerencias = UI.cubSug.length ? `<ul class="sug" id="sug-lista" role="listbox" aria-label="Productos encontrados">${UI.cubSug.map((x, k) => {
      const n = (lineas.find(l => l.sku === x.sku) || {}).qty;
      return `<li role="presentation"><button role="option" id="sug-${k}" tabindex="-1" aria-selected="${k === UI.cubSel}" data-cub-sug="${esc(x.sku)}" ${k === UI.cubSel ? 'class="sel"' : ''}>
        <span class="l1"><span class="code">${esc(x.sku)}</span>${x.caja_master ? `<span class="tag warn">caja master ×${x.piezas}</span>` : ''}${n ? `<span class="tag ink">ya van ${fmt(n)}</span>` : ''}</span>
        <span class="l2">${esc(x.descripcion)} · ${esc(x.medidas)}</span></button></li>`; }).join('')}</ul>`
    : (UI.cubQ.trim().length >= 2 ? '<p class="small muted sin-res">Sin coincidencias en la Base de Medidas.</p>' : '');

  /* --- reparto por sucursal cargado (predistribuido) --- */
  const reparto = inp.predistribuido || [];
  const sucs = [...new Set(reparto.map(x => x.sucursal))];
  const grp = inp.grupos || [];
  const detalleReparto = `<details><summary class="small muted">Ver detalle</summary><table class="tbl">
        ${reparto.slice(0, 300).map(x => `<tr><td>${esc(x.sucursal)}</td><td class="code">${esc(x.sku)}</td><td class="n">${fmt(x.qty)}</td></tr>`).join('')}
      </table>${reparto.length > 300 ? `<p class="small muted">…y ${reparto.length - 300} líneas más</p>` : ''}</details>`;
  const nGrp = [...new Set(grp.map(x => +x.grupo || 0))].sort((a, b) => (a || 1e9) - (b || 1e9));
  const bloqueGrupos = grp.length && !reparto.length ? `<div class="reparto ${ef.grupos ? '' : 'inactivo'}">
      <div class="row"><span><b>Grupos de carga</b> · ${nGrp.length} · ${fmt(grp.reduce((a, x) => a + (+x.qty || 0), 0))} un.</span>
        <span class="spacer"></span><button class="btn quiet sm" data-cub="quitar-reparto" title="Quitar los grupos">Quitar</button></div>
      <p class="small muted">${ef.grupos ? 'El grupo 1 va al fondo del camión y cada grupo empieza donde terminó el anterior.' : 'El destino elegido junta toda la carga: los grupos quedan guardados.'}</p>
      <details><summary class="small muted">Ver detalle</summary><table class="tbl">
        ${nGrp.map(g => `<tr><td>${g ? 'Grupo ' + g : 'Sin grupo'}</td><td class="code">${esc(grp.filter(x => (+x.grupo || 0) === g).map(x => x.sku).join(' · '))}</td><td class="n">${fmt(grp.filter(x => (+x.grupo || 0) === g).reduce((a, x) => a + (+x.qty || 0), 0))}</td></tr>`).join('')}
      </table></details></div>` : '';
  const botonImportar = (txt) => `<label class="btn sm" title="Excel (.xlsx, .xls) o .csv del cliente, o la plantilla">${ICON.file} ${txt}<input type="file" accept=".xlsx,.xlsm,.xls,.csv" data-cub-import hidden></label>`;
  const bloqueReparto = reparto.length ? `<div class="reparto ${porSucursal ? '' : 'inactivo'}">
      <div class="row"><span><b>Reparto por sucursal</b> · ${sucs.length} sucursales · ${fmt(reparto.reduce((a, x) => a + (+x.qty || 0), 0))} un.</span>
        <span class="spacer"></span><button class="btn quiet sm" data-cub="quitar-reparto" title="Quitar el reparto y volver a Stock">Quitar</button></div>
      ${porSucursal ? '' : '<p class="small muted">El modo elegido no separa por sucursal: el reparto queda guardado y se usa al cambiar a un modo predistribuido.</p>'}
      ${detalleReparto}</div>`
    : porSucursal && !grp.length ? `<div class="reparto pendiente">
      <b>Falta el reparto por sucursal</b>
      <p class="small muted">Este modo arma la carga sucursal por sucursal. Sube el predistribuido del cliente tal como lo envía: se leen la sucursal, el producto y las unidades.</p>
      <div class="row tight">${botonImportar('Subir predistribuido')}<a class="btn quiet sm" href="/api/cubicaje-libre/plantilla">Plantilla</a></div></div>` : '';

  /* --- opciones, arriba del visor: se ven y se cambian sin bajar --- */
  const cls = (UI.clientes || []).map(x => x.nombre);
  const opciones = `<div class="barra-opc">
      <label class="opt"><span>Cliente</span><select data-cub-cliente><option value="">Sin cliente</option>
        ${cls.map(n => `<option ${n === inp.cliente ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>
      <div class="opt"><span>Modo de cubicaje</span>${seg('modo', inp.modo, MODOS_CUB)}</div>
      <div class="opt"><span>Carga</span>${seg('carga', inp.piso_pallet || '', [['', 'Según modo', 'Lo que diga el modo: MDA a piso, SDA en pallets'], ['PISO', 'A piso', 'Fuerza la carga a piso, aunque el modo sea SDA'], ['PALLET', 'En pallets', 'Fuerza la carga en pallets, aunque el modo sea MDA']])}</div>
      <div class="opt"><span>Destino</span>${seg('destino', inp.destino || '', [['', 'Según modo', 'Lo que diga el modo'], ['STOCK', 'Stock', 'Toda la carga junta'], ['SUCURSAL', 'Por sucursal', 'Se separa por sucursal según el reparto del cliente']])}</div>
      ${ef.pideCaja ? `<div class="opt"><span>Caja master</span>${seg('caja_master', inp.caja_master || '', [['CON CAJA MASTER', 'Con'], ['SIN CAJA MASTER', 'Sin']])}</div>` : ''}
      <div class="opt"><span>Ver</span>${seg('vista', inp.vista || 'rampla', VISTAS)}</div>
      ${enPallet ? `<div class="opt"><span>Mostrar</span>${seg('pallet_modo', inp.pallet_camion ? 'camion' : 'solo', [['solo', 'Solo el pallet', 'Aísla el pallet elegido sobre su tarima'], ['camion', 'En el camión', 'Todos los pallets dentro del camión, con el elegido resaltado']])}</div>` : ''}
      ${enPallet && (c.pallets_disponibles || []).length > 1 ? `<label class="opt"><span>Pallet</span>
        <select data-cub-pallet>${c.pallets_disponibles.map(n => `<option value="${n}" ${n === c.pallet_visto ? 'selected' : ''}>Pallet ${n} de ${c.pallets_disponibles.length}</option>`).join('')}</select></label>` : ''}
      <span class="spacer"></span>
      ${c.visor_json ? `<div class="row tight">
        <button class="btn sm" data-cub="pdf-todos" title="Un PDF por camión, cada uno con sus dos vistas">${ICON.file} PDF por camión</button>
        <button class="btn sm" data-cub="pdf-actual" title="PDF del camión que estás viendo, con sus dos vistas">PDF este camión</button>
        ${c.visor ? `<a class="btn sm" href="${esc(c.visor)}" target="_blank" rel="noopener" title="Abrir el visor en otra pestaña">${ICON.external} Aparte</a>` : ''}</div>` : ''}
    </div>`;

  /* --- camiones: una sola vez, como fichas que también eligen qué camión ve el 3D --- */
  const chips = camiones.map((v, i) => {
    const o = ocupPorCam[v.numero] || 0;
    const tono = o > 0.92 ? 'err' : o > 0.7 ? 'warn' : 'ok';
    return `<button class="chip-cam" data-cub-cam="${i}" aria-pressed="${i === UI.cubCam}" title="Ver este camión en el 3D">
      <span class="l1"><b>${soloPallet ? 'Pallet' : esc(v.tipo) + ' ·'} n.º ${v.numero}</b><span class="num">${fmt(unidPorCam[v.numero] || 0)} un.</span></span>
      <span class="barra"><span class="${tono}" style="width:${Math.min(100, 100 * o).toFixed(1)}%"></span></span>
      <span class="l2"><span class="num">${pctCub(o)}</span><span class="num">${m3(v.vol_m3)} m³</span></span></button>`;
  }).join('');
  const cam = soloPallet ? null : camiones.find(v => v.numero === c.pallet_vehiculo);
  const resumen = soloPallet && c.pallet_visto ? `<div class="resumen">
      <div class="res-linea">Pallet <b class="num">${c.pallet_visto}</b> de <b class="num">${(c.pallets_disponibles || []).length}</b>
        <span class="sep"></span>ocupación del pallet <b class="num">${pctCub(ocupMax)}</b>
        <span class="sep"></span>pallet <span class="num">${(c.pallet || []).join(' × ')} cm</span></div></div>`
    : camiones.length ? `<div class="resumen">
      <div class="res-linea"><b class="num">${camiones.length}</b> ${soloPallet ? 'pallet' : (camiones.length === 1 ? 'camión' : 'camiones')}
        ${(c.unidades || 0) !== totUnidades ? `<span class="sep"></span><b class="num">${fmt(c.unidades || 0)}</b> de ${fmt(totUnidades)} unidades` : ''}
        <span class="sep"></span>ocupación${camiones.length > 1 ? ' máx.' : ''} <b class="num">${pctCub(ocupMax)}</b>${camiones.length === 1 ? ` de <span class="num">${m3(camiones[0].vol_m3)} m³</span>` : ''}
        ${pallets ? `<span class="sep"></span><b class="num">${pallets}</b> pallets` : ''}
        ${enPallet && c.pallet_visto ? `<span class="sep"></span>pallet <b class="num">${c.pallet_visto}</b> resaltado${cam ? ` · va en el camión <b class="num">${cam.numero}</b>` : ''}` : ''}
        ${aPiso ? `<span class="sep"></span><b class="num">${fmt(aPiso)}</b> a piso` : ''}
        <span class="sep"></span>pallet <span class="num">${(c.pallet || []).join(' × ')} cm</span>
        ${inp.pedido ? `<span class="sep"></span>pedido <span class="code">${esc(inp.pedido)}</span>` : ''}</div>
      ${camiones.length > 1 ? `<div class="chips">${chips}</div>` : ''}</div>` : '';

  /* --- avisos: solo lo que hay que atender --- */
  const msgs = [
    ...(UI.cubError && !faltaMedidas && !UI.cubFalta ? [['err', 'Error', UI.cubError]] : []),
    ...((c.sin_medidas || []).length ? [['err', 'Sin medidas', c.sin_medidas.join(', ')]] : []),
    ...(enPallet && !ef.pallets ? [['info', 'Pallets', 'Para ver un pallet se cubicó en pallets: con la carga a piso no hay pallets que mostrar.']] : []),
    ...((c.avisos || []).map(a => ['warn', 'Aviso', a])),
  ];

  const vivo = c.visor_vivo || '/visor/visor_vivo.html';
  return `<div class="mesa">
    <aside class="panel mesa-carga" aria-label="Carga">
      <div class="mc-h">
        <h2>Carga</h2><span class="muted num small" title="Una caja master es un bulto con varias unidades">${fmt(totUnidades)} un. · ${fmt(totBultos)} bultos · ${lineas.length} SKU</span>
        <div class="mc-acc"><a class="btn quiet sm" href="/api/cubicaje-libre/plantilla" title="Excel para armar la carga fuera de la plataforma">Plantilla</a>
        <label class="btn quiet sm" title="Cargar productos desde un Excel o CSV: la plantilla o el archivo del cliente">Importar<input type="file" accept=".xlsx,.xlsm,.xls,.csv" data-cub-import hidden></label>
        ${lineas.length ? `<a class="btn quiet sm" href="/api/cubicaje-libre/excel">Exportar</a><span class="spacer"></span><button class="btn quiet sm" data-cub="vaciar">Vaciar</button>` : ''}</div>
      </div>
      <div class="agregar">
        <div class="searchbox">${ICON.search}<input type="text" data-cub-q value="${esc(UI.cubQ)}" placeholder="Agregar producto: SKU o descripción" autocomplete="off" spellcheck="false" aria-label="Agregar producto" role="combobox" aria-expanded="${UI.cubSug.length > 0}" aria-controls="sug-lista" aria-autocomplete="list"${UI.cubSug.length ? ` aria-activedescendant="sug-${UI.cubSel}"` : ''}></div>
        ${sugerencias}
        ${lineas.length && !UI.cubSug.length && !UI.cubQ ? '<p class="small muted ayuda">Enter agrega y salta a las unidades; otro Enter vuelve aquí. También puedes pegar una lista desde Excel (SKU y unidades).</p>' : ''}
      </div>
      <ol class="items">${filas || `<li class="vacio"><b>Empieza por el primer producto</b><span>Escribe un SKU arriba, pega una lista desde Excel, o trae un pedido analizado.</span></li>`}</ol>
      ${bloqueReparto}${bloqueGrupos}
      <div class="mc-pie">
        <div class="row tight"><input type="text" data-cubped placeholder="Traer un pedido analizado (N°)" inputmode="numeric" style="flex:1;min-width:0"><button class="btn sm" data-cub="traer">Traer</button></div>
        ${seccionAjustes()}
      </div>
    </aside>

    <div class="mesa-vista">
      ${opciones}
      <p class="se-cubica small muted">Se cubica como <b>${ef.texto}</b>${inp.piso_pallet || inp.destino ? ' · la carga y el destino elegidos mandan sobre el modo' : ''}</p>
      ${resumen}
      ${faltaMedidas ? `<div class="panel empty"><h3>Falta la Base de Medidas</h3><p>El cubicaje necesita las medidas de los productos. Se cargan una vez y quedan guardadas.</p><button class="btn primary" data-go="config">Ir a Configuración</button></div>` : ''}
      ${alertaFaltantes(c.faltantes, '/api/cubicaje-libre/faltantes.xlsx', totUnidades)}
      ${msgs.length ? `<ul class="msgs">${msgs.map(([t, k, x]) => `<li><span class="tag ${t}">${k}</span> ${esc(x)}</li>`).join('')}</ul>` : ''}
      <div class="visor-caja" aria-busy="${UI.cubCalculando || UI.cubOcupado}">
        <iframe data-k="visor-libre" data-visor="libre" src="${esc(vivo)}#solo3d" title="Visor 3D del cubicador"></iframe>
        ${herramientasVisor()}
        ${UI.cubCalculando || UI.cubOcupado ? '<i class="calc-bar"></i><span class="calc-tag">Calculando…</span>' : ''}
      </div>
    </div>
  </div>`;
}

/* Productos que no están en la Base de Medidas: no se cubican (no se inventan medidas) y se dice cuáles son,
   cuántas unidades quedaron fuera y cómo resolverlo. `total` = unidades de toda la carga, con y sin medidas. */
function alertaFaltantes(f, url, total){
  if (!f || !f.length) return '';
  const fuera = f.reduce((a, x) => a + x.unidades, 0), cargadas = Math.max(0, total - fuera);
  const n = f.length, pct = total ? fuera / total : 0;
  return `<section class="faltantes" aria-label="Productos sin medidas">
    <div class="fl-cab">${ICON.alerta}<div>
      <h3>${n === 1 ? 'Un producto no se cargó' : `${n} productos no se cargaron`} por falta de medidas</h3>
      <p>Quedaron fuera del camión <b class="num">${fmt(fuera)}</b> unidades. Sin medidas no se cubica: agrégalas a la Base de Medidas y esta carga se recalcula sola.</p></div></div>
    <div class="fl-barra" role="img" aria-label="${fmt(cargadas)} unidades cargadas y ${fmt(fuera)} sin cargar"><i class="ok" style="width:${(100 * (1 - pct)).toFixed(1)}%"></i><i class="out" style="width:${(100 * pct).toFixed(1)}%"></i></div>
    <div class="fl-leyenda"><span><i class="sw ok"></i>Cargadas <b class="num">${fmt(cargadas)}</b></span><span><i class="sw out"></i>Sin cargar <b class="num">${fmt(fuera)}</b> · ${pctCub(pct)} de la carga</span></div>
    <div class="fl-th" aria-hidden="true"><span>SKU</span><span>Producto</span><span>Sin cargar</span></div>
    <ul class="fl-lista">${f.map(x => `<li><span class="code">${esc(x.sku)}</span><span class="nom" title="${esc(x.descripcion || '')}">${esc(x.descripcion || 'Sin nombre en la maestra')}</span><b class="num">${fmt(x.unidades)} un.</b></li>`).join('')}</ul>
    <div class="fl-acc"><a class="btn primary sm" href="${esc(url)}">${ICON.file} Descargar plantilla de medidas</a>
      <button class="btn sm" data-go="config">Ir a Base de Medidas</button>
      <span class="small muted">La plantilla ya trae estos SKU: completa largo, ancho, alto y peso, e impórtala.</span></div></section>`;
}

/* ---- Eventos del cubicador (no pasan por el manejador general) ---- */
document.addEventListener('click', ev => {
  const t = ev.target.closest('button, a'); if (!t || !UI.cubIn) return;
  const d = t.dataset;
  if (d.cubOpt){ cambiarOpcionCub(d.cubOpt, d.valor); }
  else if (d.cubSug){ agregarSku(d.cubSug, 1); }
  else if (d.cubMas !== undefined){ cambiarQty(+d.cubMas, (UI.cubIn.lineas[+d.cubMas].qty || 0) + (ev.shiftKey ? 10 : 1)); }
  else if (d.cubMenos !== undefined){ cambiarQty(+d.cubMenos, (UI.cubIn.lineas[+d.cubMenos].qty || 0) - (ev.shiftKey ? 10 : 1)); }
  else if (d.cubQuitar !== undefined){ quitarLinea(+d.cubQuitar); }
  else if (d.cubCam !== undefined){ UI.cubCam = +d.cubCam; Visor.camion(UI.cubCam); render(); }
  else if (d.cubFiltro){
    UI.cubFiltro = UI.cubFiltro === d.cubFiltro ? null : d.cubFiltro;
    Visor.filtro(UI.cubFiltro); render();
  }
  else if (d.cub === 'vaciar'){ vaciarCub(); }
  else if (d.cub === 'quitar-reparto'){ quitarRepartoCub(); }
  else if (d.cub === 'traer'){ const el = document.querySelector('[data-cubped]'); traerPedido(el ? el.value : ''); }
  else if (d.cub === 'pdf-todos'){
    const n = (UI.cub && UI.cub.camiones || []).length;
    if (n > 1) toast(`Se descargarán ${n} PDF, uno por camión. Si el navegador pregunta, permite las descargas múltiples.`);
    Visor.pdf(false);
  }
  else if (d.cub === 'pdf-actual'){ Visor.pdf(true); }
});
document.addEventListener('input', ev => {
  const el = ev.target; if (!el.matches) return;
  if (el.matches('[data-cub-q]')) pedirSugerencias(el.value);
  else if (el.matches('[data-cubqty]')){            // se aplica al dejar de escribir; Enter o salir del campo lo aplica ya
    clearTimeout(_qtyTimer); _qtyTimer = setTimeout(() => cambiarQty(+el.dataset.cubqty, el.value), 450);
  }
});
document.addEventListener('keydown', ev => {
  const el = ev.target; if (!el.matches || !UI.cubIn) return;
  if (el.matches('[data-cub-q]')){
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp'){
      if (!UI.cubSug.length) return; ev.preventDefault();
      UI.cubSel = (UI.cubSel + (ev.key === 'ArrowDown' ? 1 : -1) + UI.cubSug.length) % UI.cubSug.length; render();
    } else if (ev.key === 'Enter'){
      ev.preventDefault();
      agregarConEnter(el.value.trim());
    } else if (ev.key === 'Escape'){ UI.cubQ = ''; UI.cubSug = []; el.value = ''; render(); }
  } else if (el.matches('[data-cubqty]') && ev.key === 'Enter'){
    ev.preventDefault(); clearTimeout(_qtyTimer); cambiarQty(+el.dataset.cubqty, el.value);
    const q = document.querySelector('[data-cub-q]'); if (q) q.focus();          // siguiente producto
  } else if (el.matches('[data-cubped]') && ev.key === 'Enter'){ ev.preventDefault(); traerPedido(el.value); }
});
document.addEventListener('paste', ev => {
  const el = ev.target;
  if (!el.matches || !el.matches('[data-cub-q]') || !UI.cubIn) return;
  const txt = ev.clipboardData ? ev.clipboardData.getData('text') : '';
  if (!/[\r\n\t]/.test(txt.trim())) return;          // un solo valor: se pega como texto de búsqueda
  ev.preventDefault(); ev.stopPropagation(); pegarLista(txt);
}, true);
document.addEventListener('change', async ev => {
  const el = ev.target; if (!el.matches || !UI.cubIn) return;
  if (el.matches('[data-cub-cliente]')){ UI.cubIn.cliente = el.value; pedirCalculo(); }
  else if (el.matches('[data-cub-pallet]')){ UI.cubIn.pallet_n = +el.value; pedirCalculo(); }
  else if (el.matches('[data-cubqty]')){ clearTimeout(_qtyTimer); cambiarQty(+el.dataset.cubqty, el.value); }
  else if (el.matches('[data-cub-aj]')){ await guardarAjustes({[el.dataset.cubAj]: el.dataset.cubAj === 'celda_cm' ? +el.value : el.value}); }
  else if (el.matches('[data-cub-import]') && el.files[0]){ await importarCarga(el); el.value = ''; }
});
