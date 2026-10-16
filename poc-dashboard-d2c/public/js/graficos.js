/* graficos.js: filtrado cruzado estilo Power BI y gráficos de Chart.js (se actualizan en su lugar). */
/* ============ filtrado cruzado (como Power BI): clic en una barra o fila filtra todo el tablero ============
   El filtro queda en los mismos filtros de arriba (se ve en el selector) y vale para las tres pantallas.
   Clic de nuevo en lo seleccionado lo quita; Ctrl (o Mayús) + clic suma otro valor. El gráfico donde se hizo clic
   sigue mostrando todas las barras (el servidor no lo filtra por su propia selección) y atenúa las no elegidas. */
const alfa=(hex,a)=>{const n=parseInt(hex.slice(1),16);return `rgba(${n>>16},${n>>8&255},${n&255},${a})`;};
const igualLista=(a,b)=>a.length===b.length&&a.every(x=>b.includes(x));
function seleccion(campo){const v=S.filtros[campo]||[];return campo==='bodega'&&(igualLista(v,BASE)||!v.length)?[]:v;}
function mesSel(){const f=S.filtros;return f.fecha_ini&&f.fecha_fin&&f.fecha_ini!==f.fecha_fin&&f.fecha_ini.slice(0,7)===f.fecha_fin.slice(0,7)&&f.fecha_ini.slice(8,10)==='01'?f.fecha_ini.slice(0,7):null;}
function diaSel(){const f=S.filtros;return f.fecha_ini&&f.fecha_ini===f.fecha_fin?f.fecha_ini:null;}
function aplicarCruzado(){renderSlicers();if(S.data)render();cargar();}
function alternar(campo,v,multi){
  const cur=S.filtros[campo]||[];let nuevo;
  if(multi)nuevo=cur.includes(v)?cur.filter(x=>x!==v):[...cur,v];
  else nuevo=(cur.length===1&&cur[0]===v)?[]:[v];
  if(campo==='bodega'&&!nuevo.length)nuevo=[...BASE];   // sin bodega elegida vuelve a la base (EC01 + POST)
  S.filtros[campo]=nuevo;aplicarCruzado();
}
function sinFechas(){S.per='auto';sincPer();}
function alternarMes(m){   // 'AAAA-MM' -> del día 1 al último día del mes (o al último dato)
  if(mesSel()===m){sinFechas();return aplicarCruzado();}
  const ult=new Date(+m.slice(0,4),+m.slice(5,7),0).getDate();
  const max=S.opts&&S.opts.fecha_max;
  S.per='custom';S.filtros.fecha_ini=m+'-01';S.filtros.fecha_fin=(max&&max.slice(0,7)===m)?max:m+'-'+String(ult).padStart(2,'0');aplicarCruzado();
}
function alternarDia(d){
  if(diaSel()===d){sinFechas();return aplicarCruzado();}
  S.per='custom';S.filtros.fecha_ini=d;S.filtros.fecha_fin=d;aplicarCruzado();
}
const multiClic=ev=>!!(ev&&ev.native&&(ev.native.ctrlKey||ev.native.metaKey||ev.native.shiftKey));
const manito=(ev,els)=>{if(ev&&ev.native&&ev.native.target)ev.native.target.style.cursor=els.length?'pointer':'default';};

/* ============ graficos (se actualizan en su lugar; los colores salen de los tokens del tema) ============ */
const charts={};
const fam=()=>getComputedStyle(document.body).fontFamily;
const _mc=document.createElement('canvas').getContext('2d');
const cutPx=(l,px,sz=fz(11.5))=>{_mc.font=sz+'px '+fam();if(_mc.measureText(l).width<=px)return l;let s=l;while(s.length>1&&_mc.measureText(s+'…').width>px)s=s.slice(0,-1);return s.trimEnd()+'…';};
const valueLabels={id:'valueLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='600 '+fz(11.5)+'px '+fam();c.fillStyle=css('--text-2');c.textBaseline='middle';
  const f=ch.data.datasets[0].fmtv||fmt;
  ch.getDatasetMeta(0).data.forEach((b,i)=>c.fillText(f(ch.data.datasets[0].data[i]),b.x+fz(5),b.y));c.restore();}};
