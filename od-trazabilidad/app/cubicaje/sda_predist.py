"""Port de Cubicaje_SDA_Predistribuido: pallets por sucursal.

Reglas propias de este modo (además de todo lo de SDA Stock):
- Los bloques salen de la tabla Predistribuido, topeados por la carga del análisis.
- La columna "unidades por bulto" del cliente manda sobre las piezas de la caja master.
- **Mono-sucursal**: cada sucursal arma sus propios pallets. Solo el último pallet, si
  quedó bajo el 60% y la sucursal hizo dos o más, se deshace y su contenido va al pool.
- **Nivel 2**: con los conchos del pool se arman pallets mono-SKU completos.
- **Nivel 3**: lo que aún queda se mezcla en pallets mix.
- **Clientes híbridos** (SODIMAC, RIPLEY): no hay niveles 2 y 3; los conchos van a piso.
- La reubicación de sobrantes se restringe a pallets de la MISMA sucursal.
"""
from __future__ import annotations

from .core import Restric
from .datos import Dims, get_dims_for
from .mda import Camion, Fila03, NO_ENCONTRADO, Posicion, Resultado
from .mda_predist import FilaPredist
from .sda import (EPS_SDA, MAX_BLOQUES_PALLET, U_SDA, Bloque, Pallet, asignar_vehiculos,
                  calcular_capacidades, cargar_piso, restricciones_piso, restricciones_sda,
                  ubicar_pallets, validar_pallets)
from .vb import clng, vb_int, vb_round

HIBRIDOS = ("SODIMAC", "RIPLEY")
MAX_BLOQUES_PALLET_PD = 14      # este modo permite más bloques por pallet que SDA Stock


def es_cliente_hibrido(cliente: str) -> bool:
    c = (cliente or "").strip().upper()
    return any(h in c for h in HIBRIDOS)


def construir_bloques_predist(predist: list[FilaPredist], posiciones: list[Posicion],
                              cache: dict[str, Dims], usa_caja_master: bool,
                              pasa_filtro=None) -> tuple[list[Bloque], list[str], list[str]]:
    """Filas del predistribuido -> bloques por sucursal, topeadas por la carga del análisis."""
    sop: dict[str, int] = {}
    pedido_de: dict[str, str] = {}
    for p in posiciones:
        sk = str(p.sku).strip()
        if not sk or str(p.desc).strip() == NO_ENCONTRADO:
            continue
        if isinstance(p.carga, (int, float)):
            sop[sk] = sop.get(sk, 0) + clng(p.carga)
        pedido_de.setdefault(sk, str(p.pedido).strip())

    # orden alfabético por sucursal, estable (insertion sort del VBA)
    filas = sorted(range(len(predist)), key=lambda i: str(predist[i].sucursal).strip().upper())
    bloques: list[Bloque] = []
    sin_medidas: list[str] = []
    fuera_de_pedido: list[str] = []
    usado: dict[str, int] = {}

    for i in filas:
        f = predist[i]
        suc = str(f.sucursal).strip().upper()
        sk = str(f.sku).strip()
        if not suc or not sk:
            continue
        if pasa_filtro is not None and not pasa_filtro(sk):
            continue
        und = clng(f.unidades) if isinstance(f.unidades, (int, float)) else 0
        if und <= 0:
            continue
        if sk not in sop:
            if sk not in fuera_de_pedido:
                fuera_de_pedido.append(sk)
            continue
        disponible = sop[sk] - usado.get(sk, 0)
        if disponible <= 0:
            continue
        und = min(und, disponible)
        usado[sk] = usado.get(sk, 0) + und
        ped = pedido_de.get(sk) or f"_pre{i + 2}"

        dc = get_dims_for(cache, "C" + sk)
        por_bulto = getattr(f, "por_bulto", 0) or 0            # columna E del cliente
        if por_bulto >= 1:
            bulto = int(por_bulto)
        elif usa_caja_master and dc is not None:
            bulto = dc.piezas if dc.piezas > 0 else 1
        else:
            bulto = 1

        if bulto > 1 and dc is not None:
            cajas, sueltas = divmod(und, bulto)
            if cajas > 0:
                bloques.append(Bloque(cod=sk, desc=dc.desc or sk, tipo="Caja", cm_por_caja=bulto,
                                      n=cajas, L=dc.L, w=dc.w, h=dc.h, apilable=dc.apilable,
                                      rotable=False, peso=dc.peso, pedido=ped))
                bloques[-1].sucursal = suc
            if sueltas > 0:
                ds = get_dims_for(cache, sk)
                if ds is not None:
                    bloques.append(Bloque(cod=sk, desc=ds.desc or sk, tipo="Suelta", cm_por_caja=1,
                                          n=sueltas, L=ds.L, w=ds.w, h=ds.h, apilable=ds.apilable,
                                          rotable=False, peso=ds.peso, pedido=ped))
                    bloques[-1].sucursal = suc
        else:
            d = get_dims_for(cache, sk)
            if d is None:
                if sk not in sin_medidas:
                    sin_medidas.append(sk)
                continue
            bloques.append(Bloque(cod=sk, desc=d.desc or sk, tipo="Indiv", cm_por_caja=1, n=und,
                                  L=d.L, w=d.w, h=d.h, apilable=d.apilable, rotable=False,
                                  peso=d.peso, pedido=ped))
            bloques[-1].sucursal = suc
    return bloques, sin_medidas, fuera_de_pedido


