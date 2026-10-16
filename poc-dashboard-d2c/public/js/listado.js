/* listado.js: ventana emergente para las tablas largas (todos los pedidos, facturados sin despacho, matriz por día).
   Las pantallas muestran gráficos y unas pocas filas; la lista completa se abre solo cuando se necesita. */
S.lst={abierto:false,tipo:'det',opener:null};
const LISTAS={
  det:{t:'Pedidos',exp:'det',sub:()=>fmt(S.data.n_filtrado)+' pedidos con los filtros actuales'+(S.data.detalle.length>=500?'. Se muestran los primeros 500: exporta a CSV para tener todos.':''),cuerpo:()=>tablaDetalle()},
  crit:{t:'Facturado en SAP, pendiente en VTEX',exp:'crit',sub:()=>fmt(S.data.criticos_total.n)+' pedidos, '+money(S.data.criticos_total.monto),cuerpo:()=>tablaCriticos()},
  dia:{t:'Pedidos por día de creación',exp:null,sub:()=>'Clic en un día para filtrar todo el tablero con él',cuerpo:()=>tablaCreacion()}};
function abrirListado(tipo,opener){
  if(!S.data||!LISTAS[tipo])return;
  cerrarChat(false);cerrarPedido(false);S.np&&cerrarNotif(false);if(S.vt.zoom)cerrarZoom(false);
  S.lst={abierto:true,tipo,opener:opener||document.activeElement};renderListado(true);
}
function cerrarListado(devolverFoco=true){
  if(!S.lst.abierto)return;
  S.lst.abierto=false;$('#lista').replaceChildren();
  const op=S.lst.opener;if(devolverFoco&&op&&op.isConnected)op.focus();
}
function renderListado(foco){
  if(!S.lst.abierto||!S.data)return;
  const c=LISTAS[S.lst.tipo],el=$('#lista');
  const exp=c.exp?`<button class="btn sm" data-exp-ped="${c.exp}">${ico('descarga',14)}Exportar CSV</button>`:'';
  morph(el,`<div class="lst-scrim" data-cerrar-lista></div><div class="lst-d" role="dialog" aria-modal="true" aria-labelledby="lst-t" tabindex="-1">
    <div class="lst-h"><div><h2 id="lst-t">${esc(c.t)}</h2><p>${esc(c.sub())}</p></div><div class="zoom-acc">${exp}<button class="dr-x" data-cerrar-lista aria-label="Cerrar la lista" title="Cerrar (Esc)">${ico('x',18)}</button></div></div>
    <div class="lst-b" tabindex="0">${c.cuerpo()}</div></div>`);
  if(foco){const dlg=el.querySelector('.lst-d');if(dlg)dlg.focus();}
}
