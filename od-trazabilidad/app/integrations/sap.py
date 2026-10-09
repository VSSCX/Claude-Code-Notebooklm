"""Lectura de posiciones de VL01N directo desde Python, sin Excel.

Port de Extraer_Datos_VL01N.bas: mismos IDs de pantalla, misma navegación y las
mismas tolerancias (reintentos por celda, espera de sesión ocupada, detección de
columna). Solo LEE: no crea, no modifica y no borra nada en SAP.

Requisitos: Windows, pywin32 y una sesión SAP abierta con scripting habilitado.
"""
import logging
import re
import time
from dataclasses import dataclass, field

log = logging.getLogger("sap")

# Rastro de lo que SAP no aceptó. Antes estos errores se silenciaban y un campo mal
# escrito se veía igual que uno correcto; ahora quedan anotados y viajan al resultado.
_incidencias: list[str] = []


def limpiar_incidencias() -> None:
    _incidencias.clear()


def incidencias() -> list[str]:
    return list(_incidencias)


def anotar(paso: str, error: "Exception | str" = "") -> None:
    txt = f"{paso}: {str(error)[:120]}" if error else paso
    if txt not in _incidencias:
        _incidencias.append(txt)
    log.debug("incidencia SAP - %s", txt)


PESTANA_PICKING = "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02"
TABLA = (PESTANA_PICKING + "/ssubSUBSCREEN_BODY:SAPMV50A:1104/tblSAPMV50ATC_LIPS_PICK")
BARRA_ESTADO = "wnd[0]/sbar"
FOCO = TABLA + "/ctxtLIPS-MATNR[1,3]"
F_MATERIAL = "LIPS-MATNR"
F_ENTREGA = "LIPSD-G_LFIMG"
F_PENDIENTE = "RV50A-LFPMG"
COL_DEFECTO = {F_MATERIAL: 1, F_ENTREGA: 4, F_PENDIENTE: 22}

ESPERA_OCUPADO = 20.0      # segundos
REINTENTOS_CELDA = 5
PAUSA_REINTENTO = 0.15
REINTENTOS_FILA_SIGUIENTE = 3  # confirmaciones antes de dar por vacía una fila que sigue a otra con datos
PAUSA_PAGINA = 0.1         # espera tras mover el scroll (antes 0,5 por fila)
FILAS_VISIBLES = 4         # mínimo de filas por pantalla (se usa PageSize si es mayor)
PANTALLAS_VACIAS = 2       # pantallas seguidas sin datos antes de cortar la lectura


class ErrorSap(RuntimeError):
    pass


@dataclass
class Posicion:
    sku: str
    qty_entrega: float = 0.0
    qty_pendiente: float = 0.0


@dataclass
class Lectura:
    pedido: str
    posiciones: list[Posicion] = field(default_factory=list)
    aviso: str = ""
    duplicados: list[str] = field(default_factory=list)   # materiales repetidos en el pedido
    incidencias: list[str] = field(default_factory=list)  # lo que SAP no aceptó por el camino
    filas_tabla: int = 0                                  # filas que declara SAP en la tabla


ultima_sesion: str = ""        # "SISTEMA/mandante · usuario" de la sesión de SAP que se usó (para el diagnóstico)


def _info_sesion(ses) -> tuple[str, str, str]:
    try:
        i = ses.Info
        return str(i.SystemName or ""), str(i.Client or ""), str(i.User or "")
    except Exception:  # noqa: BLE001
        return "", "", ""


def conectar():
    """Devuelve la sesión SAP que se va a usar. Antes era siempre la primera de la primera conexión: a quien tiene
    SAP abierto en dos sistemas (o una conexión sin iniciar sesión) le tomaba la equivocada y todo fallaba raro.
    Ahora se prefiere una sesión con usuario iniciado, y SAP_SISTEMA permite fijar el sistema (PRD, QAS…)."""
    global ultima_sesion
    from ..config import settings
    try:
        import win32com.client
    except ImportError as e:
        raise ErrorSap("Leer SAP requiere Windows con pywin32 instalado.") from e
    try:
        gui = win32com.client.GetObject("SAPGUI").GetScriptingEngine
    except Exception as e:  # noqa: BLE001
        raise ErrorSap("No se encontró SAP abierto con scripting habilitado. Abre SAP Logon, inicia sesión "
                       "y revisa que el scripting esté activado (SAP GUI → Opciones → Accesibilidad y scripting).") from e
    sesiones = []
    try:
        for i in range(int(gui.Children.Count)):
            con = gui.Children(i)
            for j in range(int(con.Children.Count)):
                sesiones.append(con.Children(j))
    except Exception:  # noqa: BLE001
        sesiones = []
    if not sesiones:
        try:
            sesiones = [gui.Children(0).Children(0)]          # el comportamiento de siempre, si no se puede recorrer
        except Exception as e:  # noqa: BLE001
            raise ErrorSap("No se encontró una sesión SAP activa. Abre SAP e inicia sesión.") from e
    info = [(s, *_info_sesion(s)) for s in sesiones]
    pedido = settings.sap_sistema.strip().upper()
    if pedido:
        coinciden = [x for x in info if x[1].upper() == pedido]
        if coinciden:
            s, sis, cli, usu = next((x for x in coinciden if x[3]), coinciden[0])      # la que ya inició sesión
            ultima_sesion = f"{sis}/{cli} · {usu}"
            return s
        vistos = ", ".join(sorted({f"{sis}/{cli}" for _, sis, cli, _ in info if sis})) or "ninguno"
        raise ErrorSap(f"SAP_SISTEMA={pedido}, pero las sesiones abiertas son: {vistos}. Abre una sesión de {pedido}.")
    con_usuario = [x for x in info if x[3]] or info
    s, sis, cli, usu = con_usuario[0]
    if len({(x[1], x[2]) for x in con_usuario}) > 1:
        log.warning("Hay sesiones de SAP en más de un sistema; se usa %s/%s. Define SAP_SISTEMA para fijarlo.", sis, cli)
    ultima_sesion = f"{sis}/{cli} · {usu}".strip(" ·/")
    return s