def armar_pallets_por_sucursal(bloques: list[Bloque], hibrido: bool) -> tuple[list[Pallet], list, list]:
    """Nivel 1 (mono-sucursal), nivel 2 (mono-SKU con los conchos) y nivel 3 (mix)."""
    sucursales = sorted({b.sucursal for b in bloques})
    pallets: list[Pallet] = []
    pool: list[list] = []            # [índice de bloque, unidades]
    piso: list[tuple[int, int]] = []

    for suc in sucursales:
        idx = [i for i, b in enumerate(bloques) if b.sucursal == suc]
        idx.sort(key=lambda i: -bloques[i].volumen)          # volumen DESC dentro de la sucursal
        pal_ini = len(pallets)
        actual: Pallet | None = None
        for bi in idx:
            if bloques[bi].no_cabe:
                piso.append((bi, bloques[bi].n))
                continue
            pend = bloques[bi].n
            while pend > 0:
                if actual is None:
                    actual = Pallet()
                    actual.sucursal = suc
                    actual.tipo = "Mono-Suc"
                    pallets.append(actual)
                caben = vb_int((1.0 - actual.frac) * bloques[bi].cap_pallet + EPS_SDA)
                if caben <= 0:
                    actual = None
                    continue
                m = min(pend, caben)
                k = next((k for k, (b, _) in enumerate(actual.contenido) if b == bi), None)
                if k is None:
                    actual.contenido.append((bi, 0))
                    k = len(actual.contenido) - 1
                b0, n0 = actual.contenido[k]
                actual.contenido[k] = (b0, n0 + m)
                actual.frac += m / bloques[bi].cap_pallet
                pend -= m
                if actual.frac >= 1.0 - EPS_SDA:
                    actual = None
        # El concho: solo si la sucursal hizo 2 o más pallets y el último quedó flojo
        if len(pallets) - pal_ini >= 2:
            ult = pallets[-1]
            if ult.k > 0 and ult.frac < U_SDA - EPS_SDA:
                for bi, n in ult.contenido:
                    pool.append([bi, n])
                ult.contenido = []
                ult.frac = 0.0
        actual = None

    pallets = [p for p in pallets if p.k > 0]
    if hibrido:                       # SODIMAC / RIPLEY: los conchos van a piso
        piso.extend((bi, n) for bi, n in pool if n > 0)
        return pallets, [], piso

    # Nivel 2: pallets mono-SKU completos con los conchos del mismo producto
    procesados = set()
    for q in range(len(pool)):
        if q in procesados or pool[q][1] <= 0:
            continue
        bi0 = pool[q][0]
        clave = (bloques[bi0].cod, bloques[bi0].tipo)
        cap = bloques[bi0].cap_pallet
        hermanos = [i for i in range(len(pool))
                    if (bloques[pool[i][0]].cod, bloques[pool[i][0]].tipo) == clave]
        total = sum(pool[i][1] for i in hermanos if pool[i][1] > 0)
        while total >= cap:
            nuevo = Pallet()
            nuevo.tipo = "Mono-SKU"
            nuevo.sucursal = "~"
            falta = cap
            for i in hermanos:
                if falta <= 0:
                    break
                if pool[i][1] > 0:
                    take = min(pool[i][1], falta)
                    nuevo.contenido.append((pool[i][0], take))
                    pool[i][1] -= take
                    falta -= take
            nuevo.frac = 1.0
            pallets.append(nuevo)
            total -= cap
        procesados.update(hermanos)

    # Nivel 3: lo que queda se mezcla, del más lleno al menos
    resto = [x for x in pool if x[1] > 0]
    resto.sort(key=lambda x: -(x[1] / bloques[x[0]].cap_pallet))
    mix_desde = len(pallets)
    for bi, pend in resto:
        while pend > 0:
            colocado = False
            for pp in range(mix_desde, len(pallets)):
                p = pallets[pp]
                if p.k >= MAX_BLOQUES_PALLET_PD:
                    continue
                caben = vb_int((1.0 - p.frac) * bloques[bi].cap_pallet + EPS_SDA)
                if caben <= 0:
                    continue
                m = min(pend, caben)
                p.contenido.append((bi, m))
                p.frac += m / bloques[bi].cap_pallet
                pend -= m
                colocado = True
                if pend <= 0:
                    break
            if pend > 0 and not colocado:
                nuevo = Pallet()
                nuevo.tipo = "Mix"
                nuevo.sucursal = "~"
                m = min(pend, bloques[bi].cap_pallet)
                nuevo.contenido.append((bi, m))
                nuevo.frac = m / bloques[bi].cap_pallet
                pallets.append(nuevo)
                pend -= m
    return pallets, pool, piso


