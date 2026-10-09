/* app.js: escala del tablero, render, eventos globales y arranque. Se carga al final de los módulos de arriba. */
/* ============ escala: el tablero se ajusta a la ventana (como "ajustar a la pagina" de Power BI) ============ */
function ajustarEscala(){
  let u=1,flow=false;
  if(innerWidth>=900){
    const rw=S.tv?1280:1440,rh=S.tv?720:860;   // el modo TV parte de un lienzo mucho menor: letra y cifras salen muy grandes
    u=Math.min(3,Math.min(innerWidth/rw,innerHeight/rh));
    if(u<.9){u=.9;flow=true;}                  // en ventanas chicas la letra no baja de 9/10: la pantalla scrollea en vez de achicarse
  }
  document.documentElement.classList.toggle('flow',flow);
  if(Math.abs(u-S.u)<0.01)return false;
  S.u=u;document.documentElement.style.setProperty('--u',u.toFixed(3));return true;
}
function marcarAncho(){   // columnas que se ocultan si la tarjeta queda angosta (umbrales escalados)
  const u=U(),k=S.tv?.72:1;   // en TV el lienzo ya es chico: se esconden menos columnas
  document.querySelectorAll('.card').forEach(c=>{const w=c.clientWidth;
    c.classList.toggle('no-monto',w<800*u*k);c.classList.toggle('no-crea',w<660*u*k);c.classList.toggle('mx-ab',w<440*u*k);});
}