def _esperar(ses, timeout: float = ESPERA_OCUPADO):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if not ses.Busy:
                return
        except Exception:  # noqa: BLE001
            return
        time.sleep(0.05)


def _numero(s: str) -> float:
    """'1.234,5' (formato SAP) -> 1234.5"""
    s = (s or "").strip().replace(" ", "")
    if not s or s == "-":
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    m = re.match(r"^-?\d+(\.\d+)?", s)
    return float(m.group()) if m else 0.0


def _por_id(ses, ident):
    try:
        return ses.findById(ident)
    except Exception:  # noqa: BLE001
        return None


def _escribir(ses, ident: str, valor: str):
    campo = _por_id(ses, ident)
    if campo is None:
        return
    try:
        campo.SetFocus()
        campo.Text = ""
        campo.CaretPosition = 0
        campo.Text = valor
        campo.CaretPosition = len(valor)
    except Exception:  # noqa: BLE001
        pass


def _cerrar_popup(ses):
    ventana = _por_id(ses, "wnd[1]")
    if ventana is not None:
        try:
            ventana.sendVKey(0)
        except Exception:  # noqa: BLE001
            pass


_prefijo_celda: dict[str, str] = {}      # "txt" o "ctxt" que usa cada campo: se prueba primero el que ya funcionó


def _leer_celda(ses, campo: str, col: int, fila: int, reintentos: int = REINTENTOS_CELDA) -> str:
    """Texto de una celda de la tabla. Los reintentos esperan a que SAP termine de pintar; una fila
    vacía no los necesita, por eso quien la lee decide cuántos."""
    orden = sorted(("txt", "ctxt"), key=lambda p: p != _prefijo_celda.get(campo))
    for intento in range(reintentos):
        for prefijo in orden:
            celda = _por_id(ses, f"{TABLA}/{prefijo}{campo}[{col},{fila}]")
            if celda is not None:
                try:
                    valor = str(celda.Text).strip()
                except Exception:  # noqa: BLE001
                    valor = ""
                if valor:
                    _prefijo_celda[campo] = prefijo
                    return valor
        if intento < reintentos - 1:
            time.sleep(PAUSA_REINTENTO)
    return ""


def _detectar_columna(ses, campo: str) -> int:
    """Columna del campo en el layout de este analista. Casi siempre es la de fábrica: se prueba
    primero y solo si no está se recorren las demás (antes eran hasta 60 consultas por campo)."""
    candidatas = [COL_DEFECTO[campo]] + [i for i in range(31) if i != COL_DEFECTO[campo]]
    for idx in candidatas:
        for prefijo in ("txt", "ctxt"):
            if _por_id(ses, f"{TABLA}/{prefijo}{campo}[{idx},0]") is not None:
                return idx
    return COL_DEFECTO[campo]


def _tabla_picking(ses, intentos: int = 3):
    """GetPickingTable_NB: selecciona la pestaña de picking y devuelve la tabla."""
    for i in range(intentos):
        pest = _por_id(ses, PESTANA_PICKING)
        if pest is not None:
            try:
                pest.Select()
            except Exception as e:  # noqa: BLE001
                anotar("No se pudo abrir la pestaña de picking", e)
            _esperar(ses)
        if _esperar_objeto(ses, TABLA, 1.0 + 0.5 * i):       # en cuanto aparece sigue, sin pausa fija
            return _por_id(ses, TABLA)
        _cerrar_popup(ses)          # a veces queda un aviso tapando la pantalla
        time.sleep(0.3 * (i + 1))
    return None


