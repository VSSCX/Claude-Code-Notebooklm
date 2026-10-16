"""Herramientas de administracion de seguridad (se ejecutan en tu equipo; no se suben a ningun lado).

  python seguridad_admin.py claves                   genera SESSION_SECRET y SNAPSHOT_KEYS nuevas
  python seguridad_admin.py usuario correo rol       crea la linea para DASH_USUARIOS (rol: lector | analista | admin; pide la clave sin mostrarla)
  python seguridad_admin.py verificar-auditoria      comprueba que la bitacora no fue alterada
  python seguridad_admin.py rotar-clave              genera una clave nueva para anteponer a SNAPSHOT_KEYS (las anteriores siguen abriendo)
"""
import getpass
import secrets
import sys


def main(a: list[str]) -> int:
    if not a:
        print(__doc__)
        return 1
    cmd = a[0]
    if cmd in ("claves", "rotar-clave"):
        from cryptography.fernet import Fernet
        k = Fernet.generate_key().decode()
        if cmd == "claves":
            print("SESSION_SECRET=" + secrets.token_urlsafe(48))
        print("SNAPSHOT_KEYS=" + k + ("   # antepon esta a las anteriores separando con coma" if cmd == "rotar-clave" else ""))
        print("\nGuárdalas en el .env local y en las variables de entorno de Vercel. No las subas al repositorio.")
        return 0
    if cmd == "usuario" and len(a) == 3:
        from app import auth
        if a[2] not in auth.ROLES:
            print("Rol inválido: " + ", ".join(auth.ROLES))
            return 1
        c1, c2 = getpass.getpass("Clave (mínimo 12 caracteres): "), getpass.getpass("Repite la clave: ")
        if c1 != c2 or len(c1) < 12:
            print("Las claves no coinciden o tienen menos de 12 caracteres.")
            return 1
        print(f"{a[1].strip().lower()}:{auth.hash_clave(c1)}:{a[2]}")
        print("\nAgrega esa línea a DASH_USUARIOS (varios usuarios se separan con punto y coma).")
        return 0
    if cmd == "verificar-auditoria":
        from app import auditoria
        r = auditoria.verificar()
        print(("ÍNTEGRA" if r["ok"] else "ALTERADA") + f": {r['registros']} registros" + (f". {r['error']}" if r["error"] else ""))
        return 0 if r["ok"] else 2
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
