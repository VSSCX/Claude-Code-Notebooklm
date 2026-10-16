"""Asistente de consultas del tablero (ver ASISTENTE.md)."""
from . import memoria
from .motor import info_motor, responder
from .redactar import EJEMPLOS

__all__ = ["responder", "info_motor", "EJEMPLOS", "memoria"]
