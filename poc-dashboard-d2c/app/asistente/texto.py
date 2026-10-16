"""Texto de la pregunta: sin acentos ni mayusculas, decimales 8,5 -> 85, y busqueda que recuerda que palabras ya se usaron."""
from __future__ import annotations

import re
import unicodedata


def sa(t) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _limpia(t) -> str:
    return re.sub(r"(?<=\d)[.,](?=\d)", "", sa(t))      # 8,5 -> 85 (igual en la pregunta y en la descripcion del producto)


def tokens(t) -> list[str]:
    return re.findall(r"[a-z0-9]+", _limpia(t))


def compacto(t) -> str:
    return "".join(tokens(t))


def variantes(tok: str) -> list[str]:
    """Singular y plural simples: lavadoras -> lavadora, refrigeradores -> refrigerador."""
    v = [tok]
    if len(tok) > 3 and tok.endswith("es"):
        v.append(tok[:-2])
    if len(tok) > 3 and tok.endswith("s"):
        v.append(tok[:-1])
    return v


def lista_es(xs: list[str]) -> str:
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


class Texto:
    """La pregunta normalizada. `buscar` encuentra un patron y marca como usadas las palabras que cubre,
    asi lo que sobra al final (`libres`) es lo que podria ser el nombre de un producto."""

    def __init__(self, q: str):
        self.t = _limpia(q)
        self.tok = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[a-z0-9]+", self.t)]
        self.usado = [False] * len(self.tok)

    def hay(self, patron: str) -> bool:
        return re.search(patron, self.t) is not None

    def buscar(self, patron: str, marcar: bool = True):
        m = re.search(patron, self.t)
        if m and marcar:
            self.marcar(m.start(), m.end())
        return m

    def marcar(self, a: int, b: int) -> None:
        for i, (_, s, e) in enumerate(self.tok):
            if s < b and e > a:
                self.usado[i] = True

    def marcar_tokens(self, palabras) -> None:
        for i, (t, _, _) in enumerate(self.tok):
            if t in palabras:
                self.usado[i] = True

    def todos(self) -> list[str]:
        return [t for t, _, _ in self.tok]

    def libres(self) -> list[str]:
        return [t for (t, _, _), u in zip(self.tok, self.usado) if not u]
