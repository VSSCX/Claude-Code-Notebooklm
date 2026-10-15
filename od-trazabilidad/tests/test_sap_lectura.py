"""Pruebas del lector de VL01N con una sesión SAP simulada.

Reproduce el comportamiento real: tabla de picking dentro de una pestaña, scroll de
a una fila con 4 visibles, celdas txt/ctxt, popups y barra de estado. Sirve para
detectar errores de recorrido sin depender de SAP.
"""
import pytest

from app.integrations import sap, sap_crear


class Campo:
    def __init__(self, texto=""):
        self.Text = texto
        self.CaretPosition = 0

    def SetFocus(self):
        pass

    def press(self):
        pass

    def Select(self):
        pass


class Scroll:
    def __init__(self, maximo, page):
        self.Maximum = maximo
        self.PageSize = page
        self.historia = []
        self._pos = 0

    @property
    def Position(self):
        return self._pos

    @Position.setter
    def Position(self, v):
        self._pos = v
        self.historia.append(v)


class Tabla:
    def __init__(self, scroll):
        self.verticalScrollbar = scroll


class SesionFake:
    """Sesión mínima: sirve celdas según la posición del scroll."""

    def __init__(self, filas, visibles=4, con_pestana=True, mensaje="", pestana_falla_veces=0,
                 columnas=(1, 4, 22)):
        self.filas = filas                 # [(material, ctd entrega, pendiente)]
        self.visibles = visibles
        self.con_pestana = con_pestana
        self.mensaje = mensaje
        self.pestana_falla_veces = pestana_falla_veces
        self.col_mat, self.col_ent, self.col_pen = columnas
        self.scroll = Scroll(max(len(filas) - visibles, 0), visibles)
        self.tabla = Tabla(self.scroll)
        self.Busy = False
        self.pestana_selects = 0
        self.okcd = Campo()

    # --- API que usa el port ---
    def findById(self, ident):
        if ident == "wnd[0]/tbar[0]/okcd":
            return self.okcd
        if ident == "wnd[0]":
            return self
        if ident == sap.BARRA_ESTADO:
            return Campo(self.mensaje)
        if ident == sap.PESTANA_PICKING:
            if not self.con_pestana:
                raise KeyError(ident)
            self.pestana_selects += 1
            if self.pestana_selects <= self.pestana_falla_veces:
                raise KeyError(ident)
            return Campo()
        if ident == sap.TABLA:
            if self.pestana_selects <= self.pestana_falla_veces:
                raise KeyError(ident)
            return self.tabla
        if ident.startswith(sap.TABLA + "/"):
            return self._celda(ident[len(sap.TABLA) + 1:])
        if ident.startswith("wnd[0]/usr/"):
            return Campo()
        raise KeyError(ident)              # wnd[1] (popup) y cualquier otro id

    def sendVKey(self, _):
        pass

    def _celda(self, resto):
        prefijo, _, coord = resto.partition("[")
        col, _, fila = coord.rstrip("]").partition(",")
        col, fila = int(col), int(fila)
        campo = prefijo[4:] if prefijo.startswith("ctxt") else prefijo[3:]
        # la detección de columnas pregunta por la fila 0 de cada índice
        esperado = {sap.F_MATERIAL: self.col_mat, sap.F_ENTREGA: self.col_ent,
                    sap.F_PENDIENTE: self.col_pen}.get(campo)
        if esperado is None or col != esperado:
            raise KeyError(resto)
        idx = self.scroll.Position + fila
        if idx >= len(self.filas):
            return Campo("")
        v = self.filas[idx]
        return Campo({sap.F_MATERIAL: v[0], sap.F_ENTREGA: v[1], sap.F_PENDIENTE: v[2]}[campo])


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(sap.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sap, "PAUSA_PAGINA", 0)


def filas(n, desde=1):
    return [(f"90000{i:04d}", f"{i}", f"{i * 2}") for i in range(desde, desde + n)]


def test_lee_todas_las_lineas_con_scroll():
    """20 líneas con 4 visibles: hay que recorrer toda la tabla, sin perder ni repetir."""
    f = filas(20)
    ses = SesionFake(f)
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert [p.sku for p in r.posiciones] == [x[0] for x in f]
    assert r.posiciones[0].qty_entrega == 1 and r.posiciones[0].qty_pendiente == 2
    assert r.posiciones[-1].qty_pendiente == 40
    assert r.aviso == ""


