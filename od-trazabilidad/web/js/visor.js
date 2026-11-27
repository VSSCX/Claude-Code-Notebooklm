/* Puente con el visor 3D (iframe).
   El visor se abre una sola vez y la página le manda cada cálculo nuevo por postMessage: no se
   recarga la página, ni las librerías, ni se pierde la cámara. Un iframe lleva data-visor:
     "libre"        → resultado del cubicador   (UI.cub)
     "pedido:<n°>"  → cubicaje de un pedido     (UI.cubicaje[n°]) */
const Visor = {
  /* Qué se lee sobre las cajas del 3D: la descripción del producto o su letra. La letra sirve cuando el PDF se imprime
     en blanco y negro, donde los colores no distinguen un producto de otro. Queda recordado en este equipo. */
  etiqueta: (() => { try { return localStorage.getItem('od_etiqueta') === 'letra' ? 'letra' : 'desc'; } catch(e){ return 'desc'; } })(),
  etiquetar(modo){
    this.etiqueta = modo === 'letra' ? 'letra' : 'desc';
    try { localStorage.setItem('od_etiqueta', this.etiqueta); } catch(e){ /* sin almacenamiento: vale para esta sesión */ }
    this.mandar({tipo: 'od-visor-etiqueta', letra: this.etiqueta === 'letra'});
  },
  /* Color de las cajas cuando hay sucursales (flujo predistribuido): por sucursal (lo que el visor hace de entrada) o por producto. */
  color: (() => { try { return localStorage.getItem('od_color') === 'prod' ? 'prod' : 'suc'; } catch(e){ return 'suc'; } })(),
  colorear(modo){
    this.color = modo === 'prod' ? 'prod' : 'suc';
    try { localStorage.setItem('od_color', this.color); } catch(e){ /* vale para esta sesión */ }
    this.mandar({tipo: 'od-visor-color', suc: this.color === 'suc'});
  },
  /* Vista libre (el ojo): la cámara gira por completo, se mueve y entra al camión. Dura lo que la sesión. */
  libre: false,
  verLibre(on){ this.libre = !!on; this.mandar({tipo: 'od-visor-libre', on: this.libre}); },
  listos: new WeakSet(),       // iframes que ya avisaron "listo"
  enviado: new WeakMap(),      // último dato enviado a cada iframe
  palEnv: new WeakMap(),       // último pallet resaltado enviado a cada iframe
  edit: {},                   // por visor: el último ajuste a mano, hasta que el servidor lo confirma
  pend: {},                   // por visor: ajuste que llegó mientras se guardaba el anterior
  subiendo: {},
  editEnv: new WeakMap(),     // último permiso de edición enviado a cada iframe
  leyendas: {},               // por visor: qué color lleva cada sucursal del camión que muestra (lo avisa el propio visor)
  frames(){ return [...document.querySelectorAll('iframe[data-visor]')]; },
  filtroSuc(clave, nombre, activa){ this.mandar({tipo: 'od-visor-filtro', suc: activa ? null : nombre}, this.frames().find(x => x.dataset.visor === clave)); },
  datos(f){
    const k = f.dataset.visor;
    if (this.edit[k]) return this.edit[k];                 // lo que el analista dejó en el 3D manda mientras se guarda
    if (k === 'libre') return (UI.cub && UI.cub.visor_json) || camionVacioJSON((UI.cubIn || {}).vista);
    if (k.startsWith('pedido:')){ const cb = UI.cubicaje[k.slice(7)]; return cb && cb.visor_json; }
    if (k.startsWith('entrega:')){ const d = UI.cubEnt[k.slice(8)]; return d && d.visor_json; }
    return null;
  },
  /* Manda al visor lo que no tiene todavía. Se llama después de cada render. */
  sincronizar(){
    for (const f of this.frames()){
      if (!this.listos.has(f) || !f.contentWindow) continue;
      const json = this.datos(f);
      this.resaltarPallet(f);
      this.permitirEdicion(f);
      if (!json || this.enviado.get(f) === json) continue;
      this.enviado.set(f, json);
      f.contentWindow.postMessage({tipo: 'od-visor-datos', datos: json}, location.origin);
      this.mandar({tipo: 'od-visor-etiqueta', letra: this.etiqueta === 'letra'}, f);
      this.mandar({tipo: 'od-visor-color', suc: this.color === 'suc'}, f);
      if (this.libre) this.mandar({tipo: 'od-visor-libre', on: true}, f);
      const libre = f.dataset.visor === 'libre';
      this.camion(libre ? UI.cubCam : f.dataset.visor.startsWith('entrega:') ? 0 : (UI.pedCam[f.dataset.visor.slice(7)] || 0), f);
      if (libre) this.mandar({tipo: 'od-visor-filtro', cod: UI.cubFiltro || null}, f);       // el visor limpia su filtro al recibir datos
    }
  },
  /* "Pallets en el camión": el visor resalta el pallet elegido. Solo se manda cuando cambia. */
  resaltarPallet(f){
    if (f.dataset.visor !== 'libre') return;
    const inp = UI.cubIn || {}, c = UI.cub || {};
    const idx = inp.vista === 'pallet' && inp.pallet_camion ? (c.pallet_visto || null) : null;
    if (this.palEnv.get(f) === idx) return;
    this.palEnv.set(f, idx);
    this.mandar({tipo: 'od-visor-pallet', idx}, f);
  },
  /* Por qué un 3D no se puede ajustar ('' = se puede). El visor lo muestra para que el analista sepa qué pasa. */
  motivoNoEditable(f){
    const k = f.dataset.visor;
    if (k === 'libre'){
      const c = UI.cub || {};
      if (!(c.camiones && c.camiones.length)) return 'todavía no hay carga cubicada';
      if ((UI.cubIn || {}).vista === 'pallet') return 'un pallet suelto no se ajusta; cambia a Rampla o Camión';
      return UI.cubCalculando ? 'se está calculando' : '';
    }
    if (k.startsWith('pedido:')){
      const cb = UI.cubicaje[k.slice(7)];
      if (!(cb && cb.camiones)) return 'el pedido no está cubicado';
      if (cb.conjunto) return 'es un cubicaje conjunto';
      return cb.recalculando ? 'se está recalculando' : '';
    }
    return 'la entrega ya está creada';
  },
  editable(f){ return !this.motivoNoEditable(f); },
  permitirEdicion(f){
    const motivo = this.motivoNoEditable(f), on = !motivo, v = on ? '1' : '0:' + motivo;
    if (this.editEnv.get(f) === v) return;
    this.editEnv.set(f, v);
    this.mandar({tipo: 'od-visor-editable', on, motivo}, f);
    if (on) this.mandar({tipo: 'od-visor-vehiculos', lista: ['rampla', 'camion50'].map(v => { const [tipo, L, W, H] = medidasVista(v); return {tipo, L, W, H}; })}, f);
  },
  /* El analista movió cajas en el 3D: se guarda en el servidor (que rehace las cargas de cada camión). Un solo guardado a la vez;
     si llega otro cambio mientras tanto, se guarda después con lo último. */
  ajustar(f, datos){
    const k = f.dataset.visor;
    this.edit[k] = datos; this.enviado.set(f, datos);
    if (this.subiendo[k]){ this.pend[k] = datos; return; }
    this.guardar(f, k, datos);
  },
  async guardar(f, k, datos){
    this.subiendo[k] = true;
    let sig = datos;
    while (sig){
      this.pend[k] = null;
      try {
        const libre = k === 'libre', n = libre ? '' : k.slice(7);
        const doc = await api('POST', libre ? '/cubicaje-libre/ajustes' : `/cubicaje/${encodeURIComponent(n)}/ajustes`, {visor: sig});
        if (libre) UI.cub = {...UI.cub, ...doc}; else UI.cubicaje[n] = {...UI.cubicaje[n], ...doc};
        if (!this.pend[k]){ delete this.edit[k]; this.enviado.set(f, sig); }
      } catch(e){
        toast(e.message);
        this.pend[k] = null; delete this.edit[k]; this.enviado.delete(f);       // el visor vuelve a lo último guardado
      }
      sig = this.pend[k];
    }
    this.subiendo[k] = false;
    render();
  },
  mandar(msg, f){ (f ? [f] : this.frames()).forEach(x => this.listos.has(x) && x.contentWindow && x.contentWindow.postMessage(msg, location.origin)); },
  camion(idx, f){ this.mandar({tipo: 'od-visor-camion', idx: idx || 0}, f); },
  filtro(cod){ this.mandar({tipo: 'od-visor-filtro', cod: cod || null}); },
  pdf(soloActual){ this.mandar({tipo: 'od-visor-pdf', soloActual: !!soloActual}); },
};
window.addEventListener('message', ev => {
  const m = ev.data;
  if (ev.origin === location.origin && m && m.tipo === 'od-visor-leyenda'){          // colores por sucursal del camión que se ve
    const f = Visor.frames().find(x => x.contentWindow === ev.source);
    const k = f && f.dataset.visor, s = JSON.stringify(m);
    if (k && Visor.leyendas[k] !== s){ Visor.leyendas[k] = s; render(); }
    return;
  }
  if (ev.origin === location.origin && m && m.tipo === 'od-visor-editado' && typeof m.datos === 'string'){
    const f = Visor.frames().find(x => x.contentWindow === ev.source);
    if (f && Visor.editable(f)) Visor.ajustar(f, m.datos);
    return;
  }
  if (ev.origin === location.origin && m && m.tipo === 'od-visor-camion-actual'){          // el analista cambió de camión dentro del 3D
    const f = Visor.frames().find(x => x.contentWindow === ev.source), k = f && f.dataset.visor, i = +m.idx || 0;
    if (k === 'libre' && UI.cubCam !== i){ UI.cubCam = i; render(); }
    else if (k && k.startsWith('pedido:') && (UI.pedCam[k.slice(7)] || 0) !== i){ UI.pedCam[k.slice(7)] = i; render(); }
    return;
  }
  if (ev.origin !== location.origin || !m || m.tipo !== 'od-visor-listo') return;
  for (const f of Visor.frames()) if (f.contentWindow === ev.source){ Visor.listos.add(f); Visor.enviado.delete(f); Visor.palEnv.delete(f); Visor.editEnv.delete(f); }
  Visor.sincronizar();
});

