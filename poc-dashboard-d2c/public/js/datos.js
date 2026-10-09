/* datos.js: estado de la pantalla (S), período por defecto, redibujado por diferencias (morph), carga y sondeo de /api. */
/* ============ estado y marcadores (replican los bookmarks del Power BI) ============ */
const BASE=['EC01','POST_Fechado'];
const INICIAL=()=>({alerta:null,tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'abiertos'});
const MARC={ // cada boton fija su propio alcance, igual que el marcador correspondiente
  bws:{alerta:'bws',tarjeta:null,bodega:['EC01'],sla_excluir:['Servicios'],alcance:'todos'},
  pos:{alerta:'pos',tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'},
  mkp:{alerta:'mkp',tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'},
  fac:{alerta:'fac',tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'}};
const LIMPIAR={alerta:null,tarjeta:null,bodega:[...BASE],sla_excluir:[],alcance:'todos'}; // = marcador "Pedidos VTEX"
const VISTAS=['pedidos','resumen','diagnostico'];
const S={fa:false,u:1,orden:{det:null,crit:null,canal:null},data:null,version:'',view:VISTAS.includes(location.hash.slice(1))?location.hash.slice(1):(VISTAS.includes(leer('vista'))?leer('vista'):'pedidos'),poll:5,opts:null,req:0,err:null,mon:null,revisadoAt:null,
  vistos:new Set(),vistosInit:false,prevTarj:null,filtros:null,
  tema:['light','dark'].includes(leer('tema'))?leer('tema'):'auto',tv:leer('tv')==='1',subs:{},pintada:null,per:'auto',mas:false,dr:null};
const VACIO=()=>({canal:[],cliente:[],clasif2:[],status:[],sla:[],buscar:'',fecha_ini:null,fecha_fin:null,...INICIAL()});
S.filtros=VACIO();

/* ============ período: al abrir, Pedidos VTEX muestra solo el mes en curso (se puede mirar hacia atrás) ============
   'auto' = el período por defecto de cada pantalla (mes en curso en Pedidos VTEX, todo en las demás, que comparan meses).
   Cualquier elección del usuario (selector, fechas o clic en un mes o día) lo fija para las tres pantallas. */
const iso=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
const fechaDe=s=>new Date(s+'T12:00:00');
const PER=[['mes','Mes en curso'],['mes_ant','Mes anterior'],['30','Últimos 30 días'],['todo','Todo el período'],['custom','Personalizado']];
const perEf=()=>S.per!=='auto'?S.per:(S.view==='pedidos'?'mes':'todo');
function rangoPer(p){
  const o=S.opts;if(!o)return [null,null];
  const h=fechaDe(o.hoy||o.fecha_max),y=h.getFullYear(),m=h.getMonth();
  if(p==='mes')return [iso(new Date(y,m,1)),iso(h)];
  if(p==='mes_ant')return [iso(new Date(y,m-1,1)),iso(new Date(y,m,0))];
  if(p==='30')return [iso(new Date(y,m,h.getDate()-29)),iso(h)];
  return [o.fecha_min,o.fecha_max];
}
function sincPer(){const p=perEf();if(p==='custom'||!S.opts)return;const r=rangoPer(p);S.filtros.fecha_ini=r[0];S.filtros.fecha_fin=r[1];}

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
async function bajarCSV(url,body,fallback){   // pide un CSV al servidor y lo descarga; avisa si falla
  try{
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){const j=await r.json().catch(()=>({}));toast('No se pudo exportar',j.error||'Intenta de nuevo');return;}
    const cd=r.headers.get('Content-Disposition')||'',nom=(cd.match(/filename="([^"]+)"/)||[])[1]||fallback;
    const u=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=u;a.download=nom;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),2000);
    const n=r.headers.get('X-Filas');if(n)toast('Exportación lista',fmt(n)+' pedidos en '+nom);
  }catch(e){toast('No se pudo exportar','No hay conexión con el servidor.');}
}
function cuerpoFiltros(){   // los filtros tal como se mandan al servidor (los usa el tablero y las ventas por clasificación)
  const body={...S.filtros}; if(S.view!=='pedidos') body.alcance='todos';
  if(body.buscar){body.alcance='todos';body.bodega=[];body.fecha_ini=null;body.fecha_fin=null;}   // una busqueda puntual ignora el alcance, la bodega y el periodo
  return body;
}
async function cargar(){
  sincPer();
  const id=++S.req; $('#shell').classList.add('loading');
  const body=cuerpoFiltros();
  body.orden_det=S.orden.det;body.orden_crit=S.orden.crit;   // el orden se aplica en el servidor sobre TODO el conjunto
  try{
    const r=await fetch('/api/dashboard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json(); if(id!==S.req)return;
    $('#shell').classList.remove('loading');
    if(j.error&&!j.kpi){S.err=j.error;render();return;}
    avisarLlegadas(j);
    S.prevTarj=S.data?S.data.tarjetas:null;
    S.data=j;S.version=j.version;S.err=j.error||null;
    render();
    if(S.view==='pedidos')cargarVentas();
  }catch(e){
    if(id!==S.req)return; $('#shell').classList.remove('loading');
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
  else if(S.mon.error&&S.mon.estado==='lento'){dot='warn';l1='Se actualiza cada '+S.mon.respaldo_min+' min, datos de las '+esc(S.mon.consulta||'-');l2='La detección rápida de pedidos nuevos falló: '+esc(S.mon.error).slice(0,48);}
  else if(S.mon.error){dot='err';l1='Sin acceso a las bases'+(S.mon.consulta?', mostrando datos de las '+esc(S.mon.consulta):'');l2=esc(S.mon.error).slice(0,70);}
  else{
    const seg=S.revisadoAt==null?null:Math.max(0,Math.round((Date.now()-S.revisadoAt)/1000));
    l1='En vivo'+(seg==null?'':', hace '+seg+'\u00a0s');
    if(S.data&&S.data.ultimo_pedido) l2='Último pedido VTEX '+esc(S.data.ultimo_pedido);
  }
  morph(el,`<div class="l1"><span class="dot ${dot}"></span><span>${l1}</span></div>${l2?`<div class="l2">${l2}</div>`:''}`);
  el.title=[l1,l2].filter(Boolean).join('. ').replace(/&nbsp;|\u00a0/g,' ');
}

