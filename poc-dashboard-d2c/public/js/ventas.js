/* ventas.js: ventas por clasificación 2 de la maestra de productos (tarjeta de Pedidos VTEX) y su "zoom" por producto.
   Las ventas salen de las líneas de los pedidos, sin cancelados, y respetan todos los filtros del tablero. Se piden aparte
   (/api/ventas) para no demorar el resto de la pantalla: leer las líneas puede tardar la primera vez. */
S.vt={estado:'cargando',data:null,zoom:false,sel:null,prods:null,req:0,opener:null,cargandoProds:false};
const ventaTxt=n=>money(n);

async function pedirVentas(clasif){
  const body={...cuerpoFiltros()};if(clasif)body.zoom_clasif=clasif;
  const r=await fetch('/api/ventas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return r.json();
}
async function cargarVentas(){
  const id=++S.vt.req;
  try{
    const j=await pedirVentas(null);if(id!==S.vt.req)return;
    S.vt.estado=j.ok?'ok':'aviso';S.vt.data=j;
    if(S.vt.zoom&&S.vt.sel){   // el zoom abierto se actualiza con los filtros nuevos
      if(j.ok&&j.clasif.some(c=>c.nombre===S.vt.sel)){const p=await pedirVentas(S.vt.sel);if(id===S.vt.req)S.vt.prods=p.ok?p:null;}
      else{S.vt.sel=null;S.vt.prods=null;}
    }
  }catch(e){if(id!==S.vt.req)return;S.vt.estado='error';S.vt.data={motivo:'No se pudieron calcular las ventas.'};}
  if(S.view==='pedidos'){render();}
  if(S.vt.zoom)renderZoom();
}
function mensajeVentas(){
  const v=S.vt;
  if(v.estado==='cargando')return `<div class="dr-sk" aria-hidden="true"><i></i><i></i><i></i></div><div class="sr" role="status">Calculando las ventas…</div>`;
  const d=v.data||{},tablas=(d.tablas||[]).length?`<p class="vt-t">Tablas parecidas en el servidor: ${d.tablas.map(esc).join(', ')}</p>`:'';
  return `<div class="empty"><div><h3>Ventas por clasificación no disponibles</h3>${esc(d.motivo||'Sin datos')}${tablas}</div></div>`;
}
function cardVentas(){
  const v=S.vt,ok=v.estado==='ok'&&v.data&&v.data.clasif.length;
  const total=ok?`<span class="vt-tot" title="Venta total de lo filtrado, sin cancelados">${ventaTxt(v.data.total)}</span>`:'';
  const zoom=`<button class="ibtn" data-zoom aria-haspopup="dialog" aria-label="Zoom: ver las ventas por producto de cada clasificación" title="Zoom: ver las ventas por producto de cada clasificación"${ok?'':' disabled'}>${ico('zoom',16)}</button>`;
  const cuerpo=ok?`<div class="chart-wrap">${chartBox('cClas','Ventas por clasificación 2')}</div>`:`<div class="chart-wrap">${mensajeVentas()}</div>`;
  return card('','Ventas por Clasif2',`<span id="sub-cClas">${esc(S.subs.cClas||'')}</span>${total}${zoom}`,cuerpo);
}
function pintarVentas(intento=0){
  const v=S.vt;if(v.estado!=='ok'||!v.data)return;
  const el=document.getElementById('cClas');   // la tarjeta se arma después de la carga: si aún no tiene alto, se espera al siguiente cuadro
  if(el&&!el.parentElement.clientHeight&&intento<6){requestAnimationFrame(()=>pintarVentas(intento+1));return;}
  miniBar('cClas',{labels:v.data.clasif.map(c=>c.nombre),valores:v.data.clasif.map(c=>c.venta),total:v.data.clasif.length},css('--primary'),'clasif2',ventaTxt);   // clic en una barra: filtra todo el tablero por esa clasificación
}

/* ---------- zoom: clasificaciones a la izquierda, productos de la elegida a la derecha ---------- */
function abrirZoom(opener){
  if(S.vt.estado!=='ok')return;
  cerrarChat(false);cerrarPedido(false);S.np&&cerrarNotif(false);
  S.vt.zoom=true;S.vt.opener=opener||document.activeElement;renderZoom(true);
}
function cerrarZoom(devolverFoco=true){
  if(!S.vt.zoom)return;
  S.vt.zoom=false;$('#zoom').replaceChildren();
  for(const id of Object.keys(charts)){if(!charts[id].canvas.isConnected){charts[id].destroy();delete charts[id];}}
  const op=S.vt.opener;if(devolverFoco&&op&&op.isConnected)op.focus();
}
async function elegirClasif(nombre){
  const v=S.vt;
  if(v.sel===nombre){v.sel=null;v.prods=null;renderZoom();return;}
  v.sel=nombre;v.prods=null;v.cargandoProds=true;renderZoom();
  try{const p=await pedirVentas(nombre);if(v.sel!==nombre)return;v.prods=p.ok?p:null;}catch(e){v.prods=null;}
  v.cargandoProds=false;renderZoom();
}
const altoBarras=n=>Math.max(180,Math.round(n*fz(26)+fz(16)));
function renderZoom(abrir){
  const el=$('#zoom');if(!S.vt.zoom){el.replaceChildren();return;}
  const v=S.vt,d=v.data;if(!d||!d.ok){cerrarZoom(false);return;}
  const prods=v.prods&&v.prods.productos?v.prods.productos.slice(0,30):[];
  const opciones=`<option value="">Elige una clasificación</option>${d.clasif.map(c=>`<option value="${esc(c.nombre)}" ${v.sel===c.nombre?'selected':''}>${esc(c.nombre)}</option>`).join('')}`;
  let der;
  if(!v.sel)der=`<div class="empty"><div><h3>Elige una clasificación</h3>Haz clic en una barra de la izquierda para ver sus productos.</div></div>`;
  else if(v.cargandoProds)der=`<div class="dr-sk" aria-hidden="true"><i></i><i></i><i></i></div>`;
  else if(!prods.length)der=`<div class="empty"><div><h3>Sin productos</h3>Esta clasificación no tiene ventas con los filtros actuales.</div></div>`;
  else der=`<div class="zoom-ch" style="height:${altoBarras(prods.length)}px"><canvas id="zProd" role="img" aria-label="Ventas por producto de ${esc(v.sel)}"></canvas></div>`;
  const subDer=v.sel&&v.prods?`${v.prods.n_productos>prods.length?`primeros ${prods.length} de ${v.prods.n_productos}, `:''}${ventaTxt(v.prods.total)}`:'';
  const html=`<div class="zoom-scrim" data-zoom-cerrar></div>
    <div class="zoom-d" id="zoom-d" role="dialog" aria-modal="true" aria-labelledby="zoom-tit" tabindex="-1">
      <div class="zoom-h"><div><h2 id="zoom-tit">Ventas por clasificación 2 y producto</h2><p>Monto de los pedidos, sin cancelados. Respeta los filtros y los clics del tablero.${d.fuente?` Maestra: ${esc(d.fuente)}.`:''}</p></div>
        <div class="zoom-acc"><button class="btn sm" data-vt-exp="sel" ${v.sel?'':'disabled'} title="Exporta Clasif2, producto y venta de la clasificación elegida">${ico('descarga',14)}Exportar la elegida</button>
          <button class="btn sm" data-vt-exp="todo" title="Exporta Clasif2, producto y venta de todas las clasificaciones">${ico('descarga',14)}Exportar todo</button>
          <button class="dr-x" data-zoom-cerrar aria-label="Cerrar el zoom" title="Cerrar (Esc)">${ico('x',18)}</button></div></div>
      <div class="zoom-b">
        <section class="card"><div class="card-h"><h2>Clasificación 2</h2><span class="sub">${ventaTxt(d.total)} en total</span></div>
          <div class="card-b" tabindex="0"><div class="zoom-ch" style="height:${altoBarras(d.clasif.length)}px"><canvas id="zClas" role="img" aria-label="Ventas por clasificación 2"></canvas></div></div></section>
        <section class="card"><div class="card-h"><h2>${v.sel?`Productos de ${esc(v.sel)}`:'Productos'}</h2><span class="sub">${esc(subDer)}</span></div>
          <div class="zoom-sel"><label for="zoom-cl" class="sr">Clasificación</label><select id="zoom-cl" data-zoom-sel autocomplete="off">${opciones}</select></div>
          <div class="card-b" tabindex="0">${der}</div></section>
      </div></div>`;
  morph(el,html);
  if(abrir){const a=$('#zoom-d');if(a)a.focus();}
  requestAnimationFrame(pintarZoom);
}
function barrasZoom(id,labels,vals,color,selIdx,onClick){
  const o=baseO();o.indexAxis='y';o.layout={padding:{right:fz(76)}};o.scales.x={display:false,beginAtZero:true};
  const maxPx=Math.max(fz(80),(document.getElementById(id).parentElement.clientWidth-fz(76))*.45);
  o.scales.y.ticks={autoSkip:false,color:css('--text-2'),font:{size:fz(11.5)},padding:fz(4),callback:function(v){return cutPx(this.getLabelForValue(v),maxPx);}};
  o.plugins.tooltip={callbacks:{title:i=>labels[i[0].dataIndex],label:c=>' '+money(c.raw)}};
  if(onClick){o.onClick=(ev,els)=>{if(els.length)onClick(labels[els[0].index]);};o.onHover=manito;}
  grafico(id,{type:'bar',data:{labels,datasets:[{data:vals,backgroundColor:labels.map((_,i)=>selIdx<0||i===selIdx?color:alfa(color,.3)),borderRadius:4,barPercentage:.74,categoryPercentage:.92,maxBarThickness:fz(20),fmtv:ventaTxt}]},options:o,plugins:[valueLabels]});
}
function pintarZoom(){
  const v=S.vt,d=v.data;if(!v.zoom||!d||!d.ok)return;
  Chart.defaults.font.family=fam();Chart.defaults.color=css('--text-3');
  if(document.getElementById('zClas')){const L=d.clasif.map(c=>c.nombre);barrasZoom('zClas',L,d.clasif.map(c=>c.venta),css('--primary'),L.indexOf(v.sel),elegirClasif);}
  if(document.getElementById('zProd')&&v.prods){const P=v.prods.productos.slice(0,30);barrasZoom('zProd',P.map(p=>p.producto),P.map(p=>p.venta),css('--primary'),-1,null);}
}
function exportarVentas(cual){
  const body={...cuerpoFiltros()};if(cual==='sel'&&S.vt.sel)body.zoom_clasif=S.vt.sel;
  return bajarCSV('/api/ventas/exportar',body,'ventas.csv');
}
function exportarPedidos(que){   // todos los pedidos que dejan los filtros (no solo las filas que se ven)
  const body={...cuerpoFiltros()};
  if(que==='crit'){body.criticos=true;body.orden_crit=S.orden.crit;}else body.orden_det=S.orden.det;
  return bajarCSV('/api/pedidos/exportar',body,'pedidos.csv');
}
document.addEventListener('click',ev=>{
  const z=ev.target.closest('[data-zoom]');if(z){abrirZoom(z);return;}
  if(ev.target.closest('[data-zoom-cerrar]')){cerrarZoom(true);return;}
  const e=ev.target.closest('[data-vt-exp]');if(e){exportarVentas(e.dataset.vtExp);return;}
  const p=ev.target.closest('[data-exp-ped]');if(p){exportarPedidos(p.dataset.expPed);return;}
});
document.addEventListener('change',ev=>{const s=ev.target.closest('[data-zoom-sel]');if(s){if(s.value)elegirClasif(s.value);else{S.vt.sel=null;S.vt.prods=null;renderZoom();}}});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&S.vt.zoom){ev.preventDefault();cerrarZoom(true);}});
