/* Cajón de detalle de un pedido: al hacer clic en un pedido se abre una pestaña lateral con sus líneas
   (código SAP, descripción, cantidad, precio y monto, lo que trae OrderItems). No cubre la pantalla:
   el tablero sigue visible a la izquierda. Se cierra con la X, con Esc o haciendo clic fuera. */
const peso=n=>n==null?'-':'$'+fmt(n);
const drNav=()=>{const l=S.data?S.data.detalle.map(r=>r.sequence):[],i=S.dr?l.indexOf(S.dr.seq):-1;return {l,i};};

function marcarFila(){
  document.querySelectorAll('tr[data-pv].sel').forEach(r=>r.classList.remove('sel'));
  if(S.dr)document.querySelectorAll('tr[data-pv="'+CSS.escape(S.dr.seq)+'"]').forEach(r=>r.classList.add('sel'));
}
function abrirPedido(seq,opener){
  cerrarChat(false);S.np&&cerrarNotif(false);
  seq=String(seq);
  S.dr={seq,estado:'cargando',data:null,opener:opener||(S.dr&&S.dr.opener)||document.activeElement,msg:''};
  renderDrawer(true);marcarFila();cargarPedido(seq);
}
async function cargarPedido(seq){
  try{
    const r=await fetch('/api/pedido/'+encodeURIComponent(seq)),j=await r.json();
    if(!S.dr||S.dr.seq!==seq)return;
    if(r.ok){S.dr.estado='ok';S.dr.data=j;}else{S.dr.estado='error';S.dr.msg=j.error||'No se pudo cargar el pedido.';}
  }catch(e){if(!S.dr||S.dr.seq!==seq)return;S.dr.estado='error';S.dr.msg='No hay conexión con el servidor.';}
  renderDrawer(false);
}
function cerrarPedido(devolverFoco=true){
  if(!S.dr)return;
  const op=S.dr.opener;S.dr=null;
  $('#drawer').replaceChildren();marcarFila();
  if(devolverFoco&&op&&op.isConnected)op.focus();
}
function irPedido(delta){
  const n=drNav(),j=n.i+delta;if(n.i<0||j<0||j>=n.l.length)return;
  const seq=n.l[j];abrirPedido(seq);
  const fila=document.getElementById('r'+seq);if(fila)fila.scrollIntoView({block:'nearest'});
}
function drLineas(d){
  const L=d.lineas||[];
  if(!L.length)return `<p class="dr-vacio">${ico('vacio',28)}<span>Este pedido no tiene líneas en OrderItems.</span></p>`;
  const sumaU=L.reduce((a,x)=>a+(+x.qty||0),0),sumaM=L.some(x=>x.monto!=null)?L.reduce((a,x)=>a+(+x.monto||0),0):null;
  const dif=sumaM!=null&&Math.abs(sumaM-d.pedido.monto)>1;
  return `<div class="dr-tw" tabindex="0" role="region" aria-label="Líneas del pedido"><table class="t dr-l"><thead><tr><th scope="col">Código SAP</th><th scope="col">Descripción</th><th scope="col" class="n">Cant.</th><th scope="col" class="n c-pre">Precio</th><th scope="col" class="n">Monto</th></tr></thead><tbody>
    ${L.map(x=>`<tr><td class="num" translate="no">${esc(x.sku||'-')}</td><td class="desc">${esc(x.descripcion||'-')}</td><td class="n">${fmt(x.qty)}</td><td class="n c-pre">${peso(x.precio)}</td><td class="n">${peso(x.monto)}</td></tr>`).join('')}
    </tbody><tfoot><tr class="fin"><td colspan="2">${L.length} línea${L.length>1?'s':''}</td><td class="n">${fmt(sumaU)}</td><td class="c-pre"></td><td class="n">${peso(sumaM)}</td></tr></tfoot></table></div>
    ${dif?`<p class="dr-nota">El total del pedido en VTEX es ${peso(d.pedido.monto)}: la diferencia puede ser despacho o descuentos que no están en las líneas.</p>`:''}`;
}
function renderDrawer(abrir){
  const el=$('#drawer');if(!S.dr){el.replaceChildren();return;}
  const d=S.dr,p=d.data&&d.data.pedido,n=drNav();
  let cuerpo;
  if(d.estado==='cargando')cuerpo=`<div class="dr-sk" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><div class="sr" role="status">Cargando el pedido…</div>`;
  else if(d.estado==='error')cuerpo=`<p class="dr-vacio">${ico('alerta',28)}<span>${esc(d.msg)}</span></p>`;
  else{
    const hecho=(k,v)=>`<div><dt>${k}</dt><dd>${v}</dd></div>`;
    cuerpo=`<div class="dr-tags">${pill(p.estado)}<span class="tag">${esc(p.status)}</span>${p.causa?`<span class="tag a">${esc(p.causa)}</span>`:''}</div>
      <dl class="dr-facts">${hecho('Cliente',esc(p.cliente)+' <small>'+esc(p.canal)+'</small>')}${hecho('Monto del pedido','<b>'+peso(p.monto)+'</b>')}${hecho('Creación',fd(p.fecha))}${hecho('Entrega est.',fd(p.sed))}
      ${hecho('SLA Type',esc(p.sla))}${hecho('Bodega',esc(p.warehouse))}${hecho('Pedido SAP','<span class="code">'+esc(p.pedido_sap||'Sin ingresar a SAP')+'</span>')}${hecho('Unidades',fmt(p.unidades))}</dl>
      <h3 class="dr-sec">Líneas del pedido</h3>${drLineas(d.data)}
      ${d.data.aviso?`<p class="aviso-inline">${ico('alerta',16)}<span>${esc(d.data.aviso)}</span></p>`:''}`;
  }
  const btn=(attr,lab,ic,off)=>`<button ${attr} aria-label="${lab}" title="${lab}" ${off?'disabled':''}>${ico(ic,16)}</button>`;
  const html=`<div class="dr-scrim" data-dr-cerrar></div>
    <div class="dr" id="dr" role="dialog" aria-labelledby="dr-tit" tabindex="-1">
      <div class="dr-h"><div class="dr-t"><span class="dr-ic">${ico('paquete',18)}</span><div><h2 id="dr-tit">Pedido <span class="code" translate="no">${esc(d.seq)}</span></h2><p>${p?esc(p.orden):'Detalle del pedido'}</p></div></div>
      <div class="dr-nav">${n.i>=0?btn('data-dr-prev','Pedido anterior de la tabla','arriba',n.i<=0)+btn('data-dr-next','Pedido siguiente de la tabla','abajo',n.i>=n.l.length-1):''}<button data-dr-cerrar id="dr-x" aria-label="Cerrar el detalle" title="Cerrar (Esc)">${ico('x',18)}</button></div></div>
      <div class="dr-b">${cuerpo}</div></div>`;
  const nuevo=!el.firstElementChild;
  morph(el,html);
  if(abrir||nuevo){const a=$('#dr');if(a)a.focus();}
}
document.addEventListener('click',ev=>{
  if(ev.target.closest('[data-dr-cerrar]')){cerrarPedido(true);return;}
  if(ev.target.closest('[data-dr-prev]')){irPedido(-1);return;}
  if(ev.target.closest('[data-dr-next]')){irPedido(1);return;}
});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&S.dr&&!S.np){ev.preventDefault();cerrarPedido(true);}});
