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
    preparar_carpeta(destino, origen, forzar=True)
    assert falsa.read_text(encoding="utf-8") == "// libreria real " * 50


def test_visor_vivo_no_se_reescribe_ni_se_corrompe(tmp_path):
    from app.cubicaje import visor
    visor._vivo_escrito.clear()
    asegurar_visor_vivo(tmp_path, "uno __CUBICAJE_JSON__")
    assert not list(tmp_path.glob("*.tmp"))                        # escritura atomica: sin temporales
    ruta = tmp_path / VISOR_VIVO
    ruta.write_text("alguien lo cambio", encoding="utf-8")        # distinto al esperado, mismo huella en memoria
    visor._vivo_escrito.clear()                                    # nuevo arranque: se detecta y se repara
    asegurar_visor_vivo(tmp_path, "uno __CUBICAJE_JSON__")
    assert ruta.read_text(encoding="utf-8") == 'uno {"camiones":[]}'


def test_datos_del_visor_van_en_su_archivo(tmp_path):
    from app.cubicaje.visor import guardar_datos_visor, leer_datos_visor
    assert leer_datos_visor(tmp_path, "libre_datos") == ""
    guardar_datos_visor(tmp_path, "libre_datos", '{"camiones":[1]}')
    assert leer_datos_visor(tmp_path, "libre_datos") == '{"camiones":[1]}'


def test_con_copia_local_no_se_consulta_la_red_en_cada_calculo(tmp_path, monkeypatch):
    """Preguntar a la carpeta de red costaba varios segundos por cálculo en los PC reales."""
    import threading
    from app.cubicaje import visor
    origen, destino = tmp_path / "red", tmp_path / "local"
    origen.mkdir()
    for lib in visor.LIBRERIAS:
        (origen / lib).write_text("// real " * 50, encoding="utf-8")
    visor._revision.clear()
    llamadas = []
    real = visor._sincronizar
    hecha = threading.Event()

    def contada(d, o):
        llamadas.append(1)
        r = real(d, o)
        hecha.set()
        return r

    monkeypatch.setattr(visor, "_sincronizar", contada)
    assert preparar_carpeta(destino, origen) == []                # primera vez: copia
    assert len(llamadas) == 1
    for _ in range(20):
        assert preparar_carpeta(destino, origen) == []
    assert len(llamadas) == 1                                     # 20 cálculos más sin tocar la red
    visor._revision[(str(destino), str(origen))] = 0.0            # pasaron 10 minutos: se revisa en segundo plano
    hecha.clear()
    assert preparar_carpeta(destino, origen) == []                # y no espera la red
    assert hecha.wait(2)
    assert len(llamadas) == 2