/* ============ render ============ */
function render(){
  renderNav();renderLive();renderTools();renderNotif();
  const b=$('#banner');
  morph(b,S.err?`${ico('alert')}<span>${esc(S.err)}${S.data?', se muestran los últimos datos.':''}</span>`:'');
  b.className=S.err?'on':'';
  const app=$('#app');
  if(!S.data){app.innerHTML=splashHTML(S.err?'No se pudieron cargar los datos':'Cargando datos de VTEX y SAP…',!S.err);S.pintada=null;return;}
  const html=S.view==='pedidos'?vistaPedidos():S.view==='resumen'?vistaResumen():vistaDiagnostico();
  if(S.pintada!==S.view){app.innerHTML=html;S.pintada=S.view;}   // otra pantalla: se arma de cero; la misma: solo cambia lo que cambió
  else morph(app,html);
  if(S.prevTarj&&S.view==='pedidos'){ // destello en las cifras que cambiaron (pedido nuevo, cambio de estado)
    document.querySelectorAll('.trow .tv').forEach(el=>{const k=el.dataset.v;if(S.prevTarj[k]!==undefined&&S.prevTarj[k]!==S.data.tarjetas[k]){const r=el.closest('.trow');r.classList.remove('flash');void r.offsetWidth;r.classList.add('flash');}});
  }
  marcarAncho();ajustarFilas();
  requestAnimationFrame(()=>(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(pintar));
}
function ajustarFilas(){   // en TV una fila cortada a la mitad se lee mal: solo se muestran las filas que caben enteras, y se avisa cuántas faltan
  document.querySelectorAll('.card-b.cut').forEach(b=>{b.classList.remove('cut');b.removeAttribute('data-mas');});
  document.querySelectorAll('.corte').forEach(r=>r.classList.remove('corte'));
  if(!S.tv)return;
  document.querySelectorAll('.card-b:not(.fit)').forEach(b=>{
    const filas=b.querySelectorAll('table.t tbody tr,.crow');if(!filas.length)return;
    const lim=b.getBoundingClientRect().bottom-2;
    const fuera=[...filas].filter(r=>r.getBoundingClientRect().bottom>lim);   // todas las lecturas primero...
    fuera.forEach(r=>r.classList.add('corte'));                                // ...y despues las escrituras
    b.classList.add('cut');if(fuera.length)b.dataset.mas=fuera.length;
  });
}
const splashHTML=(titulo,sk=true)=>`<div class="splash">${sk?'<div class="sk" aria-hidden="true"><i></i><i></i><i></i><i></i></div>':''}<div class="prog" id="prog"><h3>${esc(titulo)}</h3>${sk?'<p>Las consultas corren en paralelo.</p>':''}</div></div>`;
function aplicarTema(){
  const d=document.documentElement;
  if(S.tema==='auto')delete d.dataset.theme;else d.dataset.theme=S.tema;
  guardar('tema',S.tema);
  const m=document.querySelector('meta[name=theme-color]');if(m)m.content=css('--bg');
}
function aplicarTV(){
  document.documentElement.classList.toggle('tv',S.tv);guardar('tv',S.tv?'1':'0');
  ajustarEscala();
}
function irA(v){S.view=v;guardar('vista',v);if(location.hash!=='#'+v)history.replaceState(null,'','#'+v);S.pintada=null;S.mas=false;sincPer();renderNav();renderSlicers();if(S.data)render();cargar();}

/* ============ eventos ============ */
document.addEventListener('click',ev=>{
  if(S.np&&!ev.target.closest('#notif'))cerrarNotif(false);   // clic fuera del panel: se cierra
  if(S.mas&&!ev.target.closest('.mas')){S.mas=false;renderSlicers();}
  if(ev.target.closest('[data-mas]')){S.mas=!S.mas;renderSlicers();if(S.mas){const pm=$('#panel-mas');if(pm)pm.focus();}return;}
  if(ev.target.closest('[data-notif]')){if(!S.np){cerrarPedido(false);cerrarChat(false);}S.np=!S.np;if(S.np)$('#avisos').replaceChildren();renderNotif();if(S.np){const pn=$('#panel-notif');if(pn)pn.focus();}return;}
  if(ev.target.closest('[data-leer-todas]')){S.notifs.forEach(n=>{n.leida=true;});guardarNotifs();renderNotif();return;}
  const ni=ev.target.closest('[data-notif-item]');if(ni){abrirPedidoNotif(ni.dataset.notifItem);return;}
  const pv=ev.target.closest('[data-pv]');if(pv){abrirPedido(pv.dataset.pv,pv);return;}
  const fcan=ev.target.closest('[data-fcanal]');if(fcan){alternar('canal',fcan.dataset.fcanal,ev.ctrlKey||ev.metaKey||ev.shiftKey);return;}
  const fdia=ev.target.closest('[data-fdia]');if(fdia){alternarDia(fdia.dataset.fdia);return;}
  const g=ev.target.closest('[data-go]');if(g){irA(g.dataset.go);return;}
  if(ev.target.closest('[data-ftoggle]')){S.fa=!S.fa;renderSlicers();return;}
  const tm=ev.target.closest('[data-tema]');if(tm){S.tema=tm.dataset.tema;aplicarTema();renderTools();pintar();return;}
  if(ev.target.closest('[data-tv]')){S.tv=!S.tv;aplicarTV();render();return;}
  const al=ev.target.closest('[data-alerta]');
  if(al){const k=al.dataset.alerta;Object.assign(S.filtros,S.filtros.alerta===k?INICIAL():MARC[k]);renderSlicers();if(S.data)render();cargar();return;}
  if(ev.target.closest('[data-limpiar-vista]')){Object.assign(S.filtros,LIMPIAR);renderSlicers();if(S.data)render();cargar();return;}
  const tr=ev.target.closest('[data-tarjeta]');
  if(tr){const k=tr.dataset.tarjeta||null;S.filtros.tarjeta=(k&&S.filtros.tarjeta!==k)?k:null;if(S.data)render();cargar();return;}
  const th=ev.target.closest('[data-ord]');
  if(th){ordenar(th);return;}
  if(ev.target.closest('[data-limpiar-sl]')){S.filtros=VACIO();S.per='auto';S.mas=false;sincPer();S.orden={det:null,crit:null,canal:null};renderSlicers();cargar();return;}
  if(ev.target.closest('#demoSim')){fetch('/api/demo/pedido',{method:'POST'}).then(r=>r.json()).then(p=>toast('Pedido simulado enviado','Aparecerá en unos segundos (Sequence '+p.sequence+')')).catch(()=>{});return;}
});
function ordenar(th){
  const tb=th.dataset.tabla,col=th.dataset.ord,o=S.orden[tb];
  S.orden[tb]=(!o||o.col!==col)?{col,dir:'asc'}:(o.dir==='asc'?{col,dir:'desc'}:null);
  if(tb==='canal')render();else{if(S.data)render();cargar();}
}
document.addEventListener('keydown',ev=>{
  if(ev.key==='Escape'&&S.np){cerrarNotif(true);return;}
  if(ev.key==='Escape'&&S.mas){S.mas=false;renderSlicers();const b=$('[data-mas]');if(b)b.focus();return;}
  const th=ev.target.closest&&ev.target.closest('th[data-ord]');
  if(th&&(ev.key==='Enter'||ev.key===' ')){ev.preventDefault();ordenar(th);}
  const pvk=ev.target.closest&&ev.target.closest('tr[data-pv]');
  if(pvk&&(ev.key==='Enter'||ev.key===' ')){ev.preventDefault();abrirPedido(pvk.dataset.pv,pvk);return;}
  const fr=ev.target.closest&&ev.target.closest('tr[data-fcanal],tr[data-fdia]');
  if(fr&&(ev.key==='Enter'||ev.key===' ')){ev.preventDefault();if(fr.dataset.fcanal)alternar('canal',fr.dataset.fcanal,ev.ctrlKey||ev.metaKey||ev.shiftKey);else alternarDia(fr.dataset.fdia);}
});
document.addEventListener('change',ev=>{
  const sl=ev.target.closest('[data-sl]');if(sl){if(sl.value==='__multi')return;S.filtros[sl.dataset.sl]=sl.value?[sl.value]:[];cargar();return;}
  const bo=ev.target.closest('[data-bodega]');if(bo){S.filtros.bodega=bo.value==='__base'?[...BASE]:bo.value==='__todas'?[]:[bo.value];cargar();return;}
  const ac=ev.target.closest('[data-alcance]');if(ac){S.filtros.alcance=ac.value;cargar();return;}
  const pr=ev.target.closest('[data-per]');if(pr){S.per=pr.value;sincPer();renderSlicers();cargar();return;}
  const fe=ev.target.closest('[data-fecha]');if(fe){S.per='custom';S.filtros[fe.dataset.fecha==='ini'?'fecha_ini':'fecha_fin']=fe.value||null;cargar();}
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
    const el=document.getElementById('prog'); if(!el||S.data||!Object.keys(p).length)return;
    const seg=c.inicio?Math.max(0,Math.round(Date.now()/1000-c.inicio)):null;
    const mk=e=>e==='ok'?ico('check',14):e==='error'?ico('x',14):'…';
    el.innerHTML=`<h3>Cargando datos de VTEX y SAP${seg!=null&&!c.total?`, ${seg} s`:''}</h3>${Object.entries(p).map(([k,v])=>
      `<div class="pp ${v.estado}"><span>${mk(v.estado)}</span>${esc(k)}${v.seg!=null?`<small>${dec1(v.seg)} s${v.filas!=null?', '+fmt(v.filas)+' filas':''}</small>`:''}</div>`).join('')}
      ${c.total?`<p>Consultas listas en ${dec1(c.total)} s, armando el tablero…</p>`:'<p>Las consultas corren en paralelo.</p>'}`;
  }catch(e){}
}

/* ============ arranque ============ */
addEventListener('hashchange',()=>{const v=location.hash.slice(1);if(VISTAS.includes(v)&&v!==S.view)irA(v);});
S.tv=document.documentElement.classList.contains('tv');
ajustarEscala();renderNav();renderTools();renderNotif();$('#app').innerHTML=splashHTML('Cargando datos de VTEX y SAP…');
let _rz=null;
addEventListener('resize',()=>{clearTimeout(_rz);_rz=setTimeout(()=>{if(ajustarEscala()&&S.data)render();else if(S.data)marcarAncho();},150);});
(async()=>{
  try{const c=await(await fetch('/api/config')).json();S.poll=c.poll||5;if(c.demo){$('#demo').hidden=false;if(c.simulable){$('#demoSim').innerHTML=ico('plus')+'Simular pedido';}else $('#demoSim').hidden=true;}}catch(e){}
  S._pr=setInterval(progresoInicial,700);progresoInicial();
  await cargarOpts();await cargar();await poll();
  setInterval(poll,Math.max(1,S.poll)*1000);
  setInterval(renderLive,1000);
  setInterval(()=>{if(S.np)renderNotif();},30000);   // la hora relativa de cada notificación se refresca con el panel abierto
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
})();
