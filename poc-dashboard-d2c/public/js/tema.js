/* Tema y modo TV antes del primer pintado, para que no parpadee. Va en un archivo aparte para poder usar una CSP sin scripts en linea. */
try{var d=document.documentElement,t=localStorage.getItem('d2c.tema');
  if(t==='light'||t==='dark')d.dataset.theme=t;
  if(localStorage.getItem('d2c.tv')==='1')d.classList.add('tv');
  var m=document.querySelector('meta[name=theme-color]'),osOscuro=matchMedia('(prefers-color-scheme: dark)').matches;
  if(m)m.content=(t==='dark'||(t!=='light'&&osOscuro))?'#0E1216':'#E4E8EC';}catch(e){}
