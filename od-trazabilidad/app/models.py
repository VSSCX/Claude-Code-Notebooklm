"""Modelo relacional (Unicode -> NVARCHAR en SQL Server, acentos y Ñ seguros).

Pedido 1-N LineaPedido
Pedido 1-N Entrega 1-N LineaEntrega
                   1-N PasoEntrega   (estado actual de cada paso)
                   1-N Evento        (historial: base para medir tiempos por etapa)
Un camión = entregas con el mismo cita_numero.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint,
                        Unicode, UnicodeText)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def ahora() -> datetime:
    """UTC sin zona (portable entre SQLite y SQL Server)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Pedido(Base):
    __tablename__ = "pedidos"
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido: Mapped[str] = mapped_column(Unicode(20), unique=True, index=True)
    oc: Mapped[str] = mapped_column(Unicode(40), default="")
    cliente: Mapped[str] = mapped_column(Unicode(80), default="", index=True)
    canal: Mapped[str] = mapped_column(Unicode(30), default="")
    fecha_oc: Mapped[date | None] = mapped_column(Date, nullable=True)
    obs: Mapped[str] = mapped_column(Unicode(500), default="")
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)

    lineas: Mapped[list["LineaPedido"]] = relationship(
        back_populates="pedido_ref", cascade="all, delete-orphan", order_by="LineaPedido.id")
    entregas: Mapped[list["Entrega"]] = relationship(
        back_populates="pedido_ref", cascade="all, delete-orphan")


class LineaPedido(Base):
    __tablename__ = "lineas_pedido"
    __table_args__ = (UniqueConstraint("pedido_id", "sku"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(Unicode(40))
    descripcion: Mapped[str] = mapped_column(Unicode(120), default="")
    qty: Mapped[int] = mapped_column(Integer, default=0)
    # Unidades en entregas SAP creadas antes de registrarlas en la plataforma
    externa: Mapped[int] = mapped_column(Integer, default=0)

    pedido_ref: Mapped[Pedido] = relationship(back_populates="lineas")


class Entrega(Base):
    __tablename__ = "entregas"
    id: Mapped[int] = mapped_column(primary_key=True)
    entrega: Mapped[str] = mapped_column(Unicode(20), unique=True, index=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), index=True)
    grupo: Mapped[str] = mapped_column(Unicode(20), default="", index=True)
    tipo: Mapped[str] = mapped_column(Unicode(20), default="Stock")
    cita_numero: Mapped[str] = mapped_column(Unicode(30), default="", index=True)
    cita_fecha: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    cita_hora: Mapped[str] = mapped_column(Unicode(5), default="")
    vehiculo: Mapped[str] = mapped_column(Unicode(20), default="Rampla 53")
    carga: Mapped[str] = mapped_column(Unicode(10), default="MIX")
    un: Mapped[str] = mapped_column(Unicode(10), default="MDA")
    region: Mapped[str] = mapped_column(Unicode(20), default="RM")
    factura: Mapped[str] = mapped_column(Unicode(30), default="")
    obs: Mapped[str] = mapped_column(Unicode(500), default="")
    anulada: Mapped[bool] = mapped_column(Boolean, default=False)
    reprogramaciones: Mapped[int] = mapped_column(Integer, default=0)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)

    pedido_ref: Mapped[Pedido] = relationship(back_populates="entregas")
    lineas: Mapped[list["LineaEntrega"]] = relationship(
        back_populates="entrega_ref", cascade="all, delete-orphan", order_by="LineaEntrega.id")
    pasos: Mapped[list["PasoEntrega"]] = relationship(
        back_populates="entrega_ref", cascade="all, delete-orphan")
    eventos: Mapped[list["Evento"]] = relationship(
        back_populates="entrega_ref", cascade="all, delete-orphan",
        order_by="(Evento.at.desc(), Evento.id.desc())")


