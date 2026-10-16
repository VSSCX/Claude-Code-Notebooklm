"""Exportar a CSV (punto y coma y UTF-8 con BOM: abre bien en Excel en espanol)."""
from __future__ import annotations


def celda(v) -> str:
    s = "" if v is None else str(v)
    if s[:1] in ("=", "+", "-", "@") and not s.lstrip("-").replace(".", "", 1).isdigit():
        s = "'" + s                                     # un texto que empieza con = + - @ no se ejecuta como formula en Excel
    return '"' + s.replace('"', '""') + '"' if any(x in s for x in ';"\n\r') else s


def a_csv(columnas: list[str], filas) -> str:
    lineas = [";".join(celda(c) for c in columnas)] + [";".join(celda(v) for v in f) for f in filas]
    return "﻿" + "\r\n".join(lineas) + "\r\n"