def test_pedido_de_una_sola_linea():
    ses = SesionFake(filas(1))
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 1 and r.aviso == ""


def test_tabla_mas_grande_que_el_scroll_declarado():
    """Si SAP declara un máximo corto, igual se sigue leyendo hasta que no haya datos."""
    ses = SesionFake(filas(30))
    ses.scroll.Maximum = 0                      # SAP a veces informa 0
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 30


def test_material_repetido_avisa_y_no_duplica():
    f = filas(3) + [filas(1)[0]]                # el primer material aparece dos veces
    ses = SesionFake(f)
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 3
    assert r.duplicados == ["900000001"] and "más de una línea" in r.aviso


def test_pestana_de_picking_se_selecciona():
    """La tabla solo aparece después de abrir la pestaña: el port la selecciona."""
    ses = SesionFake(filas(6), pestana_falla_veces=1)
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 6 and ses.pestana_selects >= 2


def test_sin_tabla_informa_el_mensaje_de_sap():
    ses = SesionFake([], con_pestana=False, mensaje="El pedido 4001 no existe")
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert r.posiciones == [] and "no existe" in r.aviso


def test_columnas_en_otra_posicion():
    """Si el layout mueve las columnas, la detección las encuentra igual."""
    ses = SesionFake(filas(5), columnas=(2, 7, 25))
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 5


def test_numeros_con_formato_sap():
    ses = SesionFake([("900000001", "1.234,000", "2.000,500")])
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert r.posiciones[0].qty_entrega == 1234.0 and r.posiciones[0].qty_pendiente == 2000.5


def test_una_pantalla_vacia_no_corta_la_lectura():
    """Un hueco momentáneo (SAP lento) no debe truncar el pedido."""
    f = filas(12)
    ses = SesionFake(f)
    original = ses._celda
    estado = {"saltos": 0}

    def con_hueco(resto):
        # simula una pantalla que llega vacía una sola vez, a mitad del recorrido
        if ses.scroll.Position == 4 and estado["saltos"] < 4:
            estado["saltos"] += 1
            return Campo("")
        return original(resto)

    ses._celda = con_hueco
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 12