const segLabels={id:'segLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='700 '+fz(11.5)+'px '+fam();c.textAlign='center';c.textBaseline='middle';
  ch.data.datasets.forEach((ds,di)=>{c.fillStyle=onClr(ds.colorBase||ds.backgroundColor);ch.getDatasetMeta(di).data.forEach((b,i)=>{
    const v=ds.data[i],w=Math.abs(b.x-b.base);if(v>=7&&w>fz(34)&&(b.height||0)>=fz(13))c.fillText(dec1(v)+'%',(b.x+b.base)/2,b.y);});});c.restore();}};
const pointLabels={id:'pointLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='700 '+fz(12)+'px '+fam();c.textAlign='center';
  ch.data.datasets.forEach((ds,di)=>{c.fillStyle=ds.borderColor;ch.getDatasetMeta(di).data.forEach((p,i)=>{
    const v=ds.data[i];if(v==null)return;c.fillText(ds.fmt(v),p.x,p.y-(di?-fz(18):fz(13)));});});c.restore();}};
const sinMov=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
const baseO=()=>({responsive:true,maintainAspectRatio:false,animation:sinMov()?false:{duration:320,easing:'easeOutQuart'},plugins:{legend:{display:false}},
  scales:{x:{ticks:{color:css('--text-3'),font:{size:fz(11.5)}},grid:{color:css('--line')},border:{display:false}},
          y:{ticks:{color:css('--text-3'),font:{size:fz(11.5)}},grid:{display:false},border:{display:false}}}});
const leyenda=()=>({display:true,position:'bottom',labels:{color:css('--text-2'),font:{size:fz(11.5)},boxWidth:fz(10),boxHeight:fz(10),usePointStyle:true,pointStyle:'rect',padding:fz(12)}});
const ejeFecha=()=>({color:css('--text-3'),font:{size:fz(11.5)},maxTicksLimit:12,maxRotation:0,callback:function(v){return fd(this.getLabelForValue(v)).slice(0,5);}});

function grafico(id,cfg){
  const el=document.getElementById(id); if(!el)return;
  const ex=charts[id];
  if(ex&&ex.canvas===el&&ex.config.type===cfg.type){ex.data=cfg.data;ex.options=cfg.options;ex.update(sinMov()?'none':undefined);return;}
  if(ex)ex.destroy();
  charts[id]=new Chart(el,cfg);
}
function miniBar(id,data,color,campo,f){
  const el=document.getElementById(id);if(!el||!data||!data.labels.length)return;
  const n=Math.max(2,Math.floor((el.parentElement.clientHeight-fz(4))/fz(19)));
  const L=data.labels.slice(0,n),V=data.valores.slice(0,n);
  const sub=data.total>L.length?`top ${L.length} de ${data.total}`:'';
  S.subs[id]=sub;const se=document.getElementById('sub-'+id);if(se)se.textContent=sub;
  const o=baseO();o.indexAxis='y';const pad=f?fz(92):fz(36);o.layout={padding:{right:pad}};
  const maxPx=Math.max(fz(48),((el.parentElement.clientWidth-pad)/2)-fz(18));
  o.scales.x={display:false,beginAtZero:true};
  o.scales.y.ticks={autoSkip:false,color:css('--text-2'),font:{size:fz(11.5)},padding:fz(4),callback:function(v){return cutPx(this.getLabelForValue(v),maxPx);}};
  o.plugins.tooltip={callbacks:{title:i=>L[i[0].dataIndex]}};
  const sel=campo?seleccion(campo):[];
  o.onClick=(ev,els)=>{if(campo&&els.length)alternar(campo,L[els[0].index],multiClic(ev));};o.onHover=manito;
  grafico(id,{type:'bar',data:{labels:L,datasets:[{data:V,backgroundColor:sel.length?L.map(l=>sel.includes(l)?color:alfa(color,.28)):color,borderRadius:4,barPercentage:.74,categoryPercentage:.92,maxBarThickness:fz(20),fmtv:f}]},options:o,plugins:[valueLabels]});
}

