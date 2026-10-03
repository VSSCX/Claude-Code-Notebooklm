"""Port de M_Visor3D: arma el JSON del visor 3D y lo inserta en Plantilla_Visor.html."""
from __future__ import annotations

import threading
import time

from .core import Placement
from .vb import fmt_num, round1

PALETA = ["#E8534E", "#F2C94C", "#56A3D9", "#27AE60", "#9B59B6", "#E67E22",
          "#1ABC9C", "#E84393", "#3498DB", "#F39C12", "#7F8C8D", "#16A085"]
MARCA_PLANTILLA = "__CUBICAJE_JSON__"


def letra(idx: int) -> str:
    """Letra(): A..Z, AA, AB, ..."""
    s, i = "", idx
    while True:
        s = chr(65 + (i % 26)) + s
        i = i // 26 - 1
        if i < 0:
            return s


def _js(s: str) -> str:
    t = str(s or "").replace("\\", "\\\\").replace('"', '\\"')
    return t.replace("\r", " ").replace("\n", " ").replace("\t", " ")


def _letras_colores(placed: list[Placement]):
    letras, colores, n = {}, {}, 0
    for p in placed:
        if p.cod not in letras:
            letras[p.cod] = letra(n)
            colores[p.cod] = PALETA[n % len(PALETA)]
            n += 1
    return letras, colores


def _medidas(placed: list[Placement]):
    med = {}
    for p in placed:
        if p.cod not in med:
            med[p.cod] = (p.desc, p.oL, p.oW, p.oH, (p.peso / p.n) if p.n > 0 else 0.0)
    return med


def construir_json(placed: list[Placement], camiones, es_sda: bool = False,
                   pallets: list[dict] | None = None, tarima: float = 14.5) -> str:
    """ConstruirJson: mismo formato que consume Plantilla_Visor.html."""
    med = _medidas(placed)
    letras, colores = _letras_colores(placed)
    pedido = _js(placed[0].ped) if placed else ""
    partes = []
    for c, cam in enumerate(camiones, start=1):
        partes.append(_camion_json(c, cam, placed, med, letras, colores, pallets or [], tarima))
    return ('{"titulo":"Order Desk - Cubicaje B2B","esSda":' + ("true" if es_sda else "false") +
            ',"pedido":"' + pedido + '","camiones":[' + ",".join(partes) + "]}")


def _camion_json(c: int, cam, placed, med, letras, colores, pallets=(), tarima=14.5) -> str:
    vol_cap = cam.L * cam.w * cam.h / 1_000_000.0
    vol_tot = peso_tot = 0.0
    items, orden, cajas = {}, [], []
    for p in placed:
        if p.container != c:
            continue
        vol_tot += p.volM3
        peso_tot += p.peso
        if p.cod not in items:
            items[p.cod] = [0, 0.0]
            orden.append(p.cod)
        items[p.cod][0] += p.n
        items[p.cod][1] += p.peso
        for u in range(p.n):
            cajas.append(
                '{"cod":"' + _js(p.cod) + '","x":' + fmt_num(p.x) + ',"y":' + fmt_num(p.y) +
                ',"z":' + fmt_num(p.z + u * p.oH) + ',"dx":' + fmt_num(p.oL) +
                ',"dy":' + fmt_num(p.oW) + ',"dz":' + fmt_num(p.oH) +
                ',"color":"' + colores[p.cod] + '","letra":"' + letras[p.cod] +
                '","suc":"' + _js(p.suc) + '","piso":1}')
    items_json = []
    for cod in orden:
        desc, dL, dW, dH, _ = med.get(cod, ("", 0, 0, 0, 0))
        n, peso = items[cod]
        pu = peso / n if n > 0 else 0.0
        items_json.append(
            '{"cod":"' + _js(cod) + '","desc":"' + _js(desc) + '","n":' + str(n) +
            ',"L":' + fmt_num(dL) + ',"W":' + fmt_num(dW) + ',"H":' + fmt_num(dH) +
            ',"pesoU":' + fmt_num(pu) + ',"letra":"' + letras[cod] +
            '","color":"' + colores[cod] + '"}')
    pal_json = ",".join(
        '{"x":' + fmt_num(p.get("x", 0)) + ',"y":' + fmt_num(p.get("y", 0)) +
        ',"dl":' + fmt_num(p.get("dl", 0)) + ',"dw":' + fmt_num(p.get("dw", 0)) +
        ',"tar":' + fmt_num(tarima) + ',"tipo":"' + _js(p.get("tipo", "")) +
        '","suc":"' + _js(p.get("sucursal", "")) + '","idx":' + str(p.get("numero", 0)) + "}"
        for p in pallets if p.get("vehiculo") == c)
    ocup = (vol_tot / vol_cap * 100) if vol_cap > 0 else 0.0
    return ('{"idx":' + str(c) + ',"tipo":"' + _js(cam.tipo) + '","L":' + fmt_num(cam.L) +
            ',"W":' + fmt_num(cam.w) + ',"H":' + fmt_num(cam.h) +
            ',"volTot":' + fmt_num(round1(vol_tot, 2)) + ',"volCap":' + fmt_num(round1(vol_cap, 2)) +
            ',"ocupVol":' + fmt_num(round1(ocup, 1)) + ',"pesoTot":' + fmt_num(round1(peso_tot, 1)) +
            ',"items":[' + ",".join(items_json) + '],"cajas":[' + ",".join(cajas) +
            '],"pallets":[' + pal_json + "]}")


