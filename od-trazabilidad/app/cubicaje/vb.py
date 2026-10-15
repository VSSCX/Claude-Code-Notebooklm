"""Equivalentes exactos de funciones de VBA que cambian resultados si se traducen a la ligera."""
import math
import re
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal


def clng(x) -> int:
    """CLng: redondeo bancario (2.5 -> 2, 3.5 -> 4)."""
    return int(Decimal(str(float(x))).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def vb_round(x: float, d: int = 0) -> float:
    """Round() de VBA: también bancario."""
    q = Decimal(1).scaleb(-d)
    return float(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_EVEN))


def vb_int(x: float) -> int:
    """Int(): piso (Int(-2.5) = -3)."""
    return math.floor(x)


def ceil_neg_int(x: float) -> int:
    """-Int(-x): techo, como lo escribe el VBA."""
    return -math.floor(-x)


def val(s) -> float:
    """Val(): lee el número del inicio del texto; 0 si no hay."""
    m = re.match(r"\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", str(s or ""))
    return float(m.group(1)) if m else 0.0


def cdbl(x):
    """CDbl que devuelve None cuando el VBA lanzaría error (texto no numérico)."""
    if x is None or x == "":
        return 0.0 if x is None else None
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fmt_num(x: float) -> str:
    """Format$(x, "0.###") con punto decimal (nm() del visor)."""
    d = Decimal(repr(float(x))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    s = format(d, "f").rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def round1(x: float, d: int) -> float:
    """Round1 del visor: Int(x * 10^d + 0.5) / 10^d."""
    f = 10 ** d
    return math.floor(x * f + 0.5) / f