/* ============ entrega estimada: columnas por día, franjas vencido / hoy / próximos, clic en cualquier parte de la columna ============ */
const bandasEntrega={id:'bandasEntrega',beforeDatasetsDraw(ch){
  const cols=ch.data.cols;if(!cols)return;
  const c=ch.ctx,a=ch.chartArea,sc=ch.scales.x,w=cols.length>1?Math.abs(sc.getPixelForValue(1)-sc.getPixelForValue(0)):a.right-a.left;
  const act=ch.tooltip&&ch.tooltip.getActiveElements?ch.tooltip.getActiveElements():[],hov=act.length?act[0].index:-1;
  c.save();
  cols.forEach((k,j)=>{
    const x=sc.getPixelForValue(j)-w/2;
    c.fillStyle=k.rel<0?alfa(css('--err'),.07):k.rel===0?alfa(css('--warn-solid'),.16):'transparent';c.fillRect(x,a.top,w,a.bottom-a.top);
    if(ch.data.activa&&ch.data.activa[j]){c.fillStyle=alfa(css('--primary'),.12);c.fillRect(x,a.top,w,a.bottom-a.top);c.fillStyle=css('--primary');c.fillRect(x+w*.12,a.bottom,w*.76,fz(3));}
    else if(j===hov){c.fillStyle=alfa(css('--text'),.05);c.fillRect(x,a.top,w,a.bottom-a.top);}
  });
  c.font='700 '+fz(10)+'px '+fam();c.textAlign='center';c.textBaseline='top';
  const grupo=(rel,txt,color)=>{const idx=cols.map((k,j)=>k.rel===rel?j:-1).filter(j=>j>=0);if(!idx.length)return;
    const x=(sc.getPixelForValue(idx[0])+sc.getPixelForValue(idx[idx.length-1]))/2;c.fillStyle=color;c.fillText(txt,x,a.top-fz(20));};
  grupo(-1,'VENCIDO',alfa(css('--err'),.9));grupo(0,'HOY',css('--warn'));grupo(1,'PRÓXIMOS',css('--text-3'));
  c.restore();}};
const totalesEntrega={id:'totalesEntrega',afterDatasetsDraw(ch){
  const tot=ch.data.totales;if(!tot)return;const c=ch.ctx;c.save();c.textAlign='center';c.textBaseline='bottom';
  tot.forEach((t,j)=>{if(!t)return;let y=Infinity;ch.data.datasets.forEach((ds,di)=>{const b=ch.getDatasetMeta(di).data[j];if(b&&ds.data[j]>0)y=Math.min(y,b.y);});
    if(y===Infinity)return;const act=ch.data.activa&&ch.data.activa[j];c.font=(act?'800 ':'700 ')+fz(11.5)+'px '+fam();c.fillStyle=act?css('--primary-strong'):css('--text-2');c.fillText(fmt(t),ch.getDatasetMeta(0).data[j].x,y-fz(3));});
  c.restore();}};
