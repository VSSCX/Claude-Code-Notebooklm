/* Configuración, utilidades, capa de datos, dominio y estado de la interfaz.
   Parte de la interfaz de Trazabilidad Order Desk. */

/* ============ Configuración ============ */
const STEPS = [
  {k:'solicitada', t:'Cita pedida'},
  {k:'confirmada', t:'Cita confirmada'},
  {k:'sap',        t:'Fecha en SAP'},
  {k:'etq',        t:'ETQ'},
  {k:'portal',     t:'Portal despacho'},
  {k:'proyeccion', t:'Proyección'},
  {k:'facturada',  t:'Facturada'},
  {k:'packlist',   t:'Pack list'},
  {k:'entregado',  t:'Entregado'},
];
// Al reprogramar una cita se reabren estos pasos
const REABRE_AL_REPROGRAMAR = ['confirmada','sap','portal','proyeccion'];
const CAT = {
  vehiculo:['Rampla 53','Camión 50'], carga:['MIX','MONO'], un:['MDA','SDA'],
  region:['RM','Fuera de RM','Retira'], canal:['RETAIL','ECOMMERCE','OUTLET','ESPECIALISTA'],
  tipo:['Stock','Predistribuido'],
};
const DEF_ENT = {vehiculo:'Rampla 53', carga:'MIX', un:'MDA', region:'RM', tipo:'Stock'};
const EVENTOS = {pedido:'pedido extraído de VL01N', entregas:'entregas creadas', grupos:'grupos creados', fecha_sap:'fecha y cita actualizadas en SAP'};

/* ============ Utilidades ============ */
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nf = new Intl.NumberFormat('es-CL');
const fmt = n => nf.format(Math.round(+n || 0));
const nowISO = () => new Date().toISOString();
const clone = o => JSON.parse(JSON.stringify(o ?? {}));
const safeId = s => String(s ?? '').trim().replace(/[^A-Za-z0-9_\-~:@+]/g, '_').slice(0, 120);
const normH = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
const normSku = s => String(s ?? '').trim().replace(/^0+(?=\d)/, '');
function fmtFecha(iso){ if(!iso) return ''; const [y,m,d] = iso.split('-'); return `${d}-${m}-${y}`; }
function isoWeek(iso){
  const d = new Date(iso + 'T12:00:00'); const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day + 3); const w1 = new Date(d.getFullYear(), 0, 4);
  return 1 + Math.round(((d - w1) / 864e5 - 3 + ((w1.getDay() + 6) % 7)) / 7);
}
/* Un aviso breve; con `accion` ({texto, fn}) ofrece deshacer y dura más */
function toast(msg, accion){
  const t = $('#toast'); t.textContent = msg;
  if (accion){
    const b = document.createElement('button'); b.type = 'button'; b.className = 'toast-acc'; b.textContent = accion.texto;
    b.onclick = () => { t.classList.remove('on'); accion.fn(); };
    t.append(b);
  }
  t.classList.toggle('con-acc', !!accion);
  t.classList.add('on'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('on'), accion ? 7000 : 2600);
}
/* OC comparable: sin espacios ni signos, en mayúsculas y sin ceros a la izquierda (igual que el servidor) */
const claveOc = v => String(v || '').toUpperCase().replace(/[^A-Z0-9]/g, '').replace(/^0+/, '');
/* Decimales con coma, como el resto de los números de la plataforma */
const m3 = (x, d = 1) => (+x || 0).toFixed(d).replace('.', ',');

/* Resultados que no se pueden perder de vista (SAP, cubicaje, cargas): quedan
   fijos arriba hasta que la persona los cierra, en vez de irse solos como el toast. */
