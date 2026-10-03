/* Puente con el visor 3D (iframe).
   El visor se abre una sola vez y la página le manda cada cálculo nuevo por postMessage: no se
   recarga la página, ni las librerías, ni se pierde la cámara. Un iframe lleva data-visor:
     "libre"        → resultado del cubicador   (UI.cub)
     "pedido:<n°>"  → cubicaje de un pedido     (UI.cubicaje[n°]) */
const Visor = {
  listos: new WeakSet(),       // iframes que ya avisaron "listo"
  enviado: new WeakMap(),      // último dato enviado a cada iframe
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
      if (!json || this.enviado.get(f) === json) continue;
      this.enviado.set(f, json);
      f.contentWindow.postMessage({tipo: 'od-visor-datos', datos: json}, location.origin);
      const libre = f.dataset.visor === 'libre';
      this.camion(libre ? UI.cubCam : (UI.pedCam[f.dataset.visor.slice(7)] || 0), f);
      if (libre) this.mandar({tipo: 'od-visor-filtro', cod: UI.cubFiltro || null}, f);       // el visor limpia su filtro al recibir datos
    }
  },
  mandar(msg, f){ (f ? [f] : this.frames()).forEach(x => this.listos.has(x) && x.contentWindow && x.contentWindow.postMessage(msg, location.origin)); },
  camion(idx, f){ this.mandar({tipo: 'od-visor-camion', idx: idx || 0}, f); },
  filtro(cod){ this.mandar({tipo: 'od-visor-filtro', cod: cod || null}); },
  pdf(soloActual){ this.mandar({tipo: 'od-visor-pdf', soloActual: !!soloActual}); },
};
window.addEventListener('message', ev => {
  const m = ev.data;
  if (ev.origin !== location.origin || !m || m.tipo !== 'od-visor-listo') return;
  for (const f of Visor.frames()) if (f.contentWindow === ev.source){ Visor.listos.add(f); Visor.enviado.delete(f); }
  Visor.sincronizar();
});

/* Un camión vacío para que el visor muestre algo antes de la primera carga */
const MEDIDAS_VISTA = {rampla: ['Rampla 53', 1540, 245, 230], camion50: ['Camión 50', 620, 244, 230]};
function camionVacioJSON(vista){
  const [tipo, L, W, H] = MEDIDAS_VISTA[vista] || MEDIDAS_VISTA.rampla;
  return JSON.stringify({titulo: 'Order Desk - Cubicaje B2B', esSda: false, pedido: '', camiones: [
    {idx: 1, tipo, L, W, H, volTot: 0, volCap: +(L * W * H / 1e6).toFixed(2), ocupVol: 0, pesoTot: 0, items: [], cajas: [], pallets: []}]});
}
