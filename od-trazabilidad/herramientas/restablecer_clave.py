"""Fija la clave de una cuenta directamente en la base (la crea si no existe). Para cuando nadie puede entrar.

Uso, desde la carpeta od-trazabilidad (con la plataforma cerrada o abierta):
    .venv\\Scripts\\python herramientas\\restablecer_clave.py --listar
    .venv\\Scripts\\python herramientas\\restablecer_clave.py VicenteS Elux1234 --admin
    .venv\\Scripts\\python herramientas\\restablecer_clave.py JuanS Elux1234 --nombre "Juan Soto"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import seguridad  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Base, Usuario  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("usuario", nargs="?")
    ap.add_argument("clave", nargs="?")
    ap.add_argument("--admin", action="store_true", help="la cuenta queda como administrador")
    ap.add_argument("--nombre", default="")
    ap.add_argument("--cambiar", action="store_true", help="pedir cambiar la clave en el próximo ingreso")
    ap.add_argument("--listar", action="store_true", help="solo mostrar las cuentas que hay")
    a = ap.parse_args()
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if a.listar or not (a.usuario and a.clave):
            print(f"Base: {engine.url.render_as_string(hide_password=True)}")
            filas = s.scalars(select(Usuario).order_by(Usuario.id)).all()
            for u in filas:
                print(f"  {u.usuario:<14} {u.rol:<9} {'activa' if u.activo else 'DESACTIVADA':<11} {u.nombre}")
            print(f"{len(filas)} cuenta(s)." if filas else "No hay ninguna cuenta.")
            return
        u = seguridad.nombre_usuario(a.usuario)
        motivo = seguridad.validar_clave_nueva(a.clave, u)
        if not u or motivo:
            raise SystemExit(f"No se hizo nada: {motivo or 'usuario inválido'}")
        fila = s.scalar(select(Usuario).where(Usuario.usuario == u))
        nuevo = fila is None
        if nuevo:
            fila = Usuario(usuario=u, nombre=a.nombre or a.usuario, rol="admin" if a.admin else "analista", clave_hash="")
            s.add(fila)
        elif a.admin:
            fila.rol = "admin"
        if a.nombre:
            fila.nombre = a.nombre
        fila.clave_hash = seguridad.hashear(a.clave)
        fila.activo = True
        fila.debe_cambiar_clave = a.cambiar
        s.commit()
        seguridad.cerrar_sesiones_de(s, fila.id)
        print(f"{'Creada' if nuevo else 'Clave restablecida de'} la cuenta {u} ({fila.rol}). Ya puede entrar con esa clave.")


if __name__ == "__main__":
    main()