const Avisos = {
  lista: [],
  agregar(tipo, titulo, detalle, pasos){
    this.lista.unshift({id: Date.now() + '-' + Math.random().toString(16).slice(2, 6),
                        tipo, titulo, detalle: detalle || '', pasos: pasos || [],
                        hora: new Date().toTimeString().slice(0, 5)});
    this.lista = this.lista.slice(0, 5);
    if (typeof render === 'function') render();
  },
  cerrar(id){ this.lista = this.lista.filter(x => x.id !== id); render(); },
  html(){
    if (!this.lista.length) return '';
    return `<div class="avisos">${this.lista.map(a => `
      <div class="aviso ${esc(a.tipo)}" data-k="av-${esc(a.id)}" role="${a.tipo === 'error' ? 'alert' : 'status'}">
        <div class="aviso-cuerpo">
          <div><b>${esc(a.titulo)}</b> <span class="small muted num">${esc(a.hora)}</span></div>
          ${a.detalle ? `<div class="small">${esc(a.detalle)}</div>` : ''}
          ${(a.pasos || []).length ? `<ul class="small muted">${a.pasos.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}
        </div>
        <button class="btn quiet icon" data-cerrar-aviso="${esc(a.id)}" title="Cerrar" aria-label="Cerrar aviso">${ICON.x}</button>
      </div>`).join('')}</div>`;
  },
};
function setSync(state, text){
  _pieSync = {estado: state, texto: text};
  renderFoot();
}
function toDateISO(v){
  if (v == null || v === '') return '';
  if (v instanceof Date && !isNaN(v)) return v.toISOString().slice(0,10);
  if (typeof v === 'number'){ const d = new Date(Math.round((v - 25569) * 864e5)); return d.toISOString().slice(0,10); }
  const m = String(v).trim().match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$/);
  if (m){ const y = m[3].length === 2 ? '20' + m[3] : m[3]; return `${y}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`; }
  if (/^\d{4}-\d{2}-\d{2}/.test(String(v))) return String(v).slice(0,10);
  return '';
}
function toHora(v){
  if (v instanceof Date && !isNaN(v)) return v.toTimeString().slice(0,5);
  if (typeof v === 'number' && v >= 0 && v < 1){ const mins = Math.round(v * 1440); return String(Math.floor(mins/60)).padStart(2,'0') + ':' + String(mins % 60).padStart(2,'0'); }
  const m = String(v ?? '').match(/^(\d{1,2}):(\d{2})/); return m ? m[1].padStart(2,'0') + ':' + m[2] : '';
}
function normTipo(v){ const s = normH(v); if (s.startsWith('pred')) return 'Predistribuido'; if (s.startsWith('stock')) return 'Stock'; return v ? String(v) : ''; }

/* ============ Capa de datos: API REST ============
   Toda la app habla con Store. El servidor es la fuente de verdad. */
/* Quién está usando la plataforma: viaja en cada llamada y queda en el historial */
const Usuario = {
  /* Ya no se pregunta el nombre: el servidor usa el usuario de Windows del PC. Un nombre escrito antes (con clave de acceso) se respeta solo en ese caso. */
  get(){ try { return Sesion.conCuentas() ? '' : (sessionStorage.getItem('od_usuario') || ''); } catch(e){ return ''; } },
  set(v){ try { sessionStorage.setItem('od_usuario', (v || '').trim().slice(0, 40)); } catch(e){} },
};
/* Cabeceras de toda llamada: quién (modo abierto) y la marca que el servidor exige contra peticiones de otros sitios */
const cab = (extra = {}) => ({'X-Requested-With': 'od', ...(Usuario.get() ? {'X-Usuario': Usuario.get()} : {}), ...extra});
async function api(method, path, body){
  let r;
  const cabeceras = cab(body ? {'Content-Type':'application/json'} : {});
  try {
    r = await fetch('/api' + path, {method, headers: cabeceras, body: body ? JSON.stringify(body) : undefined});
  } catch(e){ throw new Error('Sin conexión con el servidor. Revisa que run.bat siga abierto.'); }
  const codigo = r.headers.get('X-Request-ID') || '';
  if (r.status === 401 && !path.startsWith('/sesion')){
    if (Sesion.conCuentas()) Sesion.expirada();
    else if (typeof pedirSesion === 'function') await pedirSesion();
    const e = new Error('Hay que entrar para continuar.'); e.api = true; throw e;
  }
  if (!r.ok){
    let msg = `Error ${r.status}`, j = {};
    try {
      j = await r.json();
      msg = typeof j.detail === 'string' ? j.detail : (j.detail || []).map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ') || msg;
    } catch(e) {}
    if (r.status === 403 && j.cambiar_clave && Sesion.cuenta){ Sesion.cuenta.debe_cambiar_clave = true; Sesion.pantalla('cambio'); }
    const e = new Error(msg); e.api = true; e.status = r.status; e.codigo = j.codigo || codigo; throw e;
  }
  return r.status === 204 ? null : r.json();
}
const COLS = ['pedidos','entregas','config'];
/* El render se agrupa por cuadro de animación: varios cambios en el mismo instante pintan una sola vez */
let _rafRender = 0;
function renderSoon(){ if (_rafRender) return; _rafRender = requestAnimationFrame(() => { _rafRender = 0; render(); }); }
const Store = {
  data: {pedidos:new Map(), entregas:new Map(), config:new Map()}, archivos: [],
  loaded: new Set(), offline: false, version: '', queues: new Map(),
  rev: 0,          // sube con cada cambio local: invalida los índices memoizados
  pendientes: 0,   // guardados en vuelo; mientras haya, el sondeo no pisa lo que se ve
  async init(){
    await this.refresh();
    setInterval(() => this.poll(), 10000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) this.poll(); });
  },
  async refresh(){
    try {
      const st = await api('GET', '/estado');
      this.data.pedidos = new Map(st.pedidos.map(p => [safeId(p.pedido), p]));
      this.data.entregas = new Map(st.entregas.map(e => [safeId(e.entrega), e]));
      this.data.config = new Map(Object.entries(st.config || {}));
      this.archivos = st.archivos || [];
      this.version = st.version; this.offline = false; this.rev++;
      COLS.forEach(c => this.loaded.add(c));
      setSync('ok', 'Conectado al servidor');
    } catch(e){ this.offline = true; setSync('err', 'Sin conexión con el servidor'); }
    render();
  },
  async poll(){
    if (this.pendientes) return;
    try {
      const {version} = await api('GET', '/version');
      const editando = dlg.open || (document.activeElement && document.activeElement.closest('#app input, #app textarea, #app select'));
      if (version !== this.version && !editando) await this.refresh();
      else if (this.offline) await this.refresh();
    } catch(e){ this.offline = true; setSync('err', 'Sin conexión con el servidor'); }
  },
  list(col){ return [...this.data[col].values()]; },
  get(col, id){ return this.data[col].get(id); },
  enqueue(key, fn){
    const prev = this.queues.get(key) || Promise.resolve();
    const p = prev.then(fn, fn); this.queues.set(key, p.catch(()=>{})); return p;
  },
  ruta(col, id, obj){
    if (col === 'pedidos') return '/pedidos/' + encodeURIComponent(obj.pedido);
    if (col === 'entregas') return '/entregas/' + encodeURIComponent(obj.entrega);
    return '/config/' + encodeURIComponent(id);
  },
  /* Optimista: lo local se ve al instante y el servidor confirma por detrás.
     Si el servidor rechaza, se vuelve a cargar su versión y el error sube a quien llamó. */
  async set(col, id, obj){
    this.data[col].set(id, obj); this.rev++; renderSoon();
    this.pendientes++;
    return this.enqueue(col + '/' + id, async () => {
      try {
        const guardado = await api('PUT', this.ruta(col, id, obj), obj);
        this.data[col].set(id, guardado); this.rev++;
      } catch(e){
        this.pendientes--; await this.refresh(); throw e;
      }
      this.pendientes--; renderSoon();
    });
  },
  async del(col, id){
    const obj = this.get(col, id); if (!obj) return;
    this.data[col].delete(id);
    if (col === 'pedidos') for (const [k, e] of this.data.entregas) if (e.pedido === obj.pedido) this.data.entregas.delete(k);
    this.rev++; renderSoon(); this.pendientes++;
    try { await api('DELETE', this.ruta(col, id, obj)); }
    catch(e){ this.pendientes--; await this.refresh(); throw e; }
    this.pendientes--;
  },
};
const dbErr = e => (e && e.message) || 'No se pudo guardar.';
async function save(col, id, obj){ try { await Store.set(col, id, obj); return true; } catch(e){ toast(dbErr(e)); return false; } }

/* ============ Dominio ============ */
const pasoOk = (e, k) => !!(e.pasos && e.pasos[k] && e.pasos[k].ok);
const unidades = e => (e.lineas || []).reduce((a, l) => a + (+l.qty || 0), 0);
const siguiente = e => e.anulada ? null : (STEPS.find(s => !pasoOk(e, s.k)) || null);
/* Índices que se recalculan solo cuando cambian los datos (Store.rev) */
function porRev(calcular){
  let rev = -1, valor;
  return () => { if (rev !== Store.rev){ valor = calcular(); rev = Store.rev; } return valor; };
}
const _entPorPedido = porRev(() => {
  const m = new Map();
  for (const e of Store.list('entregas')){ const l = m.get(e.pedido) || []; l.push(e); m.set(e.pedido, l); }
  for (const l of m.values())
    l.sort((a,b) => (a.cita?.fecha || '9').localeCompare(b.cita?.fecha || '9') || String(a.entrega).localeCompare(String(b.entrega)));
  return m;
});
const entregasDe = ped => _entPorPedido().get(ped) || [];
const config = () => Store.get('config', 'app') || {};
// Región y canal siguen lo último usado para ese cliente
function patron(cliente){
  const byAct = (a, b) => (b.actualizado || '').localeCompare(a.actualizado || '');
  const peds = Store.list('pedidos').filter(p => cliente && p.cliente === cliente).sort(byAct);
  const ids = new Set(peds.map(p => p.pedido));
  const ent = Store.list('entregas').filter(e => ids.has(e.pedido) && e.region).sort(byAct)[0];
  return {region: ent ? ent.region : DEF_ENT.region, canal: (peds.find(p => p.canal) || {}).canal || 'RETAIL'};
}
const normVeh = v => { const s = normH(v); return s.includes('rampla') ? 'Rampla 53' : s.includes('cami') ? 'Camión 50' : String(v || ''); };

const _resumenCache = {rev: -1, m: new Map()};
function resumen(p){
  if (_resumenCache.rev !== Store.rev){ _resumenCache.rev = Store.rev; _resumenCache.m = new Map(); }
  const hit = _resumenCache.m.get(p);
  if (hit) return hit;
  const r = calcularResumen(p); _resumenCache.m.set(p, r); return r;
}
function calcularResumen(p){
  const m = new Map();
  for (const l of (p.lineas || [])){
    const k = normSku(l.sku); const r = m.get(k) || {sku:k, desc:l.desc || '', pedida:0, enEntrega:0, entregado:0, agendado:0, sinCita:0, facturado:0, externa:0};
    r.pedida += +l.qty || 0; r.externa += +l.externa || 0; if (!r.desc) r.desc = l.desc || ''; m.set(k, r);
  }
  for (const e of entregasDe(p.pedido)){
    if (e.anulada) continue;
    const ent = pasoOk(e,'entregado'), conf = pasoOk(e,'confirmada'), fac = pasoOk(e,'facturada');
    for (const l of (e.lineas || [])){
      const k = normSku(l.sku), q = +l.qty || 0;
      const r = m.get(k) || {sku:k, desc:l.desc || '', pedida:0, enEntrega:0, entregado:0, agendado:0, sinCita:0, facturado:0, externa:0, fuera:true};
      r.enEntrega += q; if (fac) r.facturado += q;
      if (ent) r.entregado += q; else if (conf) r.agendado += q; else r.sinCita += q;
      m.set(k, r);
    }
  }
  const filas = [...m.values()].map(r => ({...r, pendiente: Math.max(0, r.pedida - r.enEntrega - r.externa), exceso: Math.max(0, r.enEntrega + r.externa - r.pedida)}));
  const tot = filas.reduce((a, r) => { for (const k of ['pedida','enEntrega','entregado','agendado','sinCita','facturado','pendiente','exceso','externa']) a[k] += r[k]; return a; },
    {pedida:0, enEntrega:0, entregado:0, agendado:0, sinCita:0, facturado:0, pendiente:0, exceso:0, externa:0});
  return {filas, tot};
}
const cerrado = p => { const {tot} = resumen(p); return tot.pedida > 0 && tot.pendiente === 0 && tot.entregado >= tot.pedida; };

function barHTML(tot, big){
  const base = Math.max(tot.pedida, tot.enEntrega) || 1;
  const w = v => (100 * v / base).toFixed(2) + '%';
  return `<div class="bar ${big ? 'big' : ''}" role="img" aria-label="Entregado ${fmt(tot.entregado)}, agendado ${fmt(tot.agendado)}, sin cita ${fmt(tot.sinCita)}, pendiente ${fmt(tot.pendiente)}">
    <i class="s-ent" style="width:${w(tot.entregado)}"></i><i class="s-age" style="width:${w(tot.agendado)}"></i><i class="s-sin" style="width:${w(tot.sinCita)}"></i></div>`;
}
/* Reparte el trabajo en tandas: no se pide todo de golpe ni uno por uno */
async function enLotes(items, n, fn){
  for (let i = 0; i < items.length; i += n) await Promise.all(items.slice(i, i + n).map(fn));
}
const pct = (a, b) => b ? Math.round(100 * a / b) + '%' : '—';

/* Un grupo = un camión. Puede tener varias entregas, incluso de otros pedidos
   (conchos). Los pasos del camión se derivan: hechos solo si TODAS sus entregas
   los tienen. 'facturada' se marca por entrega, porque la factura es por entrega. */
const POR_ENTREGA = ['facturada'];
const grupos = porRev(calcularGrupos);
function calcularGrupos(){
  const m = new Map();
  for (const e of Store.list('entregas')){
    if (e.anulada) continue;
    // las entregas de un camión compartido entre pedidos (cubicaje conjunto) forman un solo grupo aunque aún no tengan número
    const key = e.grupo ? 'G' + e.grupo : e.camion_ref ? 'C' + e.camion_ref : 'E' + e.entrega;
    const g = m.get(key) || {key, grupo:e.grupo || '', sinGrupo:!e.grupo, entregas:[]};
    g.entregas.push(e); m.set(key, g);
  }
  for (const g of m.values()){
    const e0 = g.entregas[0];
    Object.assign(g, {cita:e0.cita || {}, vehiculo:e0.vehiculo, carga:e0.carga, un:e0.un,
                      region:e0.region, tipo:e0.tipo});
    g.unidades = g.entregas.reduce((a, e) => a + unidades(e), 0);
    g.pedidos = [...new Set(g.entregas.map(e => e.pedido))];
    g.pasos = {}; g.parcial = false;
    for (const s of STEPS){
      const n = g.entregas.filter(e => pasoOk(e, s.k)).length;
      g.pasos[s.k] = n === g.entregas.length;
      if (n > 0 && n < g.entregas.length) g.parcial = true;
    }
    g.next = STEPS.find(s => !g.pasos[s.k]) || null;
  }
  return [...m.values()];
}
const gruposDe = ped => grupos().filter(g => g.entregas.some(e => e.pedido === ped))
  .sort((a, b) => (a.cita.fecha || '9').localeCompare(b.cita.fecha || '9') || String(a.grupo).localeCompare(String(b.grupo)));
const grupo1 = key => grupos().find(g => g.key === key);

async function marcarPasoGrupo(key, k, forzar){
  const g = grupo1(key); if (!g || POR_ENTREGA.includes(k)) return;
  const nuevo = forzar ?? !g.pasos[k];
  if (nuevo && k === 'confirmada' && !(g.cita.fecha && g.cita.hora))
    return abrirGrupo(key, {marcar:'confirmada', msg:'Para confirmar la cita ingresa fecha y hora.'});
  await Promise.all(g.entregas.map(e => marcarPaso(safeId(e.entrega), k, nuevo)));
}

async function marcarPaso(id, k, forzar){
  const e = clone(Store.get('entregas', id)); if (!e.entrega) return;
  e.pasos = e.pasos || {};
  const estaba = pasoOk(e, k), nuevo = forzar ?? !estaba;
  if (nuevo && k === 'confirmada' && !(e.cita && e.cita.fecha && e.cita.hora)) return abrirEntrega(e.pedido, id, {marcar:'confirmada', msg:'Para confirmar la cita ingresa fecha y hora.'});
  if (nuevo && k === 'facturada' && !e.factura) return abrirEntrega(e.pedido, id, {marcar:'facturada', msg:'Para marcar facturada ingresa el N° de factura.'});
  if (nuevo === estaba) return;
  e.pasos[k] = {ok: nuevo, at: nowISO()};
  addLog(e, `${nuevo ? 'Hecho' : 'Reabierto'}: ${STEPS.find(s => s.k === k).t}`);
  await save('entregas', safeId(e.entrega), e);   // se ve al instante; solo un error merece aviso
}
function addLog(e, txt){ e.log = [{at: nowISO(), txt}, ...(e.log || [])].slice(0, 40); }

/* ============ Estado de UI ============ */
const UI = { juntar:false, juntarSel:new Set(), conjunto:null, verConjunto:false, conjuntoCargando:false, view:'pedidos', sel:null, sub:'entregas', q:'', soloAbiertos:true, cliente:'', open:new Set(),
  pDesde: new Date(Date.now() - 7*864e5).toISOString().slice(0,10), pHasta: '', pPorConf:true, imp:null };

/* Entrada suave del contenido al cambiar de pestaña o de vista: solo opacidad y un desplazamiento mínimo (160 ms, ease-out).
   Es de entrada y no de salida, para no sumar espera. Se dispara al cambiar de pestaña, no en cada redibujado: los datos que
   llegan en vivo no deben parpadear. Con "reducir movimiento" queda el fundido sin desplazamiento. */
const EASE_OUT = 'cubic-bezier(0.23, 1, 0.32, 1)';
function entrar(el, dx = 0, dy = 0){
  if (!el || !el.animate) return;
  const reducido = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const previas = el.getAnimations();
  const desde = previas.length ? +getComputedStyle(el).opacity : 0;       // si se interrumpe, parte de lo que ya se ve
  previas.forEach(a => a.cancel());
  el.animate([{opacity: desde, transform: reducido ? 'none' : `translate(${dx}px, ${dy}px)`}, {opacity: 1, transform: 'none'}],
             {duration: 160, easing: EASE_OUT});
}
function go(view){
  const cambia = UI.view !== view;
  UI.view = view; render();
  if (cambia) entrar($('#app'), 0, 4);
}

/* Indicador de la pestaña activa: una sola barra que se desliza (transform, sin tocar el layout) en vez de saltar */
function moverIndicador(){
  const sel = document.querySelector('.tabs [aria-selected="true"]'), ind = document.querySelector('.tabs .tab-ind');
  if (!sel || !ind) return;
  const mover = `translateX(${sel.offsetLeft}px) scaleX(${sel.offsetWidth})`;
  if (!ind.style.transform){                                        // primera vez: aparece en su lugar, sin recorrerlo
    ind.style.transition = 'none'; ind.style.transform = mover; void ind.offsetWidth; ind.style.transition = '';
  } else if (ind.style.transform !== mover) ind.style.transform = mover;
  UI.tabInd = mover;
}
window.addEventListener('resize', moverIndicador);
const NAV = [['pedidos','Pedidos'], ['bandeja','Por hacer'], ['cubicador','Cubicador'],
             ['proyeccion','Proyección'], ['importar','SAP'], ['config','Configuración']];
function renderNav(){
  const pendientes = grupos().filter(g => g.next).length;
  const items = Sesion.esAdmin() ? [...NAV, ['admin', 'Administración']] : NAV;
  const html = items.map(([v, t]) => {
    const c = v === 'bandeja' && pendientes ? `<span class="count">${pendientes}</span>`
      : v === 'admin' && UI.erroresNuevos ? `<span class="count alerta" title="Errores sin revisar">${UI.erroresNuevos}</span>` : '';
    return `<button class="rail-item" data-go="${v}" ${UI.view === v ? 'aria-current="page"' : ''}>${ICON[v === 'importar' ? 'sap' : v === 'bandeja' ? 'porhacer' : v === 'config' ? 'config' : v]}<span>${t}</span>${c}</button>`;
  }).join('');
  pintar($('#nav'), html);
}

/* Redibuja solo lo que cambió (morphdom): no se pierden scroll, foco ni iframes al llegar datos nuevos */
function pintar(el, html){
  if (!el) return;
  if (!window.morphdom){ el.innerHTML = html; return; }
  const destino = el.cloneNode(false); destino.innerHTML = html;
  morphdom(el, destino, {
    childrenOnly: true,
    getNodeKey: n => n.nodeType === 1 ? (n.id || n.getAttribute('data-k') || undefined) : undefined,
    onBeforeElUpdated(de, a){
      if (de.isEqualNode(a)) return false;
      // lo que la persona está tocando manda sobre lo que dice el servidor
      if (de === document.activeElement && /^(INPUT|TEXTAREA|SELECT)$/.test(de.tagName)) return false;
      if (de.tagName === 'DETAILS') a.open = de.open;
      // una sola animación de autoría: la celda que cambió se marca una vez
      if (de.hasAttribute('data-flash') && de.textContent !== a.textContent){
        de.classList.remove('flash'); void de.offsetWidth; de.classList.add('flash');
      }
      return true;
    },
  });
}

/* ---- La ruta de 9 pasos de un camión (o de una entrega suelta) ---- */
function rutaHTML(g, {entrega} = {}){
  return `<div class="ruta" role="group" aria-label="Pasos del camión">${STEPS.map((s, i) => {
    const fijo = POR_ENTREGA.includes(s.k);
    // 'Facturada' es por entrega: en la tarjeta de una entrega se marca ahí mismo; en el camión es de solo lectura
    const hecho = fijo && entrega ? pasoOk(entrega, s.k) : g.pasos[s.k];
    const sig = !hecho && g.next && g.next.k === s.k;
    const accion = fijo ? (entrega ? `data-paso="${s.k}" data-ent="${esc(safeId(entrega.entrega))}"` : '')
                        : `data-gpaso="${s.k}" data-grupo="${esc(g.key)}"`;
    const bloqueado = fijo && !entrega;
    const tit = fijo && !entrega ? `${s.t} · se marca en cada entrega` : `${s.t}${hecho ? ' · hecho' : sig ? ' · siguiente' : ''}`;
    return `<button class="paso ${hecho ? 'done' : ''} ${sig ? 'next' : ''} ${i === STEPS.length - 1 ? 'last' : ''} ${bloqueado ? 'fixed' : ''}" ${bloqueado ? 'tabindex="-1" aria-disabled="true"' : accion}
      aria-pressed="${!!hecho}" title="${esc(tit)}"><span class="k">${hecho ? ICON.check : i + 1}</span><span class="t">${esc(s.t)}</span></button>`;
  }).join('')}</div>`;
}

/* Flujo del pedido, como en el Excel: análisis → ajuste de carga → cubicaje → entregas (una por camión) → grupos.
   Se deduce del resumen que guarda el servidor ("flujo:<pedido>") y de las entregas del pedido. */
const FLUJO_ACCION = {analisis: 'Analizar pedido', ajuste: 'Revisar la carga', cubicaje: 'Cubicar', entregas: 'Crear entregas', grupos: 'Crear grupos'};
function flujoDe(p){
  const fl = Store.get('config', 'flujo:' + p.pedido) || {};
  const an = fl.analisis || null, cb = fl.cubicaje || null;
  const ents = entregasDe(p.pedido).filter(e => !e.anulada);
  const camiones = cb ? cb.camiones : 0, conGrupo = ents.filter(e => e.grupo).length;
  const desact = !!an && (an.cliente || '').toUpperCase() !== (p.cliente || '').toUpperCase();   // se cambió el cliente después de analizar
  const lim = an ? an.limitadas : 0;
  const hecho = {
    analisis: !!an && !desact,
    ajuste: !!an && !desact && (!!cb || lim === 0),
    cubicaje: !!cb && camiones > 0,
    entregas: ents.length > 0 && (!camiones || ents.length >= camiones),
    grupos: ents.length > 0 && conGrupo === ents.length,
  };
  // un pedido que ya tiene entregas pero nunca se analizó aquí no necesita pasar por los primeros pasos
  const omitido = !an && ents.length > 0 ? new Set(['analisis', 'ajuste', 'cubicaje']) : new Set();
  const det = {
    analisis: desact ? `era de ${an.cliente}` : an ? `${an.filas} productos` : 'pendiente',
    ajuste: !an ? '' : lim ? `${lim} limitados por el plan${an.excedidas ? ` · ${an.excedidas} autorizados` : ''}` : 'sin límites',
    cubicaje: cb ? `${camiones} ${camiones === 1 ? 'camión' : 'camiones'}` : '',
    entregas: camiones ? `${ents.length} de ${camiones}` : ents.length ? String(ents.length) : '',
    grupos: ents.length ? `${conGrupo} de ${ents.length}` : '',
  };
  const pasos = ['analisis', 'ajuste', 'cubicaje', 'entregas', 'grupos'].map(k => ({
    k, t: {analisis: 'Análisis', ajuste: 'Ajuste de carga', cubicaje: 'Cubicaje', entregas: 'Entregas', grupos: 'Grupos'}[k],
    hecho: hecho[k], omit: omitido.has(k), det: det[k]}));
  const sig = pasos.find(x => !x.hecho && !x.omit) || null;
  if (sig) sig.sig = true;
  const tab = {analisis: 'analisis', ajuste: 'analisis', cubicaje: 'cubicaje', entregas: ents.length ? 'entregas' : 'cubicaje', grupos: 'grupos'};
  return {pasos, sig, an, cb, ents, enPlataforma: !!an, desact, tabSig: sig ? tab[sig.k] : (ents.length ? 'entregas' : 'analisis'), tab};
}

/* Qué falta hacer en un pedido: el siguiente paso del flujo o, si ya está encaminado, el del camión con la cita más próxima */
function proximaAccion(p){
  const f = flujoDe(p);
  if (f.enPlataforma && f.sig){
    const extra = f.sig.k === 'ajuste' ? ` (${f.an.limitadas} limitados)` : f.sig.k === 'analisis' ? ' (cambió el cliente)' : '';
    return {txt: FLUJO_ACCION[f.sig.k] + extra, tono: 'warn'};
  }
  const gs = gruposDe(p.pedido).filter(g => g.next);
  if (!gs.length){
    const ents = entregasDe(p.pedido).filter(e => !e.anulada);
    if (!ents.length) return {txt: 'Sin entregas', tono: ''};
    return {txt: 'Todo entregado', tono: 'ok'};
  }
  const g = gs[0];
  const cita = g.cita && g.cita.fecha ? ` · cita ${fmtFecha(g.cita.fecha).slice(0, 5)}` : '';
  return {txt: `Falta ${g.next.t}${cita}`, tono: 'warn'};
}

/* La librería de Excel pesa 880 KB y casi nunca se usa: se carga la primera vez que hace falta */
let _xlsxCarga;
function asegurarXLSX(){
  if (window.XLSX) return Promise.resolve(true);
  if (_xlsxCarga) return _xlsxCarga;
  const probar = src => new Promise(ok => { const s = document.createElement('script'); s.src = src; s.onload = () => ok(true); s.onerror = () => ok(false); document.head.appendChild(s); });
  _xlsxCarga = probar('/vendor/xlsx.full.min.js')
    .then(ok => ok || probar('https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js'))
    .then(ok => { if (!ok) _xlsxCarga = null; return ok; });
  return _xlsxCarga;
}