def cubicaje_sda_predistribuido(posiciones: list[Posicion], predist: list[FilaPredist],
                                cache: dict[str, Dims], pal_L: float, pal_W: float, pal_H: float,
                                usa_caja_master: bool, cliente: str, pasa_filtro=None,
                                cam_offset: int = 0, hibrido: bool | None = None,
                                orientacion: str = "excel", capacidad: str = "geometria") -> Resultado:
    res = Resultado(modo="SDA PREDISTRIBUIDO")
    restric = restricciones_sda()
    bloques, sin_medidas, fuera = construir_bloques_predist(predist, posiciones, cache,
                                                            usa_caja_master, pasa_filtro)
    res.sin_medidas = sin_medidas
    if fuera:
        res.avisos.append("SKU del reparto que no están en el pedido: " + ", ".join(fuera))
    if not bloques:
        res.avisos.append("Sin SKUs cubicables en SDA Predistribuido.")
        return res

    from .sda import grilla_simple, orientar_pallet, _items_de_pallet
    tabla = capacidad == "tabla"
    # La orientación acomoda las cajas dentro del pallet; la estiba en el camión no cambia
    pack_L, pack_W = orientar_pallet(pal_L, pal_W, orientacion, bloques, restric, pal_H)
    calcular_capacidades(bloques, pack_L, pack_W, pal_H, restric, cache, tabla)
    hibrido = es_cliente_hibrido(cliente) if hibrido is None else bool(hibrido)
    if hibrido:
        res.avisos.append(f"{cliente}: cliente híbrido, los conchos van a piso (sin pallets mix).")
    pallets, _pool, piso = armar_pallets_por_sucursal(bloques, hibrido)
    if tabla:
        pallets = [p for p in pallets if sum(n for _, n in p.contenido) > 0]
        placements = {i: grilla_simple(_items_de_pallet(p, bloques), pack_L, pack_W)
                      for i, p in enumerate(pallets)}
    else:
        pallets, placements = validar_pallets(pallets, bloques, pack_L, pack_W, pal_H, restric,
                                              misma_sucursal=True)
    if not pallets and not piso:
        res.avisos.append("SDA Predistribuido: sin pallets resultantes.")
        return res

    vehiculos = asignar_vehiculos(len(pallets))
    colocados, filas04, geo = ubicar_pallets(pallets, placements, bloques, vehiculos, pal_L, pal_W,
                                             girar=(pack_L, pack_W) != (pal_L, pal_W))
    for f, p in zip(filas04, [p for p in pallets for _ in p.contenido if _[1] > 0]):
        f.sucursal = getattr(p, "sucursal", "")
    piso_pl, piso_filas, vehiculos = cargar_piso(piso, bloques, vehiculos, geo, pal_W,
                                                 restricciones_piso())
    for f in piso_filas:
        bi = next((i for i, b in enumerate(bloques) if b.cod == f.sku), None)
        f.sucursal = bloques[bi].sucursal if bi is not None else ""
    res.placed = colocados + piso_pl
    res.filas04 = filas04 + piso_filas
    res.pallets = [{"numero": i + 1, "tipo": getattr(p, "tipo", "Mono-Suc"),
                    "sucursal": getattr(p, "sucursal", ""),
                    "vehiculo": geo.get(i + 1, {}).get("veh", 0),
                    "x": geo.get(i + 1, {}).get("x", 0.0), "y": geo.get(i + 1, {}).get("y", 0.0),
                    "dl": pal_W, "dw": pal_L} for i, p in enumerate(pallets)]

    for v in vehiculos:
        del_cam = [p for p in res.placed if p.container == v.numero]
        if not del_cam:
            continue
        vol_cam = v.L * v.w * v.h / 1_000_000.0 or 1.0
        res.camiones.append(Camion(numero=v.numero + cam_offset, tipo=v.tipo, L=v.L, w=v.w, h=v.h))
        agg: list[dict] = []
        for p in del_cam:
            b = bloques[p.fila] if 0 <= p.fila < len(bloques) else None
            cod = b.cod if b else p.cod
            suc = b.sucursal if b else ""
            f = next((a for a in agg if a["cod"] == cod and a["suc"] == suc), None)
            if f is None:
                f = {"cod": cod, "desc": b.desc if b else p.desc, "u": 0, "v": 0.0,
                     "fila": p.fila, "suc": suc, "ped": b.pedido if b else p.ped}
                agg.append(f)
            f["u"] += p.n * (max(b.cm_por_caja, 1) if b else 1)
            f["v"] += p.volM3
        acum = 0.0
        for a in agg:
            acum += a["v"]
            res.filas03.append(Fila03(
                camion=v.numero + cam_offset, tipo_camion=v.tipo, cap_m3=vb_round(vol_cam, 2),
                sku=a["cod"], descripcion=a["desc"], unidades=a["u"], ocup_linea=a["v"] / vol_cam,
                ocup_acum=acum / vol_cam, libre_m3=vb_round(vol_cam - acum, 2),
                fila_origen=a["fila"], tipo_carga=f"Sucursal {a['suc']}", pedido=a["ped"],
                pedidos_camion="", sucursal=a["suc"]))
    return res
