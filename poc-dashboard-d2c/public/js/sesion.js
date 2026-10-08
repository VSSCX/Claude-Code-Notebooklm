/* Sesion: si el servidor responde 401 (sin sesion o vencida) se vuelve a la pantalla de acceso; muestra quien es el usuario y su rol. */
(function(){
  var orig=window.fetch;
  window.fetch=function(){
    return orig.apply(this,arguments).then(function(r){
      if(r.status===401&&location.pathname!=='/login.html')location.replace('/login.html?volver='+encodeURIComponent(location.pathname+location.search));
      return r;
    });
  };
  document.addEventListener('DOMContentLoaded',function(){
    orig('/api/yo').then(function(r){return r.ok?r.json():null;}).then(function(j){
      if(!j)return;
      document.documentElement.dataset.rol=j.rol||'';
      var el=document.getElementById('sesion');
      if(!j.auth||!el)return;
      el.hidden=false;
      var rol=document.createElement('span');rol.className='rol';rol.textContent=j.rol;rol.title='Sesión de '+j.usuario;rol.setAttribute('aria-label','Sesión de '+j.usuario+', rol '+j.rol);
      var s=document.createElement('button');s.className='btn sm';s.textContent='Salir';
      s.addEventListener('click',function(){orig('/api/logout',{method:'POST'}).finally(function(){location.replace('/login.html');});});
      el.append(rol,s);
    }).catch(function(){});
  });
})();
