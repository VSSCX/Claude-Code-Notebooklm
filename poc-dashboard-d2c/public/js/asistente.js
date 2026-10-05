/* Asistente de consultas: un chat plegable (ícono de consulta arriba a la derecha) para preguntar en lenguaje natural,
   por ejemplo "¿cuál es la venta de los últimos 7 días del MED165B?". La pregunta se traduce en el servidor a un plan
   validado y la cifra la calcula el servidor con sus propios datos (ver app/asistente y ASISTENTE.md). */
const CHAT_MAX=30;
S.chat={open:false,msgs:[],espera:false,prev:null,motor:null};
(function(){try{const a=JSON.parse(sessionStorage.getItem('d2c.chat')||'[]');if(Array.isArray(a))S.chat.msgs=a.slice(-CHAT_MAX);}catch(e){}})();
const guardarChat=()=>{try{sessionStorage.setItem('d2c.chat',JSON.stringify(S.chat.msgs.slice(-CHAT_MAX)));}catch(e){}};

/* formatos de columna que manda el servidor: t texto, n número, $ pesos, pct porcentaje, dias, d fecha, p pedido (abre el detalle) */
const NUMERICO={n:1,'$':1,pct:1,dias:1};
const celdaIA=(v,f)=>{
  if(v==null)return 'sin dato';
  if(f==='n')return fmt(v);if(f==='$')return peso(v);if(f==='pct')return pct(v);if(f==='dias')return dec1(v)+' d';if(f==='d')return fd(v);
  if(f==='p')return `<button class="ia-pv" data-pv="${esc(v)}" aria-haspopup="dialog" title="Ver el detalle del pedido">${esc(v)}</button>`;
  return esc(v);
};
const valorIA=(v,f)=>f==='$'?peso(v):f==='pct'?pct(v):f==='dias'?dec1(v)+' d':fmt(v);
const ejBtn=t=>`<button class="ia-ej" data-chat-ej="${esc(t)}">${esc(t)}</button>`;

