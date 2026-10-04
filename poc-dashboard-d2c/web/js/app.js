/* Dashboard D2C · cruce VTEX vs SAP.
   El servidor entrega los datos ya calculados (/api/dashboard); aquí solo se pintan.
   Redibujado por diferencias (morphdom): una actualización en vivo no quita foco, scroll ni filtros,
   y los gráficos se actualizan en su lugar en vez de recrearse. */

/* ============ utilidades ============ */
const $=s=>document.querySelector(s);
const U=()=>S.u||1;
const fz=n=>Math.round(n*U()*10)/10;
const nf=new Intl.NumberFormat('es-CL'), nf1=new Intl.NumberFormat('es-CL',{maximumFractionDigits:1});
const fmt=n=>nf.format(Math.round(+n||0));
const dec1=v=>nf1.format(Math.round(v*10)/10);
const money=n=>{const v=+n||0,a=Math.abs(v);if(a>=1e6)return '$'+dec1(v/1e6)+' mill.';if(a>=1e3)return '$'+fmt(v/1e3)+' mil';return '$'+fmt(v);};
const pct=v=>v==null?'—':dec1(v*100)+'%';
const pctD=v=>v==null?'—':(v>=0?'+':'−')+dec1(Math.abs(v*100))+' pp';
const esc=v=>String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fd=s=>s?s.slice(8,10)+'-'+s.slice(5,7)+'-'+s.slice(2,4):'—';
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const mes=m=>{const t=new Date(m+'-01T12:00:00').toLocaleDateString('es-CL',{month:'long',year:'numeric'});return t.charAt(0).toUpperCase()+t.slice(1);};
const dia=(f,conAnio=true)=>{const d=new Date(f+'T12:00:00');return d.toLocaleDateString('es-CL',{weekday:'short'}).replace('.','')+' '+(conAnio?fd(f):fd(f).slice(0,5));};
const vacio=(t,m)=>`<div class="empty"><div>${t?`<h3>${t}</h3>`:''}${m||''}</div></div>`;
const guardar=(k,v)=>{try{localStorage.setItem('d2c.'+k,v);}catch(e){}};
const leer=k=>{try{return localStorage.getItem('d2c.'+k);}catch(e){return null;}};

/* íconos: un solo trazo (1.75) sobre rejilla de 24 */
const P={
  up:'<path d="M5 14l7-7 7 7"/>',down:'<path d="M5 10l7 7 7-7"/>',flat:'<path d="M5 12h14"/>',
  x:'<path d="M6 6l12 12M18 6L6 18"/>',plus:'<path d="M12 5v14M5 12h14"/>',check:'<path d="M5 12.5l4.5 4.5L19 7"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
  moon:'<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
  auto:'<rect x="3" y="4" width="18" height="12" rx="1"/><path d="M8 20h8M12 16v4"/>',
  tv:'<rect x="2.5" y="5" width="19" height="12.5" rx="1"/><path d="M8 21h8"/>',
  alert:'<path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5M12 17.5h.01"/>',
  asc:'<path d="M7 14l5-5 5 5"/>',desc:'<path d="M7 10l5 5 5-5"/>',both:'<path d="M8 9l4-4 4 4M8 15l4 4 4-4"/>'};
const ico=(k,s=16)=>`<svg class="i" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[k]}</svg>`;

/* los cinco estados de un pedido: el color vive en los tokens (--st-*), así sigue al tema */
const ST={"Integrado · Facturado":'--st-if',"Integrado · Pendiente":'--st-ip',"No integrado · Facturado":'--st-nf',"No integrado · Pendiente":'--st-np',"Cancelado":'--st-ca'};
const stVar=e=>`var(${ST[e]||'--edge'})`, stClr=e=>css(ST[e]||'--edge');
const PILL={"Integrado · Facturado":"g","Integrado · Pendiente":"b","No integrado · Facturado":"r","No integrado · Pendiente":"a","Cancelado":"n"};
const pill=e=>`<span class="tag ${PILL[e]||'n'}">${esc(e)}</span>`;
const lum=h=>{const n=parseInt(h.slice(1),16),f=c=>{c/=255;return c<=.03928?c/12.92:Math.pow((c+.055)/1.055,2.4);};return .2126*f(n>>16)+.7152*f(n>>8&255)+.0722*f(n&255);};
const onClr=h=>lum(h)>.3?'#12171C':'#FFFFFF';