def test_avanza_por_pantalla_y_no_pierde_filas():
    """Con 4 filas visibles se avanza de a 3 (traslape de 1): menos vueltas, mismas filas."""
    for n in (1, 3, 4, 5, 12, 21, 40):
        ses = SesionFake(filas(n))
        r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
        assert len(r.posiciones) == n, f"con {n} filas leyó {len(r.posiciones)}"
        assert len(ses.scroll.historia) <= (n // 3) + 3, f"demasiadas vueltas con {n} filas"


def test_paginacion_con_mas_filas_visibles():
    ses = SesionFake(filas(30), visibles=8)
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 30


# ---------------------------------------------------------------- rapidez de la lectura
def _medir(monkeypatch, n, visibles=12, **kw):
    """Pausas acumuladas y consultas a SAP de una lectura (el tiempo real es pausas + consultas × ~10 ms)."""
    ses = SesionFake(filas(n), visibles=visibles, **kw)
    llamadas = {"n": 0}
    original = ses.findById

    def contado(ident):
        llamadas["n"] += 1
        return original(ident)

    ses.findById = contado
    pausas = {"s": 0.0}
    monkeypatch.setattr(sap.time, "sleep", lambda s=0: pausas.__setitem__("s", pausas["s"] + s))
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    return r, pausas["s"], llamadas["n"], ses


@pytest.mark.parametrize("n", [1, 2, 3, 8, 11])
def test_un_pedido_chico_no_espera_pantallas_vacias(monkeypatch, n):
    """Con un solo producto SAP informa 'sin scroll': antes se leían 100 filas vacías con cinco reintentos
    cada una (~28 s). Ahora termina en cuanto se acaban los productos."""
    r, pausas, consultas, ses = _medir(monkeypatch, n)
    assert len(r.posiciones) == n and r.aviso == ""
    assert pausas <= 0.6, f"{n} producto(s): {pausas:.1f} s de pausas"
    assert consultas <= 70, f"{n} producto(s): {consultas} consultas"
    assert len(ses.scroll.historia) == 1                        # no se movió el scroll de más


@pytest.mark.parametrize("n", [11, 12, 13, 23, 24, 25, 60, 120])
def test_pedido_grande_se_lee_completo_y_sin_vueltas_de_mas(monkeypatch, n):
    r, pausas, consultas, ses = _medir(monkeypatch, n)
    assert [p.sku for p in r.posiciones] == [x[0] for x in filas(n)]
    assert len(ses.scroll.historia) <= (n // 11) + 3
    assert pausas <= 0.25 * (n // 11 + 2) + 0.4, f"{n} productos: {pausas:.1f} s de pausas"


def test_tabla_con_scroll_declarado_en_cero_se_lee_igual(monkeypatch):
    """SAP a veces informa máximo 0 aunque haya muchas filas: la pantalla llena manda seguir."""
    ses = SesionFake(filas(30), visibles=12)
    ses.scroll.Maximum = 0
    monkeypatch.setattr(sap.time, "sleep", lambda *_: None)
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 30


def test_un_atraso_de_sap_a_mitad_de_pantalla_no_corta_la_lectura(monkeypatch):
    """Una fila que llega vacía un par de veces (SAP lento) no debe truncar el pedido."""
    ses = SesionFake(filas(20), visibles=12)
    original = ses._celda
    estado = {"vacias": 0}

    def con_atraso(resto):
        if ses.scroll.Position == 0 and resto.endswith(",5]") and "MATNR" in resto and estado["vacias"] < 3:
            estado["vacias"] += 1
            return Campo("")
        return original(resto)

    ses._celda = con_atraso
    monkeypatch.setattr(sap.time, "sleep", lambda *_: None)
    r = sap.leer_pedido("4001", "PN01", "22.09.2026", ses=ses)
    assert len(r.posiciones) == 20 and estado["vacias"] == 3


def test_la_columna_de_fabrica_se_detecta_sin_recorrer_las_demas(monkeypatch):
    ses = SesionFake(filas(2))
    consultadas = []
    original = ses.findById
    ses.findById = lambda ident: (consultadas.append(ident), original(ident))[1]
    monkeypatch.setattr(sap.time, "sleep", lambda *_: None)
    assert sap._detectar_columna(ses, sap.F_PENDIENTE) == 22
    assert len(consultadas) <= 2                                # antes: ~45 consultas hasta llegar a la 22


# ---------------------------------------------------------------- borrado en SAP
class SesionBorrado(SesionFake):
    """Simula VL06 / VG02: registra los ids usados y controla si aparece el popup."""

    def __init__(self, con_fila=True, con_popup=True, mensaje="Entrega 8705 borrada"):
        super().__init__(filas(0), mensaje=mensaje)
        self.con_fila, self.con_popup = con_fila, con_popup
        self.usados, self.textos = [], {}

    def findById(self, ident):
        self.usados.append(ident)
        if ident == "wnd[1]":
            if not self.con_popup:
                raise KeyError(ident)
            return Campo()
        if ident == "wnd[1]/usr/btnSPOP-OPTION1":
            if not self.con_popup:
                raise KeyError(ident)
            self.usados.append("CONFIRMA")
            return Campo()
        if ident == "wnd[0]/usr/lbl[6,5]":
            if not self.con_fila:
                raise KeyError(ident)
            return Campo()
        if ident.startswith("wnd[0]/tbar") or ident.startswith("wnd[0]/usr/btn"):
            return Campo()
        return super().findById(ident)


def test_borrar_entrega_confirma_y_reporta():
    ses = SesionBorrado()
    ok, msg = sap.borrar_entrega("8705709527", ses=ses)
    assert ok and "borrada" in msg.lower()
    assert "CONFIRMA" in ses.usados                     # confirmó el popup de SAP
    assert "wnd[0]/usr/ctxtIT_VBELN-LOW" in ses.usados  # filtró por la entrega
    assert ses.usados.count("wnd[0]/tbar[0]/btn[3]") == 3   # vuelve al menú


def test_borrar_entrega_sin_resultado_no_borra():
    ses = SesionBorrado(con_fila=False, mensaje="La entrega no existe")
    ok, msg = sap.borrar_entrega("8705709527", ses=ses)
    assert not ok and "no aparece" in msg and "CONFIRMA" not in ses.usados


def test_borrar_entrega_sin_popup_avisa_el_motivo():
    ses = SesionBorrado(con_popup=False, mensaje="Documento facturado")
    ok, msg = sap.borrar_entrega("8705709527", ses=ses)
    assert not ok and "no pidió confirmación" in msg and "facturado" in msg


def test_borrar_grupo():
    ses = SesionBorrado(mensaje="Grupo 1392270 borrado")
    ok, msg = sap.borrar_grupo("1392270", ses=ses)
    assert ok and "CONFIRMA" in ses.usados
    ses = SesionBorrado(con_popup=False, mensaje="El grupo no existe")
    ok, msg = sap.borrar_grupo("1392270", ses=ses)
    assert not ok and "no existe" in msg


# ---------------------------------------------------------------- creación en SAP
class SesionCrear(SesionFake):
    """Simula VL01N: campos de cabecera, tabla de picking y barra de estado."""

    def __init__(self, posiciones, mensaje="Entrega 8705709999 grabada", tipo_msg="S",
                 con_tabla=True, popup=False):
        super().__init__(posiciones, mensaje=mensaje)
        self.con_tabla, self.popup = con_tabla, popup
        self.tipo_msg = tipo_msg
        self.campos, self.usados, self.qty_escritas = {}, [], {}
        self.borradas, self.guardado, self.salio = [], False, False

    def findById(self, ident):
        self.usados.append(ident)
        if ident == "wnd[1]":
            if not self.popup:
                raise KeyError(ident)
            return Campo()
        if ident.startswith("wnd[1]"):
            if not self.popup:
                raise KeyError(ident)
            self.popup = False
            return Campo()
        if ident == sap.BARRA_ESTADO:
            c = Campo(self.mensaje)
            c.MessageType = self.tipo_msg
            return c
        if ident == sap.TABLA and not self.con_tabla:
            raise KeyError(ident)
        if ident.startswith(sap.TABLA + "/txtLIPSD-G_LFIMG"):
            col, fila = ident.rstrip("]").rsplit("[", 1)[1].split(",")
            campo = Campo()
            if int(col) != 4:
                raise KeyError(ident)
            idx = self.scroll.Position + int(fila)
            if idx < len(self.filas):
                self.qty_escritas[self.filas[idx][0]] = campo
            return campo
        if ident.startswith("wnd[0]/usr/ctxt"):
            self.campos.setdefault(ident, Campo())
            return self.campos[ident]
        if ident == "wnd[0]/tbar[0]/btn[3]":
            self.salio = True
            return Campo()
        return super().findById(ident)

    def sendVKey(self, key):
        if key == 11:
            self.guardado = True


@pytest.fixture(autouse=True)
def sin_esperas_crear(monkeypatch):
    from app.integrations import sap_crear
    monkeypatch.setattr(sap_crear.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sap_crear, "PAUSA", 0)


def test_crear_entrega_modo_ensayo_no_guarda():
    from app.integrations import sap_crear
    ses = SesionCrear(filas(3))
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026",
                                {"900000001": 5, "900000002": 3}, ensayo=True, ses=ses)
    assert r.ok and r.ensayo and not ses.guardado and ses.salio
    assert "sin grabar" in r.mensaje
    assert ses.campos["wnd[0]/usr/ctxtLIKP-VSTEL"].Text == "PN01"
    assert ses.campos["wnd[0]/usr/ctxtLV50C-VBELN"].Text == "4001"
    assert r.borradas == 1            # la tercera posición no va en este camión
    assert r.ajustadas == 2


def test_crear_entrega_real_devuelve_el_numero():
    from app.integrations import sap_crear
    ses = SesionCrear(filas(2))
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026", {"900000001": 5, "900000002": 2},
                                fecha_cita="25.09.2026", hora_cita="09:00:00", ses=ses)
    assert r.ok and r.entrega == "8705709999" and ses.guardado
    assert any("Cita" in p for p in r.pasos)


def test_crear_entrega_sin_confirmacion_de_sap():
    from app.integrations import sap_crear
    ses = SesionCrear(filas(1), mensaje="El pedido está bloqueado", tipo_msg="E")
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026", {"900000001": 5}, ses=ses)
    assert not r.ok and "bloqueado" in r.mensaje


def test_crear_entrega_valida_lo_que_recibe():
    from app.integrations import sap_crear
    assert not sap_crear.crear_entrega("", "PN01", "22.09.2026", {"1": 1}, ses=SesionCrear([])).ok
    assert not sap_crear.crear_entrega("4001", "", "22.09.2026", {"1": 1}, ses=SesionCrear([])).ok
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026", {}, ses=SesionCrear([]))
    assert not r.ok and "cantidad" in r.mensaje


def test_crear_entrega_sin_tabla_de_posiciones():
    from app.integrations import sap_crear
    ses = SesionCrear(filas(2), con_tabla=False)
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026", {"900000001": 5}, ses=ses)
    assert not r.ok and "no mostró las posiciones" in r.mensaje and not ses.guardado


def test_normalizar_material():
    from app.integrations.sap_crear import norm_material
    assert norm_material("900081624") == "000000000900081624"
    assert norm_material(" 900.081.624 ") == "000000000900081624"
    assert norm_material("S135000785") == "S135000785"     # con letras se deja igual


class SesionGrupo(SesionCrear):
    """Simula VL06 con su ventana de selección múltiple, los checks y el menú de grupo."""

    def __init__(self, n_entregas=2, con_menu=True, con_popup_grupo=True, mensaje="Grupo 1392270 creado"):
        super().__init__([], mensaje=mensaje)
        self.n, self.con_menu, self.con_popup_grupo = n_entregas, con_menu, con_popup_grupo
        self.multi, self.marcados, self.popup_grupo = {}, [], {}
        self.menu_usado = False

    def findById(self, ident):
        if ident == sap_crear.MULTI_ENTREGAS:
            self.popup = True
            return Campo()
        if ident.startswith("wnd[1]/usr/tabsTAB_STRIP"):
            fila = int(ident.rstrip("]").rsplit("[", 1)[1].split(",")[1])
            self.multi[fila] = Campo()
            return self.multi[fila]
        if ident.startswith("wnd[0]/usr/chk[1,"):
            idx = int(ident.rstrip("]").rsplit("[", 1)[1].split(",")[1])
            if idx >= sap_crear.PRIMERA_CHK + self.n:
                raise KeyError(ident)
            c = Campo()
            self.marcados.append(idx)
            return c
        if ident == sap_crear.MENU_CREAR_GRUPO:
            if not self.con_menu:
                raise KeyError(ident)
            self.menu_usado = True
            return Campo()
        if ident.startswith("wnd[1]/usr/") and "VBSK" in ident or "LIKP-LGNUM" in ident:
            if not self.con_popup_grupo:
                raise KeyError(ident)
            self.popup_grupo.setdefault(ident, Campo())
            return self.popup_grupo[ident]
        if ident == "wnd[1]":
            if not self.popup:
                raise KeyError(ident)
            return Campo()
        if ident.startswith("wnd[1]/tbar"):
            if ident.endswith("btn[8]"):
                self.popup = False          # copiar la selección cierra la ventana
            return Campo()
        if ident == "wnd[2]":
            raise KeyError(ident)
        return super().findById(ident)


def test_crear_grupo_sigue_la_secuencia_del_excel():
    from app.integrations import sap_crear
    ses = SesionGrupo(n_entregas=2)
    r = sap_crear.crear_grupo(["8705709527", "8705709528"], ensayo=False, ses=ses,
                              cliente="PARIS", camion="3")
    assert r.ok and r.grupo == "1392270"
    assert [c.Text for c in ses.multi.values()] == ["8705709527", "8705709528"]   # selección múltiple
    assert ses.marcados == [5, 6]                                                 # filas marcadas
    assert ses.menu_usado                                                         # menú crear grupo
    vals = {k.rsplit("/", 1)[1]: v.Text for k, v in ses.popup_grupo.items()}
    assert vals["ctxtVBSK-SMART"] == "K" and vals["ctxtLIKP-LGNUM"] == "CD3"
    # el Excel corta la referencia en 30 caracteres
    assert vals["txtVBSK-VTEXT"] == "CAM3_8705709527_8705709528_PARIS"[:30]
    assert len(vals["txtVBSK-VTEXT"]) == 30


def test_crear_grupo_en_ensayo_no_abre_el_menu():
    from app.integrations import sap_crear
    ses = SesionGrupo(n_entregas=2)
    r = sap_crear.crear_grupo(["8705709527", "8705709528"], ensayo=True, ses=ses)
    assert r.ok and not ses.menu_usado and not r.grupo and "sin crear el grupo" in r.mensaje
    assert not sap_crear.crear_grupo([], ses=SesionGrupo()).ok


def test_crear_grupo_avisa_si_no_puede_marcar():
    from app.integrations import sap_crear
    ses = SesionGrupo(n_entregas=0)
    r = sap_crear.crear_grupo(["8705709527"], ses=ses)
    assert not r.ok and "marcar las entregas" in r.mensaje


def test_cita_del_grupo_recorre_sus_entregas():
    from app.integrations import sap_crear

    class SesionVG02(SesionCrear):
        def __init__(self, entregas):
            super().__init__([], mensaje="ok")
            self.entregas = entregas
            self.campos_cita = {}
            self.guardados = 0

        def findById(self, ident):
            if ident.startswith(sap_crear.VG02_TABLA):
                fila = int(ident.rstrip("]").rsplit("[", 1)[1].split(",")[1])
                if fila >= len(self.entregas):
                    raise KeyError(ident)
                return Campo(self.entregas[fila])
            if ident in (sap_crear.VG02_FECHA, sap_crear.VG02_HORA):
                self.campos_cita.setdefault(ident, Campo())
                return self.campos_cita[ident]
            if ident == "wnd[0]/tbar[0]/btn[11]":
                self.guardados += 1
                return Campo()
            if ident in ("wnd[1]", "wnd[2]"):
                raise KeyError(ident)
            return super().findById(ident)

    ses = SesionVG02(["8705700001", "8705700002"])
    r = sap_crear.actualizar_grupo("1392270", "26.09.2026", "10:30:00", ses=ses)
    assert r.ok and ses.guardados == 2                    # guardó cada entrega del grupo
    assert ses.campos_cita[sap_crear.VG02_FECHA].Text == "26.09.2026"

    ses = SesionVG02(["8705700001"])
    r = sap_crear.actualizar_grupo("1392270", "26.09.2026", ensayo=True, ses=ses)
    assert r.ok and ses.guardados == 0 and "sin grabar" in r.mensaje

    assert not sap_crear.actualizar_grupo("", "26.09.2026", ses=SesionVG02([])).ok
    assert not sap_crear.actualizar_grupo("1392270", "", ses=SesionVG02([])).ok


def test_incidencias_quedan_registradas():
    """Lo que SAP no acepta ya no se silencia: queda anotado y llega al resultado."""
    from app.integrations import sap_crear

    class SesionTerca(SesionCrear):
        def findById(self, ident):
            o = super().findById(ident)
            if ident.startswith(sap.TABLA + "/txtLIPSD-G_LFIMG"):
                class Rechaza(Campo):
                    def __setattr__(self, k, v):
                        if k == "Text":
                            raise RuntimeError("campo bloqueado")
                        object.__setattr__(self, k, v)
                return Rechaza()
            return o

    ses = SesionTerca(filas(2))
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026", {"900000001": 5}, ensayo=True, ses=ses)
    assert r.incidencias, "lo que SAP rechaza tiene que quedar anotado"
    assert any("No se pudo" in x for x in r.incidencias)
    # el aviso dice qué paso falló, no solo que hubo un error
    assert any(("posición" in x) or ("cantidad" in x) for x in r.incidencias)


def test_incidencias_se_limpian_entre_operaciones():
    from app.integrations import sap, sap_crear
    sap.limpiar_incidencias()
    sap.anotar("algo viejo")
    assert sap.incidencias() == ["algo viejo"]
    r = sap_crear.crear_entrega("4001", "PN01", "22.09.2026", {"900000001": 5},
                                ensayo=True, ses=SesionCrear(filas(1)))
    assert "algo viejo" not in r.incidencias        # cada operación parte con el rastro limpio
