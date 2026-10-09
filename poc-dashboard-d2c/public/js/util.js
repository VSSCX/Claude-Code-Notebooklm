/* util.js: formato, íconos y colores de estado. No guarda estado. Se carga primero. */
/* Dashboard D2C · cruce VTEX vs SAP.
   El servidor entrega los datos ya calculados (/api/dashboard); aquí solo se pintan.
   Redibujado por diferencias (morphdom): una actualización en vivo no quita foco, scroll ni filtros,
   y los gráficos se actualizan en su lugar en vez de recrearse. */

/* ============ utilidades ============ */
const $=s=>document.querySelector(s);
const U=()=>S.u||1;
const fz=n=>Math.round(n*U()*(S.tv?1.15:1)*10)/10;   // en TV los rótulos de los gráficos salen aún mayores
const nf=new Intl.NumberFormat('es-CL'), nf1=new Intl.NumberFormat('es-CL',{maximumFractionDigits:1});
const fmt=n=>nf.format(Math.round(+n||0));
const dec1=v=>nf1.format(Math.round(v*10)/10);
const money=n=>{const v=+n||0,a=Math.abs(v);if(a>=1e6)return '$'+dec1(v/1e6)+'\u00a0mill.';if(a>=1e3)return '$'+fmt(v/1e3)+'\u00a0mil';return '$'+fmt(v);};
const pct=v=>v==null?'-':dec1(v*100)+'%';
const pctD=v=>v==null?'-':(v>=0?'+':'−')+dec1(Math.abs(v*100))+' pp';
const esc=v=>String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fd=s=>s?s.slice(8,10)+'-'+s.slice(5,7)+'-'+s.slice(2,4):'-';
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const mes=m=>{const t=new Date(m+'-01T12:00:00').toLocaleDateString('es-CL',{month:'long',year:'numeric'});return t.charAt(0).toUpperCase()+t.slice(1);};
const dia=(f,conAnio=true)=>{const d=new Date(f+'T12:00:00');return d.toLocaleDateString('es-CL',{weekday:'short'}).replace('.','')+' '+(conAnio?fd(f):fd(f).slice(0,5));};
const vacio=(t,m)=>`<div class="empty"><div>${t?`<h3>${t}</h3>`:''}${m||''}</div></div>`;
const guardar=(k,v)=>{try{localStorage.setItem('d2c.'+k,v);}catch(e){}};
const leer=k=>{try{return localStorage.getItem('d2c.'+k);}catch(e){return null;}};

/* íconos: Tabler Icons (iconos.js), un solo trazo (1.75) sobre rejilla de 24 */
const ALIAS={up:'sube',down:'baja',flat:'plano',x:'x',plus:'mas',check:'ok',sun:'sol',moon:'luna',auto:'auto',tv:'tv',alert:'alerta',asc:'arriba',desc:'abajo',both:'orden'};
const ico=(k,s=16)=>`<svg class="i" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONOS[ALIAS[k]||k]||''}</svg>`;

/* los cinco estados de un pedido: el color vive en los tokens (--st-*), así sigue al tema */
const ST={"Integrado · Facturado":'--st-if',"Integrado · Pendiente":'--st-ip',"No integrado · Facturado":'--st-nf',"No integrado · Pendiente":'--st-np',"Cancelado":'--st-ca'};
const stVar=e=>`var(${ST[e]||'--edge'})`, stClr=e=>css(ST[e]||'--edge');
const PILL={"Integrado · Facturado":"g","Integrado · Pendiente":"b","No integrado · Facturado":"r","No integrado · Pendiente":"a","Cancelado":"n"};
const pill=e=>`<span class="tag ${PILL[e]||'n'}">${esc(e)}</span>`;
const lum=h=>{const n=parseInt(h.slice(1),16),f=c=>{c/=255;return c<=.03928?c/12.92:Math.pow((c+.055)/1.055,2.4);};return .2126*f(n>>16)+.7152*f(n>>8&255)+.0722*f(n&255);};
const onClr=h=>lum(h)>.3?'#12171C':'#FFFFFF';