/* Un camión vacío para que el visor muestre algo antes de la primera carga */
const NOMBRE_VISTA = {rampla: 'Rampla 53', camion50: 'Camión 50'};
function medidasVista(vista){                                  // las de Configuración; si aún no cargaron, las de fábrica
  const v = vista in NOMBRE_VISTA ? vista : 'rampla', c = ((UI.ajustes || {}).camiones || {})[v] || (v === 'rampla' ? {largo: 1540, ancho: 245, alto: 235} : {largo: 620, ancho: 244, alto: 230});
  return [NOMBRE_VISTA[v], c.largo, c.ancho, c.alto];
}
function camionVacioJSON(vista){
  const [tipo, L, W, H] = medidasVista(vista);
  return JSON.stringify({titulo: 'Order Desk - Cubicaje B2B', esSda: false, pedido: '', camiones: [
    {idx: 1, tipo, L, W, H, volTot: 0, volCap: +(L * W * H / 1e6).toFixed(2), ocupVol: 0, pesoTot: 0, items: [], cajas: [], pallets: []}]});
}

/* Interruptor pequeño sobre el visor: "Cajas [Descripción | Letra]". El color (producto / sucursal) va en la barra de arriba, ver barraColor(). */
function herramientasVisor(visorJson){
  const e = Visor.etiqueta;
  return `<div class="vis-tools" role="group" aria-label="Texto sobre las cajas"><span>Cajas</span><div class="seg sm">
    <button type="button" data-vis-etiqueta="desc" aria-pressed="${e === 'desc'}">Descripción</button>
    <button type="button" data-vis-etiqueta="letra" aria-pressed="${e === 'letra'}" title="La letra de cada producto se lee en una impresión en blanco y negro">Letra</button></div>
    <button type="button" class="vis-ojo" data-vis-libre aria-pressed="${Visor.libre}" aria-label="Vista libre del camión" title="Vista libre: gira por completo, mueve con clic derecho o Shift y acércate hasta entrar al camión">${ICON.ojo}</button></div>`;
}
/* Barra sobre el visor: con sucursales (flujo predistribuido) permite elegir el color de las cajas, por producto o por sucursal,
   y dice qué color es cada sucursal del camión que se ve (clic: aísla esa sucursal en el 3D). `clave` es el data-visor del iframe. */
