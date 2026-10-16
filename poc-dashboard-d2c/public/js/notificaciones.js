/* notificaciones.js: avisos (toast) y centro de notificaciones (campana) de pedidos nuevos. */
/* ============ avisos de pedidos nuevos ============ */
function toast(titulo,sub){   // aviso arriba a la derecha, como las notificaciones de Ant: se cierra solo o con la X
  const box=$('#avisos');
  while(box.children.length>=3)box.firstElementChild.remove();
  const t=document.createElement('div');t.className='aviso';t.setAttribute('role','status');
  t.innerHTML=`<span class="tp">${ico('paquete',18)}</span><div class="tx"><b>${esc(titulo)}</b>${sub?`<span>${esc(sub)}</span>`:''}</div><button class="cierra" aria-label="Cerrar aviso">${ico('x',14)}</button>`;
  box.appendChild(t);
  const cerrar=()=>{t.classList.add('sale');setTimeout(()=>t.remove(),200);};
  t.querySelector('.cierra').addEventListener('click',cerrar);
  setTimeout(cerrar,7000);
}

/* ============ centro de notificaciones (campana): un pedido nuevo en VTEX suma una notificación sin leer ============ */
const NOTIF_MAX=50;
const rtf=new Intl.RelativeTimeFormat('es-CL',{numeric:'auto'});
function cargarNotifs(){try{const a=JSON.parse(leer('notifs')||'[]');return Array.isArray(a)?a.filter(n=>n&&n.seq).slice(0,NOTIF_MAX):[];}catch(e){return [];}}
S.notifs=cargarNotifs();S.np=false;
const sinLeer=()=>S.notifs.filter(n=>!n.leida).length;
const guardarNotifs=()=>guardar('notifs',JSON.stringify(S.notifs.slice(0,NOTIF_MAX)));
function hace(t){const m=Math.floor((Date.now()-t)/60000);if(m<1)return 'ahora mismo';if(m<60)return rtf.format(-m,'minute');const h=Math.floor(m/60);return h<24?rtf.format(-h,'hour'):rtf.format(-Math.floor(h/24),'day');}
function renderNotif(){
  const n=sinLeer();
  const lista=S.notifs.length?`<ul class="pn-l">${S.notifs.map(x=>`<li><button class="pn-i ${x.leida?'':'nueva'}" data-notif-item="${esc(x.seq)}" title="Ver este pedido en el detalle"><span class="pn-ic">${ico('paquete',16)}</span><span class="pn-t"><b>Pedido ${esc(x.seq)}</b><span>${esc(x.canal||'VTEX')}, ${hace(x.t)}</span></span>${x.leida?'':'<span class="pn-pt" role="img" aria-label="Sin leer"></span>'}</button></li>`).join('')}</ul>`
    :`<div class="pn-vacio">${ico('vacio',32)}<b>Sin notificaciones</b><span>Aquí aparecerán los pedidos nuevos que lleguen desde VTEX.</span></div>`;
  const panel=S.np?`<div class="panel-notif" id="panel-notif" role="dialog" aria-label="Notificaciones" tabindex="-1"><div class="pn-h"><h2>Notificaciones</h2><button class="link" data-leer-todas ${n?'':'disabled'}>${ico('leidas',16)}Marcar todas como leídas</button></div>${lista}<div class="pn-f">Se guardan los últimos ${NOTIF_MAX} pedidos nuevos en este navegador.</div></div>`:'';
  morph($('#notif'),`<button class="campana" data-notif aria-label="Notificaciones${n?`, ${n} sin leer`:''}" aria-haspopup="dialog" aria-expanded="${S.np}"${S.np?' aria-controls="panel-notif"':''}>${ico('campana',20)}${n?`<span class="ins">${n>99?'99+':n}</span>`:''}</button>${panel}`);
}
function nuevasNotifs(nuevas){
  nuevas.forEach(x=>S.notifs.unshift({seq:String(x.seq),canal:x.canal||'',t:Date.now(),leida:false}));
  S.notifs=S.notifs.slice(0,NOTIF_MAX);guardarNotifs();renderNotif();
  const b=$('#notif .campana');if(b){b.classList.remove('suena');void b.offsetWidth;b.classList.add('suena');}
  const a=$('#anuncio');a.textContent=`${nuevas.length} pedido${nuevas.length>1?'s':''} nuevo${nuevas.length>1?'s':''} en VTEX. ${sinLeer()} sin leer.`;
}
function cerrarNotif(devolverFoco){if(!S.np)return;S.np=false;renderNotif();if(devolverFoco){const b=$('#notif .campana');if(b)b.focus();}}
function abrirPedidoNotif(seq){
  const x=S.notifs.find(n=>n.seq===seq);if(x)x.leida=true;guardarNotifs();cerrarNotif(true);
  S.filtros.buscar=seq;renderSlicers();   // el detalle se filtra por ese Sequence: la búsqueda ignora alcance y bodega
  if(S.view!=='pedidos')irA('pedidos');else cargar();
  abrirPedido(seq);
}
function avisarLlegadas(j){
  const ll=j.llegadas||[]; const nuevas=ll.filter(x=>!S.vistos.has(x.seq));
  if(S.vistosInit&&nuevas.length){
    const n=nuevas.length,p=nuevas[0];
    toast(`${n} pedido${n>1?'s':''} nuevo${n>1?'s':''} en VTEX`,`${p.canal}, Sequence ${p.seq}${n>1?` y ${n-1} más`:''}`);
    nuevasNotifs(nuevas);
  }
  ll.forEach(x=>S.vistos.add(x.seq)); S.vistosInit=true;
}

