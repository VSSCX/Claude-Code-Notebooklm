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
  listos: new WeakSet(),       // iframes que ya avisaron "listo"
  enviado: new WeakMap(),      // último dato enviado a cada iframe
  palEnv: new WeakMap(),       // último pallet resaltado enviado a cada iframe
  frames(){ return [...document.querySelectorAll('iframe[data-visor]')]; },
  datos(f){
    const k = f.dataset.visor;
    if (k === 'libre') return (UI.cub && UI.cub.visor_json) || camionVacioJSON((UI.cubIn || {}).vista);
    if (k.startsWith('pedido:')){ const cb = UI.cubicaje[k.slice(7)]; return cb && cb.visor_json; }
    return null;
  },
  /* Manda al visor lo que no tiene todavía. Se llama después de cada render. */
  sincronizar(){
    for (const f of this.frames()){
      if (!this.listos.has(f) || !f.contentWindow) continue;
      const json = this.datos(f);
      this.resaltarPallet(f);
      if (!json || this.enviado.get(f) === json) continue;
      this.enviado.set(f, json);
      f.contentWindow.postMessage({tipo: 'od-visor-datos', datos: json}, location.origin);
      this.mandar({tipo: 'od-visor-etiqueta', letra: this.etiqueta === 'letra'}, f);
      const libre = f.dataset.visor === 'libre';
      this.camion(libre ? UI.cubCam : (UI.pedCam[f.dataset.visor.slice(7)] || 0), f);
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
  mandar(msg, f){ (f ? [f] : this.frames()).forEach(x => this.listos.has(x) && x.contentWindow && x.contentWindow.postMessage(msg, location.origin)); },
  camion(idx, f){ this.mandar({tipo: 'od-visor-camion', idx: idx || 0}, f); },
  filtro(cod){ this.mandar({tipo: 'od-visor-filtro', cod: cod || null}); },
  pdf(soloActual){ this.mandar({tipo: 'od-visor-pdf', soloActual: !!soloActual}); },
};
window.addEventListener('message', ev => {
  const m = ev.data;
  if (ev.origin !== location.origin || !m || m.tipo !== 'od-visor-listo') return;
  for (const f of Visor.frames()) if (f.contentWindow === ev.source){ Visor.listos.add(f); Visor.enviado.delete(f); Visor.palEnv.delete(f); }
  Visor.sincronizar();
});

/* Un camión vacío para que el visor muestre algo antes de la primera carga */
const MEDIDAS_VISTA = {rampla: ['Rampla 53', 1540, 245, 230], camion50: ['Camión 50', 620, 244, 230]};
function camionVacioJSON(vista){
  const [tipo, L, W, H] = MEDIDAS_VISTA[vista] || MEDIDAS_VISTA.rampla;
  return JSON.stringify({titulo: 'Order Desk - Cubicaje B2B', esSda: false, pedido: '', camiones: [
    {idx: 1, tipo, L, W, H, volTot: 0, volCap: +(L * W * H / 1e6).toFixed(2), ocupVol: 0, pesoTot: 0, items: [], cajas: [], pallets: []}]});
}

/* Interruptor pequeño sobre el visor: "Cajas  [Descripción | Letra]" */
function herramientasVisor(){
  const e = Visor.etiqueta;
  return `<div class="vis-tools" role="group" aria-label="Texto sobre las cajas"><span>Cajas</span><div class="seg sm">
    <button type="button" data-vis-etiqueta="desc" aria-pressed="${e === 'desc'}">Descripción</button>
    <button type="button" data-vis-etiqueta="letra" aria-pressed="${e === 'letra'}" title="La letra de cada producto se lee en una impresión en blanco y negro">Letra</button></div></div>`;
}
document.addEventListener('click', ev => {
  const b = ev.target.closest && ev.target.closest('[data-vis-etiqueta]');
  if (b){ Visor.etiquetar(b.dataset.visEtiqueta); render(); }
});
