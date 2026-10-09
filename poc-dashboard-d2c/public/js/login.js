(function(){
  var f=document.getElementById('f'),err=document.getElementById('err'),ok=document.getElementById('ok');
  function msg(t){err.textContent=t;err.hidden=!t;}
  f.addEventListener('submit',function(ev){
    ev.preventDefault();msg('');
    var u=f.usuario.value.trim(),c=f.clave.value;
    if(!u||!c){msg('Escribe tu correo y tu clave.');return;}
    ok.disabled=true;ok.textContent='Entrando…';
    fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({usuario:u,clave:c})})
      .then(function(r){return r.json().then(function(j){return[r.status,j];});})
      .then(function(x){
        if(x[0]===200){var v=new URLSearchParams(location.search).get('volver')||'/';location.replace(v.charAt(0)==='/'&&v.charAt(1)!=='/'?v:'/');return;}
        msg(x[1].error||'No se pudo entrar.');ok.disabled=false;ok.textContent='Entrar';f.clave.value='';f.clave.focus();
      })
      .catch(function(){msg('No hay conexión con el servidor.');ok.disabled=false;ok.textContent='Entrar';});
  });
})();
