"""Codigo SAP en un solo formato: la misma pieza puede venir como "240096077", "000000240096077" o "240096077.0" segun la tabla."""
import pandas as pd


def limpiar(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip().str.replace(r"\.0+$", "", regex=True).str.lstrip("0")
    return t.where(t != "", "0")