/* ============ estado y marcadores (replican los bookmarks del Power BI) ============ */
const BASE=['EC01','POS_Fechado'];
const INICIAL=()=>({alerta:null,tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'abiertos'});
const MARC={ // cada boton fija su propio alcance, igual que el marcador correspondiente
  bws:{alerta:'bws',tarjeta:null,bodega:['EC01'],sla_excluir:['Servicios'],alcance:'todos'},
  pos:{alerta:'pos',tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'},
  mkp:{alerta:'mkp',tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'},
  fac:{alerta:'fac',tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'}};
const LIMPIAR={alerta:null,tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'}; // = marcador "Pedidos VTEX"
const VISTAS=['pedidos','resumen','diagnostico'];
const S={u:1,orden:{det:null,crit:null,canal:null},data:null,version:'',view:VISTAS.includes(leer('vista'))?leer('vista'):'pedidos',poll:5,opts:null,req:0,err:null,mon:null,revisadoAt:null,
  vistos:new Set(),vistosInit:false,prevTarj:null,filtros:null,
  tema:['light','dark'].includes(leer('tema'))?leer('tema'):'auto',tv:leer('tv')==='1',subs:{},pintada:null};
const VACIO=()=>({canal:[],cliente:[],status:[],sla:[],buscar:'',
  fecha_ini:S.opts?S.opts.fecha_min:null,fecha_fin:S.opts?S.opts.fecha_max:null,...INICIAL()});
S.filtros=VACIO();

/* ============ redibujado por diferencias ============ */
function morph(el,html){
  const to=el.cloneNode(false);to.innerHTML=html;
  morphdom(el,to,{childrenOnly:true,
    onBeforeElUpdated(f,t){
      if(f.nodeName==='CANVAS')return false;                              // el gráfico se actualiza aparte
      if(f===document.activeElement&&f.nodeName==='INPUT')return false;   // no pisar lo que se está escribiendo
      return !f.isEqualNode(t);}});
}

/* ============ carga ============ */
async function cargar(){
  const id=++S.req; $('#stage').classList.add('loading');
  const body={...S.filtros}; if(S.view!=='pedidos') body.alcance='todos';
  if(body.buscar){body.alcance='todos';body.bodega=[];}   // una busqueda puntual ignora el alcance y la bodega
  body.orden_det=S.orden.det;body.orden_crit=S.orden.crit;   // el orden se aplica en el servidor sobre TODO el conjunto
  try{
    const r=await fetch('/api/dashboard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json(); if(id!==S.req)return;
    $('#stage').classList.remove('loading');
    if(j.error&&!j.kpi){S.err=j.error;render();return;}
    avisarLlegadas(j);
    S.prevTarj=S.data?S.data.tarjetas:null;
    S.data=j;S.version=j.version;S.err=j.error||null;
    render();
  }catch(e){
    if(id!==S.req)return; $('#stage').classList.remove('loading');
    S.err='No hay conexión con el servidor. ¿Está corriendo el dashboard (run.bat)?';render();
  }
}
async function poll(){
  try{
    const j=await(await fetch('/api/version')).json();
    S.mon=j; S.revisadoAt=j.revisado==null?null:Date.now()-j.revisado*1000;
    if(j.cargado&&j.version&&j.version!==S.version) await cargar(); else renderLive();
  }catch(e){S.mon=null;renderLive();}
}
function renderLive(){
  const el=$('#sync'); if(!el)return;
  let dot='ok',l1,l2='';
  if(!S.mon){dot='err';l1='Sin conexión con el servidor';}
  else if(S.mon.error&&S.mon.estado==='lento'){dot='warn';l1='Se actualiza cada '+S.mon.respaldo_min+' min · datos de las '+esc(S.mon.consulta||'—');l2='La detección rápida de pedidos nuevos falló: '+esc(S.mon.error).slice(0,48);}
  else if(S.mon.error){dot='err';l1='Sin acceso a las bases'+(S.mon.consulta?' · mostrando datos de las '+esc(S.mon.consulta):'');l2=esc(S.mon.error).slice(0,70);}
  else{
    const seg=S.revisadoAt==null?null:Math.max(0,Math.round((Date.now()-S.revisadoAt)/1000));
    l1='En vivo'+(seg==null?'':' · revisado hace '+seg+' s');
    if(S.data&&S.data.ultimo_pedido) l2='Último pedido VTEX '+esc(S.data.ultimo_pedido);
  }
  morph(el,`<div class="l1"><span class="dot ${dot}"></span><span>${l1}</span></div>${l2?`<div class="l2">${l2}</div>`:''}`);
}

/* ============ avisos de pedidos nuevos ============ */
function toast(titulo,sub){
  const t=document.createElement('div');t.className='toast';
  t.innerHTML=`<span class="tp">${ico('plus',18)}</span><div>${esc(titulo)}${sub?`<small>${esc(sub)}</small>`:''}</div>`;
  $('#toasts').appendChild(t);
  setTimeout(()=>{t.classList.add('sale');setTimeout(()=>t.remove(),180);},7000);
}
function avisarLlegadas(j){
  const ll=j.llegadas||[]; const nuevas=ll.filter(x=>!S.vistos.has(x.seq));
  if(S.vistosInit&&nuevas.length){
    const n=nuevas.length,p=nuevas[0];
    toast(`${n} pedido${n>1?'s':''} nuevo${n>1?'s':''} en VTEX`,`${p.canal} · Sequence ${p.seq}${n>1?` y ${n-1} más`:''}`);
  }
  ll.forEach(x=>S.vistos.add(x.seq)); S.vistosInit=true;
}

/* ============ riel y filtros ============ */
async function cargarOpts(){
  try{S.opts=await(await fetch('/api/filtros')).json();S.filtros.fecha_ini=S.opts.fecha_min;S.filtros.fecha_fin=S.opts.fecha_max;}catch(e){S.opts=null;}
  renderSlicers();
}
function renderSlicers(){
  const el=$('#slicers');
  if(!S.opts||S.opts.error){morph(el,'');return;}
  const o=S.opts,f=S.filtros;
  const sel=(k,l,arr)=>`<div class="sl"><label for="sl-${k}">${l}</label><select id="sl-${k}" data-sl="${k}"><option value="">Todas</option>${(arr||[]).map(v=>`<option value="${esc(v)}" ${f[k][0]===v?'selected':''}>${esc(v)}</option>`).join('')}</select></div>`;
  const igual=(a,b)=>a.length===b.length&&a.every(x=>b.includes(x));
  const bv=igual(f.bodega,BASE)?'__base':(f.bodega.length===0?'__todas':f.bodega[0]);
  const bodega=`<div class="sl"><label for="sl-bodega">Bodega</label><select id="sl-bodega" data-bodega>
    <option value="__base" ${bv==='__base'?'selected':''}>EC01 + POS</option><option value="__todas" ${bv==='__todas'?'selected':''}>Todas</option>
    ${(o.bodega||[]).map(v=>`<option value="${esc(v)}" ${bv===v?'selected':''}>${esc(v)}</option>`).join('')}</select></div>`;
  const alcance=S.view==='pedidos'?`<div class="sl"><label for="sl-alcance">Alcance</label><select id="sl-alcance" data-alcance>
    <option value="abiertos" ${f.alcance==='abiertos'?'selected':''}>En seguimiento</option><option value="todos" ${f.alcance==='todos'?'selected':''}>Todos (con cerrados)</option></select></div>`:'';
  morph(el,sel('canal','Canal',o.canal)+sel('cliente','Cliente',o.cliente)+sel('status','Status',o.status)+sel('sla','SLA Type',o.sla)+bodega+alcance
   +`<div class="sl d"><label for="sl-ini">Creación desde</label><input id="sl-ini" type="date" data-fecha="ini" value="${f.fecha_ini||''}" min="${o.fecha_min}" max="${o.fecha_max}"></div>`
   +`<div class="sl d"><label for="sl-fin">Creación hasta</label><input id="sl-fin" type="date" data-fecha="fin" value="${f.fecha_fin||''}" min="${o.fecha_min}" max="${o.fecha_max}"></div>`
   +`<div class="sl q"><label for="sl-q">Buscar pedido</label><input id="sl-q" type="search" data-buscar placeholder="Sequence, SAP u Order" value="${esc(f.buscar)}"></div>`
   +`<button class="btn" data-limpiar-sl title="Vuelve a la vista inicial">Restablecer</button>`);
}
function renderNav(){
  const it=[['pedidos','Pedidos VTEX'],['resumen','Resumen ejecutivo'],['diagnostico','Diagnóstico']];
  morph($('#nav'),it.map(([v,t])=>`<button data-go="${v}" ${S.view===v?'aria-current="page"':''}>${t}</button>`).join(''));
}
function renderTools(){
  const tm=[['auto','Tema del sistema','auto'],['light','Tema claro','sun'],['dark','Tema oscuro','moon']];
  morph($('#tools'),`<div class="seg" role="group" aria-label="Tema">${tm.map(([k,t,i])=>`<button data-tema="${k}" aria-pressed="${S.tema===k}" title="${t}" aria-label="${t}">${ico(i)}</button>`).join('')}</div>
    <button class="rbtn" data-tv aria-pressed="${S.tv}" title="Pantalla grande: letra mayor, sin filtros">${ico('tv')}Modo TV</button>`);
}

/* ============ piezas ============ */
function kpiCard(lab,val,d,mejor,risk,nota){
  let dH=`<div class="dlt flat">${nota||'sin mes anterior'}</div>`;
  if(d!=null){const b=mejor==='arriba'?d>=0:d<=0;const c=d===0?'flat':(b?'up':'down');dH=`<div class="dlt ${c}">${ico(d>0?'up':d<0?'down':'flat',14)}${pctD(Math.abs(d))} vs mes ant.</div>`;}
  return `<div class="kpi ${risk?'risk':''}"><div class="lab cap" title="${esc(lab)}">${esc(lab)}</div><div class="val">${val}</div>${dH}</div>`;
}
const NOMBRE_COL={sequence:'Sequence',pedido_sap:'Pedido SAP',estado:'Estado',canal:'Canal',sla:'SLA Type',fecha:'Creación',sed:'Entrega est.',monto:'Monto',dias:'Días facturado pendiente',vigentes:'Vigentes',pct_pendiente:'% Pendiente',monto_riesgo:'Monto en riesgo'};
function thOrd(tabla,col,txt,cls=''){
  const o=S.orden[tabla],on=o&&o.col===col,ar=on?(o.dir==='asc'?'asc':'desc'):'both';
  const tip=on?(o.dir==='asc'?'Orden ascendente. Clic: descendente':'Orden descendente. Clic: quitar orden'):'Clic: ordenar ascendente';
  return `<th class="ord ${cls} ${on?'on':''}" tabindex="0" scope="col" ${on?`aria-sort="${o.dir==='asc'?'ascending':'descending'}"`:''} data-tabla="${tabla}" data-ord="${col}" title="${tip}"><div class="thw"><span>${txt}</span><span class="ar">${ico(ar,12)}</span></div></th>`;
}
const descOrden=tabla=>{const o=S.orden[tabla];return o?` · orden: ${NOMBRE_COL[o.col]} ${o.dir==='asc'?'ascendente':'descendente'}`:'';};
function tablaDetalle(){
  const d=S.data,rows=d.detalle;
  if(!rows.length)return vacio('Sin pedidos','Ningún pedido cumple los filtros actuales.');
  return `<table class="t"><thead><tr>${thOrd('det','sequence','Sequence')}${thOrd('det','pedido_sap','Pedido SAP')}${thOrd('det','estado','Estado')}${thOrd('det','canal','Canal')}${thOrd('det','sla','SLA Type')}${thOrd('det','fecha','Creación','c-crea')}${thOrd('det','sed','Entrega est.')}${thOrd('det','monto','Monto','n c-monto')}</tr></thead><tbody>
  ${rows.map(r=>{const v=r.sed&&r.sed<d.hoy&&r.estado.includes('Pendiente');
   return `<tr id="r${esc(r.sequence)}" class="${r.nuevo?'nw':''}" title="Monto: ${money(r.monto)} · ${esc(r.warehouse)}"><td class="num">${esc(r.sequence)}${r.nuevo?'<span class="tag tagnew">NUEVO</span>':''}</td><td class="num">${esc(r.pedido_sap||'—')}</td><td>${pill(r.estado)}</td><td>${esc(r.canal)}</td><td class="ell" title="${esc(r.sla)}">${esc(r.sla)}</td><td class="c-crea">${fd(r.fecha)}</td><td class="${v?'venc':''}">${fd(r.sed)}</td><td class="n c-monto">${money(r.monto)}</td></tr>`;}).join('')}
</tbody></table>`;
}
function tablaEntrega(){
  const m=S.data.matriz_entrega;
  if(!m.cols.length)return vacio('Sin pedidos abiertos con fecha de entrega','Ajusta los filtros.');
  const th=m.cols.map(c=>`<th class="${c.rel<0?'v':c.rel===0?'h':''}">${esc(c.etq)}</th>`).join('');
  const fila=(e,i)=>`<tr><td class="f"><i style="background:${stVar(e)}"></i>${esc(e)}</td>${m.filas[i].map((v,j)=>{
    const c=m.cols[j]; if(!v)return '<td class="z">·</td>';
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
  const cel=(v,j)=>v?`<td style="background:color-mix(in srgb,${stVar(m.columnas[j])} ${Math.round(14+46*v/mx[j])}%,transparent)">${fmt(v)}</td>`:'<td class="z">0</td>';
  return `<table class="mx"><thead><tr><th class="f">Día</th>${m.columnas.map(c=>`<th title="${esc(c)}"><i style="background:${stVar(c)}"></i><span class="fl">${esc(c).replace(' · ','<br>')}</span><span class="ab">${AB[c]||esc(c)}</span></th>`).join('')}<th>Total</th></tr></thead><tbody>
  <tr class="fin arriba"><td class="f">Total</td>${m.totales_col.map(v=>`<td>${fmt(v)}</td>`).join('')}<td>${fmt(m.total)}</td></tr>
  ${m.fechas.map((f,i)=>`<tr id="d${f}"><td class="f">${esc(dia(f,anios))}</td>${m.filas[i].map(cel).join('')}<td class="tot">${fmt(m.totales_fila[i])}</td></tr>`).join('')}</tbody></table>`;
}
function tablaCriticos(){
  const t=S.data.tabla_criticos;
  if(!t.length)return vacio('Nada facturado sin despacho','Ningún pedido pendiente tiene factura en SAP.');
  return `<table class="t"><thead><tr>${thOrd('crit','sequence','Sequence')}${thOrd('crit','canal','Canal')}${thOrd('crit','dias','Días facturado pendiente','n')}${thOrd('crit','monto','Monto','n')}</tr></thead><tbody>
  ${t.map(r=>`<tr id="c${esc(r.sequence)}"><td class="num">${esc(r.sequence)}</td><td>${esc(r.canal)}</td><td class="n ${r.dias>3?'down':''}">${r.dias??'—'}</td><td class="n">${money(r.monto)}</td></tr>`).join('')}
</tbody></table>`;
}
function tablaCanal(){
  let c=S.data.canal; if(!c.length)return vacio('Sin datos');
  const oc=S.orden.canal;
  if(oc){c=[...c].sort((a,b)=>{const x=a[oc.col],y=b[oc.col];if(x==null)return 1;if(y==null)return -1;const r=typeof x==='string'?x.localeCompare(y,'es'):x-y;return oc.dir==='asc'?r:-r;});}
  const V=c.reduce((a,r)=>a+r.vigentes,0),P_=c.reduce((a,r)=>a+r.pendientes,0),M=c.reduce((a,r)=>a+r.monto_riesgo,0);
  return `<table class="t"><thead><tr>${thOrd('canal','canal','Canal')}${thOrd('canal','vigentes','Pedidos vigentes mes actual','n')}${thOrd('canal','pct_pendiente','% Pendiente','n')}${thOrd('canal','monto_riesgo','Monto en riesgo','n')}</tr></thead><tbody>
  ${c.map(r=>`<tr id="k${esc(r.canal)}"><td><b>${esc(r.canal)}</b></td><td class="n">${fmt(r.vigentes)}</td><td class="n">${pct(r.pct_pendiente)}</td><td class="n">${money(r.monto_riesgo)}</td></tr>`).join('')}
  <tr class="fin"><td>Total</td><td class="n">${fmt(V)}</td><td class="n">${pct(V?P_/V:null)}</td><td class="n">${money(M)}</td></tr></tbody></table>`;
}
const card=(cls,titulo,sub,cuerpo,bcls='')=>`<section class="card ${cls}"><div class="card-h"><h2>${titulo}</h2>${sub?`<span class="sub">${sub}</span>`:''}</div><div class="card-b ${bcls}">${cuerpo}</div></section>`;
const chartBox=(id,label)=>`<div class="chart-box"><canvas id="${id}" role="img" aria-label="${esc(label)}"></canvas></div>`;
const chartCard=(cls,titulo,id,data,vacioT,vacioM)=>card(cls,titulo,`<span id="sub-${id}">${esc(S.subs[id]||'')}</span>`,
  `<div class="chart-wrap">${data&&data.labels&&data.labels.length?chartBox(id,titulo):vacio(vacioT||'',vacioM||'Sin datos')}</div>`);

/* ============ vistas (mismo orden que el Power BI) ============ */
function vistaPedidos(){
  const d=S.data,t=d.tarjetas,a=d.alertas,F=S.filtros;
  const btn=(k,l,n,tip,crit)=>`<button class="mbtn ${crit?'crit':''}" data-alerta="${k}" aria-pressed="${F.alerta===k}" title="${esc(tip)}"><i></i>${l}<b>${fmt(n)}</b></button>`;
  const botones=btn('bws','Atención BWS',a.bws,'BWS · listo para preparar · entrega estimada vencida (bodega EC01, sin SLA Servicios)')
    +btn('pos','POS Fechado',a.pos,'Bodega POS Fechado · listo para preparar')
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
    <div class="marc a-marc">${botones}<span class="ctx"><b>${fmt(d.n_filtrado)}</b> pedidos · ${alc}</span></div>
    <div class="rail-col a-rail">
      <section class="card"><div class="tl-head cap"><span>Tarjeta</span><span>Órdenes</span></div>${tiles}</section>
      <section class="card"><div class="card-h"><h2>Causa pendiente</h2></div><div class="card-b flush">${causa}</div></section>
    </div>
    ${card('a-tabla','Detalle de pedidos',fmt(d.n_filtrado)+' pedidos'+(d.detalle.length>=500?' · primeros 500':'')+descOrden('det'),tablaDetalle())}
    <div class="charts3 a-graf">${chartCard('','Pedidos por SLA Type','cSla',d.g_sla)}${chartCard('','Pedidos por Cliente','cCli',d.g_cli)}${chartCard('','Pedidos por Warehouse','cWh',d.g_wh)}</div>
    ${card('a-entr','Matriz por día de entrega estimada','<span class="lg"><i class="r"></i>vencido</span><span class="lg"><i class="a"></i>vence hoy</span><span>(Integrado · Pendiente)</span>',tablaEntrega(),'fit')}
  </div>`;
}
function vistaResumen(){
  const d=S.data,e=d.ejecutivo,cp=d.composicion,ci=d.cierre;
  const band=[kpiCard('% Ingreso',pct(e.pct_integracion.v),e.pct_integracion.d,'arriba'),
    kpiCard('% Pendiente',pct(e.pct_pendiente.v),e.pct_pendiente.d,'abajo'),
    kpiCard('% Cumplimiento Fecha Entrega',pct(e.pct_cumplimiento.v),null,'arriba',false,'solo canal BWS'),
    kpiCard('Antigüedad Prom Pendiente',e.antig_prom.v==null?'—':dec1(e.antig_prom.v),null,'abajo',false,'días'),
    kpiCard('% Facturado Sin Despacho',pct(e.pct_fac_sd.v),e.pct_fac_sd.d,'abajo'),
    kpiCard('Monto En Riesgo',money(e.monto_en_riesgo.v),null,'abajo',true,'no integrado + fact. sin desp.')].join('');
  const cuerpo=(ok,id,t,vt,vm)=>`<div class="chart-wrap">${ok?chartBox(id,t):vacio(vt,vm)}</div>`;
  return `<div class="screen resumen">
    <div class="kpis a-kpi">${band}</div>
    ${card('a-comp','Pedidos por mes y estado','% de los pedidos de cada mes',cuerpo(cp.meses.length,'cComp','Pedidos por mes y estado','','Sin datos para los filtros actuales'))}
    ${card('a-crit','Facturado en SAP, pendiente en VTEX',`${fmt(d.criticos_total.n)} pedidos · ${money(d.criticos_total.monto)}`,tablaCriticos())}
    ${card('a-canal','Riesgo por canal','',tablaCanal(),'fit')}
    ${card('a-cierre','% Cumplimiento al cierre y antigüedad prom. al cierre por mes','solo meses ya cerrados',cuerpo(ci.meses.length,'cCierre','% Cumplimiento al cierre y antigüedad promedio por mes','Aún no hay meses cerrados','El primer punto aparece el día 1 del mes siguiente, cuando el mes termina.'))}
  </div>`;
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

/* ============ graficos (se actualizan en su lugar; los colores salen de los tokens del tema) ============ */
const charts={};
const fam=()=>getComputedStyle(document.body).fontFamily;
const _mc=document.createElement('canvas').getContext('2d');
const cutPx=(l,px,sz=fz(10.5))=>{_mc.font=sz+'px '+fam();if(_mc.measureText(l).width<=px)return l;let s=l;while(s.length>1&&_mc.measureText(s+'…').width>px)s=s.slice(0,-1);return s.trimEnd()+'…';};
const valueLabels={id:'valueLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='600 '+fz(10.5)+'px '+fam();c.fillStyle=css('--ink-2');c.textBaseline='middle';
  ch.getDatasetMeta(0).data.forEach((b,i)=>c.fillText(fmt(ch.data.datasets[0].data[i]),b.x+fz(5),b.y));c.restore();}};
const segLabels={id:'segLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='700 '+fz(10.5)+'px '+fam();c.textAlign='center';c.textBaseline='middle';
  ch.data.datasets.forEach((ds,di)=>{c.fillStyle=onClr(ds.backgroundColor);ch.getDatasetMeta(di).data.forEach((b,i)=>{
    const v=ds.data[i],w=Math.abs(b.x-b.base);if(v>=7&&w>fz(34))c.fillText(dec1(v)+'%',(b.x+b.base)/2,b.y);});});c.restore();}};
const pointLabels={id:'pointLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='700 '+fz(11)+'px '+fam();c.textAlign='center';
  ch.data.datasets.forEach((ds,di)=>{c.fillStyle=ds.borderColor;ch.getDatasetMeta(di).data.forEach((p,i)=>{
    const v=ds.data[i];if(v==null)return;c.fillText(ds.fmt(v),p.x,p.y-(di?-fz(18):fz(13)));});});c.restore();}};
const baseO=()=>({responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
  scales:{x:{ticks:{color:css('--muted'),font:{size:fz(10.5)}},grid:{color:css('--hair')},border:{display:false}},
          y:{ticks:{color:css('--muted'),font:{size:fz(10.5)}},grid:{display:false},border:{display:false}}}});
const leyenda=()=>({display:true,position:'bottom',labels:{color:css('--ink-2'),font:{size:fz(10.5)},boxWidth:fz(10),boxHeight:fz(10),usePointStyle:true,pointStyle:'rect',padding:fz(12)}});
const ejeFecha=()=>({color:css('--muted'),font:{size:fz(10.5)},maxTicksLimit:12,maxRotation:0,callback:function(v){return fd(this.getLabelForValue(v)).slice(0,5);}});

function grafico(id,cfg){
  const el=document.getElementById(id); if(!el)return;
  const ex=charts[id];
  if(ex&&ex.canvas===el&&ex.config.type===cfg.type){ex.data=cfg.data;ex.options=cfg.options;ex.update('none');return;}
  if(ex)ex.destroy();
  charts[id]=new Chart(el,cfg);
}
function miniBar(id,data,color){
  const el=document.getElementById(id);if(!el||!data||!data.labels.length)return;
  const n=Math.max(3,Math.floor(el.parentElement.clientHeight/fz(17)));
  const L=data.labels.slice(0,n),V=data.valores.slice(0,n);
  const sub=data.total>L.length?`top ${L.length} de ${data.total}`:'';
  S.subs[id]=sub;const se=document.getElementById('sub-'+id);if(se)se.textContent=sub;
  const o=baseO();o.indexAxis='y';o.layout={padding:{right:fz(36)}};
  const maxPx=Math.max(fz(48),((el.parentElement.clientWidth-fz(36))/2)-fz(18));
  o.scales.x={display:false,beginAtZero:true};
  o.scales.y.ticks={autoSkip:false,color:css('--ink-2'),font:{size:fz(10.5)},padding:fz(4),callback:function(v){return cutPx(this.getLabelForValue(v),maxPx);}};
  o.plugins.tooltip={callbacks:{title:i=>L[i[0].dataIndex]}};
  grafico(id,{type:'bar',data:{labels:L,datasets:[{data:V,backgroundColor:color,borderRadius:2,barPercentage:.74,categoryPercentage:.92,maxBarThickness:fz(20)}]},options:o,plugins:[valueLabels]});
}
function pintar(){
  const d=S.data;if(!d)return;
  Chart.defaults.font.family=fam();Chart.defaults.color=css('--muted');
  const ink2=css('--ink-2');
  if(S.view==='pedidos'){miniBar('cSla',d.g_sla,ink2);miniBar('cCli',d.g_cli,ink2);miniBar('cWh',d.g_wh,css('--edge'));}
  if(S.view==='resumen'){
    const cp=d.composicion;
    if(document.getElementById('cComp')&&cp.meses.length){
      const P_=cp.filas.map(f=>{const t=f.reduce((a,b)=>a+b,0)||1;return f.map(x=>100*x/t);});
      const o=baseO();o.indexAxis='y';o.plugins.legend=leyenda();
      o.scales.x.stacked=true;o.scales.x.max=100;o.scales.x.ticks={color:css('--muted'),font:{size:fz(10.5)},callback:v=>v+'%'};
      o.scales.y.stacked=true;o.scales.y.ticks={autoSkip:false,color:css('--ink-2'),font:{size:fz(11.5),weight:'600'}};
      o.plugins.tooltip={callbacks:{label:c=>` ${c.dataset.label}: ${fmt(cp.filas[c.dataIndex][c.datasetIndex])} (${dec1(c.raw)}%)`}};
      grafico('cComp',{type:'bar',data:{labels:cp.meses.map(mes),datasets:cp.columnas.map((col,i)=>({label:col,data:P_.map(r=>r[i]),backgroundColor:stClr(col),maxBarThickness:fz(42),borderSkipped:false}))},options:o,plugins:[segLabels]});
    }
    const ci=d.cierre;
    if(document.getElementById('cCierre')&&ci.meses.length){
      const c1=css('--ink'),c2=css('--sched');
      const o=baseO();o.plugins.legend=leyenda();o.layout={padding:{top:fz(18),left:fz(4),right:fz(4)}};
      o.scales.x.grid={display:false};o.scales.x.offset=true;
      o.scales.y={position:'left',min:0,max:100,ticks:{color:c1,font:{size:fz(10.5)},callback:v=>v+'%'},grid:{color:css('--hair')},border:{display:false},title:{display:true,text:'% Cumplimiento al cierre',color:c1,font:{size:fz(10.5)}}};
      o.scales.y1={position:'right',min:0,ticks:{color:c2,font:{size:fz(10.5)}},grid:{display:false},border:{display:false},title:{display:true,text:'Antigüedad prom. (días)',color:c2,font:{size:fz(10.5)}}};
      const ds=(label,data,color,eje,f)=>({label,data,yAxisID:eje,borderColor:color,backgroundColor:color,borderWidth:fz(2.5),pointRadius:fz(5),pointHoverRadius:fz(6),tension:.2,spanGaps:true,fmt:f});
      grafico('cCierre',{type:'line',data:{labels:ci.meses.map(mes),datasets:[
        ds('% Cumplimiento al cierre',ci.cumpl.map(v=>v==null?null:v*100),c1,'y',v=>dec1(v)+'%'),
        ds('Antigüedad prom. al cierre (días)',ci.antig,c2,'y1',v=>dec1(v)+' d')]},options:o,plugins:[pointLabels]});
    }
  }
  if(S.view==='diagnostico'){
    miniBar('cNoInt',d.g_noint,css('--err'));
    const m=d.matriz_dia;
    if(document.getElementById('cDiaEst')&&m.fechas.length){
      const o=baseO();o.plugins.legend=leyenda();o.scales.x.stacked=true;o.scales.y.stacked=true;o.scales.x.grid={display:false};o.scales.x.ticks=ejeFecha();
      o.plugins.tooltip={callbacks:{title:i=>dia(m.fechas[i[0].dataIndex])}};
      grafico('cDiaEst',{type:'bar',data:{labels:m.fechas,datasets:m.columnas.map((col,i)=>({label:col,data:m.filas.map(f=>f[i]),backgroundColor:stClr(col),borderSkipped:false}))},options:o});
    }
  }
  for(const id of Object.keys(charts)){if(!charts[id].canvas.isConnected){charts[id].destroy();delete charts[id];}}   // gráficos de pantallas que ya no están
}

/* ============ escala: el tablero se ajusta a la ventana (como "ajustar a la pagina" de Power BI) ============ */
function ajustarEscala(){
  let u=1;
  if(innerWidth>=900){const rw=S.tv?1280:1440,rh=S.tv?720:800;u=Math.max(.55,Math.min(2.8,Math.min(innerWidth/rw,innerHeight/rh)));}   // el modo TV parte de un lienzo menor: todo sale mayor
  if(Math.abs(u-S.u)<0.01)return false;
  S.u=u;document.documentElement.style.setProperty('--u',u.toFixed(3));return true;
}
function marcarAncho(){   // columnas que se ocultan si la tarjeta queda angosta (umbrales escalados)
  const u=U();
  document.querySelectorAll('.card').forEach(c=>{const w=c.clientWidth;
    c.classList.toggle('no-monto',w<800*u);c.classList.toggle('no-crea',w<660*u);c.classList.toggle('mx-ab',w<440*u);});
}

/* ============ render ============ */
function render(){
  renderNav();renderLive();renderTools();
  const b=$('#banner');
  morph(b,S.err?`${ico('alert')}<span>${esc(S.err)}${S.data?' · se muestran los últimos datos.':''}</span>`:'');
  b.className=S.err?'on':'';
  const app=$('#app');
  if(!S.data){app.innerHTML=`<div class="splash">${S.err?'No se pudieron cargar los datos.':'Cargando datos de VTEX y SAP…'}</div>`;S.pintada=null;return;}
  const html=S.view==='pedidos'?vistaPedidos():S.view==='resumen'?vistaResumen():vistaDiagnostico();
  if(S.pintada!==S.view){app.innerHTML=html;S.pintada=S.view;}   // otra pantalla: se arma de cero; la misma: solo cambia lo que cambió
  else morph(app,html);
  if(S.prevTarj&&S.view==='pedidos'){ // destello en las cifras que cambiaron (pedido nuevo, cambio de estado)
    document.querySelectorAll('.trow .tv').forEach(el=>{const k=el.dataset.v;if(S.prevTarj[k]!==undefined&&S.prevTarj[k]!==S.data.tarjetas[k]){const r=el.closest('.trow');r.classList.remove('flash');void r.offsetWidth;r.classList.add('flash');}});
  }
  marcarAncho();
  requestAnimationFrame(()=>(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(pintar));
}
function aplicarTema(){
  const d=document.documentElement;
  if(S.tema==='auto')delete d.dataset.theme;else d.dataset.theme=S.tema;
  guardar('tema',S.tema);
}
function aplicarTV(){
  document.documentElement.classList.toggle('tv',S.tv);guardar('tv',S.tv?'1':'0');
  ajustarEscala();
}
function irA(v){S.view=v;guardar('vista',v);S.pintada=null;renderNav();renderSlicers();if(S.data)render();cargar();}

/* ============ eventos ============ */
document.addEventListener('click',ev=>{
  const g=ev.target.closest('[data-go]');if(g){irA(g.dataset.go);return;}
  const tm=ev.target.closest('[data-tema]');if(tm){S.tema=tm.dataset.tema;aplicarTema();renderTools();pintar();return;}
  if(ev.target.closest('[data-tv]')){S.tv=!S.tv;aplicarTV();render();return;}
  const al=ev.target.closest('[data-alerta]');
  if(al){const k=al.dataset.alerta;Object.assign(S.filtros,S.filtros.alerta===k?INICIAL():MARC[k]);renderSlicers();if(S.data)render();cargar();return;}
  if(ev.target.closest('[data-limpiar-vista]')){Object.assign(S.filtros,LIMPIAR);renderSlicers();if(S.data)render();cargar();return;}
  const tr=ev.target.closest('[data-tarjeta]');
  if(tr){const k=tr.dataset.tarjeta||null;S.filtros.tarjeta=(k&&S.filtros.tarjeta!==k)?k:null;if(S.data)render();cargar();return;}
  const th=ev.target.closest('[data-ord]');
  if(th){ordenar(th);return;}
  if(ev.target.closest('[data-limpiar-sl]')){S.filtros=VACIO();S.orden={det:null,crit:null,canal:null};renderSlicers();cargar();return;}
  if(ev.target.closest('#demoSim')){fetch('/api/demo/pedido',{method:'POST'}).then(r=>r.json()).then(p=>toast('Pedido simulado enviado','Aparecerá en unos segundos (Sequence '+p.sequence+')')).catch(()=>{});return;}
});
function ordenar(th){
  const tb=th.dataset.tabla,col=th.dataset.ord,o=S.orden[tb];
  S.orden[tb]=(!o||o.col!==col)?{col,dir:'asc'}:(o.dir==='asc'?{col,dir:'desc'}:null);
  if(tb==='canal')render();else{if(S.data)render();cargar();}
}
document.addEventListener('keydown',ev=>{
  const th=ev.target.closest&&ev.target.closest('th[data-ord]');
  if(th&&(ev.key==='Enter'||ev.key===' ')){ev.preventDefault();ordenar(th);}
});
document.addEventListener('change',ev=>{
  const sl=ev.target.closest('[data-sl]');if(sl){S.filtros[sl.dataset.sl]=sl.value?[sl.value]:[];cargar();return;}
  const bo=ev.target.closest('[data-bodega]');if(bo){S.filtros.bodega=bo.value==='__base'?[...BASE]:bo.value==='__todas'?[]:[bo.value];cargar();return;}
  const ac=ev.target.closest('[data-alcance]');if(ac){S.filtros.alcance=ac.value;cargar();return;}
  const fe=ev.target.closest('[data-fecha]');if(fe){S.filtros[fe.dataset.fecha==='ini'?'fecha_ini':'fecha_fin']=fe.value||null;cargar();}
});
let _t=null;
document.addEventListener('input',ev=>{
  const q=ev.target.closest('[data-buscar]');if(!q)return;
  clearTimeout(_t);_t=setTimeout(()=>{S.filtros.buscar=q.value.trim();cargar();},350);
});
let _idle=null;   // modo TV: el cursor se oculta si nadie lo mueve
document.addEventListener('mousemove',()=>{const d=document.documentElement;d.classList.remove('idle');clearTimeout(_idle);_idle=setTimeout(()=>d.classList.add('idle'),4000);});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(S.tema==='auto')pintar();});

/* ============ avance de la primera carga ============ */
async function progresoInicial(){
  if(S.data){clearInterval(S._pr);return;}
  try{
    const j=await(await fetch('/api/version')).json(),c=j.carga||{},p=c.pasos||{};
    const el=document.querySelector('#app .splash'); if(!el||S.data||!Object.keys(p).length)return;
    const seg=c.inicio?Math.max(0,Math.round(Date.now()/1000-c.inicio)):null;
    const mk=e=>e==='ok'?ico('check',14):e==='error'?ico('x',14):'…';
    el.innerHTML=`<div class="prog"><h3>Cargando datos de VTEX y SAP${seg!=null&&!c.total?` · ${seg} s`:''}</h3>${Object.entries(p).map(([k,v])=>
      `<div class="pp ${v.estado}"><span>${mk(v.estado)}</span>${esc(k)}${v.seg!=null?`<small>${dec1(v.seg)} s${v.filas!=null?' · '+fmt(v.filas)+' filas':''}</small>`:''}</div>`).join('')}
      ${c.total?`<p>Consultas listas en ${dec1(c.total)} s · armando el tablero…</p>`:'<p>Las consultas corren en paralelo.</p>'}</div>`;
  }catch(e){}
}

/* ============ arranque ============ */
S.tv=document.documentElement.classList.contains('tv');
ajustarEscala();renderNav();renderTools();
let _rz=null;
addEventListener('resize',()=>{clearTimeout(_rz);_rz=setTimeout(()=>{if(ajustarEscala()&&S.data)render();else if(S.data)marcarAncho();},150);});
(async()=>{
  try{const c=await(await fetch('/api/config')).json();S.poll=c.poll||5;if(c.demo){$('#demo').hidden=false;$('#demoSim').innerHTML=ico('plus')+'Simular pedido';}}catch(e){}
  S._pr=setInterval(progresoInicial,700);progresoInicial();
  await cargarOpts();await cargar();await poll();
  setInterval(poll,Math.max(1,S.poll)*1000);
  setInterval(renderLive,1000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
})();
