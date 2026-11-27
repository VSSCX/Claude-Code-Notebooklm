/* Centro de alertas: la campanita del riel.
   Todo lo que antes salía como un recuadro arriba o un aviso que se iba solo queda aquí, clasificado en tres niveles:
     Urgente (rojo)   algo falló y hay que actuar          Alerta (amarillo)  terminó con reservas o falta algo
     Aceptado (verde) se hizo bien
   Se avisa con un toast breve en la esquina; el historial se guarda en este equipo (últimos 14 días). */
const Alertas = {
  MAX: 60, DIAS: 14, CLAVE: 'od_alertas',
  NIVELES: {
    err:  {txt: 'Urgente',  icono: 'urgente',  ms: 10000},
    warn: {txt: 'Alerta',   icono: 'alerta',   ms: 6500},
    ok:   {txt: 'Aceptado', icono: 'aceptado', ms: 3200},
  },
  lista: [], abierto: false, filtro: 'todas',

  cargar(){
    try {
      const corte = Date.now() - this.DIAS * 864e5;
      this.lista = (JSON.parse(localStorage.getItem(this.CLAVE) || '[]') || []).filter(a => a && a.at > corte && this.NIVELES[a.nivel]).slice(0, this.MAX);
    } catch(e){ this.lista = []; }
  },
  guardar(){ try { localStorage.setItem(this.CLAVE, JSON.stringify(this.lista)); } catch(e){ /* sin almacenamiento: vale para esta sesión */ } },

  /* Los avisos viejos hablaban de «error», «warn» e «info»: info trae reservas (p. ej. filas que no se cargaron), va como Alerta */
  nivelDe(tipo){ return tipo === 'error' || tipo === 'err' ? 'err' : tipo === 'warn' || tipo === 'info' ? 'warn' : 'ok'; },
  inferir(msg){
    const m = String(msg || '');
    if (/^(error|no se pudo|no se encontr|no hay conexi|sin conexi|no se puede|falló|fallo)/i.test(m)) return 'err';
    if (/(falta|ingresa|indica|elige|selecciona|escribe|debe |supera|ya existe|no tiene|no alcanz|inválid|revisa|intenta de nuevo)/i.test(m)) return 'warn';
    return 'ok';
  },

  registrar({nivel, titulo, detalle = '', pasos = []}){
    const ahora = Date.now(), previa = this.lista[0];
    if (previa && previa.nivel === nivel && previa.titulo === titulo && ahora - previa.at < 4000){   // el mismo aviso repetido: se cuenta, no se duplica
      previa.veces = (previa.veces || 1) + 1; previa.at = ahora; previa.leida = this.abierto;
    } else {
      this.lista.unshift({id: ahora + '-' + Math.random().toString(16).slice(2, 6), nivel, titulo, detalle, pasos, at: ahora, leida: this.abierto, veces: 1});
      this.lista = this.lista.slice(0, this.MAX);
    }
    this.guardar(); this.pintar(); this.suena(nivel);
    return this.lista[0];
  },
  agregar(tipo, titulo, detalle, pasos){
    const nivel = this.nivelDe(tipo);
    this.registrar({nivel, titulo, detalle: detalle || '', pasos: pasos || []});
    this.mostrar(nivel, titulo, null, !!(detalle || (pasos || []).length));
  },
  toast(msg, accion, nivel){
    const n = nivel || this.inferir(msg);
    this.registrar({nivel: n, titulo: String(msg)});
    this.mostrar(n, msg, accion, false);
  },

  /* El toast: una línea en la esquina, con el icono del nivel. No tapa el trabajo y se va solo; lo urgente dura más y ofrece abrir el detalle. */
  mostrar(nivel, texto, accion, conDetalle){
    const t = $('#toast'), niv = this.NIVELES[nivel];
    t.className = 'nivel-' + nivel;
    t.replaceChildren();
    const ico = document.createElement('span'); ico.className = 't-ico'; ico.innerHTML = ICON[niv.icono];
    const txt = document.createElement('span'); txt.className = 't-txt'; txt.textContent = texto;
    t.append(ico, txt);
    const boton = (etq, fn) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'toast-acc'; b.textContent = etq; b.onclick = fn; t.append(b); };
    if (accion) boton(accion.texto, () => { t.classList.remove('on'); accion.fn(); });
    else if (nivel !== 'ok' || conDetalle) boton('Ver', () => { t.classList.remove('on'); this.abrir(); });
    t.classList.toggle('con-acc', t.querySelector('.toast-acc') !== null);
    t.classList.add('on');
    clearTimeout(this._t);
    const dura = accion ? 7000 : niv.ms;
    this._t = setTimeout(() => t.classList.remove('on'), dura);
    t.onpointerenter = () => clearTimeout(this._t);                                    // si lo estás leyendo, no se va
    t.onpointerleave = () => { clearTimeout(this._t); this._t = setTimeout(() => t.classList.remove('on'), 2000); };
  },

  /* Campanita: el número de alertas sin leer, con el color de la más grave */
  sinLeer(){ return this.lista.filter(a => !a.leida); },
  pintar(){
    const b = $('#al-bell'); if (!b) return;
    const nl = this.sinLeer(), peor = nl.some(a => a.nivel === 'err') ? 'err' : nl.some(a => a.nivel === 'warn') ? 'warn' : nl.length ? 'ok' : '';
    const urg = nl.filter(a => a.nivel === 'err').length;
    b.setAttribute('aria-label', nl.length ? `Alertas: ${nl.length} sin leer${urg ? `, ${urg} urgente${urg === 1 ? '' : 's'}` : ''}` : 'Alertas');
    b.setAttribute('aria-expanded', String(this.abierto));
    b.innerHTML = ICON.campana + (nl.length ? `<span class="al-badge nivel-${peor}">${nl.length > 9 ? '9+' : nl.length}</span>` : '');
    b.dataset.peor = peor;
    if (this.abierto) this.pintarPanel();
  },
  suena(nivel){
    const b = $('#al-bell'); if (!b || nivel === 'ok' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    b.classList.remove('suena'); void b.offsetWidth; b.classList.add('suena');
  },

  hace(ms){
    const s = Math.max(0, (Date.now() - ms) / 1000);
    if (s < 45) return 'ahora';
    if (s < 3600) return `hace ${Math.round(s / 60)} min`;
    if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
    const d = new Date(ms); return `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')} ${d.toTimeString().slice(0, 5)}`;
  },
  cuenta(n){ return this.lista.filter(a => a.nivel === n).length; },
  pintarPanel(){
    const el = $('#alertas'); if (!el) return;
    const vis = this.filtro === 'todas' ? this.lista : this.lista.filter(a => a.nivel === this.filtro);
    const filtros = [['todas', 'Todas', this.lista.length], ['err', 'Urgente', this.cuenta('err')], ['warn', 'Alerta', this.cuenta('warn')], ['ok', 'Aceptado', this.cuenta('ok')]];
    const vacio = this.lista.length
      ? `<p class="al-vacio">No hay alertas en este nivel.</p>`
      : `<div class="al-vacio"><b>Todo tranquilo</b><span>Aquí queda el resultado de lo que hagas en SAP, los cubicajes y las cargas: lo urgente en rojo, las alertas en amarillo y lo que salió bien en verde.</span></div>`;
    pintar(el, `
      <header class="al-h"><h2>Alertas</h2>
        <button type="button" class="btn quiet sm" data-al="leer" ${this.sinLeer().length ? '' : 'disabled'}>Marcar leídas</button>
        <button type="button" class="btn quiet sm" data-al="limpiar" ${this.lista.length ? '' : 'disabled'}>Limpiar</button>
        <button type="button" class="btn quiet sm icon" data-al="cerrar" aria-label="Cerrar las alertas">${ICON.x}</button></header>
      <div class="al-filtros" role="group" aria-label="Filtrar por nivel">${filtros.map(([k, t, n]) =>
        `<button type="button" class="al-filtro ${k === 'todas' ? '' : 'nivel-' + k}" data-al-filtro="${k}" aria-pressed="${this.filtro === k}">${k === 'todas' ? '' : '<i class="al-punto" aria-hidden="true"></i>'}${t}<span class="num">${n}</span></button>`).join('')}</div>
      <ul class="al-lista">${vis.length ? vis.map(a => `
        <li class="al-item nivel-${a.nivel} ${a.leida ? '' : 'nueva'}" data-k="al-${esc(a.id)}">
          <span class="al-ico" aria-hidden="true">${ICON[this.NIVELES[a.nivel].icono]}</span>
          <div class="al-cuerpo"><div class="al-tit"><span class="al-nivel">${this.NIVELES[a.nivel].txt}</span><b>${esc(a.titulo)}</b>${a.veces > 1 ? `<span class="al-veces num">×${a.veces}</span>` : ''}</div>
            ${a.detalle ? `<div class="al-det small">${esc(a.detalle)}</div>` : ''}
            ${(a.pasos || []).length ? `<ul class="al-pasos small">${a.pasos.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}
            <time class="al-hora small num">${esc(this.hace(a.at))}</time></div>
          <button type="button" class="btn quiet sm icon al-quitar" data-al-quitar="${esc(a.id)}" aria-label="Quitar esta alerta" title="Quitar">${ICON.x}</button>
        </li>`).join('') : `<li class="al-sin">${vacio}</li>`}</ul>`);
  },

  abrir(){
    if (this.abierto) return;
    this.abierto = true;
    const el = $('#alertas'); el.hidden = false; this.pintarPanel();
    el.classList.remove('entra'); void el.offsetWidth; el.classList.add('entra');
    // lo que estaba sin leer se marca al verlo; las filas conservan su marca un momento para que se note qué era nuevo
    setTimeout(() => { if (this.abierto){ this.lista.forEach(a => { a.leida = true; }); this.guardar(); this.pintar(); } }, 1800);
    this.pintar();
    const cerrar = el.querySelector('[data-al="cerrar"]'); if (cerrar) cerrar.focus({preventScroll: true});
  },
  cerrar(devolverFoco = true){
    if (!this.abierto) return;
    this.abierto = false; $('#alertas').hidden = true; this.pintar();
    if (devolverFoco){ const b = $('#al-bell'); if (b) b.focus({preventScroll: true}); }
  },
  alternar(){ this.abierto ? this.cerrar() : this.abrir(); },
};
Alertas.cargar();
document.addEventListener('DOMContentLoaded', () => Alertas.pintar());
document.addEventListener('click', ev => {
  const t = ev.target.closest && ev.target.closest('[data-al],[data-al-filtro],[data-al-quitar]');
  if (t){
    if (t.dataset.al === 'alternar') Alertas.alternar();
    else if (t.dataset.al === 'cerrar') Alertas.cerrar();
    else if (t.dataset.al === 'leer'){ Alertas.lista.forEach(a => { a.leida = true; }); Alertas.guardar(); Alertas.pintar(); }
    else if (t.dataset.al === 'limpiar'){ Alertas.lista = []; Alertas.guardar(); Alertas.pintar(); }
    else if (t.dataset.alFiltro){ Alertas.filtro = t.dataset.alFiltro; Alertas.pintarPanel(); }
    else if (t.dataset.alQuitar){ Alertas.lista = Alertas.lista.filter(a => a.id !== t.dataset.alQuitar); Alertas.guardar(); Alertas.pintar(); }
    return;
  }
  if (Alertas.abierto && !ev.target.closest('#alertas')) Alertas.cerrar(false);            // tocar fuera la cierra
});
document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && Alertas.abierto){ ev.stopPropagation(); Alertas.cerrar(); } }, true);
setInterval(() => { if (Alertas.abierto) Alertas.pintarPanel(); }, 30000);                    // «hace 5 min» sigue corriendo

/* Riel: un resalte que se desliza de un apartado al otro mientras pasas el puntero (solo con mouse) */
(function(){
  const nav = document.getElementById('nav'); if (!nav) return;
  nav.addEventListener('pointerover', ev => {
    if (ev.pointerType && ev.pointerType !== 'mouse') return;
    const it = ev.target.closest && ev.target.closest('.rail-item'); if (!it || getComputedStyle(nav).flexDirection === 'row') return;
    nav.style.setProperty('--hy', it.offsetTop + 'px'); nav.style.setProperty('--hh', it.offsetHeight + 'px'); nav.classList.add('hover');
  });
  nav.addEventListener('pointerleave', () => nav.classList.remove('hover'));
})();