def html_visor(plantilla: str, json_cubicaje: str) -> str:
    """Reemplaza la marca de la plantilla por el JSON, igual que GenerarVisorArchivo."""
    if MARCA_PLANTILLA not in plantilla:
        raise ValueError("La plantilla del visor no tiene la marca __CUBICAJE_JSON__.")
    return plantilla.replace(MARCA_PLANTILLA, json_cubicaje)


VISOR_VIVO = "visor_vivo.html"
_vivo_escrito: dict = {}      # carpeta -> huella de la plantilla con la que se escribió el visor vivo


def _escribir_atomico(ruta, texto: str) -> None:
    """Escribe en un temporal y lo renombra: nadie lee un archivo a medio escribir."""
    import os
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, ruta)


def asegurar_visor_vivo(carpeta, plantilla: str) -> str:
    """Visor sin datos con una dirección fija. La plataforma lo abre una sola vez y le manda
    cada cálculo nuevo por postMessage, en vez de recargar una página distinta en cada cambio.
    Solo se escribe si la plantilla cambió. Devuelve la URL pública, o "" si no se pudo dejar listo."""
    import hashlib
    from pathlib import Path
    ruta = Path(carpeta) / VISOR_VIVO
    huella = hashlib.md5(plantilla.encode("utf-8")).hexdigest()
    def estado():
        e = ruta.stat()
        return (huella, e.st_size, e.st_mtime_ns)
    try:
        # sin releer el archivo: basta con que siga igual que lo que se escribió (misma plantilla,
        # tamaño y fecha). Si alguien lo cambió por fuera, se detecta y se repara.
        if _vivo_escrito.get(str(ruta)) == estado():
            return f"/visor/{VISOR_VIVO}"
    except OSError:
        pass
    try:
        html = html_visor(plantilla, '{"camiones":[]}')
        if not ruta.exists() or ruta.read_text(encoding="utf-8") != html:
            _escribir_atomico(ruta, html)
        _vivo_escrito[str(ruta)] = estado()
    except (OSError, ValueError):
        return ""
    return f"/visor/{VISOR_VIVO}"


def guardar_datos_visor(carpeta, nombre: str, json_visor: str) -> None:
    """Los datos del visor de un cálculo viven en un archivo aparte, no en la base de datos:
    son miles de cajas y la base solo necesita el resultado del cubicaje."""
    from pathlib import Path
    try:
        _escribir_atomico(Path(carpeta) / f"{nombre}.json", json_visor)
    except OSError:
        pass


def leer_datos_visor(carpeta, nombre: str) -> str:
    from pathlib import Path
    try:
        return (Path(carpeta) / f"{nombre}.json").read_text(encoding="utf-8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Carpeta local del visor: el HTML generado busca sus librerías en ./visor/
# ---------------------------------------------------------------------------
LIBRERIAS = ("three.min.js", "jspdf.min.js", "gltf_loader.js", "scania_data.js")


REVISAR_LIBRERIAS_CADA = 600          # segundos entre revisiones de la carpeta de red
_revision: dict[tuple[str, str], float] = {}
_revisando: set[tuple[str, str]] = set()
_candado_revision = threading.Lock()


def _sincronizar(destino, origen) -> list[str]:
    """Copia la plantilla y sus librerías a la carpeta local (solo si faltan o cambiaron)."""
    import shutil
    from pathlib import Path
    destino, origen = Path(destino), Path(origen)
    (destino / "visor").mkdir(parents=True, exist_ok=True)
    faltan = []
    for nombre in LIBRERIAS:
        dst = destino / "visor" / nombre
        src = origen / nombre
        try:
            # se copia si falta, si el origen es mas nuevo o si cambio de tamano (una copia
            # danada o de prueba mas nueva que la real no debe quedarse para siempre)
            if src.exists() and (not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime
                                 or src.stat().st_size != dst.stat().st_size):
                shutil.copy2(src, dst)
            if not dst.exists():
                faltan.append(nombre)
        except OSError:
            if not dst.exists():
                faltan.append(nombre)
    _revision[(str(destino), str(origen))] = time.time()
    return faltan


def preparar_carpeta(destino, origen, forzar: bool = False) -> list[str]:
    """Deja las librerías del visor en la carpeta local y devuelve las que faltan.

    Preguntarle a la carpeta de red (\\\\servidor\\...) en cada cálculo costaba varios segundos
    por cada consulta de archivo. Ahora, si ya hay copia local, se responde al instante y la
    comparación con la red se hace como mucho cada 10 minutos, en segundo plano."""
    from pathlib import Path
    clave = (str(Path(destino)), str(Path(origen)))
    locales = [n for n in LIBRERIAS if (Path(destino) / "visor" / n).exists()]
    if forzar or len(locales) < len(LIBRERIAS):
        return _sincronizar(destino, origen)              # primera vez o falta algo: hay que copiarlas ya
    if time.time() - _revision.get(clave, 0.0) >= REVISAR_LIBRERIAS_CADA:
        with _candado_revision:
            if clave in _revisando:
                return []
            _revisando.add(clave)

        def revisar():
            try:
                _sincronizar(destino, origen)
            finally:
                with _candado_revision:
                    _revisando.discard(clave)
        threading.Thread(target=revisar, daemon=True).start()
    return []