def _mensaje_sap(ses) -> str:
    """Texto de la barra de estado: dice por qué SAP no mostró el picking."""
    barra = _por_id(ses, BARRA_ESTADO)
    if barra is None:
        return ""
    try:
        return str(barra.Text or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _posicion(tabla, pedida: int) -> int:
    """Fila en la que quedó realmente la tabla (SAP no deja pasar del final)."""
    try:
        return int(tabla.verticalScrollbar.Position)
    except Exception:  # noqa: BLE001
        return pedida


def _mover(ses, tabla, destino: int, actual: int) -> int:
    """Mueve el scroll y devuelve la fila en la que quedó, esperando a que SAP termine de repintar."""
    try:
        tabla.verticalScrollbar.Position = destino
    except Exception as e:  # noqa: BLE001
        anotar(f"No se pudo mover la tabla a la fila {destino}", e)
    _esperar(ses)
    real = _posicion(tabla, destino)
    for _ in range(3):                                   # pidió avanzar y sigue donde estaba: puede ser lentitud
        if real != actual or destino == actual:
            break
        time.sleep(PAUSA_PAGINA)
        _esperar(ses)
        real = _posicion(tabla, destino)
    time.sleep(PAUSA_PAGINA)
    return real


def _leer_pantalla(ses, cols: dict, visibles: int) -> list[tuple[int, str, float, float]]:
    """Filas de la pantalla actual. Las posiciones son seguidas: en la primera fila vacía se acaba.

    La primera fila de cada pantalla puede llegar tarde, así que tiene todos los reintentos. Después
    de la última con datos basta una confirmación corta: antes cada fila vacía costaba cinco reintentos,
    y un pedido con pocos productos esperaba toda una pantalla de filas vacías."""
    out: list[tuple[int, str, float, float]] = []
    for fila in range(visibles):
        sku = _leer_celda(ses, F_MATERIAL, cols[F_MATERIAL], fila, REINTENTOS_CELDA if fila == 0 else REINTENTOS_FILA_SIGUIENTE)
        if not sku:
            break
        out.append((fila, sku,
                    _numero(_leer_celda(ses, F_ENTREGA, cols[F_ENTREGA], fila)),
                    _numero(_leer_celda(ses, F_PENDIENTE, cols[F_PENDIENTE], fila))))
    return out


def _leer_tabla(ses, lectura: "Lectura") -> list[Posicion]:
    cols = {c: _detectar_columna(ses, c) for c in (F_MATERIAL, F_ENTREGA, F_PENDIENTE)}
    vistos: dict[str, Posicion] = {}
    tabla = _por_id(ses, TABLA)
    if tabla is None:
        return []
    try:
        maximo = int(tabla.verticalScrollbar.Maximum)
    except Exception:  # noqa: BLE001
        maximo = 0
    try:
        visibles = max(int(tabla.verticalScrollbar.PageSize), FILAS_VISIBLES)
    except Exception:  # noqa: BLE001
        visibles = FILAS_VISIBLES
    lectura.filas_tabla = maximo + 1 if maximo > 0 else 0

    foco = _por_id(ses, FOCO)
    if foco is not None:
        try:
            foco.SetFocus()
            foco.CaretPosition = 0
        except Exception as e:  # noqa: BLE001
            anotar("No se pudo poner el foco en la tabla", e)

    # Se avanza por pantalla dejando una fila de traslape. La tabla se acaba cuando una pantalla no se
    # llena y SAP no declara más filas por delante; el máximo que informa SAP es solo una pista (a veces
    # dice 0 aunque haya muchas filas, y con un solo producto también dice 0).
    paso = max(visibles - 1, 1)
    leidas_abs: set[int] = set()        # filas ya procesadas (las pantallas se superponen)
    pedido_scroll, actual, vacias = 0, -1, 0
    while True:
        actual_nuevo = _mover(ses, tabla, pedido_scroll, actual)
        if actual_nuevo == actual:
            break                                       # no pudo avanzar: se llegó al final
        actual = actual_nuevo
        tabla = _por_id(ses, TABLA) or tabla
        pantalla = _leer_pantalla(ses, cols, visibles)
        for fila, sku, ent, pen in pantalla:
            absoluta = actual + fila                    # fila real dentro de la tabla
            if absoluta in leidas_abs:
                continue                                # ya la leímos en la pantalla anterior
            leidas_abs.add(absoluta)
            if sku in vistos:
                if sku not in lectura.duplicados:
                    lectura.duplicados.append(sku)      # igual que el Excel: manda la 1a fila
                continue
            vistos[sku] = Posicion(sku=sku, qty_entrega=ent, qty_pendiente=pen)
        vacias = vacias + 1 if not pantalla else 0
        llena = len(pantalla) >= visibles
        if not llena and actual >= maximo:
            break                                       # la pantalla no se llenó y SAP no declara más
        if vacias >= PANTALLAS_VACIAS:
            break                                       # varias pantallas vacías seguidas: no hay más
        pedido_scroll = actual + paso if llena else min(actual + paso, maximo)
        if not llena and pedido_scroll <= actual:
            break
    return list(vistos.values())


def leer_pedido(pedido: str, puesto: str, fecha: str, ses=None) -> Lectura:
    """Abre VL01N con el pedido y devuelve sus posiciones. fecha en dd.MM.yyyy."""
    ses = ses or conectar()
    okcd = _por_id(ses, "wnd[0]/tbar[0]/okcd")
    if okcd is None:
        raise ErrorSap("La ventana de SAP no responde al scripting.")
    okcd.Text = "/nVL01N"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    _esperar_objeto(ses, "wnd[0]/usr/ctxtLV50C-VBELN", 3)      # la pantalla de entrada ya está lista
    _cerrar_popup(ses)

    for ident in ("wnd[0]/usr/ctxtLIKP-VSTEL", "wnd[0]/usr/ctxtLV50C-DATBI",
                  "wnd[0]/usr/ctxtLV50C-VBELN"):
        campo = _por_id(ses, ident)
        if campo is not None:
            campo.Text = ""
    _escribir(ses, "wnd[0]/usr/ctxtLIKP-VSTEL", puesto)
    _escribir(ses, "wnd[0]/usr/ctxtLV50C-DATBI", fecha)
    _escribir(ses, "wnd[0]/usr/ctxtLV50C-VBELN", pedido)

    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    _cerrar_popup(ses)

    limpiar_incidencias()
    lectura = Lectura(pedido=pedido)
    if _tabla_picking(ses) is None:
        msg = _mensaje_sap(ses)
        lectura.aviso = ("No se encontró la tabla de picking." +
                         (f" SAP dice: {msg}" if msg else
                          " Revisa el pedido, el puesto y la fecha, o si ya está entregado."))
        return lectura
    lectura.posiciones = _leer_tabla(ses, lectura)
    avisos = []
    if not lectura.posiciones:
        msg = _mensaje_sap(ses)
        avisos.append("El pedido no devolvió posiciones." + (f" SAP dice: {msg}" if msg else ""))
    if lectura.duplicados:
        avisos.append("El pedido trae más de una línea para: " + ", ".join(lectura.duplicados) +
                      ". Se leyó la primera de cada uno, igual que el Excel.")
    if lectura.filas_tabla and len(lectura.posiciones) + len(lectura.duplicados) < lectura.filas_tabla:
        avisos.append(f"SAP declara {lectura.filas_tabla} líneas y se leyeron "
                      f"{len(lectura.posiciones) + len(lectura.duplicados)}: revisa el pedido en VL01N.")
    lectura.incidencias = incidencias()
    if lectura.incidencias:
        avisos.append(f"{len(lectura.incidencias)} paso(s) que SAP no aceptó: " +
                      "; ".join(lectura.incidencias[:3]))
    lectura.aviso = " ".join(avisos)
    return lectura


# ===========================================================================
# ZSD001_03 — Qty en entrega por producto (port de Qty_Entrega.bas)
# Mismos filtros que el Excel: TC04 / VCT4 / canal 14-15 / clases ZC34-ZC32,
# pedidos desde hace un mes hasta dentro de un mes, cliente y materiales.
# ===========================================================================
MULTI = ("wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/"
         "tblSAPLALDBSINGLE")


def _multi_celda(fila: int) -> str:
    return f"{MULTI}/ctxtRSCSEL_255-SLOW_I[1,{fila}]"


def _presionar(ses, ident: str, espera: float = 5, opcional: bool = False):
    obj = _por_id(ses, ident)
    if obj is None:
        if opcional:
            return
        anotar(f"No existe el botón {ident.rsplit('/', 1)[-1]}")
        return
    try:
        obj.press()
    except Exception as e:  # noqa: BLE001
        anotar(f"No se pudo presionar {ident.rsplit('/', 1)[-1]}", e)
    _esperar(ses, espera)


def _texto(ses, ident: str, valor: str):
    obj = _por_id(ses, ident)
    if obj is None:
        anotar(f"No existe el campo {ident.rsplit('/', 1)[-1]}")
        return
    try:
        obj.Text = valor
    except Exception as e:  # noqa: BLE001
        anotar(f"No se pudo escribir {ident.rsplit('/', 1)[-1]} = {valor}", e)


def _cargar_multiseleccion(ses, valores: list[str]) -> int:
    tabla = _por_id(ses, MULTI)
    if tabla is None:
        return 0
    try:
        visibles = int(tabla.verticalScrollbar.PageSize) or 20
    except Exception:  # noqa: BLE001
        visibles = 20
    escritos = 0
    for i, v in enumerate(valores):
        base = (i // visibles) * visibles
        local = i - base
        if local == 0 and i > 0:
            tabla = _por_id(ses, MULTI)
            try:
                tabla.verticalScrollbar.Position = base
            except Exception:  # noqa: BLE001
                pass
            _esperar(ses, 3)
        celda = _por_id(ses, _multi_celda(local))
        if celda is not None:
            celda.Text = str(v)
            escritos += 1
    return escritos


def _sumar_meses(d, meses: int):
    import calendar
    m = d.month - 1 + meses
    y, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def carpeta_export(base=None) -> "Path":
    """Carpeta donde SAP deja la exportación. Siempre la misma por instalación (SAP_EXPORT_DIR, o data\\sap),
    y se comprueba ANTES de abrir SAP que se puede escribir ahí y que la ruta le sirve a SAP (corta, sin tildes).
    Si no sirve, cae a una carpeta fija y simple del equipo en vez de fallar al final del análisis."""
    import tempfile
    from pathlib import Path
    from ..config import BASE_DIR, settings
    candidatas = [Path(settings.sap_export_dir)] if settings.sap_export_dir.strip() else []
    candidatas += [Path(base) if base else BASE_DIR / "data" / "sap", Path(tempfile.gettempdir()) / "OrderDesk" / "sap"]
    for c in candidatas:
        ruta = str(c)
        if not ruta.isascii() or len(ruta) > 100:
            log.warning("Carpeta de exportación descartada (tildes o ruta larga): %s", ruta)
            continue
        try:
            c.mkdir(parents=True, exist_ok=True)
            prueba = c / ".escritura"
            prueba.write_text("ok")
            prueba.unlink()
            return c
        except OSError as e:
            log.warning("Carpeta de exportación sin permiso de escritura: %s (%s)", ruta, e)
    raise ErrorSap("No hay una carpeta donde guardar la exportación de ZSD001_03. Define SAP_EXPORT_DIR en el .env "
                   "con una ruta corta y sin tildes (ej. C:\\OrderDesk\\sap).")


NOMBRE_PUBLICADO = "Qty En Entrega.xlsx"
FILA_LAYOUT = 43                   # el layout que elige la macro del Excel: es una POSICIÓN en la lista, distinta si el analista tiene layouts propios


def _fila_layout(layout) -> int:
    """Fila del layout a usar. Con ZSD_LAYOUT se busca por nombre; si no, la fila 43 de la macro, comprobando que exista
    (con menos layouts en la lista, esa fila no existe y antes SAP quedaba con el layout que tuviera, sin avisar)."""
    from ..config import settings
    try:
        n = int(layout.RowCount)
    except Exception:  # noqa: BLE001
        n = 0
    nombre = settings.zsd_layout.strip().lower()
    if nombre:
        textos = []
        for i in range(n):
            try:
                t = str(layout.GetCellValue(i, "TEXT") or "")
            except Exception:  # noqa: BLE001
                t = ""
            textos.append(t)
            if nombre in t.lower():
                return i
        raise ErrorSap(f"No hay un layout que contenga «{settings.zsd_layout}» en ZSD001_03. "
                       f"Layouts de este usuario (primeros 8): {', '.join(x.strip() for x in textos[:8] if x.strip())}.")
    if n and FILA_LAYOUT >= n:
        raise ErrorSap(f"El layout de ZSD001_03 que usa la macro es el de la fila {FILA_LAYOUT}, pero este usuario solo tiene {n} layouts. "
                       "Define ZSD_LAYOUT en el .env con el nombre del layout (el mismo que usa la macro).")
    return FILA_LAYOUT


def validar_columnas(filas: list[dict], layout: str = "") -> None:
    """El análisis necesita el nombre del material y la Qty en entrega. Con otro layout esas columnas no vienen y la
    Qty en entrega quedaba en 0 sin que nadie lo notara: ahora se detiene diciendo qué columnas llegaron."""
    if not filas:
        return
    from ..analisis import _col
    f0 = filas[0]
    faltan = [n for n, alts in (("Nombre Codigo de Material", ("Nombre Codigo de Material", "Nombre Código de Material")),
                                ("Qty. En Entrega", ("Qty. En Entrega", "Qty En Entrega"))) if _col(f0, *alts) is None]
    if faltan:
        raise ErrorSap(f"El archivo de ZSD001_03 no trae la columna {' ni '.join(faltan)}. Columnas recibidas: "
                       f"{', '.join(list(f0)[:10])}. Layout elegido: «{layout or 'desconocido'}». "
                       "Usa el mismo layout de la macro (ZSD_LAYOUT en el .env).")


def revisar_publicacion() -> str:
    """Antes de abrir SAP: ¿se puede escribir en la ruta fija donde queda publicado el archivo? '' si sí (o si no se publica);
    si no, el motivo. Igual que la macro, que verificaba la carpeta antes de empezar."""
    from pathlib import Path
    from ..config import settings
    destino = settings.zsd_publicar_dir.strip()
    if not destino:
        return ""
    try:
        d = Path(destino)
        if not d.is_dir():
            return f"No se llega a la carpeta de publicación: {destino}"
        prueba = d / f".escritura-{time.time_ns()}"
        prueba.write_text("ok")
        prueba.unlink()
        return ""
    except OSError as e:
        return f"Sin permiso de escritura en {destino}: {e}"


def publicar_export(origen, carpeta=None) -> dict:
    """Deja una copia del archivo exportado en la ruta fija con el nombre fijo, sin que nadie lea un archivo a medias:
    se copia con un nombre temporal en la misma carpeta y se reemplaza de una vez. Luego se comprueba tamaño y que abre.
    Devuelve {'ok', 'ruta', 'motivo'}."""
    import os
    import shutil
    from pathlib import Path
    from ..config import settings
    carpeta = str(carpeta).strip() if carpeta is not None else settings.zsd_publicar_dir.strip()
    if not carpeta:
        return {"ok": False, "ruta": "", "motivo": "", "omitido": True}
    destino = Path(carpeta) / NOMBRE_PUBLICADO
    tmp = Path(carpeta) / f".{NOMBRE_PUBLICADO}.{os.getpid()}.tmp"
    ultimo = ""
    for intento in range(4):
        try:
            shutil.copyfile(origen, tmp)
            os.replace(tmp, destino)                     # atómico: quien lea ve el archivo anterior o el nuevo, nunca uno a medias
            if destino.stat().st_size != Path(origen).stat().st_size:
                raise OSError("el tamaño copiado no coincide con el exportado")
            with open(destino, "rb"):
                pass
            return {"ok": True, "ruta": str(destino), "motivo": ""}
        except OSError as e:
            ultimo = str(e)
            try:
                tmp.unlink()
            except OSError:
                pass
            time.sleep(1.0 + intento)                    # lo más común: alguien tiene el archivo abierto en Excel
    motivo = (f"No se pudo publicar en {destino}: {ultimo}. Si alguien lo tiene abierto en Excel, que lo cierre; "
              "si la carpeta no responde, revisa la red o la VPN.")
    return {"ok": False, "ruta": str(destino), "motivo": motivo}


def zsd001_03(cliente_cod: "str | list[str]", materiales: list[str], carpeta: str, nombre: str, avisar=None, publicado=None) -> list[dict]:
    """Ejecuta ZSD001_03, exporta el resultado y devuelve sus filas como diccionarios.
    SAP guarda en una carpeta LOCAL (corta, sin tildes, sin permisos de red que pidan confirmación) y de ahí se publica
    una copia en la ruta fija de la macro. `publicado` (dict) recibe el resultado de la publicación."""
    import datetime as dt
    from pathlib import Path

    limpiar_incidencias()
    ses = conectar()
    try:
        ses.findById("wnd[0]").maximize()
    except Exception:  # noqa: BLE001
        pass
    okcd = _por_id(ses, "wnd[0]/tbar[0]/okcd")
    if okcd is None:
        raise ErrorSap("La ventana de SAP no responde al scripting.")
    okcd.Text = "/NZSD001_03"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 30)
    _presionar(ses, "wnd[1]/tbar[0]/btn[0]", 10, opcional=True)      # el aviso inicial solo sale a veces
    if _por_id(ses, "wnd[0]/usr/ctxtSOSOCFAC-LOW") is None:
        raise ErrorSap("No se pudo abrir ZSD001_03" + (": " + "; ".join(incidencias()[:3]) if incidencias() else "") + ".")

    _texto(ses, "wnd[0]/usr/ctxtSOSOCFAC-LOW", "TC04")
    _texto(ses, "wnd[0]/usr/ctxtSOORGVEN-LOW", "VCT4")

    # Canal de distribución 14 y 15
    _presionar(ses, "wnd[0]/usr/btn%_SOCANDIS_%_APP_%-VALU_PUSH", 10)
    if _por_id(ses, "wnd[1]") is not None:
        _presionar(ses, "wnd[1]/tbar[0]/btn[16]", 3)
        _texto(ses, _multi_celda(0), "14")
        _texto(ses, _multi_celda(1), "15")
        _presionar(ses, "wnd[1]/tbar[0]/btn[0]")
        _presionar(ses, "wnd[1]/tbar[0]/btn[8]")

    # Clase de documento ZC34 y ZC32
    _texto(ses, "wnd[0]/usr/ctxtSOCLADOC-LOW", "ZC34")
    _presionar(ses, "wnd[0]/usr/btn%_SOCLADOC_%_APP_%-VALU_PUSH", 10)
    if _por_id(ses, "wnd[1]") is not None:
        _texto(ses, _multi_celda(1), "ZC32")
        _presionar(ses, "wnd[1]/tbar[0]/btn[0]")
        _presionar(ses, "wnd[1]/tbar[0]/btn[8]")

    hoy = dt.date.today()
    desde, hasta = _sumar_meses(hoy, -1), _sumar_meses(hoy, 1)   # igual que DateAdd("m", ±1)
    _texto(ses, "wnd[0]/usr/ctxtSOFECPED-LOW", desde.strftime("%d.%m.%Y"))
    _texto(ses, "wnd[0]/usr/ctxtSOFECPED-HIGH", hasta.strftime("%d.%m.%Y"))
    codigos = [cliente_cod] if isinstance(cliente_cod, str) else [str(c) for c in cliente_cod if c]
    if len(codigos) == 1:
        _texto(ses, "wnd[0]/usr/ctxtSOSOLIC-LOW", codigos[0])
    elif codigos:
        # Clientes que comparten plan (REGION 2 / REGION 3): todos sus solicitantes en una sola consulta
        _presionar(ses, "wnd[0]/usr/btn%_SOSOLIC_%_APP_%-VALU_PUSH", 10)
        if _por_id(ses, "wnd[1]") is not None:
            _presionar(ses, "wnd[1]/tbar[0]/btn[16]", 3)
            cargados = _cargar_multiseleccion(ses, codigos)
            if cargados < len(codigos) and avisar:
                avisar(f"Se cargaron {cargados} de {len(codigos)} solicitantes del grupo en ZSD001_03: "
                       "la Qty en entrega puede salir incompleta.")
            _presionar(ses, "wnd[1]/tbar[0]/btn[0]")
            _presionar(ses, "wnd[1]/tbar[0]/btn[8]")
        else:
            _texto(ses, "wnd[0]/usr/ctxtSOSOLIC-LOW", codigos[0])
            if avisar:
                avisar("No se pudo abrir la selección múltiple de solicitantes: se consultó solo el cliente analizado.")

    if materiales:
        _presionar(ses, "wnd[0]/usr/btn%_SOCODMAT_%_APP_%-VALU_PUSH", 10)
        if _por_id(ses, "wnd[1]") is not None:
            _presionar(ses, "wnd[1]/tbar[0]/btn[16]", 3)
            cargados = _cargar_multiseleccion(ses, materiales)
            if cargados < len(materiales) and avisar:
                avisar(f"Se cargaron {cargados} de {len(materiales)} materiales en el filtro de ZSD001_03: "
                       "la Qty en entrega puede salir incompleta.")
            _presionar(ses, "wnd[1]/tbar[0]/btn[0]")
            _presionar(ses, "wnd[1]/tbar[0]/btn[8]")

    _presionar(ses, "wnd[0]/tbar[1]/btn[8]", 120)   # Ejecutar

    # Si SAP no encontró nada, no hay lista que exportar: se dice con sus palabras en vez de fallar más adelante
    if _por_id(ses, "wnd[0]/tbar[1]/btn[33]") is None:
        msg = _mensaje_sap(ses)
        if re.search(r"no se (han )?(seleccion|encontr)|sin datos|no data|no hay", msg, re.I):
            if avisar:
                avisar("ZSD001_03 no encontró entregas para este cliente y estos materiales: la Qty en entrega queda en 0.")
            return []
        raise ErrorSap("ZSD001_03 no mostró la lista de resultados" + (f" (SAP dice: «{msg[:150]}»)." if msg else "."))

    # Layout y exportación (mismos pasos que el Excel)
    _presionar(ses, "wnd[0]/tbar[1]/btn[33]", 5)
    layout = _por_id(ses, "wnd[1]/usr/ssubD0500_SUBSCREEN:SAPLSLVC_DIALOG:0501/cntlG51_CONTAINER/shellcont/shell")
    elegido = ""
    if layout is not None:
        fila = _fila_layout(layout)
        try:
            elegido = str(layout.GetCellValue(fila, "TEXT") or "").strip()
            layout.setCurrentCell(fila, "TEXT")
            layout.firstVisibleRow = max(0, fila - 7)
            layout.selectedRows = str(fila)
            layout.clickCurrentCell()
        except Exception as e:  # noqa: BLE001
            anotar(f"No se pudo elegir el layout de la fila {fila}", e)
        _esperar(ses, 5)
    else:
        anotar("SAP no mostró la lista de layouts")
    if publicado is not None:
        publicado["layout"] = elegido
    menu = _por_id(ses, "wnd[0]/mbar/menu[0]/menu[3]/menu[1]")
    if menu is not None:
        menu.Select()
        _esperar(ses, 5)
    radio = _por_id(ses, "wnd[1]/usr/radRB_3")
    if radio is not None:
        radio.Select()
    _presionar(ses, "wnd[1]/tbar[0]/btn[0]", 5)
    if _por_id(ses, "wnd[1]/usr/ctxtDY_PATH") is None:
        raise ErrorSap("ZSD001_03 no mostró el diálogo para guardar el archivo" + _ventana_inesperada(ses) + ".")

    Path(carpeta).mkdir(parents=True, exist_ok=True)
    destino = Path(carpeta) / nombre
    _limpiar_exportaciones(Path(carpeta), conservar=destino)
    _texto(ses, "wnd[1]/usr/ctxtDY_PATH", str(carpeta))
    _texto(ses, "wnd[1]/usr/ctxtDY_FILENAME", nombre)
    campo = _por_id(ses, "wnd[1]/usr/ctxtDY_PATH")
    try:
        puesto = str(campo.Text).strip().rstrip("\\/") if campo is not None else ""
    except Exception:  # noqa: BLE001
        puesto = ""
    if puesto and puesto.lower() != str(carpeta).rstrip("\\/").lower():
        raise ErrorSap(f"SAP cambió la carpeta de guardado: pedí «{carpeta}» y quedó «{puesto}». "
                       "Define SAP_EXPORT_DIR con una ruta corta y sin tildes.")
    _presionar(ses, "wnd[1]/tbar[0]/btn[11]", 10)    # Reemplazar / guardar

    _esperar_archivo(ses, destino)
    try:
        filas = leer_export(destino)
        validar_columnas(filas, (publicado or {}).get("layout", ""))
        if incidencias() and avisar:
            avisar(f"{len(incidencias())} paso(s) de ZSD001_03 que SAP no aceptó: " + "; ".join(incidencias()[:3]))
        # solo se guarda lo que ya se pudo leer: la última exportación queda siempre en la carpeta local con nombre fijo
        local = publicar_export(destino, Path(carpeta))
        if publicado is not None:
            publicado.update(local)
        if not local["ok"] and local.get("motivo") and avisar:
            avisar(local["motivo"])
        red = publicar_export(destino)                    # copia opcional en otra ruta (ZSD_PUBLICAR_DIR)
        if not red["ok"] and red.get("motivo") and avisar:
            avisar(red["motivo"])
        if publicado is not None and not red.get("omitido"):
            publicado["copia"] = red
        log.info("ZSD001_03 exportado (%s filas); local: %s; copia: %s", len(filas), local, red)
        return filas
    finally:
        pass     # el archivo NO se borra aquí: SAP lo abre en Excel apenas lo guarda y, si ya no existe, Excel dice «no hemos encontrado…»


def _ventana_inesperada(ses) -> str:
    """' (SAP muestra: «título»)' si hay una ventana abierta que el flujo no esperaba, p. ej. la de seguridad de SAP GUI."""
    if _por_id(ses, "wnd[1]") is None:
        return ""
    try:
        titulo = " ".join(str(ses.findById("wnd[1]").Text or "").split())
    except Exception:  # noqa: BLE001
        titulo = ""
    return f" (SAP muestra una ventana: «{titulo[:90]}»)" if titulo else " (SAP muestra una ventana que no esperaba)"


def _limpiar_exportaciones(carpeta, conservar=None, dias: float = 1.0) -> None:
    """Borra exportaciones viejas que hayan quedado de análisis interrumpidos."""
    limite = time.time() - dias * 86400
    for f in carpeta.glob("Qty En Entrega*.xls*"):
        try:
            if f != conservar and f.name != NOMBRE_PUBLICADO and f.stat().st_mtime < limite:
                f.unlink()
        except OSError:
            pass


def _esperar_archivo(ses, destino, maximo: float = 60.0) -> None:
    """Espera a que SAP termine de escribir el archivo: existe, tiene contenido, deja de crecer y se puede abrir.
    Antes se leía apenas aparecía (más 1 s fijo): un archivo a medio escribir se leía vacío y el análisis seguía
    con la Qty en entrega en cero."""
    t0, ultimo, estable = time.time(), -1, 0
    while time.time() - t0 < maximo:
        try:
            tam = destino.stat().st_size if destino.exists() else -1
        except OSError:
            tam = -1
        if tam > 0 and tam == ultimo:
            estable += 1
            if estable >= 2:
                try:
                    with open(destino, "rb"):
                        return
                except OSError:
                    estable = 0                     # todavía lo tiene abierto quien lo escribe
        else:
            estable = 0
        ultimo = tam
        if tam < 0 and time.time() - t0 > 4 and _por_id(ses, "wnd[1]") is not None:
            # SAP sigue mostrando una ventana y no hay archivo: casi siempre es el aviso de seguridad de SAP GUI
            # (acceso a archivos) o un error al guardar. Se dice cuál es en vez de esperar al vacío.
            raise ErrorSap(f"SAP no guardó el archivo de ZSD001_03{_ventana_inesperada(ses)}. "
                           f"Si es el aviso de seguridad de SAP GUI, márcalo como «Permitir siempre» para la carpeta {destino.parent} "
                           "(o pide a TI que la agregue a las rutas permitidas del scripting de SAP GUI).")
        time.sleep(0.5)
    if not destino.exists():
        raise ErrorSap(f"ZSD001_03 no generó el archivo {destino.name} en {destino.parent}. Revisa que SAP pueda escribir en esa carpeta.")
    raise ErrorSap(f"El archivo {destino.name} de ZSD001_03 no terminó de guardarse (sigue abierto o creciendo).")


def leer_export(ruta) -> list[dict]:
    """Lee el archivo exportado por SAP. Acepta xlsx real o texto con tabuladores."""
    from pathlib import Path
    ruta = Path(ruta)
    try:
        from openpyxl import load_workbook
        wb = load_workbook(ruta, read_only=True, data_only=True)
        filas = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
        wb.close()
    except Exception:  # noqa: BLE001 - SAP a veces guarda texto con extensión .xlsx
        texto = None
        for enc in ("utf-16", "utf-8-sig", "cp1252"):
            try:
                texto = ruta.read_text(encoding=enc)
                if "\t" in texto:
                    break
            except Exception:  # noqa: BLE001
                continue
        filas = [linea.split("\t") for linea in (texto or "").splitlines()]
    filas = [f for f in filas if any(str(c or "").strip() for c in f)]
    if not filas:
        raise ErrorSap("El archivo exportado de ZSD001_03 llegó vacío: SAP no lo escribió completo. Vuelve a intentar.")
    i_cab = next((i for i, f in enumerate(filas[:15])
                  if any("material" in str(c or "").lower() for c in f)), None)
    if i_cab is None:
        raise ErrorSap("El archivo exportado de ZSD001_03 no trae la columna de material: no tiene el formato esperado. "
                       "Revisa el layout elegido en SAP.")
    cab = [str(c or "").strip() for c in filas[i_cab]]
    return [{cab[j]: f[j] for j in range(min(len(cab), len(f))) if cab[j]}
            for f in filas[i_cab + 1:]]


# ===========================================================================
# MMBE — stock por almacén (port de Consultar_MMBE.bas)
# ===========================================================================
MMBE_ARBOL = "wnd[0]/usr/cntlCC_CONTAINER/shellcont/shell/shellcont[1]/shell[1]"
MMBE_GRILLA = "wnd[1]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell"
FILA_CD30, FILA_EC01, FILA_TP01 = "          4", "          6", "          8"
COL_STOCK = "C          2"


def _entero_sap(v) -> int:
    s = str(v or "").strip().replace(" ", "").replace(".", "").replace(",", ".")
    if not s or s == "-":
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _esperar_objeto(ses, ident: str, seg: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < seg:
        if _por_id(ses, ident) is not None:
            return True
        time.sleep(0.05)
    return False


def _popup_almacen(ses, fila: str) -> tuple[int, int]:
    """Abre el detalle de un almacén y devuelve (stock neto, reserva)."""
    arbol = _por_id(ses, MMBE_ARBOL)
    if arbol is None:
        return 0, 0
    try:
        arbol.selectItem(fila, COL_STOCK)
        arbol.ensureVisibleHorizontalItem(fila, COL_STOCK)
        arbol.doubleClickItem(fila, COL_STOCK)
    except Exception:  # noqa: BLE001
        return 0, 0
    if not _esperar_objeto(ses, "wnd[1]", 8):
        return 0, 0
    stock = reserva = 0
    grilla = _por_id(ses, MMBE_GRILLA)
    if grilla is not None:
        try:
            libre = _entero_sap(grilla.GetCellValue(0, "BSTNDTXT"))
            e = _entero_sap(grilla.GetCellValue(10, "BSTNDTXT"))
            reserva = _entero_sap(grilla.GetCellValue(13, "BSTNDTXT"))
            stock = libre - e - reserva
        except Exception:  # noqa: BLE001
            pass
    try:
        ses.findById("wnd[1]").Close()
    except Exception:  # noqa: BLE001
        pass
    return stock, reserva


def mmbe(skus: list[str], avance=None) -> dict[str, dict]:
    """Stock neto CD30, reserva CD30, stock neto EC01 y TP01 por SKU (centro CE02)."""
    if not skus:
        return {}
    ses = conectar()
    try:
        ses.findById("wnd[0]").maximize()
    except Exception:  # noqa: BLE001
        pass
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "/NMMBE"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    time.sleep(0.5)
    _texto(ses, "wnd[0]/usr/ctxtMS_WERKS-LOW", "CE02")
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)

    _presionar(ses, "wnd[0]/usr/btn%_MS_LGORT_%_APP_%-VALU_PUSH", 5)
    time.sleep(0.4)
    for i, alm in enumerate(("CD30", "EC01", "TP01")):
        _texto(ses, _multi_celda(i), alm)
    _presionar(ses, "wnd[1]/tbar[0]/btn[0]")
    _presionar(ses, "wnd[1]/tbar[0]/btn[8]")

    _texto(ses, "wnd[0]/usr/ctxtMS_CHARG-LOW", "LOTE1")
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    for ident, valor in (("wnd[0]/usr/chkKZNUL", False), ("wnd[0]/usr/chkKZLSO", False),
                         ("wnd[0]/usr/chkKZLON", True)):
        obj = _por_id(ses, ident)
        if obj is not None:
            try:
                obj.Selected = valor
            except Exception:  # noqa: BLE001
                pass
    time.sleep(0.2)

    out = {}
    for n, sku in enumerate(skus, 1):
        if avance:
            avance(f"Consultando stock MMBE {n} de {len(skus)}")
        _texto(ses, "wnd[0]/usr/ctxtMS_MATNR-LOW", sku)
        ses.findById("wnd[0]/tbar[1]/btn[8]").press()
        _esperar(ses)
        _esperar_objeto(ses, MMBE_ARBOL, 12)
        cd30, reserva = _popup_almacen(ses, FILA_CD30)
        ec01, _ = _popup_almacen(ses, FILA_EC01)
        tp01, _ = _popup_almacen(ses, FILA_TP01)
        out[sku] = {"cd30": cd30, "reserva_cd30": reserva, "ec01": ec01, "tp01": tp01}
        _presionar(ses, "wnd[0]/tbar[0]/btn[3]", 5)   # volver a la selección
    return out


# ===========================================================================
# Borrado en SAP (port de los scripts grabados: VL06 para entregas, VG02 para grupos)
# Solo se ejecuta con confirmación explícita del usuario y se verifica el resultado.
# ===========================================================================
POPUP_SI = "wnd[1]/usr/btnSPOP-OPTION1"


def _hay_popup(ses) -> bool:
    return _por_id(ses, "wnd[1]") is not None


def borrar_entrega(entrega: str, ses=None) -> tuple[bool, str]:
    """VL06 -> lista de entregas -> selecciona la entrega -> borrar -> confirmar."""
    ses = ses or conectar()
    try:
        ses.findById("wnd[0]").maximize()
    except Exception:  # noqa: BLE001
        pass
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "/nvl06"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    _presionar(ses, "wnd[0]/usr/btnBUTTON1", 10)          # entregas para picking
    for campo in ("wnd[0]/usr/ctxtIT_KODAT-LOW", "wnd[0]/usr/ctxtIT_KODAT-HIGH"):
        obj = _por_id(ses, campo)
        if obj is not None:
            obj.Text = ""
    _presionar(ses, "wnd[0]/tbar[1]/btn[19]", 10)         # más criterios de selección
    campo = _por_id(ses, "wnd[0]/usr/ctxtIT_VBELN-LOW")
    if campo is None:
        return False, "VL06 no mostró el campo de entrega; revisa la pantalla en SAP."
    campo.Text = str(entrega)
    _presionar(ses, "wnd[0]/tbar[1]/btn[8]", 60)          # ejecutar

    fila = _por_id(ses, "wnd[0]/usr/lbl[6,5]")
    if fila is None:
        msg = _mensaje_sap(ses)
        return False, f"La entrega {entrega} no aparece en VL06." + (f" SAP dice: {msg}" if msg else "")
    try:
        fila.SetFocus()
        fila.CaretPosition = 2
    except Exception:  # noqa: BLE001
        pass
    ses.findById("wnd[0]").sendVKey(2)                    # abrir la entrega
    _esperar(ses, 30)
    _presionar(ses, "wnd[0]/tbar[1]/btn[25]", 10)         # marcar todas las posiciones
    _presionar(ses, "wnd[0]/tbar[1]/btn[14]", 10)         # borrar
    if not _hay_popup(ses):
        msg = _mensaje_sap(ses)
        return False, ("SAP no pidió confirmación: probablemente la entrega no se puede borrar "
                       "(facturada, con salida de mercancía o dentro de un grupo)." +
                       (f" Dice: {msg}" if msg else ""))
    _presionar(ses, POPUP_SI, 30)
    mensaje = _mensaje_sap(ses)
    for _ in range(3):
        _presionar(ses, "wnd[0]/tbar[0]/btn[3]", 5)       # volver al menú
    ok = "borrad" in mensaje.lower() or "elimin" in mensaje.lower() or mensaje == ""
    return ok, mensaje or f"Entrega {entrega} borrada."


def borrar_grupo(grupo: str, ses=None) -> tuple[bool, str]:
    """VG02 -> abre el grupo -> borrar -> confirmar."""
    ses = ses or conectar()
    try:
        ses.findById("wnd[0]").maximize()
    except Exception:  # noqa: BLE001
        pass
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "/nvg02"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    campo = _por_id(ses, "wnd[0]/usr/ctxtVBSK-SAMMG")
    if campo is None:
        return False, "VG02 no mostró el campo de grupo."
    campo.Text = str(grupo)
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 30)
    msg = _mensaje_sap(ses)
    if "no existe" in msg.lower():
        return False, f"El grupo {grupo} no existe en SAP."
    _presionar(ses, "wnd[0]/tbar[1]/btn[14]", 10)         # borrar
    if not _hay_popup(ses):
        return False, ("SAP no pidió confirmación: el grupo no se puede borrar." +
                       (f" Dice: {_mensaje_sap(ses)}" if _mensaje_sap(ses) else ""))
    _presionar(ses, POPUP_SI, 30)
    mensaje = _mensaje_sap(ses)
    _presionar(ses, "wnd[0]/tbar[0]/btn[15]", 5)          # salir
    ok = "borrad" in mensaje.lower() or "elimin" in mensaje.lower() or mensaje == ""
    return ok, mensaje or f"Grupo {grupo} borrado."