function tablaIA(t,i){
  if(!t||!t.filas.length)return '';
  const cab=t.cols.map(c=>`<th scope="col" class="${NUMERICO[c.f]?'n':''}">${esc(c.n)}</th>`).join('');
  const filas=t.filas.map(f=>`<tr>${f.map((v,j)=>`<td class="${NUMERICO[t.cols[j].f]?'n':'desc'}">${celdaIA(v,t.cols[j].f)}</td>`).join('')}</tr>`).join('');
  return `<div class="ia-tw" tabindex="0" role="region" aria-label="Tabla de la respuesta"><table class="t ia-t"><thead><tr>${cab}</tr></thead><tbody>${filas}</tbody></table></div>
    <button class="link ia-csv" data-ia-csv="${i}">${ico('descarga',14)}Descargar CSV (${t.filas.length} filas)</button>`;
}
function utilIA(r,i,util){   // pulgar arriba o abajo: el asistente aprende de lo que le sirve a los analistas
  if(!r.id)return '';
  if(util===true)return `<div class="ia-util">${ico('ok',14)}Gracias, lo recordaré para responder mejor.</div>`;
  if(util===false)return `<div class="ia-util">Gracias. Prueba con otras palabras o escribe «qué puedes hacer».</div>`;
  return `<div class="ia-util"><span>¿Te sirvió?</span><button class="ibtn" data-ia-util="1" data-i="${i}" aria-label="Sí, me sirvió" title="Sí, me sirvió">${ico('pulgar-arriba',16)}</button><button class="ibtn" data-ia-util="0" data-i="${i}" aria-label="No me sirvió" title="No me sirvió">${ico('pulgar-abajo',16)}</button></div>`;
}
function resHTML(r,i,util){
  const via=r.via==='ia'&&r.motor?`<div class="ia-via">Plan armado con ${esc(r.motor)}; la cifra la calculó el servidor.</div>`:(r.via==='memoria'?'<div class="ia-via">Pregunta ya validada antes: se recalculó con los datos de ahora.</div>':'');
  const notas=(r.notas||[]).concat(r.aviso?[r.aviso]:[]).map(t=>`<p class="ia-nota">${esc(t)}</p>`).join('');
  const chips=(r.chips||[]).length?`<div class="ia-chips">${r.chips.map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>`:'';
  const seguir=(r.seguir||[]).length?`<div class="ia-seguir"><span>Seguir con</span>${r.seguir.map(ejBtn).join('')}</div>`:'';
  if(!r.ok){
    return `<p>${esc(r.texto)}</p>${(r.ejemplos||[]).length?`<div class="ia-ejs">${r.ejemplos.map(ejBtn).join('')}</div>`:''}${chips}${notas}${via}`;
  }
  if(r.tipo==='pedido'){
    const p=r.pedido;
    return `<p>${esc(r.texto)}</p>${(r.lineas||[]).slice(0,5).map(x=>`<div class="ia-lin"><span class="code">${esc(x.sku)}</span><span>${esc(x.descripcion)}</span><b>${fmt(x.qty)}</b></div>`).join('')}
      <button class="btn sm primario" data-pv="${esc(p.sequence)}">Ver el detalle completo${ico('ir',14)}</button>${notas}${utilIA(r,i,util)}${via}`;
  }
  const num=r.valor!=null?`<div class="ia-num"><b>${valorIA(r.valor,r.formato)}</b><span>${esc(r.unidad||'')}</span></div>`:'';
  const rs=r.resumen,st=rs?[['pedidos',fmt(rs.pedidos),'pedidos'],['unidades',fmt(rs.unidades),'unidades'],['monto',rs.monto==null?null:peso(rs.monto),'en ventas']].filter(x=>x[1]!=null&&x[0]!==r.metrica):[];
  const stats=r.tipo==='valor'||r.tipo==='tabla'||r.tipo==='lista'?(st.length&&rs&&rs.pedidos?`<div class="ia-stats">${st.map(x=>`<span><b>${x[1]}</b> ${x[2]}</span>`).join('')}</div>`:''):'';
  return `${num}<p>${esc(r.texto)}</p>${stats}${chips}${tablaIA(r.tabla,i)}${notas}${seguir}${utilIA(r,i,util)}${via}`;
}
function renderChat(){
  const el=$('#chat-log'),m=S.chat.msgs;
  let h=m.map((x,i)=>x.rol==='u'?`<div class="ia-row u"><div class="ia-m u"><p>${esc(x.texto)}</p></div></div>`
    :`<div class="ia-row a"><span class="ia-av" aria-hidden="true">${ico('chispas',16)}</span><div class="ia-m a">${resHTML(x.res,i,x.util)}</div></div>`).join('');
  if(S.chat.espera)h+=`<div class="ia-row a"><span class="ia-av" aria-hidden="true">${ico('chispas',16)}</span><div class="ia-m a espera" role="status"><div class="dr-sk" aria-hidden="true"><i></i><i></i></div><span class="sr">Consultando…</span></div></div>`;
  if(!m.length&&!S.chat.espera){
    const ej=(S.chat.motor&&S.chat.motor.ejemplos)||[];
    const fr=((S.chat.motor&&S.chat.motor.frecuentes)||[]).filter(t=>!ej.includes(t));
    h=`<div class="ia-ini"><span class="ia-ini-i">${ico('consulta',26)}</span><h3>Pregunta sobre los pedidos</h3>${ej.map(ejBtn).join('')}${fr.length?`<h4 class="ia-sub">${ico('historial',14)}Lo que más se pregunta</h4>${fr.map(ejBtn).join('')}`:''}</div>`;
  }
  morph(el,h);el.scrollTop=el.scrollHeight;
  const mo=S.chat.motor;$('#chat-motor').textContent=mo?mo.nombre+(mo.modo==='reglas'?'':(mo.local?', los datos no salen de tu red':', se envía el texto de la pregunta')):'';
  $('#chat-limpia').disabled=!m.length;
}
function csvIA(t){   // el mismo contenido de la tabla; comillas dobles escapadas y punto y coma como separador (Excel en español)
  const c=v=>{const s=v==null?'':String(v);return /[";\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;};
  return '﻿'+[t.cols.map(x=>c(x.n)).join(';'),...t.filas.map(f=>f.map(c).join(';'))].join('\r\n');
}
function descargarCSV(i){
  const x=S.chat.msgs[i];if(!x||!x.res||!x.res.tabla)return;
  const url=URL.createObjectURL(new Blob([csvIA(x.res.tabla)],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='consulta-'+new Date().toISOString().slice(0,10)+'.csv';document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
}
function cargarMotorChat(){   // motor, ejemplos y las preguntas del historial (alimentan las sugerencias y el autocompletado)
  fetch('/api/chat/motor').then(r=>r.json()).then(j=>{S.chat.motor=j;const dl=$('#chat-hist');if(dl)dl.innerHTML=[...new Set([...(j.frecuentes||[]),...(j.recientes||[])])].map(t=>`<option value="${esc(t)}">`).join('');if(S.chat.open)renderChat();}).catch(()=>{});
}
async function valorarIA(i,util){
  const x=S.chat.msgs[i];if(!x||!x.res||!x.res.id||x.util!=null)return;
  x.util=util;guardarChat();renderChat();
  try{await fetch('/api/chat/valorar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:x.res.id,util})});}catch(e){}
}
function abrirChat(){
  cerrarPedido(false);S.np&&cerrarNotif(false);
  S.chat.open=true;$('#chat').hidden=false;$('#chatBtn').setAttribute('aria-expanded','true');$('#chatBtn').classList.add('on');
  cargarMotorChat();
  renderChat();setTimeout(()=>$('#chat-q').focus(),30);
}
function cerrarChat(devolverFoco=true){
  if(!S.chat.open)return;
  S.chat.open=false;$('#chat').hidden=true;$('#chatBtn').setAttribute('aria-expanded','false');$('#chatBtn').classList.remove('on');
  if(devolverFoco)$('#chatBtn').focus();
}
async function preguntar(texto){
  texto=String(texto||'').trim().slice(0,300);if(!texto||S.chat.espera)return;
  S.chat.msgs.push({rol:'u',texto});S.chat.espera=true;renderChat();$('#chat-q').value='';
  let res;
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:texto,previo:S.chat.prev})});
    res=await r.json();
    if(!r.ok||res.error)res={ok:false,texto:res.error||'No pude responder en este momento.'};
  }catch(e){res={ok:false,texto:'No hay conexión con el servidor.'};}
  S.chat.espera=false;
  if(res.ok&&res.plan)S.chat.prev=res.plan;
  S.chat.msgs.push({rol:'a',res});S.chat.msgs=S.chat.msgs.slice(-CHAT_MAX);guardarChat();renderChat();cargarMotorChat();
}
document.addEventListener('click',ev=>{
  if(ev.target.closest('[data-chat]')){S.chat.open?cerrarChat(false):abrirChat();return;}
  if(ev.target.closest('[data-chat-cerrar]')){cerrarChat(true);return;}
  if(ev.target.closest('[data-chat-limpia]')){S.chat.msgs=[];S.chat.prev=null;guardarChat();renderChat();$('#chat-q').focus();return;}
  const ej=ev.target.closest('[data-chat-ej]');if(ej){preguntar(ej.dataset.chatEj);return;}
  const csv=ev.target.closest('[data-ia-csv]');if(csv){descargarCSV(+csv.dataset.iaCsv);return;}
  const ut=ev.target.closest('[data-ia-util]');if(ut){valorarIA(+ut.dataset.i,ut.dataset.iaUtil==='1');return;}
});
$('#chat-f').addEventListener('submit',ev=>{ev.preventDefault();preguntar($('#chat-q').value);});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&S.chat.open&&!S.np&&!S.dr){ev.preventDefault();cerrarChat(true);}});
$('#chatBtn').innerHTML=ico('consulta',20);$('#chat-ic').innerHTML=ico('chispas',18);$('#chat-limpia').innerHTML=ico('basura',16);$('#chat-x').innerHTML=ico('x',18);$('#chat-send').innerHTML=ico('enviar',16);$('#chat-in-i').innerHTML=ico('consulta',16);
