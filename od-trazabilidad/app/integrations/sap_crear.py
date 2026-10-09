"""Creación en SAP desde la plataforma: entregas (VL01N), grupos (VL06) y fecha/hora.

Port de Crear_Entregas.bas, Crear_Grupos.bas y Actualizar_FechayHora.bas.

Todo acepta `ensayo=True`: la plataforma recorre las mismas pantallas, escribe los mismos
campos y se detiene **antes de guardar**, saliendo sin grabar. Sirve para comprobar la
navegación sin crear nada en SAP.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .sap import (BARRA_ESTADO, limpiar_incidencias, FILAS_VISIBLES, PESTANA_PICKING, TABLA, _cerrar_popup, _esperar,
                  _leer_celda, _mensaje_sap, _por_id, _presionar, anotar, conectar)

FOCO = TABLA + "/ctxtLIPS-MATNR[1,3]"
BTN_BORRAR = ("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
              "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
              "subSUBSCREEN_ICONBAR:SAPMV50A:1708/btnBT_POLO_T")
ID_FECHA = (TABLA.rsplit("/tbl", 1)[0] + "/ctxtLIKP-KODAT")
ID_HORA = (TABLA.rsplit("/tbl", 1)[0] + "/ctxtLIKP-KOUHR")
POPUP_SI = "wnd[1]/usr/btnSPOP-OPTION1"
CAMPO_QTY = "LIPSD-G_LFIMG"
PAUSA = 0.2


@dataclass
class Resultado:
    ok: bool = False
    entrega: str = ""
    grupo: str = ""
    mensaje: str = ""
    ensayo: bool = False
    pasos: list[str] = field(default_factory=list)
    borradas: int = 0
    ajustadas: int = 0
    incidencias: list[str] = field(default_factory=list)

    def paso(self, txt: str):
        self.pasos.append(txt)


def norm_material(mat: str) -> str:
    """NormalizeMaterial: los códigos numéricos se comparan con 18 dígitos."""
    s = str(mat or "").strip()
    if re.search(r"[A-Za-z]", s):
        return s
    return s.replace(" ", "").replace(".", "").replace(",", "").rjust(18, "0")


def _aceptar_popups(ses, veces: int = 5):
    for _ in range(veces):
        if _por_id(ses, "wnd[1]") is None:
            return
        for ident in (POPUP_SI, "wnd[1]/tbar[0]/btn[0]", "wnd[1]/usr/btnBUTTON_1"):
            if _por_id(ses, ident) is not None:
                _presionar(ses, ident, 3)
                break
        else:
            return


def _error_sap(ses) -> str:
    """CheckSapError_NB: popup abierto o mensaje de error en la barra de estado."""
    if _por_id(ses, "wnd[1]") is not None:
        textos = []
        for ident in ("wnd[1]/usr/txtMESSTXT1", "wnd[1]/usr/txtMESSTXT2",
                      "wnd[1]/usr/txtSPOP-TEXTLINE1", "wnd[1]/usr/txtSPOP-TEXTLINE2"):
            o = _por_id(ses, ident)
            if o is not None:
                try:
                    textos.append(str(o.Text))
                except Exception:  # noqa: BLE001
                    pass
        txt = " ".join(t for t in textos if t).strip()
        bajo = txt.lower()
        _cerrar_popup(ses)
        if any(p in bajo for p in ("bloqueado", "siendo procesado", "ocupado", "locked",
                                   "being processed")):
            return f"El pedido está bloqueado por otro usuario: {txt}"
        return f"SAP avisa: {txt}" if txt else "SAP abrió un aviso que no se pudo leer."
    barra = _por_id(ses, BARRA_ESTADO)
    if barra is not None:
        try:
            if str(barra.MessageType) in ("E", "A"):
                return f"SAP error: {barra.Text}"
        except Exception:  # noqa: BLE001
            pass
    return ""


def _numero_entrega(ses) -> tuple[str, str]:
    """ParseDeliveryFromStatus_Strict: exige mensaje de éxito y 10 dígitos."""
    barra = _por_id(ses, BARRA_ESTADO)
    tipo, texto = "", ""
    if barra is not None:
        try:
            tipo, texto = str(barra.MessageType), str(barra.Text)
        except Exception:  # noqa: BLE001
            pass
    if tipo != "S":
        detalle = {"E": "error", "A": "error grave", "W": "advertencia",
                   "I": "información"}.get(tipo, "sin mensaje")
        return "", f"SAP no confirmó la entrega ({detalle}): {texto}".strip()
    numeros = re.findall(r"\d+", texto)
    mejor = max(numeros, key=len) if numeros else ""
    if len(mejor) == 10:
        return mejor, ""
    return "", (f"SAP confirmó pero el número no tiene 10 dígitos (leyó '{mejor}'). "
                f"Mensaje: {texto}")


def _detectar_col_qty(ses) -> int:
    for idx in range(31):
        if _por_id(ses, f"{TABLA}/txt{CAMPO_QTY}[{idx},0]") is not None:
            return idx
    return 4


def _recorrer_tabla(ses):
    """Recorre la tabla de picking devolviendo (fila absoluta, fila visible, material)."""
    tabla = _por_id(ses, TABLA)
    if tabla is None:
        return
    try:
        maximo = int(tabla.verticalScrollbar.Maximum) or 100
    except Exception:  # noqa: BLE001
        maximo = 100
    vistas = set()
    for scroll in range(maximo + 1):
        tabla = _por_id(ses, TABLA)
        if tabla is None:
            return
        foco = _por_id(ses, FOCO)
        if foco is not None:
            try:
                foco.SetFocus()
                time.sleep(0.1)
                foco.CaretPosition = 0
            except Exception:  # noqa: BLE001
                pass
        try:
            tabla.verticalScrollbar.Position = scroll
        except Exception:  # noqa: BLE001
            pass
        _esperar(ses)
        time.sleep(PAUSA)
        vacia = True
        for v in range(FILAS_VISIBLES):
            mat = _leer_celda(ses, "LIPS-MATNR", 1, v)
            if not mat:
                break
            vacia = False
            absoluta = scroll + v
            if absoluta in vistas:
                continue
            vistas.add(absoluta)
            yield absoluta, v, mat
        if vacia:
            return


def _borrar_no_deseadas(ses, deseados: dict, res: Resultado) -> None:
    """EliminarPositionsNoDeseadas: marca lo que no va en este camión y lo borra."""
    marcadas, fallidas = 0, 0
    for absoluta, _v, mat in _recorrer_tabla(ses):
        if norm_material(mat) not in deseados:
            marcadas += 1
            tabla = _por_id(ses, TABLA)
            try:
                tabla.getAbsoluteRow(absoluta).Selected = True
            except Exception as e:  # noqa: BLE001
                fallidas += 1
                anotar(f"No se pudo marcar para borrar la posición {absoluta + 1}", e)
    if marcadas:
        _presionar(ses, BTN_BORRAR, 5)
        time.sleep(0.5)
        _aceptar_popups(ses)
    res.borradas = marcadas
    res.paso(f"Posiciones que no van en este camión: {marcadas} borradas" +
             (f" ({fallidas} no se pudieron marcar)" if fallidas else ""))


def _ajustar_cantidades(ses, deseados: dict, res: Resultado) -> None:
    """AjustarCantidades: escribe la cantidad de cada material del camión."""
    col = _detectar_col_qty(ses)
    puestos: set[str] = set()
    for _absoluta, v, mat in _recorrer_tabla(ses):
        clave = norm_material(mat)
        if clave in deseados and clave not in puestos:
            valor = str(int(round(deseados[clave])))
            campo = _por_id(ses, f"{TABLA}/txt{CAMPO_QTY}[{col},{v}]")
            if campo is not None:
                try:
                    campo.Text = valor
                    campo.SetFocus()
                    campo.CaretPosition = len(valor)
                    ses.findById("wnd[0]").sendVKey(0)
                except Exception as e:  # noqa: BLE001
                    anotar(f"No se pudo escribir la cantidad {valor} de {mat}", e)
                _esperar(ses, 3)
                _aceptar_popups(ses)
                puestos.add(clave)
        if len(puestos) == len(deseados):
            break
    res.ajustadas = len(puestos)
    res.paso(f"Cantidades escritas: {len(puestos)} de {len(deseados)}")


def _cerrar(res: Resultado) -> Resultado:
    """Adjunta al resultado lo que SAP no aceptó durante el proceso."""
    from .sap import incidencias
    res.incidencias = incidencias()
    return res


def crear_entrega(pedido: str, puesto: str, fecha: str, materiales: dict, fecha_cita: str = "",
                  hora_cita: str = "", ensayo: bool = False, ses=None) -> Resultado:
    """Crea UNA entrega en VL01N con los materiales y cantidades de un camión.

    materiales: {sku: unidades}. fecha y fecha_cita en dd.MM.yyyy, hora_cita en hh:mm:ss.
    """
    res = Resultado(ensayo=ensayo)
    limpiar_incidencias()
    if not str(pedido).strip():
        res.mensaje = "Falta el número de pedido."
        return _cerrar(res)
    if not str(puesto).strip():
        res.mensaje = "Falta el puesto de expedición."
        return _cerrar(res)
    deseados = {norm_material(k): float(v) for k, v in (materiales or {}).items() if float(v) > 0}
    if not deseados:
        res.mensaje = "El camión no tiene materiales con cantidad."
        return _cerrar(res)

    ses = ses or conectar()
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "/nVL01N"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 8)
    time.sleep(0.5)
    _aceptar_popups(ses)
    res.paso("VL01N abierto")

    faltante = ""
    for _intento in range(2):
        for ident in ("wnd[0]/usr/ctxtLIKP-VSTEL", "wnd[0]/usr/ctxtLV50C-DATBI",
                      "wnd[0]/usr/ctxtLV50C-VBELN"):
            o = _por_id(ses, ident)
            if o is not None:
                o.Text = ""
        for ident, valor in (("wnd[0]/usr/ctxtLIKP-VSTEL", puesto),
                             ("wnd[0]/usr/ctxtLV50C-DATBI", fecha),
                             ("wnd[0]/usr/ctxtLV50C-VBELN", str(pedido))):
            o = _por_id(ses, ident)
            if o is not None:
                try:
                    o.SetFocus()
                    o.Text = valor
                    o.CaretPosition = len(valor)
                except Exception as e:  # noqa: BLE001
                    anotar(f"No se pudo escribir {ident.rsplit('/', 1)[-1]} = {valor}", e)
        faltante = ""
        leido_puesto = _por_id(ses, "wnd[0]/usr/ctxtLIKP-VSTEL")
        leido_pedido = _por_id(ses, "wnd[0]/usr/ctxtLV50C-VBELN")
        if leido_puesto is None or str(leido_puesto.Text).strip() != str(puesto).strip():
            faltante = "el puesto de expedición"
        elif leido_pedido is None or str(leido_pedido.Text).strip() != str(pedido).strip():
            faltante = "el número de pedido"
        if not faltante:
            break
        time.sleep(0.4)
    if faltante:
        res.mensaje = (f"No se pudo escribir {faltante} en VL01N. La pantalla no estaba lista o "
                       f"el pedido no existe.")
        return _cerrar(res)
    res.paso(f"Pedido {pedido}, puesto {puesto}, fecha {fecha}")

    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 8)
    err = _error_sap(ses)
    if err:
        res.mensaje = err
        return _cerrar(res)
    _aceptar_popups(ses)

    pest = _por_id(ses, PESTANA_PICKING)
    if pest is not None:
        try:
            pest.Select()
        except Exception:  # noqa: BLE001
            pass
    _esperar(ses, 5)
    time.sleep(0.5)
    if _por_id(ses, TABLA) is None:
        res.mensaje = "VL01N no mostró las posiciones del pedido."
        return _cerrar(res)

    _borrar_no_deseadas(ses, deseados, res)
    _ajustar_cantidades(ses, deseados, res)

    for ident, valor in ((ID_FECHA, fecha_cita), (ID_HORA, hora_cita)):
        if valor:
            o = _por_id(ses, ident)
            if o is not None:
                try:
                    o.Text = valor
                    o.SetFocus()
                    o.CaretPosition = len(valor)
                except Exception:  # noqa: BLE001
                    pass
    if fecha_cita or hora_cita:
        res.paso(f"Cita {fecha_cita} {hora_cita}".strip())

    for _ in range(4):
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses, 5)
        time.sleep(0.2)

    if ensayo:
        # Modo ensayo: se sale sin grabar (F3 y se descartan los avisos)
        _presionar(ses, "wnd[0]/tbar[0]/btn[3]", 5)
        _aceptar_popups(ses)
        res.ok = True
        res.mensaje = ("Ensayo listo: la entrega quedó cargada en pantalla y se salió sin grabar. "
                       "Revisa que SAP haya quedado en el menú.")
        res.paso("Salida sin guardar")
        return _cerrar(res)

    ses.findById("wnd[0]").sendVKey(11)          # guardar
    _esperar(ses, 10)
    entrega, error = _numero_entrega(ses)
    if not entrega:
        res.mensaje = error
        return _cerrar(res)
    res.ok = True
    res.entrega = entrega
    res.mensaje = f"Entrega {entrega} creada."
    res.paso(f"Guardada: {entrega}")
    return _cerrar(res)


LGNUM = "CD3"            # almacén del grupo de transporte
MULTI_ENTREGAS = "wnd[0]/usr/btn%_IT_VBELN_%_APP_%-VALU_PUSH"
FILA_MULTI = ("wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/"
              "tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,{}]")
MENU_CREAR_GRUPO = "wnd[0]/mbar/menu[4]/menu[3]/menu[1]"
PRIMERA_CHK = 5          # las filas del listado empiezan en chk[1,5]
VG02_TABLA = "wnd[0]/usr/tblSAPMV08ATC_GROUP/ctxtVBSS-VBELN[0,"
VG02_FECHA = ("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
              "ssubSUBSCREEN_BODY:SAPMV50A:1104/ctxtLIKP-KODAT")
VG02_HORA = ("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
             "ssubSUBSCREEN_BODY:SAPMV50A:1104/ctxtLIKP-KOUHR")


def referencia_grupo(camion: str, entregas: list, cliente: str = "") -> str:
    """Mismo texto que arma el Excel cuando no hay referencia de cita: CAM1_entrega_CLIENTE."""
    txt = "CAM" + str(camion) + "".join("_" + str(e).strip() for e in entregas)
    if cliente:
        txt += "_" + cliente.upper()
    return txt[:30]


def _numero_grupo(ses) -> str:
    """LeerGrupoDesdeStatus: los dígitos que siguen a la palabra "Grupo"."""
    m = re.search(r"grupo\s+(\d+)", _mensaje_sap(ses), re.IGNORECASE)
    return m.group(1) if m else ""


def crear_grupo(entregas: list, referencia: str = "", ensayo: bool = False, ses=None,
                cliente: str = "", camion: str = "1") -> Resultado:
    """Crea UN grupo de transporte con las entregas de un camión (VL06).

    Misma secuencia del Excel: VL06 -> lista -> selección múltiple de entregas -> ejecutar ->
    marcar las filas -> menú Crear grupo -> ventana con tipo K, referencia y almacén CD3.
    """
    res = Resultado(ensayo=ensayo)
    limpiar_incidencias()
    numeros = [str(e).strip() for e in (entregas or []) if str(e).strip()]
    if not numeros:
        res.mensaje = "No hay entregas para agrupar."
        return _cerrar(res)
    texto = (referencia or "").strip()[:30] or referencia_grupo(camion, numeros, cliente)

    ses = ses or conectar()
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "/NVL06"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    _aceptar_popups(ses)
    _presionar(ses, "wnd[0]/usr/btnBUTTON1", 10)      # lista de entregas
    _presionar(ses, "wnd[0]/tbar[1]/btn[19]", 10)     # más criterios de selección
    for campo in ("wnd[0]/usr/ctxtIT_KODAT-LOW", "wnd[0]/usr/ctxtIT_KODAT-HIGH"):
        o = _por_id(ses, campo)
        if o is not None:
            o.Text = ""
    res.paso("VL06 abierto, fechas limpias")

    if _por_id(ses, MULTI_ENTREGAS) is None:
        res.mensaje = "VL06 no mostró el botón de selección múltiple de entregas."
        return _cerrar(res)
    _presionar(ses, MULTI_ENTREGAS, 10)
    if _por_id(ses, "wnd[1]") is not None:
        for i, n in enumerate(numeros):
            o = _por_id(ses, FILA_MULTI.format(i))
            if o is not None:
                o.Text = n
        _presionar(ses, "wnd[1]/tbar[0]/btn[0]", 5)   # Enter
        _presionar(ses, "wnd[1]/tbar[0]/btn[8]", 5)   # copiar la selección
    res.paso(f"Entregas cargadas: {len(numeros)}")

    _presionar(ses, "wnd[0]/tbar[1]/btn[8]", 60)      # ejecutar
    err = _error_sap(ses)
    if err:
        res.mensaje = err
        return _cerrar(res)

    marcadas = 0
    for idx in range(PRIMERA_CHK, PRIMERA_CHK + len(numeros)):
        chk = _por_id(ses, f"wnd[0]/usr/chk[1,{idx}]")
        if chk is None:
            continue
        try:
            chk.Selected = True
            chk.SetFocus()
            marcadas += 1
        except Exception as e:  # noqa: BLE001
            anotar(f"No se pudo marcar la fila {idx} de VL06", e)
    if not marcadas:
        res.mensaje = ("No se pudieron marcar las entregas en la lista de VL06. "
                       "Revisa que aparezcan en pantalla.")
        return _cerrar(res)
    res.paso(f"Filas marcadas: {marcadas}")

    if ensayo:
        _presionar(ses, "wnd[0]/tbar[0]/btn[3]", 5)
        res.ok = True
        res.mensaje = (f"Ensayo listo: {marcadas} entregas quedaron marcadas en VL06 y se salió "
                       f"sin crear el grupo. La referencia sería '{texto}'.")
        return _cerrar(res)

    menu = _por_id(ses, MENU_CREAR_GRUPO)
    if menu is None:
        res.mensaje = "No se encontró el menú para crear el grupo de transporte."
        return _cerrar(res)
    try:
        menu.Select()
    except Exception as e:  # noqa: BLE001
        anotar("No se pudo abrir el menú de crear grupo", e)
    _esperar(ses)

    if _por_id(ses, "wnd[1]/usr/txtVBSK-VTEXT") is None:
        _aceptar_popups(ses)
        res.mensaje = "SAP no abrió la ventana para crear el grupo."
        return _cerrar(res)
    for ident, valor in (("wnd[1]/usr/ctxtVBSK-SMART", "K"),
                         ("wnd[1]/usr/txtVBSK-VTEXT", texto),
                         ("wnd[1]/usr/ctxtLIKP-LGNUM", LGNUM)):
        o = _por_id(ses, ident)
        if o is not None:
            try:
                o.Text = valor
                o.SetFocus()
                o.CaretPosition = len(valor)
            except Exception:  # noqa: BLE001
                pass
    _presionar(ses, "wnd[1]/tbar[0]/btn[0]", 20)
    for _ in range(5):
        w2 = _por_id(ses, "wnd[2]")
        if w2 is None:
            break
        try:
            w2.Close()
        except Exception:  # noqa: BLE001
            break
        _esperar(ses, 3)
    w1 = _por_id(ses, "wnd[1]")
    if w1 is not None:
        try:
            w1.Close()
        except Exception:  # noqa: BLE001
            pass
        _esperar(ses, 3)

    res.grupo = _numero_grupo(ses)
    res.ok = bool(res.grupo)
    res.mensaje = (f"Grupo {res.grupo} creado con referencia '{texto}'." if res.ok else
                   f"SAP no devolvió el número de grupo. Dice: {_mensaje_sap(ses)}")
    return _cerrar(res)


def actualizar_grupo(grupo: str, fecha: str = "", hora: str = "", referencia: str = "",
                     ensayo: bool = False, ses=None) -> Resultado:
    """Fecha, hora y referencia de un GRUPO, como el paso "Actualizar fecha" del Excel.

    Secuencia del VBA: VG02 con el grupo -> recorre sus entregas -> abre cada una (F2),
    marca todo (btn 25), escribe fecha y hora, 4 Enter y guarda (btn 11). La referencia
    se escribe al final en el grupo (VBSK-VTEXT) y se guarda.
    """
    res = Resultado(ensayo=ensayo)
    limpiar_incidencias()
    if not str(grupo).strip():
        res.mensaje = "Falta el número de grupo."
        return _cerrar(res)
    if not (fecha or hora or referencia):
        res.mensaje = "No se indicó fecha, hora ni referencia."
        return _cerrar(res)

    ses = ses or conectar()
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "VG02"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    _aceptar_popups(ses)
    campo = _por_id(ses, "wnd[0]/usr/ctxtVBSK-SAMMG")
    if campo is None:
        res.mensaje = "No se abrió VG02."
        return _cerrar(res)
    campo.Text = str(grupo)
    try:
        campo.CaretPosition = len(str(grupo))
    except Exception:  # noqa: BLE001
        pass
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses)
    _aceptar_popups(ses)
    err = _error_sap(ses)
    if err:
        res.mensaje = err
        return _cerrar(res)
    res.paso(f"Grupo {grupo} abierto en VG02")

    tocadas = 0
    if fecha or hora:
        fila = 0
        while True:
            celda = _por_id(ses, f"{VG02_TABLA}{fila}]")
            if celda is None:
                break
            try:
                entrega = str(celda.Text).strip()
            except Exception:  # noqa: BLE001
                entrega = ""
            if not entrega:
                break
            try:
                celda.SetFocus()
                celda.CaretPosition = len(entrega)
            except Exception:  # noqa: BLE001
                pass
            ses.findById("wnd[0]").sendVKey(2)          # abrir la entrega
            _esperar(ses)
            _aceptar_popups(ses)
            _presionar(ses, "wnd[0]/tbar[1]/btn[25]", 10)
            for ident, valor in ((VG02_FECHA, fecha), (VG02_HORA, hora)):
                if not valor:
                    continue
                o = _por_id(ses, ident)
                if o is not None:
                    try:
                        o.Text = valor
                        o.SetFocus()
                        o.CaretPosition = 2
                    except Exception:  # noqa: BLE001
                        pass
            for _ in range(4):
                ses.findById("wnd[0]").sendVKey(0)
                _esperar(ses, 3)
                _aceptar_popups(ses)
            if ensayo:
                _presionar(ses, "wnd[0]/tbar[0]/btn[3]", 5)   # salir sin grabar
                _aceptar_popups(ses)
            else:
                _presionar(ses, "wnd[0]/tbar[0]/btn[11]", 20)  # guardar la entrega
                _aceptar_popups(ses)
            tocadas += 1
            fila += 1
            if fila > 60:
                break
        if tocadas == 0:
            res.mensaje = f"El grupo {grupo} no tiene entregas en la tabla."
            return _cerrar(res)
        res.paso(f"Entregas con cita {'simulada' if ensayo else 'actualizada'}: {tocadas}")

    if referencia:
        _presionar(ses, "wnd[0]/tbar[1]/btn[8]", 10)
        o = _por_id(ses, "wnd[0]/usr/txtVBSK-VTEXT")
        if o is None:
            res.mensaje = "No se encontró el campo de referencia del grupo."
            return _cerrar(res)
        texto = referencia[:25]
        try:
            o.Text = texto
            o.CaretPosition = len(texto)
        except Exception:  # noqa: BLE001
            pass
        if not ensayo:
            _presionar(ses, "wnd[0]/tbar[0]/btn[11]", 20)
            _aceptar_popups(ses)
        res.paso(f"Referencia: {texto}")

    res.ok = True
    res.grupo = str(grupo)
    if ensayo:
        res.mensaje = (f"Ensayo listo: se recorrieron {tocadas} entrega(s) del grupo {grupo} "
                       f"sin grabar nada.")
    else:
        res.mensaje = f"Grupo {grupo} actualizado ({tocadas} entrega(s))."
    return _cerrar(res)


def actualizar_fecha(entrega: str, fecha: str, hora: str = "", ensayo: bool = False,
                     ses=None) -> Resultado:
    """Cambia fecha y hora de cita de una entrega (VL02N)."""
    res = Resultado(ensayo=ensayo)
    limpiar_incidencias()
    if not str(entrega).strip():
        res.mensaje = "Falta el número de entrega."
        return _cerrar(res)
    ses = ses or conectar()
    ses.findById("wnd[0]/tbar[0]/okcd").Text = "/nVL02N"
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 8)
    campo = _por_id(ses, "wnd[0]/usr/ctxtLIKP-VBELN")
    if campo is None:
        res.mensaje = "VL02N no mostró el campo de entrega."
        return _cerrar(res)
    campo.Text = str(entrega)
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 10)
    err = _error_sap(ses)
    if err:
        res.mensaje = err
        return _cerrar(res)
    pest = _por_id(ses, PESTANA_PICKING)
    if pest is not None:
        try:
            pest.Select()
        except Exception:  # noqa: BLE001
            pass
    _esperar(ses, 5)
    escritos = []
    for ident, valor, nombre in ((ID_FECHA, fecha, "fecha"), (ID_HORA, hora, "hora")):
        if not valor:
            continue
        o = _por_id(ses, ident)
        if o is None:
            res.mensaje = f"No se encontró el campo de {nombre} en la entrega."
            return _cerrar(res)
        try:
            o.Text = valor
            o.SetFocus()
            o.CaretPosition = len(valor)
            escritos.append(f"{nombre} {valor}")
        except Exception:  # noqa: BLE001
            pass
    if not escritos:
        res.mensaje = "No se indicó fecha ni hora."
        return _cerrar(res)
    res.paso("Escrito: " + ", ".join(escritos))
    ses.findById("wnd[0]").sendVKey(0)
    _esperar(ses, 5)

    if ensayo:
        _presionar(ses, "wnd[0]/tbar[0]/btn[3]", 5)
        _aceptar_popups(ses)
        res.ok = True
        res.mensaje = f"Ensayo listo: {', '.join(escritos)} quedó cargado y se salió sin grabar."
        return _cerrar(res)

    ses.findById("wnd[0]").sendVKey(11)
    _esperar(ses, 10)
    mensaje = _mensaje_sap(ses)
    err = _error_sap(ses)
    if err:
        res.mensaje = err
        return _cerrar(res)
    res.ok = True
    res.mensaje = mensaje or f"Entrega {entrega} actualizada."
    return _cerrar(res)