function pintarEntrega(){
  const d=S.data,m=d.matriz_entrega;
  if(!document.getElementById('cEnt')||!m.cols.length)return;
  const sel=S.filtros.entrega||[],hay=sel.length>0,hoy=fechaDe(d.hoy);
  const activa=m.cols.map(c=>sel.includes(c.k)||(sel.includes('vencido')&&c.rel<0)||(sel.includes('hoy')&&c.rel===0));
  const labels=m.cols.map(c=>c.k==='<'?['Anteriores','']:c.k==='>'?['Posteriores','']:[c.etq,c.dow||'']);
  const tot=m.cols.map((_,j)=>m.filas.reduce((a,f)=>a+f[j],0));
  const o=baseO();o.interaction={mode:'index',intersect:false};o.layout={padding:{top:fz(26),right:fz(6)}};
  o.scales.x={stacked:true,grid:{display:false},border:{display:false},ticks:{autoSkip:false,maxRotation:0,font:{size:fz(11)},
    color:c=>{const k=m.cols[c.index];return k&&k.rel<0?css('--err-strong'):k&&k.rel===0?css('--warn'):css('--text-2');}}};
  o.scales.y={stacked:true,beginAtZero:true,grace:'8%',grid:{color:css('--line')},border:{display:false},ticks:{maxTicksLimit:4,color:css('--text-3'),font:{size:fz(11)},callback:v=>fmt(v)}};
  o.plugins.tooltip={callbacks:{
    title:i=>{const k=m.cols[i[0].dataIndex];if(k.k==='<')return 'Entrega anterior a '+fd(iso(new Date(hoy.getTime()-6*864e5))).slice(0,5);if(k.k==='>')return 'Entrega posterior a la ventana';
      const dd=Math.round((new Date(k.k+'T12:00:00')-hoy)/864e5);return dia(k.k,false)+(dd<0?' · vencido hace '+(-dd)+(dd===-1?' día':' días'):dd===0?' · vence hoy':' · en '+dd+(dd===1?' día':' días'));},
    label:c=>` ${c.dataset.label}: ${fmt(c.raw)}`,footer:i=>'Total: '+fmt(tot[i[0].dataIndex])+' · clic para filtrar'}};
  const dentro=(ev,ch)=>{const a=ch.chartArea;return ev.x>=a.left&&ev.x<=a.right&&ev.y>=a.top-fz(24)&&ev.y<=a.bottom+fz(36);};
  o.onClick=(ev,els,ch)=>{if(!dentro(ev,ch))return;const i=Math.max(0,Math.min(m.cols.length-1,Math.round(ch.scales.x.getValueForPixel(ev.x))));alternar('entrega',m.cols[i].k,multiClic(ev));};
  o.onHover=(ev,els,ch)=>{if(ev.native&&ev.native.target)ev.native.target.style.cursor=dentro(ev,ch)?'pointer':'default';};
  grafico('cEnt',{type:'bar',data:{labels,cols:m.cols,totales:tot,activa:hay?activa:null,datasets:m.estados.map((e,i)=>{const base=stClr(e);
    return {label:e,data:m.filas[i],backgroundColor:hay?m.cols.map((c,j)=>activa[j]?base:alfa(base,.3)):base,borderSkipped:false,borderRadius:fz(2),maxBarThickness:fz(38)};})},options:o,plugins:[bandasEntrega,totalesEntrega]});
}
function pintar(){
  const d=S.data;if(!d)return;
  Chart.defaults.font.family=fam();Chart.defaults.color=css('--text-3');
  const prim=css('--primary');
  const T=Chart.defaults.plugins.tooltip;   // globos de ayuda con los colores del tema
  Object.assign(T,{backgroundColor:css('--surface'),titleColor:css('--text'),bodyColor:css('--text-2'),footerColor:css('--text-3'),borderColor:css('--line-2'),borderWidth:1,padding:fz(10),cornerRadius:fz(8),boxPadding:fz(4),titleFont:{weight:'700',size:fz(12)},bodyFont:{size:fz(12)},footerFont:{weight:'500',size:fz(11)}});
  if(S.view==='pedidos'){miniBar('cSla',d.g_sla,prim,'sla');miniBar('cCli',d.g_cli,prim,'cliente');pintarEntrega();pintarVentas();}
  if(S.view==='resumen'){
    const cn=(d.canal||[]).filter(c=>c.monto_riesgo>0);miniBar('cCanal',{labels:cn.map(c=>c.canal),valores:cn.map(c=>c.monto_riesgo),total:cn.length},css('--err'),'canal',money);pintarVentas();
    const cp=d.composicion;
    if(document.getElementById('cComp')&&cp.meses.length){
      const P_=cp.filas.map(f=>{const t=f.reduce((a,b)=>a+b,0)||1;return f.map(x=>100*x/t);});
      const o=baseO();o.indexAxis='y';o.plugins.legend=leyenda();
      o.scales.x.stacked=true;o.scales.x.max=100;o.scales.x.ticks={color:css('--text-3'),font:{size:fz(11.5)},callback:v=>v+'%'};
      o.scales.y.stacked=true;o.scales.y.ticks={autoSkip:false,color:css('--text-2'),font:{size:fz(12.5),weight:'600'}};
      o.plugins.tooltip={callbacks:{label:c=>` ${c.dataset.label}: ${fmt(cp.filas[c.dataIndex][c.datasetIndex])} (${dec1(c.raw)}%)`}};
      const ms=mesSel()||(diaSel()?diaSel().slice(0,7):null);
      o.onClick=(ev,els)=>{if(els.length)alternarMes(cp.meses[els[0].index]);};o.onHover=manito;
      grafico('cComp',{type:'bar',data:{labels:cp.meses.map(mes),datasets:cp.columnas.map((col,i)=>{const base=stClr(col);return {label:col,data:P_.map(r=>r[i]),colorBase:base,backgroundColor:ms?cp.meses.map(m=>m===ms?base:alfa(base,.3)):base,maxBarThickness:fz(42),borderSkipped:false};})},options:o,plugins:[segLabels]});
    }
    const ci=d.cierre;
    if(document.getElementById('cCierre')&&ci.meses.length){
      const c1=css('--text'),c2=css('--primary');
      const o=baseO();o.plugins.legend=leyenda();o.layout={padding:{top:fz(18),left:fz(4),right:fz(4)}};
      o.scales.x.grid={display:false};o.scales.x.offset=true;
      o.scales.y={position:'left',min:0,max:100,ticks:{color:c1,font:{size:fz(11.5)},callback:v=>v+'%'},grid:{color:css('--line')},border:{display:false},title:{display:true,text:'% Cumplimiento al cierre',color:c1,font:{size:fz(11.5)}}};
      o.scales.y1={position:'right',min:0,ticks:{color:c2,font:{size:fz(11.5)}},grid:{display:false},border:{display:false},title:{display:true,text:'Antigüedad prom. (días)',color:c2,font:{size:fz(11.5)}}};
      const ds=(label,data,color,eje,f)=>({label,data,yAxisID:eje,borderColor:color,backgroundColor:color,borderWidth:fz(2.5),pointRadius:fz(5),pointHoverRadius:fz(6),tension:.2,spanGaps:true,fmt:f});
      grafico('cCierre',{type:'line',data:{labels:ci.meses.map(mes),datasets:[
        ds('% Cumplimiento al cierre',ci.cumpl.map(v=>v==null?null:v*100),c1,'y',v=>dec1(v)+'%'),
        ds('Antigüedad prom. al cierre (días)',ci.antig,c2,'y1',v=>dec1(v)+' d')]},options:o,plugins:[pointLabels]});
    }
  }
  if(S.view==='diagnostico'){
    miniBar('cNoInt',d.g_noint,css('--err'),'cliente');
    const m=d.matriz_dia;
    if(document.getElementById('cDiaEst')&&m.fechas.length){
      const o=baseO();o.plugins.legend=leyenda();o.scales.x.stacked=true;o.scales.y.stacked=true;o.scales.x.grid={display:false};o.scales.x.ticks=ejeFecha();
      o.plugins.tooltip={callbacks:{title:i=>dia(m.fechas[i[0].dataIndex])}};
      const dsel=diaSel();
      o.onClick=(ev,els)=>{if(els.length)alternarDia(m.fechas[els[0].index]);};o.onHover=manito;
      grafico('cDiaEst',{type:'bar',data:{labels:m.fechas,datasets:m.columnas.map((col,i)=>{const base=stClr(col);return {label:col,data:m.filas.map(f=>f[i]),backgroundColor:dsel?m.fechas.map(x=>x===dsel?base:alfa(base,.3)):base,borderSkipped:false};})},options:o});
    }
  }
  for(const id of Object.keys(charts)){if(!charts[id].canvas.isConnected){charts[id].destroy();delete charts[id];}}   // gráficos de pantallas que ya no están
}