class LineaEntrega(Base):
    __tablename__ = "lineas_entrega"
    __table_args__ = (UniqueConstraint("entrega_id", "sku"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(ForeignKey("entregas.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(Unicode(40))
    qty: Mapped[int] = mapped_column(Integer, default=0)

    entrega_ref: Mapped[Entrega] = relationship(back_populates="lineas")


class PasoEntrega(Base):
    __tablename__ = "pasos_entrega"
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id", ondelete="CASCADE"), primary_key=True)
    paso: Mapped[str] = mapped_column(Unicode(20), primary_key=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    entrega_ref: Mapped[Entrega] = relationship(back_populates="pasos")


class Evento(Base):
    __tablename__ = "eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(ForeignKey("entregas.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    origen: Mapped[str] = mapped_column(Unicode(20), default="web")  # web | script | import
    texto: Mapped[str] = mapped_column(Unicode(300))

    entrega_ref: Mapped[Entrega] = relationship(back_populates="eventos")


class Archivo(Base):
    """Visores 3D generados y PDFs que sube el analista, por pedido o camión."""
    __tablename__ = "archivos"
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int | None] = mapped_column(
        ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=True, index=True)
    grupo: Mapped[str] = mapped_column(Unicode(20), default="", index=True)
    tipo: Mapped[str] = mapped_column(Unicode(20), default="adjunto")  # visor | pdf | adjunto
    nombre: Mapped[str] = mapped_column(Unicode(200))
    archivo: Mapped[str] = mapped_column(Unicode(200))   # nombre en data/archivos
    at: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Medida(Base):
    """Base de Medidas cargada en la plataforma (reemplaza la lectura del archivo de red)."""
    __tablename__ = "medidas"
    sku: Mapped[str] = mapped_column(Unicode(40), primary_key=True)
    descripcion: Mapped[str] = mapped_column(Unicode(150), default="")
    piezas: Mapped[int] = mapped_column(Integer, default=1)
    largo: Mapped[float] = mapped_column(Float, default=0.0)
    ancho: Mapped[float] = mapped_column(Float, default=0.0)
    alto: Mapped[float] = mapped_column(Float, default=0.0)
    peso: Mapped[float] = mapped_column(Float, default=0.0)
    apilar: Mapped[str] = mapped_column(Unicode(1), default="N")
    inclinar: Mapped[str] = mapped_column(Unicode(1), default="N")
    rotar: Mapped[str] = mapped_column(Unicode(1), default="N")
    max_camion: Mapped[int] = mapped_column(Integer, default=0)
    max_pallet: Mapped[int] = mapped_column(Integer, default=0)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)


class Cliente(Base):
    """Reglas por cliente: antes estaban escritas en el código y en hojas del Excel."""
    __tablename__ = "clientes"
    nombre: Mapped[str] = mapped_column(Unicode(80), primary_key=True)
    grupo_sop: Mapped[str] = mapped_column(Unicode(80), default="")
    codigo: Mapped[str] = mapped_column(Unicode(20), default="")       # solicitante en SAP
    canal: Mapped[str] = mapped_column(Unicode(30), default="RETAIL")
    region: Mapped[str] = mapped_column(Unicode(20), default="RM")
    pallet_largo: Mapped[float] = mapped_column(Float, default=120.0)
    pallet_ancho: Mapped[float] = mapped_column(Float, default=100.0)
    pallet_alto: Mapped[float] = mapped_column(Float, default=140.0)
    caja_master: Mapped[str] = mapped_column(Unicode(20), default="")  # default de F2
    calefon_aparte: Mapped[bool] = mapped_column(Boolean, default=False)   # HITES
    hibrido: Mapped[bool] = mapped_column(Boolean, default=False)          # SODIMAC / RIPLEY
    notas: Mapped[str] = mapped_column(Unicode(200), default="")
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Config(Base):
    __tablename__ = "config"
    clave: Mapped[str] = mapped_column(Unicode(50), primary_key=True)
    valor: Mapped[str] = mapped_column(UnicodeText, default="{}")
