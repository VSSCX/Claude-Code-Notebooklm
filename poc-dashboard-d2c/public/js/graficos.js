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
  ch.getDatasetMeta(0).data.forEach((b,i)=>c.fillText(fmt(ch.data.datasets[0].data[i]),b.x+fz(5),b.y));c.restore();}};
const segLabels={id:'segLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='700 '+fz(11.5)+'px '+fam();c.textAlign='center';c.textBaseline='middle';
  ch.data.datasets.forEach((ds,di)=>{c.fillStyle=onClr(ds.colorBase||ds.backgroundColor);ch.getDatasetMeta(di).data.forEach((b,i)=>{
    const v=ds.data[i],w=Math.abs(b.x-b.base);if(v>=7&&w>fz(34)&&(b.height||0)>=fz(13))c.fillText(dec1(v)+'%',(b.x+b.base)/2,b.y);});});c.restore();}};
const pointLabels={id:'pointLabels',afterDatasetsDraw(ch){
  const c=ch.ctx;c.save();c.font='700 '+fz(12)+'px '+fam();c.textAlign='center';
  ch.data.datasets.forEach((ds,di)=>{c.fillStyle=ds.borderColor;ch.getDatasetMeta(di).data.forEach((p,i)=>{
    const v=ds.data[i];if(v==null)return;c.fillText(ds.fmt(v),p.x,p.y-(di?-fz(18):fz(13)));});});c.restore();}};
const baseO=()=>({responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
  scales:{x:{ticks:{color:css('--text-3'),font:{size:fz(11.5)}},grid:{color:css('--line')},border:{display:false}},
          y:{ticks:{color:css('--text-3'),font:{size:fz(11.5)}},grid:{display:false},border:{display:false}}}});
const leyenda=()=>({display:true,position:'bottom',labels:{color:css('--text-2'),font:{size:fz(11.5)},boxWidth:fz(10),boxHeight:fz(10),usePointStyle:true,pointStyle:'rect',padding:fz(12)}});
const ejeFecha=()=>({color:css('--text-3'),font:{size:fz(11.5)},maxTicksLimit:12,maxRotation:0,callback:function(v){return fd(this.getLabelForValue(v)).slice(0,5);}});

function grafico(id,cfg){
  const el=document.getElementById(id); if(!el)return;
  const ex=charts[id];
  if(ex&&ex.canvas===el&&ex.config.type===cfg.type){ex.data=cfg.data;ex.options=cfg.options;ex.update('none');return;}
  if(ex)ex.destroy();
  charts[id]=new Chart(el,cfg);
}
function miniBar(id,data,color,campo){
  const el=document.getElementById(id);if(!el||!data||!data.labels.length)return;
  const n=Math.max(2,Math.floor((el.parentElement.clientHeight-fz(4))/fz(19)));
  const L=data.labels.slice(0,n),V=data.valores.slice(0,n);
  const sub=data.total>L.length?`top ${L.length} de ${data.total}`:'';
  S.subs[id]=sub;const se=document.getElementById('sub-'+id);if(se)se.textContent=sub;
  const o=baseO();o.indexAxis='y';o.layout={padding:{right:fz(36)}};
  const maxPx=Math.max(fz(48),((el.parentElement.clientWidth-fz(36))/2)-fz(18));
  o.scales.x={display:false,beginAtZero:true};
  o.scales.y.ticks={autoSkip:false,color:css('--text-2'),font:{size:fz(11.5)},padding:fz(4),callback:function(v){return cutPx(this.getLabelForValue(v),maxPx);}};
  o.plugins.tooltip={callbacks:{title:i=>L[i[0].dataIndex]}};
  const sel=campo?seleccion(campo):[];
  o.onClick=(ev,els)=>{if(campo&&els.length)alternar(campo,L[els[0].index],multiClic(ev));};o.onHover=manito;
  grafico(id,{type:'bar',data:{labels:L,datasets:[{data:V,backgroundColor:sel.length?L.map(l=>sel.includes(l)?color:alfa(color,.28)):color,borderRadius:4,barPercentage:.74,categoryPercentage:.92,maxBarThickness:fz(20)}]},options:o,plugins:[valueLabels]});
}
function pintar(){
  const d=S.data;if(!d)return;
  Chart.defaults.font.family=fam();Chart.defaults.color=css('--text-3');
  const prim=css('--primary');
  if(S.view==='pedidos'){miniBar('cSla',d.g_sla,prim,'sla');miniBar('cCli',d.g_cli,prim,'cliente');miniBar('cWh',d.g_wh,prim,'bodega');}
  if(S.view==='resumen'){
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

