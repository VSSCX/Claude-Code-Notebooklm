"""Catalogo de productos (codigo SAP + descripcion) y busqueda difusa.

Reconoce `med165b` como `MED 165B`, plurales (lavadoras), y corrige errores de tipeo ("refrigeradro").
Las palabras de la pregunta que NO son del catalogo se ignoran (y se avisa); un codigo de modelo que no existe
(`xyz999`) hace que no se encuentre el producto, en vez de responder con un producto parecido.
"""
from __future__ import annotations

import difflib

import pandas as pd

from .texto import compacto, tokens, variantes

_CACHE: dict = {"id": None, "cat": None}


def es_modelo(t: str) -> bool:
    """Parece un codigo de modelo: tiene digitos y letras, o es un numero largo."""
    return any(c.isdigit() for c in t) and (any(c.isalpha() for c in t) or len(t) >= 3)


class Catalogo:
    def __init__(self, lin: pd.DataFrame):
        cat = lin.drop_duplicates("SKU")[["SKU", "Descripcion"]]
        self.desc = dict(zip(cat["SKU"], cat["Descripcion"]))
        self.comp = {s: compacto(f"{d} {s}") for s, d in self.desc.items()}
        self.palabras = {s: set(tokens(d)) for s, d in self.desc.items()}
        self.vocab = sorted(set().union(*self.palabras.values())) if self.palabras else []
        self._vset = set(self.vocab)

    def _en(self, sku: str, tok: str) -> bool:
        return any(v in self.palabras[sku] or v in self.comp[sku] for v in variantes(tok))

    def reconocer(self, libres: list[str]):
        """-> (palabras de producto, correcciones {mal: bien}, palabras ignoradas, codigos de modelo que no existen)."""
        prod, corr, ign, desconocidos = [], {}, [], []
        for t in libres:
            if any(v in self._vset for v in variantes(t)) or (len(t) >= 4 and any(t in c for c in self.comp.values())):
                prod.append(t)
                continue
            if len(t) >= 5 and not es_modelo(t):
                cerca = difflib.get_close_matches(t, self.vocab, n=1, cutoff=.84)
                if cerca:
                    prod.append(cerca[0])
                    corr[t] = cerca[0]
                    continue
            (desconocidos if es_modelo(t) else ign).append(t)
        return prod, corr, ign, desconocidos

    def buscar(self, texto: str | None, sku: str | None):
        """-> (SKUs que coinciden, aproximado, sugerencias)."""
        if sku:
            return ([sku] if sku in self.desc else []), False, []
        toks = [t for t in tokens(texto or "")]
        if not toks:
            return [], False, []
        puntaje = {s: sum(self._en(s, t) for t in toks) / len(toks) for s in self.desc}
        exacto = [s for s, v in puntaje.items() if v == 1]
        if exacto:
            return exacto, False, []
        mejor = max(puntaje.values(), default=0)
        dig = [t for t in toks if any(c.isdigit() for c in t)]
        if mejor >= .6:
            cand = [s for s, v in puntaje.items() if v == mejor and all(self._en(s, t) for t in dig)]
            if cand:
                return cand, True, []
        sug = difflib.get_close_matches(" ".join(toks), [d for d in self.desc.values() if d], n=4, cutoff=.3)
        return [], False, sug


def de(lin: pd.DataFrame) -> Catalogo:
    """Un catalogo por tabla de lineas (se reconstruye solo cuando cambia la tabla)."""
    if _CACHE["id"] is not id(lin):
        _CACHE.update(id=id(lin), cat=Catalogo(lin))
    return _CACHE["cat"]
