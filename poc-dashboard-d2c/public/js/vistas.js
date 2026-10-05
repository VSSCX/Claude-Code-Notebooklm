/* vistas.js: barra de filtros, tablas y las tres pantallas (Pedidos VTEX, Resumen, Diagnóstico). Solo arman HTML. */
/* ============ riel y filtros ============ */
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
  if(f.alerta)act.push({bws:'Atención BWS',pos:'POST Fechado',mkp:'Atención MKP',fac:'Integración'}[f.alerta]);
  if(f.tarjeta)act.push({ing:'Órdenes Integradas',noing:'Órdenes Sin PV',canc:'Órdenes Canceladas'}[f.tarjeta]);
  ['canal','cliente','status','sla'].forEach(k=>{if(f[k][0])act.push(({canal:'Canal',cliente:'Cliente',status:'Status',sla:'SLA'})[k]+' '+f[k][0]);});
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
function tablaDetalle(){
  const d=S.data,rows=d.detalle;
  if(!rows.length)return vacio('Sin pedidos','Ningún pedido cumple los filtros actuales.');
  return `<table class="t"><thead><tr>${thOrd('det','sequence','Sequence')}${thOrd('det','pedido_sap','Pedido SAP')}${thOrd('det','estado','Estado')}${thOrd('det','canal','Canal')}${thOrd('det','sla','SLA Type','c-sla')}${thOrd('det','fecha','Creación','c-crea')}${thOrd('det','sed','Entrega est.')}${thOrd('det','monto','Monto','n c-monto')}</tr></thead><tbody>
  ${rows.map(r=>{const v=r.sed&&r.sed<d.hoy&&r.estado.includes('Pendiente');
   return `<tr id="r${esc(r.sequence)}" class="clic ${r.nuevo?'nw':''} ${S.dr&&S.dr.seq===r.sequence?'sel':''}" data-pv="${esc(r.sequence)}" tabindex="0" aria-haspopup="dialog" title="Clic: ver las líneas del pedido. ${esc(r.warehouse)}"><td class="num" translate="no">${esc(r.sequence)}${r.nuevo?'<span class="tag tagnew">NUEVO</span>':''}</td><td class="num">${esc(r.pedido_sap||'-')}</td><td>${pill(r.estado)}</td><td>${esc(r.canal)}</td><td class="ell c-sla" title="${esc(r.sla)}">${esc(r.sla)}</td><td class="c-crea">${fd(r.fecha)}</td><td class="${v?'venc':''}">${fd(r.sed)}</td><td class="n c-monto">${money(r.monto)}</td></tr>`;}).join('')}
</tbody></table>`;
}
function tablaEntrega(){
  const m=S.data.matriz_entrega;
  if(!m.cols.length)return vacio('Sin pedidos abiertos con fecha de entrega','Ajusta los filtros.');
  const th=m.cols.map(c=>`<th class="${c.rel<0?'v':c.rel===0?'h':''}">${esc(c.etq)}</th>`).join('');
  const fila=(e,i)=>`<tr><td class="f"><i style="background:${stVar(e)}"></i>${esc(e)}</td>${m.filas[i].map((v,j)=>{
    const c=m.cols[j]; if(!v)return '<td class="z">0</td>';
    const hl=e==='Integrado · Pendiente'?(c.rel<0?'hv':(c.rel===0?'hh':'vv')):'vv';
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
const card=(cls,titulo,sub,cuerpo,bcls='')=>`<section class="card ${cls}"><div class="card-h"><h2>${titulo}</h2>${sub?`<span class="sub">${sub}</span>`:''}</div><div class="card-b ${bcls}" tabindex="0">${cuerpo}</div></section>`;
const chartBox=(id,label)=>`<div class="chart-box"><canvas id="${id}" role="img" aria-label="${esc(label)}"></canvas></div>`;
const chartCard=(cls,titulo,id,data,vacioT,vacioM)=>card(cls,titulo,`<span id="sub-${id}">${esc(S.subs[id]||'')}</span>`,
  `<div class="chart-wrap">${data&&data.labels&&data.labels.length?chartBox(id,titulo):vacio(vacioT||'',vacioM||'Sin datos')}</div>`);

/* ============ vistas (mismo orden que el Power BI) ============ */
function vistaPedidos(){
  const d=S.data,t=d.tarjetas,a=d.alertas,F=S.filtros;
  const btn=(k,l,n,tip,crit)=>`<button class="mbtn ${crit?'crit':''}" data-alerta="${k}" aria-pressed="${F.alerta===k}" title="${esc(tip)}">${l}<b>${fmt(n)}</b></button>`;
  const botones=btn('bws','Atención BWS',a.bws,'BWS · listo para preparar · entrega estimada vencida (bodega EC01, sin SLA Servicios)')
    +btn('pos','POST Fechado',a.pos,'Bodega POST Fechado · listo para preparar')
    +btn('mkp','Atención MKP',a.mkp,'Marketplace · listo para preparar · creado hace 5 días o más')
    +btn('fac','Integración',a.fac,'Facturado en SAP y todavía pendiente en VTEX',true)
    +`<button class="mbtn limpiar" data-limpiar-vista title="Muestra todos los pedidos (igual que tu marcador Pedidos VTEX)">${ico('x',14)}Limpiar</button>`;
  const alc=F.buscar?'búsqueda en todos los estados y bodegas':(S.view==='pedidos'&&F.alcance==='abiertos'?'en seguimiento':'todos los estados');
  const trow=(l,v,k,c)=>`<button class="trow" style="--tc:${c}" data-tarjeta="${k}" aria-pressed="${k===''?F.tarjeta==null:F.tarjeta===k}"><i></i><span class="tn">${l}</span><span class="tv" data-v="${l}">${fmt(v)}</span></button>`;
  const tiles=trow('Órdenes VTEX',t['Órdenes VTEX'],'','var(--ink)')+trow('Órdenes Integradas',t['Órdenes Integradas'],'ing','var(--st-if)')
    +trow('Órdenes Sin PV',t['Órdenes Sin PV'],'noing','var(--st-nf)')
    +((t['Órdenes Canceladas']>0||F.tarjeta==='canc')?trow('Órdenes Canceladas',t['Órdenes Canceladas'],'canc','var(--st-ca)'):'');
  const cs=Object.entries(d.causa||{}).sort((a,b)=>b[1]-a[1]),cm=Math.max(1,...cs.map(e=>e[1]));
  const causa=cs.length?cs.map(([k,v])=>`<div class="crow" id="q${esc(k)}"><span>${esc(k)}</span><span class="cv">${fmt(v)}</span><span class="cb"><i style="width:${100*v/cm}%"></i></span></div>`).join(''):vacio('','Sin pendientes integrados');
  return `<div class="screen pedidos">
    <div class="marc a-marc">${botones}<span class="ctx"><b>${fmt(d.n_filtrado)}</b> pedidos, ${alc}</span></div>
    <div class="rail-col a-rail">
      <section class="card"><div class="tl-head cap"><span>Tarjeta</span><span>Órdenes</span></div>${tiles}</section>
      <section class="card"><div class="card-h"><h2>Causa pendiente</h2></div><div class="card-b flush" tabindex="0">${causa}</div></section>
    </div>
    ${card('a-tabla','Detalle de pedidos',fmt(d.n_filtrado)+' pedidos'+(d.detalle.length>=500?', primeros 500':'')+descOrden('det'),tablaDetalle())}
    <div class="charts3 a-graf">${chartCard('','Pedidos por SLA Type','cSla',d.g_sla)}${chartCard('','Pedidos por Cliente','cCli',d.g_cli)}${chartCard('','Pedidos por Warehouse','cWh',d.g_wh)}</div>
    ${card('a-entr','Matriz por día de entrega estimada','<span class="lg"><i class="r"></i>vencido</span><span class="lg"><i class="a"></i>vence hoy</span><span>(Integrado · Pendiente)</span>',tablaEntrega(),'fit')}
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
  return `<div class="screen resumen">
    <div class="kpis a-kpi">${band}</div>
    ${card('a-comp','Pedidos por mes y estado','% de los pedidos de cada mes',cuerpo(cp.meses.length,'cComp','Pedidos por mes y estado','','Sin datos para los filtros actuales'))}
    ${card('a-crit','Facturado en SAP, pendiente en VTEX',`${fmt(d.criticos_total.n)} pedidos, ${money(d.criticos_total.monto)}`,tablaCriticos())}
    ${card('a-canal','Riesgo por canal','',tablaCanal(),'fit')}
    ${card('a-cierre','% Cumplimiento al cierre y antigüedad prom. al cierre por mes','solo meses ya cerrados',ci.meses.length===1?cierreUno(ci):cuerpo(ci.meses.length,'cCierre','% Cumplimiento al cierre y antigüedad promedio por mes','Aún no hay meses cerrados','El primer punto aparece el día 1 del mes siguiente, cuando el mes termina.'))}
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
    ${chartCard('a-c1','No integrados por cliente','cNoInt',d.g_noint,'Sin pedidos no integrados','Todo lo filtrado está en SAP.')}
    ${card('a-c2','Estado de los pedidos por día','',`<div class="chart-wrap">${m.fechas.length?chartBox('cDiaEst','Estado de los pedidos por día'):vacio('','Sin datos para los filtros actuales')}</div>`)}
    ${card('a-mx','Pedidos por día de creación','por estado',tablaCreacion())}
    ${card('a-det','Detalle de pedidos',fmt(d.n_filtrado)+' pedidos'+descOrden('det'),tablaDetalle())}
  </div>`;
}