function barraColor(visorJson, clave){
  if (!/"suc":"[^"]/.test(visorJson || '')) return '';
  const col = Visor.color;
  let ley = null; try { ley = Visor.leyendas[clave] ? JSON.parse(Visor.leyendas[clave]) : null; } catch(e){ ley = null; }
  const chips = ley && col === 'suc' ? `<ul class="vis-ley-l">${ley.suc.map(s => `<li><button type="button" class="vis-suc" data-vis-suc="${esc(s.n)}" data-vis-clave="${esc(clave)}" aria-pressed="${ley.filtro === s.n}"
        title="${ley.filtro === s.n ? 'Volver a ver todas las sucursales' : 'Aislar esta sucursal en el 3D'}"><i class="sw" style="background:${esc(s.c)};color:${tintaSobre(s.c)}">${esc(s.l)}</i><span class="nm">${esc(s.n)}</span><span class="qt num">${s.p ? `${fmt(s.p)} pal. · ` : ''}${fmt(s.k)} cajas</span></button></li>`).join('')}</ul>` : '';
  return `<div class="vis-ley" role="group" aria-label="Color de las cajas"><div class="vis-ley-c"><span>Color de las cajas</span>
      <div class="seg sm"><button type="button" data-vis-color="prod" aria-pressed="${col === 'prod'}" title="Cada producto con su color">Por producto</button>
      <button type="button" data-vis-color="suc" aria-pressed="${col === 'suc'}" title="Cada sucursal con su color: lo que se distingue en un predistribuido">Por sucursal</button></div></div>${chips}</div>`;
}
document.addEventListener('click', ev => {
  const sc = ev.target.closest && ev.target.closest('[data-vis-suc]');
  if (sc){ Visor.filtroSuc(sc.dataset.visClave, sc.dataset.visSuc, sc.getAttribute('aria-pressed') === 'true'); return; }
  const b = ev.target.closest && ev.target.closest('[data-vis-etiqueta]');
  if (b){ Visor.etiquetar(b.dataset.visEtiqueta); render(); return; }
  const k = ev.target.closest && ev.target.closest('[data-vis-color]');
  if (k){ Visor.colorear(k.dataset.visColor); render(); return; }
  if (ev.target.closest && ev.target.closest('[data-vis-libre]')){ Visor.verLibre(!Visor.libre); render(); }
});

/* Aviso sobre el visor cuando el 3D tiene ajustes del analista, con la salida: volver a lo que sugirió el motor. */
function avisoAjustado(doc, accion, nota = ''){
  if (!doc || !doc.ajustado) return '';
  const a = doc.ajustado;
  return `<div class="aviso info" role="status"><div class="aviso-cuerpo"><b>Ajustado a mano en el 3D.</b>
    <span class="small">${fmt(a.cajas_ahora)} cajas ahora${a.cajas_antes !== a.cajas_ahora ? ` (el motor había sugerido ${fmt(a.cajas_antes)})` : ''}. ${nota || 'Las cargas de cada camión salen de lo que dejaste en el 3D.'}</span></div>
    <button class="btn sm" data-act="${accion}" title="Descarta tus ajustes y deja lo que sugiere el motor">Volver a la sugerencia</button></div>`;
}
