/* vistas.js: barra de filtros, tablas y las tres pantallas (Pedidos VTEX, Resumen, Diagnóstico). Solo arman HTML. */
/* ============ riel y filtros ============ */
const ALERTA_NOM={bws:'BWS atrasados',pos:'Post fechados por preparar',mkp:'Marketplace +5 días',fac:'Facturados sin despachar'};
const ALERTA_TIP={bws:'Pedidos del canal BWS (bodega EC01, sin SLA Servicios) que ya deberían estar preparados: están listos para preparar y su entrega estimada ya venció.',
  pos:'Pedidos de la bodega Post Fechado (venta con entrega programada a futuro) que están listos para preparar.',
  mkp:'Pedidos de marketplace (MELI, Falabella, Paris…) listos para preparar que llevan 5 días o más sin prepararse.',
  fac:'Pedidos ya facturados en SAP que en VTEX siguen pendientes: se cobró pero no se ha despachado.'};
async function cargarOpts(){
  try{S.opts=await(await fetch('/api/filtros')).json();sincPer();}catch(e){S.opts=null;}
  renderSlicers();
}
function renderSlicers(){
  const el=$('#slicers');
  if(!S.opts||S.opts.error){morph(el,'');return;}
  const o=S.opts,f=S.filtros;
  const sel=(k,l,arr)=>`<div class="sl"><label for="sl-${k}">${l}</label><select id="sl-${k}" name="${k}" autocomplete="off" data-sl="${k}"><option value="" ${f[k].length?'':'selected'}>Todos</option>${f[k].length>1?`<option value="__multi" selected>${f[k].length} seleccionados</option>`:''}${(arr||[]).map(v=>`<option value="${esc(v)}" ${f[k].length===1&&f[k][0]===v?'selected':''}>${esc(v)}</option>`).join('')}</select></div>`;
  const igual=(a,b)=>a.length===b.length&&a.every(x=>b.includes(x));
  const bv=igual(f.bodega,BASE)?'__base':(f.bodega.length===0?'__todas':f.bodega[0]);
  const ob=[['__base','EC01 + POST'],['EC01','EC01'],['POST_Fechado','POST_Fechado'],['__todas','Todas las bodegas']];
  if(!ob.some(x=>x[0]===bv))ob.splice(3,0,[bv,bv]);   // una bodega elegida desde el gráfico (por ejemplo CD45) también se ve en el selector
  const bodega=`<div class="sl"><label for="sl-bodega">Bodega</label><select id="sl-bodega" name="bodega" autocomplete="off" data-bodega>${ob.map(([v,t])=>`<option value="${esc(v)}" ${bv===v?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`;
  const pe=perEf();
  const periodo=`<div class="sl"><label for="sl-per">Período de creación</label><select id="sl-per" name="periodo" autocomplete="off" data-per>${PER.map(([v,t])=>`<option value="${v}" ${pe===v?'selected':''}>${t}</option>`).join('')}</select></div>`;
  const fechas=pe==='custom'?`<div class="sl d"><label for="sl-ini">Desde</label><input id="sl-ini" name="desde" autocomplete="off" type="date" data-fecha="ini" value="${f.fecha_ini||''}" min="${o.fecha_min}" max="${o.fecha_max}"></div><div class="sl d"><label for="sl-fin">Hasta</label><input id="sl-fin" name="hasta" autocomplete="off" type="date" data-fecha="fin" value="${f.fecha_fin||''}" min="${o.fecha_min}" max="${o.fecha_max}"></div>`:'';
  const alcance=S.view==='pedidos'?`<div class="sl"><label for="sl-alcance">Alcance</label><select id="sl-alcance" name="alcance" autocomplete="off" data-alcance>
    <option value="abiertos" ${f.alcance==='abiertos'?'selected':''}>En seguimiento</option><option value="todos" ${f.alcance==='todos'?'selected':''}>Todos (con cerrados)</option></select></div>`:'';
  const nMas=(f.status.length?1:0)+(f.sla.length?1:0)+(S.view==='pedidos'&&f.alcance==='todos'&&!f.alerta&&!f.buscar?1:0);
  const mas=`<div class="mas"><button class="btn" data-mas aria-expanded="${S.mas}" aria-haspopup="dialog"${S.mas?' aria-controls="panel-mas"':''}>${ico('filtro',16)}Más filtros${nMas?`<span class="cnt">${nMas}</span>`:''}</button>${S.mas?`<div class="panel-mas" id="panel-mas" role="dialog" aria-label="Más filtros" tabindex="-1">${sel('status','Status',o.status)}${sel('sla','SLA Type',o.sla)}${alcance}</div>`:''}</div>`;
  const act=[];
  if(f.alerta)act.push(ALERTA_NOM[f.alerta]);
  if(f.tarjeta)act.push({ing:'Órdenes Integradas',noing:'Órdenes Sin PV',canc:'Órdenes Canceladas'}[f.tarjeta]);
  ['canal','cliente','clasif2','status','sla'].forEach(k=>{if(f[k][0])act.push(({canal:'Canal',cliente:'Cliente',clasif2:'Clasificación',status:'Status',sla:'SLA'})[k]+' '+f[k].join(', '));});
  if(!igual(f.bodega,BASE))act.push('Bodega '+(f.bodega.length?f.bodega.join(', '):'todas'));
  if(f.buscar)act.push('Búsqueda “'+f.buscar+'”');
  const etqPer=pe==='mes'?'mes en curso':pe==='mes_ant'?'mes anterior':pe==='30'?'últimos 30 días':pe==='todo'?'todo el período':(f.fecha_ini===f.fecha_fin?fd(f.fecha_ini):fd(f.fecha_ini)+' a '+fd(f.fecha_fin));
  const fsum=`<div class="fsum"><span class="cap">Filtros</span> ${['Creación: '+etqPer,...act].map(esc).join(', ')}${!act.length&&S.view==='pedidos'&&f.alcance==='abiertos'?', pedidos en seguimiento':''}</div>`;
  morph(el,`<button class="btn fbtn" data-ftoggle aria-expanded="${!!S.fa}">Filtros${act.length?` (${act.length})`:''}${ico(S.fa?'arriba':'abajo',14)}</button>`+fsum+`<div class="fgrid ${S.fa?'open':''}">`+sel('canal','Canal',o.canal)+sel('cliente','Cliente',o.cliente)+bodega+periodo+fechas
   +`<div class="sl q"><label for="sl-q">Buscar pedido</label><input id="sl-q" name="buscar" autocomplete="off" spellcheck="false" type="search" data-buscar placeholder="Sequence o SAP…" value="${esc(f.buscar)}"></div>`
   +mas+`<button class="btn" data-limpiar-sl title="Vuelve a la vista inicial">Restablecer</button></div>`);
}
function renderNav(){
  const it=[['pedidos','Pedidos VTEX'],['resumen','Resumen ejecutivo'],['diagnostico','Diagnóstico']];
  morph($('#nav'),it.map(([v,t])=>`<button data-go="${v}" ${S.view===v?'aria-current="page"':''}>${ico(v,18)}${t}</button>`).join(''));
}
function renderTools(){
  const tm=[['auto','Tema del sistema','auto'],['light','Tema claro','sun'],['dark','Tema oscuro','moon']];
  morph($('#tools'),`<div class="seg" role="group" aria-label="Tema">${tm.map(([k,t,i])=>`<button data-tema="${k}" aria-pressed="${S.tema===k}" title="${t}" aria-label="${t}">${ico(i,14)}</button>`).join('')}</div>
    <button class="btn sm" data-tv aria-pressed="${S.tv}" title="Pantalla grande: letra mayor, sin filtros">${ico('tv',14)}Modo TV</button>`);
}

/* ============ piezas ============ */
function kpiCard(lab,val,d,mejor,risk,nota){
  let dH=`<div class="dlt flat" ${nota?'':'title="Sin mes anterior para comparar"'}>${nota||''}</div>`;
  if(d!=null){const b=mejor==='arriba'?d>=0:d<=0;const c=d===0?'flat':(b?'up':'down');dH=`<div class="dlt ${c}">${ico(d>0?'up':d<0?'down':'flat',14)}${pctD(Math.abs(d))} vs mes ant.</div>`;}
  return `<div class="kpi ${risk?'risk':''}"><div class="lab cap" title="${esc(lab)}">${esc(lab)}</div><div class="val">${val}</div>${dH}</div>`;
}
const NOMBRE_COL={sequence:'Sequence',pedido_sap:'Pedido SAP',estado:'Estado',canal:'Canal',sla:'SLA Type',fecha:'Creación',sed:'Entrega est.',monto:'Monto',dias:'Días facturado pendiente',vigentes:'Vigentes',pct_pendiente:'% Pendiente',monto_riesgo:'Monto en riesgo'};
function thOrd(tabla,col,txt,cls=''){
  const o=S.orden[tabla],on=o&&o.col===col,ar=on?(o.dir==='asc'?'asc':'desc'):'both';
  const tip=on?(o.dir==='asc'?'Orden ascendente. Clic: descendente':'Orden descendente. Clic: quitar orden'):'Clic: ordenar ascendente';
  return `<th class="ord ${cls} ${on?'on':''}" tabindex="0" scope="col" ${on?`aria-sort="${o.dir==='asc'?'ascending':'descending'}"`:''} data-tabla="${tabla}" data-ord="${col}" title="${tip}"><div class="thw"><span>${txt}</span><span class="ar">${ico(ar,12)}</span></div></th>`;
}
const descOrden=tabla=>{const o=S.orden[tabla];return o?`, orden: ${NOMBRE_COL[o.col]} ${o.dir==='asc'?'ascendente':'descendente'}`:'';};
function chipEntrega(r,hoy){   // la entrega estimada con su estado: vencida, hoy o dentro de N días
  if(!r.sed)return '<span class="en-n">sin fecha</span>';
  const abierto=r.estado.includes('Pendiente')||r.estado==='No integrado · Facturado';
  const dd=Math.round((new Date(r.sed+'T12:00:00')-new Date(hoy+'T12:00:00'))/864e5);
  if(!abierto)return `<span class="en-f">${fd(r.sed).slice(0,5)}</span>`;
  return `<span class="en-f">${fd(r.sed).slice(0,5)}</span> <span class="en ${dd<0?'v':dd===0?'h':''}">${dd<0?'vencido hace '+(-dd)+' d':dd===0?'vence hoy':'en '+dd+' d'}</span>`;
}
function tablaDetalle(){
  const d=S.data,rows=d.detalle;
  if(!rows.length)return vacio('Sin pedidos','Ningún pedido cumple los filtros actuales.');
  return `<table class="t t2"><thead><tr>${thOrd('det','sequence','Pedido')}${thOrd('det','pedido_sap','Pedido SAP','c-sap')}${thOrd('det','estado','Estado')}${thOrd('det','cliente','Cliente · SLA','c-sla')}${thOrd('det','fecha','Creación','c-crea')}${thOrd('det','sed','Entrega estimada')}${thOrd('det','monto','Monto','n c-monto')}</tr></thead><tbody>
  ${rows.map(r=>`<tr id="r${esc(r.sequence)}" class="clic ${r.nuevo?'nw':''} ${S.dr&&S.dr.seq===r.sequence?'sel':''}" data-pv="${esc(r.sequence)}" tabindex="0" aria-haspopup="dialog" title="Clic: ver las líneas del pedido. ${esc(r.warehouse)}">
    <td class="pd"><b class="num" translate="no">${esc(r.sequence)}</b>${r.nuevo?'<span class="tag tagnew">NUEVO</span>':''}</td><td class="num c-sap">${esc(r.pedido_sap||'-')}</td><td>${pill(r.estado)}</td>
    <td class="cl c-sla" title="${esc(r.sla)}"><b>${esc(r.cliente||r.canal)}</b><small>${esc(r.canal)} · ${esc(r.sla)}</small></td><td class="c-crea">${fd(r.fecha)}</td><td>${chipEntrega(r,d.hoy)}</td><td class="n c-monto">${money(r.monto)}</td></tr>`).join('')}
</tbody></table>`;
}
function tablaEntrega(){
  const m=S.data.matriz_entrega;
  if(!m.cols.length)return vacio('Sin pedidos abiertos con fecha de entrega','Ajusta los filtros.');
  const th=m.cols.map(c=>`<th class="clic ${c.rel<0?'v':c.rel===0?'h':''} ${(S.filtros.entrega||[]).includes(c.k)?'sel':''}" data-ent="${esc(c.k)}" tabindex="0" title="Clic: filtrar los pedidos con esta entrega estimada">${esc(c.etq)}</th>`).join('');
  const fila=(e,i)=>`<tr><td class="f"><i style="background:${stVar(e)}"></i>${esc(e)}</td>${m.filas[i].map((v,j)=>{
    const c=m.cols[j]; if(!v)return '<td class="z">0</td>';
    const hl=e.startsWith('Integrado · Atrasado')?'hv':(e.startsWith('Integrado · En proceso')&&c.rel===0?'hh':'vv');
    return `<td class="${hl}">${fmt(v)}</td>`;}).join('')}<td class="tot">${fmt(m.filas[i].reduce((a,b)=>a+b,0))}</td></tr>`;
  return `<table class="mx me"><thead><tr><th class="f">Estado pedido</th>${th}<th>Total</th></tr></thead><tbody>
  ${m.estados.map(fila).join('')}<tr class="fin"><td class="f">Total</td>${m.totales.map(v=>`<td>${fmt(v)}</td>`).join('')}<td>${fmt(m.total)}</td></tr></tbody></table>`;
}
function tablaCreacion(){
  const m=S.data.matriz_dia;
  if(!m.fechas.length)return vacio('Sin datos','Ajusta los filtros.');
  const AB={'Integrado · Pendiente':'Int.<br>Pend.','No integrado · Pendiente':'No int.<br>Pend.','No integrado · Facturado':'No int.<br>Fact.','Integrado · Facturado':'Int.<br>Fact.','Cancelado':'Cancel.'};
  const mx=m.columnas.map((_,j)=>Math.max(1,...m.filas.map(f=>f[j])));
  const anios=m.fechas[0].slice(0,4)!==m.fechas[m.fechas.length-1].slice(0,4);
  const cel=(v,j)=>v?`<td style="background:color-mix(in srgb,${stVar(m.columnas[j])} ${Math.round(12+36*v/mx[j])}%,transparent)">${fmt(v)}</td>`:'<td class="z">0</td>';
  return `<table class="mx"><thead><tr><th class="f">Día</th>${m.columnas.map(c=>`<th title="${esc(c)}"><i style="background:${stVar(c)}"></i><span class="fl">${esc(c).replace(' · ','<br>')}</span><span class="ab">${AB[c]||esc(c)}</span></th>`).join('')}<th>Total</th></tr></thead><tbody>
  <tr class="fin arriba"><td class="f">Total</td>${m.totales_col.map(v=>`<td>${fmt(v)}</td>`).join('')}<td>${fmt(m.total)}</td></tr>
  ${m.fechas.map((f,i)=>`<tr id="d${f}" class="clic ${diaSel()===f?'sel':''}" data-fdia="${f}" tabindex="0" title="Clic: filtrar por este día de creación"><td class="f">${esc(dia(f,anios))}</td>${m.filas[i].map(cel).join('')}<td class="tot">${fmt(m.totales_fila[i])}</td></tr>`).join('')}</tbody></table>`;
}
function tablaCriticos(){
  const t=S.data.tabla_criticos;
  if(!t.length)return vacio('Nada facturado sin despacho','Ningún pedido pendiente tiene factura en SAP.');
  return `<table class="t"><thead><tr>${thOrd('crit','sequence','Sequence')}${thOrd('crit','canal','Canal')}${thOrd('crit','dias','Días facturado pendiente','n')}${thOrd('crit','monto','Monto','n')}</tr></thead><tbody>
  ${t.map(r=>`<tr id="c${esc(r.sequence)}" class="clic ${S.dr&&S.dr.seq===r.sequence?'sel':''}" data-pv="${esc(r.sequence)}" tabindex="0" aria-haspopup="dialog" title="Clic: ver las líneas del pedido"><td class="num">${esc(r.sequence)}</td><td>${esc(r.canal)}</td><td class="n ${r.dias>3?'down':''}">${r.dias??'-'}</td><td class="n">${money(r.monto)}</td></tr>`).join('')}
</tbody></table>`;
}
function tablaCanal(){
  let c=S.data.canal; if(!c.length)return vacio('Sin datos');
  const oc=S.orden.canal;
  if(oc){c=[...c].sort((a,b)=>{const x=a[oc.col],y=b[oc.col];if(x==null)return 1;if(y==null)return -1;const r=typeof x==='string'?x.localeCompare(y,'es'):x-y;return oc.dir==='asc'?r:-r;});}
  const V=c.reduce((a,r)=>a+r.vigentes,0),P_=c.reduce((a,r)=>a+r.pendientes,0),M=c.reduce((a,r)=>a+r.monto_riesgo,0);
  return `<table class="t"><thead><tr>${thOrd('canal','canal','Canal')}${thOrd('canal','vigentes','Pedidos vigentes mes actual','n')}${thOrd('canal','pct_pendiente','% Pendiente','n')}${thOrd('canal','monto_riesgo','Monto en riesgo','n')}</tr></thead><tbody>
  ${c.map(r=>`<tr id="k${esc(r.canal)}" class="clic ${S.filtros.canal.includes(r.canal)?'sel':''}" data-fcanal="${esc(r.canal)}" tabindex="0" title="Clic: filtrar por este canal. Ctrl + clic: sumar otro"><td><b>${esc(r.canal)}</b></td><td class="n">${fmt(r.vigentes)}</td><td class="n">${pct(r.pct_pendiente)}</td><td class="n">${money(r.monto_riesgo)}</td></tr>`).join('')}
  <tr class="fin"><td>Total</td><td class="n">${fmt(V)}</td><td class="n">${pct(V?P_/V:null)}</td><td class="n">${money(M)}</td></tr></tbody></table>`;
}
const card=(cls,titulo,sub,cuerpo,bcls='',extra='')=>`<section class="card ${cls} ${extra}"><div class="card-h"><h2>${titulo}</h2>${sub?`<span class="sub">${sub}</span>`:''}</div><div class="card-b ${bcls}" tabindex="0">${cuerpo}</div></section>`;
const chartBox=(id,label)=>`<div class="chart-box"><canvas id="${id}" role="img" aria-label="${esc(label)}"></canvas></div>`;
const chartCard=(cls,titulo,id,data,vacioT,vacioM,campo)=>card(cls,titulo,`<span id="sub-${id}">${esc(S.subs[id]||'')}</span>`,
  `<div class="chart-wrap">${data&&data.labels&&data.labels.length?chartBox(id,titulo+'. Clic en una barra para filtrar todo el tablero.'):vacio(vacioT||'',vacioM||'Sin datos')}</div>`,'','vivo'+(campo&&seleccion(campo).length?' tiene-sel':''));

/* ============ filtros activos como fichas (cada una se quita con su ✕) ============ */
const NOM_ENT=k=>k==='vencido'?'Entrega vencida':k==='hoy'?'Entrega hoy':k==='<'?'Entrega anterior a la ventana':k==='>'?'Entrega posterior a la ventana':'Entrega '+fd(k).slice(0,5);
function chipsActivos(){
  const f=S.filtros,out=[],add=(k,txt,val)=>out.push({k,txt,val});
  if(f.alerta)add('alerta',ALERTA_NOM[f.alerta]);
  if(f.tarjeta)add('tarjeta',{ing:'Integrados en SAP',noing:'Sin PV en SAP',canc:'Cancelados'}[f.tarjeta]);
  [['cliente','Cliente'],['canal','Canal'],['sla','SLA'],['clasif2','Clasificación'],['causa','Causa'],['estado_ped','Estado'],['estado_ent','Entrega'],['status','Status']].forEach(([k,l])=>(f[k]||[]).forEach(v=>add(k,l+': '+v,v)));
  (f.entrega||[]).forEach(v=>add('entrega',NOM_ENT(v),v));
  if(!igualLista(f.bodega,BASE))(f.bodega.length?f.bodega:['todas']).forEach(v=>add('bodega','Bodega: '+v,v));
  const ds=diaSel(),ms=mesSel();
  if(S.per==='custom'){if(ds)add('periodo','Creados el '+fd(ds).slice(0,5));else if(ms)add('periodo','Creados en '+mes(ms));else if(f.fecha_ini)add('periodo','Creados del '+fd(f.fecha_ini).slice(0,5)+' al '+fd(f.fecha_fin).slice(0,5));}
  if(f.buscar)add('buscar','Búsqueda “'+f.buscar+'”');
  return out;
}
function barraRapida(conAlertas){
  const d=S.data,F=S.filtros,a=d.alertas;
  const btn=(k,n,crit)=>`<button class="mbtn ${crit?'crit':''}" data-alerta="${k}" aria-pressed="${F.alerta===k}" title="${esc(ALERTA_TIP[k])}">${ALERTA_NOM[k]}<b>${fmt(n)}</b></button>`;
  const botones=conAlertas?btn('bws',a.bws)+btn('pos',a.pos)+btn('mkp',a.mkp)+btn('fac',a.fac,true):'';
  const alc=F.buscar?'búsqueda en todos los estados':(S.view==='pedidos'&&F.alcance==='abiertos'?'en seguimiento':'');
  const ch=chipsActivos();
  return `<div class="qf a-qf"><div class="qf-r">${botones}<span class="ctx"><span><b>${fmt(d.n_filtrado)}</b> pedidos${alc?', '+alc:''}</span>
    <button class="btn sm" data-ver-lista="det" title="Abre la lista completa de pedidos con los filtros actuales">${ico('pedidos',14)}Ver pedidos</button>
    <button class="ibtn" data-exp-ped="det" aria-label="Exportar a CSV todos los pedidos que dejan los filtros" title="Exportar a CSV todos los pedidos que dejan los filtros">${ico('descarga',16)}</button></span></div>
    ${ch.length?`<div class="chips" role="group" aria-label="Filtros activos"><span class="cap">Filtrando por</span>${ch.map(c=>`<span class="chip"><span>${esc(c.txt)}</span><button class="x" data-quitar="${c.k}" data-val="${esc(c.val==null?'':c.val)}" aria-label="Quitar el filtro ${esc(c.txt)}" title="Quitar este filtro">${ico('x',12)}</button></span>`).join('')}<button class="chip limpiar" data-limpiar-todo>Limpiar todo</button></div>`:''}</div>`;
}

/* ============ piezas de Pedidos VTEX ============ */
function railTarjeta(){   // la tarjeta de órdenes de siempre, ahora con una fila más: entrega vencida
  const d=S.data,t=d.tarjetas,F=S.filtros,ent=F.entrega||[];
  const trow=(l,v,k,c)=>`<button class="trow" style="--tc:${c}" data-tarjeta="${k}" aria-pressed="${k===''?(F.tarjeta==null&&!ent.length):F.tarjeta===k}"><i></i><span class="tn">${l}</span><span class="tv" data-v="${l}">${fmt(v)}</span></button>`;
  const venc=`<button class="trow" style="--tc:var(--err)" data-ent="vencido" aria-pressed="${ent.includes('vencido')}" title="Pedidos abiertos con la entrega estimada ya vencida"><i></i><span class="tn">Entrega vencida</span><span class="tv">${fmt(d.vencidos.n)}</span></button>`;
  return `<section class="card"><div class="tl-head cap"><span>Tarjeta</span><span>Órdenes</span></div>${trow('Órdenes VTEX',t['Órdenes VTEX'],'','var(--ink)')}${trow('Órdenes Integradas',t['Órdenes Integradas'],'ing','var(--st-if)')}${trow('Órdenes Sin PV',t['Órdenes Sin PV'],'noing','var(--st-nf)')}${(t['Órdenes Canceladas']>0||F.tarjeta==='canc')?trow('Órdenes Canceladas',t['Órdenes Canceladas'],'canc','var(--st-ca)'):''}${venc}</section>`;
}
function railCausa(){   // causa pendiente con su barra que se llena según el total; cada fila filtra
  const d=S.data,sel=S.filtros.causa||[],cs=Object.entries(d.causa||{}).sort((a,b)=>b[1]-a[1]),cm=Math.max(1,...cs.map(e=>e[1]));
  const filas=cs.length?cs.map(([k,v])=>`<button class="crow" id="q${esc(k)}" data-causa="${esc(k)}" aria-pressed="${sel.includes(k)}" title="Clic: filtrar los pendientes con esta causa. Ctrl + clic: sumar otra"><span>${esc(k)}</span><span class="cv">${fmt(v)}</span><span class="cb"><i style="width:${100*v/cm}%"></i></span></button>`).join(''):vacio('','Sin pendientes integrados');
  return `<section class="card ${sel.length?'tiene-sel':''}"><div class="card-h"><h2>Causa pendiente</h2></div><div class="card-b flush" tabindex="0">${filas}</div></section>`;
}
function calendarioCreacion(){   // un día = una celda; el color dice cuántos pedidos se crearon, el clic filtra todo con ese día
  const m=S.data.matriz_dia;
  if(!m.fechas.length)return vacio('Sin datos','Ajusta los filtros.');
  const mx=Math.max(1,...m.totales_fila),ini=new Date(m.fechas[0]+'T12:00:00'),fin=new Date(m.fechas[m.fechas.length-1]+'T12:00:00');
  const por={};m.fechas.forEach((f,i)=>{por[f]=i;});
  const lun=new Date(ini);lun.setDate(lun.getDate()-((lun.getDay()+6)%7));
  let h=`<div class="cal" role="group" aria-label="Pedidos creados por día. Clic en un día para filtrar todo el tablero."><div class="cal-h"><span></span>${['L','M','X','J','V','S','D'].map(x=>`<span>${x}</span>`).join('')}</div>`;
  const dsel=diaSel();
  for(let w=new Date(lun);w<=fin;w.setDate(w.getDate()+7)){
    h+=`<div class="cal-w"><span class="cal-e">${w.toLocaleDateString('es-CL',{day:'numeric',month:'short'}).replace('.','')}</span>`;
    for(let k=0;k<7;k++){
      const x=new Date(w);x.setDate(x.getDate()+k);const f=iso(x),i=por[f];
      if(i==null){h+='<span class="cd vacio"></span>';continue;}
      const t=m.totales_fila[i],det=m.columnas.map((c,j)=>m.filas[i][j]?`${c}: ${fmt(m.filas[i][j])}`:'').filter(Boolean).join(' · ');
      h+=`<button class="cd ${t/mx>=.5?'hi':''} ${dsel===f?'sel':''}" style="--i:${(t/mx).toFixed(3)}" data-fdia="${f}" aria-pressed="${dsel===f}" title="${esc(dia(f))}: ${fmt(t)} pedidos${det?' ('+esc(det)+')':''}"><span class="dn">${x.getDate()}</span><b>${fmt(t)}</b></button>`;
    }
    h+='</div>';
  }
  return h+`<div class="cal-l"><span>menos</span><i style="--i:.08"></i><i style="--i:.35"></i><i style="--i:.65"></i><i style="--i:1"></i><span>más pedidos</span></div></div>`;
}
function cardEntrega(){
  const d=S.data,m=d.matriz_entrega,F=S.filtros,sel=F.entrega||[];
  const iH=m.cols.findIndex(c=>c.rel===0),nHoy=iH>=0?m.totales[iH]:0;
  const sub=`<button class="bt v" data-ent="vencido" aria-pressed="${sel.includes('vencido')}" title="Todos los pedidos abiertos con entrega estimada anterior a hoy">Vencidos <b>${fmt(d.vencidos.n)}</b></button>`
    +`<button class="bt h" data-ent="hoy" aria-pressed="${sel.includes('hoy')}" title="Pedidos abiertos que vencen hoy">Vencen hoy <b>${fmt(nHoy)}</b></button>`
    +`<button class="bt" data-ent-tabla aria-pressed="${!!S.entTabla}" title="Ver las cifras exactas como tabla">${ico('pedidos',12)}${S.entTabla?'Ver gráfico':'Ver tabla'}</button>`;
  const lg=m.estados.map((e,i)=>`<button class="lg2" style="--c:${stVar(e)}" data-festado="${esc(e)}" aria-pressed="${(F.estado_ent||[]).includes(e)}" title="Clic: filtrar por este estado de entrega">${esc(e)} <b>${fmt((m.filas[i]||[]).reduce((a,b)=>a+b,0))}</b></button>`).join('');
  const cuerpo=!m.cols.length?vacio('Sin pedidos abiertos con fecha de entrega','Ajusta los filtros.')
    :(S.entTabla?tablaEntrega():`<div class="chart-wrap">${chartBox('cEnt','Pedidos abiertos por día de entrega estimada. Clic en una barra para filtrar todo el tablero con ese día.')}</div>`)+`<div class="lgd">${lg}</div>`;
  return card('a-ent','Entrega estimada de los pedidos abiertos',sub,cuerpo,'ent-b','vivo'+(sel.length?' tiene-sel':''));
}
/* ============ pantallas ============ */
function vistaPedidos(){
  const d=S.data;
  return `<div class="screen pedidos">
    ${barraRapida(true)}
    <div class="rail-col a-rail">${railTarjeta()}${railCausa()}</div>
    ${card('a-tabla','Detalle de pedidos',fmt(d.n_filtrado)+' pedidos'+(d.detalle.length>=500?', primeros 500':'')+descOrden('det')+`<button class="bt" data-ver-lista="det" title="Abre la lista completa">${ico('pedidos',12)}Ver todos</button>`,tablaDetalle(),'','vivo')}
    <div class="charts3 a-graf">${chartCard('','Pedidos por SLA Type','cSla',d.g_sla,'','','sla')}${chartCard('','Pedidos por Cliente','cCli',d.g_cli,'','','cliente')}${cardVentas()}</div>
    ${cardEntrega()}
  </div>`;
}
function vistaResumen(){
  const d=S.data,e=d.ejecutivo,cp=d.composicion,ci=d.cierre;
  const band=[kpiCard('% Ingreso',pct(e.pct_integracion.v),e.pct_integracion.d,'arriba'),
    kpiCard('% Pendiente',pct(e.pct_pendiente.v),e.pct_pendiente.d,'abajo'),
    kpiCard('% Cumplimiento Fecha Entrega',pct(e.pct_cumplimiento.v),null,'arriba',false,'solo canal BWS'),
    kpiCard('Antigüedad Prom Pendiente',e.antig_prom.v==null?'-':dec1(e.antig_prom.v),null,'abajo',false,'días'),
    kpiCard('% Facturado Sin Despacho',pct(e.pct_fac_sd.v),e.pct_fac_sd.d,'abajo'),
    kpiCard('Monto En Riesgo',money(e.monto_en_riesgo.v),null,'abajo',true,'no integrado + fact. sin desp.')].join('');
  const cuerpo=(ok,id,t,vt,vm)=>`<div class="chart-wrap">${ok?chartBox(id,t):vacio(vt,vm)}</div>`;
  const crit=d.tabla_criticos.slice(0,5),canales=(d.canal||[]).filter(c=>c.monto_riesgo>0);
  const critH=!crit.length?vacio('Nada facturado sin despacho','Ningún pedido pendiente tiene factura en SAP.')
    :crit.map(r=>`<button class="rc" data-pv="${esc(r.sequence)}" aria-haspopup="dialog" title="Ver las líneas del pedido"><span><span class="rs">${esc(r.sequence)}</span> <span class="rd">${esc(r.canal)}</span></span><span class="${r.dias>3?'down':'rd'}">${r.dias==null?'-':r.dias+' d'}</span><span class="rm">${money(r.monto)}</span></button>`).join('')
      +`<div class="crit-f"><button class="btn sm" data-ver-lista="crit">${ico('pedidos',14)}Ver los ${fmt(d.criticos_total.n)}</button></div>`;
  const sd=(ci.meses||[]).length;
  return `<div class="screen resumen">
    ${barraRapida(false)}
    <div class="kpis a-kpi">${band}</div>
    ${card('a-comp','Pedidos por mes y estado','% de cada mes · clic en un mes filtra todo',cuerpo(cp.meses.length,'cComp','Pedidos por mes y estado. Clic en un mes para filtrar todo el tablero.','','Sin datos para los filtros actuales'),'','vivo'+(mesSel()||diaSel()?' tiene-sel':''))}
    ${cardVentas('a-cla')}
    ${card('a-crit','Facturado en SAP, pendiente en VTEX',`${fmt(d.criticos_total.n)} pedidos, ${money(d.criticos_total.monto)}`,critH,'flush','')}
    ${card('a-canal','Monto en riesgo por canal',`<span id="sub-cCanal">${esc(S.subs.cCanal||'')}</span>`,`<div class="chart-wrap">${canales.length?chartBox('cCanal','Monto en riesgo por canal. Clic en una barra para filtrar todo el tablero.'):vacio('','Sin monto en riesgo')}</div>`,'','vivo'+(seleccion('canal').length?' tiene-sel':''))}
    ${card('a-cierre','% Cumplimiento al cierre y antigüedad al cierre por mes','solo meses ya cerrados',ci.meses.length===1?cierreUno(ci):cuerpo(ci.meses.length,'cCierre','% Cumplimiento al cierre y antigüedad promedio por mes','Aún no hay meses cerrados','Cuando termine un mes aparecerá aquí.'))}
  </div>`;
}
function cierreUno(ci){   // con un solo mes cerrado no hay curva que mostrar: se muestran sus dos cifras
  const c=ci.cumpl[0];
  return `<div class="solo"><div class="cap">${esc(mes(ci.meses[0]))}</div>
    <div class="solo-g"><div class="kpi"><div class="cap">% Cumplimiento al cierre</div><div class="val">${c==null?'-':pct(c)}</div></div>
    <div class="kpi"><div class="cap">Antigüedad prom. al cierre</div><div class="val">${ci.antig[0]==null?'-':dec1(ci.antig[0])}<small> días</small></div></div></div>
    <p class="muted">La curva aparece cuando haya dos meses cerrados.</p></div>`;
}
function vistaDiagnostico(){
  const d=S.data,m=d.matriz_dia;
  return `<div class="screen diag">
    ${barraRapida(false)}
    ${card('a-c2','Estado de los pedidos por día de creación',`<button class="bt" data-ver-lista="dia" title="Ver las cifras exactas por día">${ico('pedidos',12)}Ver tabla por día</button>`,`<div class="chart-wrap">${m.fechas.length?chartBox('cDiaEst','Estado de los pedidos por día de creación. Clic en una barra para filtrar todo el tablero con ese día.'):vacio('','Sin datos para los filtros actuales')}</div>`,'','vivo'+(diaSel()?' tiene-sel':''))}
    ${chartCard('a-c1','No integrados por cliente','cNoInt',d.g_noint,'Sin pedidos no integrados','Todo lo filtrado está en SAP.','cliente')}
    ${card('a-mx','Pedidos creados por día',fmt(d.n_filtrado)+' pedidos · clic en un día',calendarioCreacion(),'','vivo'+(diaSel()?' tiene-sel':''))}
    ${card('a-det','Detalle de pedidos',fmt(d.n_filtrado)+' pedidos'+descOrden('det')+`<button class="bt" data-ver-lista="det" title="Abre la lista completa">${ico('pedidos',12)}Ver todos</button>`,tablaDetalle(),'','vivo')}
  </div>`;
}
