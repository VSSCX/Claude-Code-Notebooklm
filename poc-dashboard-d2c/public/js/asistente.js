/* Asistente de consultas: un chat plegable (ícono de consulta arriba a la derecha) para preguntar en lenguaje natural,
   por ejemplo "¿cuántas unidades del refrigerador MED 165B cayeron hoy?". La pregunta se traduce en el servidor a un plan
   validado y la cifra la calcula el servidor con sus propios datos (ver app/asistente.py y ASISTENTE.md). */
const CHAT_MAX=30;
S.chat={open:false,msgs:[],espera:false,prev:null,motor:null};
(function(){try{const a=JSON.parse(sessionStorage.getItem('d2c.chat')||'[]');if(Array.isArray(a))S.chat.msgs=a.slice(-CHAT_MAX);}catch(e){}})();
const guardarChat=()=>{try{sessionStorage.setItem('d2c.chat',JSON.stringify(S.chat.msgs.slice(-CHAT_MAX)));}catch(e){}};
const celdaIA=(v,fm,col)=>typeof v==='number'?(fm==='$'&&col===1?peso(v):fmt(v)):esc(v);

function resHTML(r){
  const via=r.via==='ia'&&r.motor?`<div class="ia-via">Plan armado con ${esc(r.motor)}; la cifra la calculó el servidor.</div>`:'';
  const notas=(r.notas||[]).concat(r.aviso?[r.aviso]:[]).map(t=>`<p class="ia-nota">${esc(t)}</p>`).join('');
  if(!r.ok){
    const ej=(r.ejemplos||[]).map(t=>`<button class="ia-ej" data-chat-ej="${esc(t)}">${esc(t)}</button>`).join('');
    return `<p>${esc(r.texto)}</p>${ej?`<div class="ia-ejs">${ej}</div>`:''}${(r.chips||[]).length?`<div class="ia-chips">${r.chips.map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>`:''}${notas}${via}`;
  }
  const chips=(r.chips||[]).length?`<div class="ia-chips">${r.chips.map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>`:'';
  if(r.tipo==='pedido'){
    const p=r.pedido;
    return `<p>${esc(r.texto)}</p>${(r.lineas||[]).slice(0,4).map(x=>`<div class="ia-lin"><span class="code">${esc(x.sku)}</span><span>${esc(x.descripcion)}</span><b>${fmt(x.qty)}</b></div>`).join('')}
      <button class="btn sm primario" data-pv="${esc(p.sequence)}">Ver el detalle completo${ico('ir',14)}</button>${via}`;
  }
  const num=r.formato==='$'?peso(r.valor):fmt(r.valor);
  const t=r.tabla,tab=t&&t.filas.length?`<div class="ia-tw" tabindex="0" role="region" aria-label="Tabla de la respuesta"><table class="t ia-t"><thead><tr>${t.cols.map((c,i)=>`<th scope="col" class="${i?'n':''}">${esc(c)}</th>`).join('')}</tr></thead><tbody>${t.filas.map(f=>`<tr>${f.map((v,i)=>`<td class="${i?'n':'desc'}">${celdaIA(v,t.formato,i)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:'';
  return `<div class="ia-num"><b>${num}</b><span>${esc(r.unidad||'')}</span></div><p>${esc(r.texto)}</p>${chips}${tab}${notas}${via}`;
}
function renderChat(){
  const el=$('#chat-log'),m=S.chat.msgs;
  let h=m.map(x=>x.rol==='u'?`<div class="ia-m u"><p>${esc(x.texto)}</p></div>`:`<div class="ia-m a">${resHTML(x.res)}</div>`).join('');
  if(S.chat.espera)h+=`<div class="ia-m a espera" role="status"><div class="dr-sk" aria-hidden="true"><i></i><i></i></div><span class="sr">Consultando…</span></div>`;
  if(!m.length&&!S.chat.espera){
    const ej=(S.chat.motor&&S.chat.motor.ejemplos)||[];
    h=`<div class="ia-ini"><span class="ia-ini-i">${ico('chispas',24)}</span><h3>Pregunta sobre los pedidos</h3><p>Escribe en lenguaje normal. Por ejemplo:</p>${ej.map(t=>`<button class="ia-ej" data-chat-ej="${esc(t)}">${esc(t)}</button>`).join('')}</div>`;
  }
  morph(el,h);el.scrollTop=el.scrollHeight;
  const mo=S.chat.motor;$('#chat-motor').textContent=mo?mo.nombre+(mo.modo==='reglas'?'':(mo.local?', los datos no salen de tu red':', se envía el texto de la pregunta')):'';
  $('#chat-limpia').disabled=!m.length;
}
function abrirChat(){
  cerrarPedido(false);S.np&&cerrarNotif(false);
  S.chat.open=true;$('#chat').hidden=false;$('#chatBtn').setAttribute('aria-expanded','true');$('#chatBtn').classList.add('on');
  if(!S.chat.motor)fetch('/api/chat/motor').then(r=>r.json()).then(j=>{S.chat.motor=j;renderChat();}).catch(()=>{});
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
  S.chat.msgs.push({rol:'a',res});S.chat.msgs=S.chat.msgs.slice(-CHAT_MAX);guardarChat();renderChat();
}
document.addEventListener('click',ev=>{
  if(ev.target.closest('[data-chat]')){S.chat.open?cerrarChat(false):abrirChat();return;}
  if(ev.target.closest('[data-chat-cerrar]')){cerrarChat(true);return;}
  if(ev.target.closest('[data-chat-limpia]')){S.chat.msgs=[];S.chat.prev=null;guardarChat();renderChat();$('#chat-q').focus();return;}
  const ej=ev.target.closest('[data-chat-ej]');if(ej){preguntar(ej.dataset.chatEj);return;}
});
$('#chat-f').addEventListener('submit',ev=>{ev.preventDefault();preguntar($('#chat-q').value);});
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&S.chat.open&&!S.np&&!S.dr){ev.preventDefault();cerrarChat(true);}});
$('#chatBtn').innerHTML=ico('consulta',20);$('#chat-ic').innerHTML=ico('chispas',18);$('#chat-limpia').innerHTML=ico('basura',16);$('#chat-x').innerHTML=ico('x',18);$('#chat-send').innerHTML=ico('enviar',16);
