"""Contratos de la API. Los nombres de campo coinciden con los que usa la web."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PASOS = ("solicitada", "confirmada", "sap", "etq", "portal", "proyeccion", "facturada", "packlist", "entregado")
REABRE_AL_REPROGRAMAR = ("confirmada", "sap", "portal", "proyeccion")


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True, str_strip_whitespace=True)


def _fecha_vacia(v):
    return None if v in ("", None) else v


# ---------- documentos (web <-> API) ----------
class LineaPedidoIn(_Base):
    sku: str = Field(min_length=1, max_length=40)
    desc: str = Field("", max_length=120)
    qty: int = Field(0, ge=0)
    externa: int = Field(0, ge=0)


class PedidoIn(_Base):
    pedido: str = Field(min_length=1, max_length=20)
    oc: str = Field("", max_length=40)
    cliente: str = Field("", max_length=80)
    canal: str = Field("", max_length=30)
    fechaOC: date | None = None
    obs: str = Field("", max_length=500)
    lineas: list[LineaPedidoIn] = []

    _f = field_validator("fechaOC", mode="before")(_fecha_vacia)


class CitaIn(_Base):
    numero: str = Field("", max_length=30)
    fecha: date | None = None
    hora: str = Field("", pattern=r"^$|^\d{2}:\d{2}$")

    _f = field_validator("fecha", mode="before")(_fecha_vacia)


class LineaEntregaIn(_Base):
    sku: str = Field(min_length=1, max_length=40)
    qty: int = Field(0, ge=0)


class PasoIn(_Base):
    ok: bool
    at: datetime | None = None


class LogIn(_Base):
    at: datetime
    txt: str = Field(max_length=300)


class EntregaIn(_Base):
    entrega: str = Field(min_length=1, max_length=20)
    pedido: str = Field(min_length=1, max_length=20)
    grupo: str = Field("", max_length=20)
    tipo: str = Field("Stock", max_length=20)
    cita: CitaIn = CitaIn()
    vehiculo: Literal["Rampla 53", "Camión 50"] = "Rampla 53"
    carga: Literal["MIX", "MONO"] = "MIX"
    un: Literal["MDA", "SDA"] = "MDA"
    region: str = Field("RM", max_length=20)
    factura: str = Field("", max_length=30)
    obs: str = Field("", max_length=500)
    anulada: bool = False
    reprog: int = Field(0, ge=0)
    lineas: list[LineaEntregaIn] = []
    pasos: dict[str, PasoIn] = {}
    log: list[LogIn] = []

    @field_validator("pasos")
    @classmethod
    def _pasos_validos(cls, v: dict[str, PasoIn]):
        malos = set(v) - set(PASOS)
        if malos:
            raise ValueError(f"Pasos desconocidos: {', '.join(sorted(malos))}")
        return v


# ---------- paquete del script VBA ----------
class PaqLineaPedido(_Base):
    sku: str
    desc: str = ""
    pendiente: int = 0
    enEntrega: int = 0


class PaqPedido(_Base):
    pedido: str
    oc: str = ""
    fechaOC: date | None = None
    lineas: list[PaqLineaPedido] = []

    _f = field_validator("fechaOC", mode="before")(_fecha_vacia)


class PaqEntrega(_Base):
    entrega: str
    pedido: str = ""
    camion: int = 0
    vehiculo: str = ""
    grupo: str = ""
    cita: str = ""
    fecha: date | None = None
    hora: str = ""
    carga: str = ""
    lineas: list[LineaEntregaIn] = []

    _f = field_validator("fecha", mode="before")(_fecha_vacia)


class PaqueteIn(_Base):
    tipo: Literal["od-traz"]
    v: int = 1
    evento: str
    at: str = ""
    analista: str = ""
    cliente: str = ""
    un: str = ""
    modalidad: str = ""   # Stock | Predistribuido, derivado de E2 en el libro
    pedidos: list[PaqPedido] = []
    entregas: list[PaqEntrega] = []
    sapOk: list[str] = []
