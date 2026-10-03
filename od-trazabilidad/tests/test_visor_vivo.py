"""Visor de dirección fija: la página lo abre una vez y le manda cada cálculo por mensaje."""
import os
import time

from app.cubicaje.visor import VISOR_VIVO, asegurar_visor_vivo, preparar_carpeta


def test_visor_vivo_se_crea_y_se_actualiza_solo_si_cambia_la_plantilla(tmp_path):
    url = asegurar_visor_vivo(tmp_path, "A __CUBICAJE_JSON__ B")
    assert url == f"/visor/{VISOR_VIVO}"
    archivo = tmp_path / VISOR_VIVO
    assert archivo.read_text(encoding="utf-8") == 'A {"camiones":[]} B'
    antes = archivo.stat().st_mtime_ns
    asegurar_visor_vivo(tmp_path, "A __CUBICAJE_JSON__ B")             # igual: no se reescribe
    assert archivo.stat().st_mtime_ns == antes
    asegurar_visor_vivo(tmp_path, "otra __CUBICAJE_JSON__")            # plantilla distinta: se reescribe
    assert archivo.read_text(encoding="utf-8") == 'otra {"camiones":[]}'


def test_las_librerias_danadas_se_restauran_aunque_sean_mas_nuevas(tmp_path):
    origen, destino = tmp_path / "red", tmp_path / "local"
    origen.mkdir()
    for lib in ("three.min.js", "jspdf.min.js", "gltf_loader.js", "scania_data.js"):
        (origen / lib).write_text("// libreria real " * 50, encoding="utf-8")
    assert preparar_carpeta(destino, origen) == []
    # una copia de prueba, más chica y más nueva que la real, no puede quedarse
    falsa = destino / "visor" / "three.min.js"
    falsa.write_text("// falsa", encoding="utf-8")
    futuro = time.time() + 3600
    os.utime(falsa, (futuro, futuro))
    preparar_carpeta(destino, origen)
    assert falsa.read_text(encoding="utf-8") == "// libreria real " * 50
