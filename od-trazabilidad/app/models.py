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
    # Camión compartido entre pedidos: las entregas creadas desde un cubicaje conjunto para el mismo camión
    # llevan la misma referencia (conjunto-camión) y se agrupan juntas en SAP.
    camion_ref: Mapped[str] = mapped_column(Unicode(40), default="", index=True)
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


class Kit(Base):
    """Kit: un SKU propio del pedido que reúne cajas separadas (horno + encimera + campana...) que viajan juntas."""
    __tablename__ = "kits"
    sku: Mapped[str] = mapped_column(Unicode(40), primary_key=True)
    descripcion: Mapped[str] = mapped_column(Unicode(200), default="")
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    componentes: Mapped[list["KitComponente"]] = relationship(
        back_populates="kit", cascade="all, delete-orphan", order_by="KitComponente.id")


class KitComponente(Base):
    __tablename__ = "kit_componentes"
    __table_args__ = (UniqueConstraint("kit_sku", "sku", name="uq_kit_componente"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kit_sku: Mapped[str] = mapped_column(Unicode(40), ForeignKey("kits.sku", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(Unicode(40))
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    kit: Mapped["Kit"] = relationship(back_populates="componentes")


class Config(Base):
    __tablename__ = "config"
    clave: Mapped[str] = mapped_column(Unicode(50), primary_key=True)
    valor: Mapped[str] = mapped_column(UnicodeText, default="{}")


# ---------------------------------------------------------------------------
# Cuentas, sesiones, historial de actividad y registro de errores (para trabajar en servidor)
# ---------------------------------------------------------------------------
class Usuario(Base):
    """Cuenta de un analista. La clave se guarda con hash (nunca en claro)."""
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(Unicode(40), unique=True, index=True)       # lo que escribe al entrar, en minúsculas
    nombre: Mapped[str] = mapped_column(Unicode(60), default="")                      # lo que se ve en el historial
    rol: Mapped[str] = mapped_column(Unicode(12), default="analista")                 # analista | admin
    clave_hash: Mapped[str] = mapped_column(Unicode(200), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    debe_cambiar_clave: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SesionWeb(Base):
    """Sesión abierta en un navegador. Del token solo se guarda su huella."""
    __tablename__ = "sesiones"
    token_hash: Mapped[str] = mapped_column(Unicode(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    vista: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)     # última actividad (la sesión caduca por inactividad)
    ip: Mapped[str] = mapped_column(Unicode(60), default="")
    agente: Mapped[str] = mapped_column(Unicode(200), default="")


class Actividad(Base):
    """Qué hizo cada analista y cuándo: una fila por acción."""
    __tablename__ = "actividad"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    usuario: Mapped[str] = mapped_column(Unicode(40), default="", index=True)         # nombre de la cuenta
    categoria: Mapped[str] = mapped_column(Unicode(12), default="pedido", index=True)  # pedido | sap | cubicaje | datos | cuenta | sistema
    accion: Mapped[str] = mapped_column(Unicode(200))                                  # "Guardó el pedido 4005…"
    entidad: Mapped[str] = mapped_column(Unicode(40), default="", index=True)          # pedido, entrega o grupo afectado
    resultado: Mapped[str] = mapped_column(Unicode(10), default="ok")                  # ok | error | rechazada
    detalle: Mapped[str] = mapped_column(Unicode(400), default="")
    ip: Mapped[str] = mapped_column(Unicode(60), default="")
    ms: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str] = mapped_column(Unicode(16), default="", index=True)


class ErrorLog(Base):
    """Un tipo de error (se agrupan los repetidos): primera vez, última, cuántas veces y su estado."""
    __tablename__ = "errores"
    id: Mapped[int] = mapped_column(primary_key=True)
    huella: Mapped[str] = mapped_column(Unicode(40), unique=True, index=True)
    nivel: Mapped[str] = mapped_column(Unicode(10), default="error")                   # error | aviso | critico
    origen: Mapped[str] = mapped_column(Unicode(12), default="servidor", index=True)  # servidor | navegador | sap | sql
    mensaje: Mapped[str] = mapped_column(Unicode(400))
    traza: Mapped[str] = mapped_column(UnicodeText, default="")
    ruta: Mapped[str] = mapped_column(Unicode(200), default="")
    primera: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ultima: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    cuenta: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(Unicode(10), default="nuevo", index=True)      # nuevo | visto | resuelto
    nota: Mapped[str] = mapped_column(Unicode(400), default="")

    ocurrencias: Mapped[list["ErrorOcurrencia"]] = relationship(
        back_populates="error_ref", cascade="all, delete-orphan", order_by="ErrorOcurrencia.id.desc()")


class ErrorOcurrencia(Base):
    """Cada vez que pasó: quién, desde dónde y con qué código de petición (para cruzarlo con el log del servidor)."""
    __tablename__ = "errores_ocurrencias"
    id: Mapped[int] = mapped_column(primary_key=True)
    error_id: Mapped[int] = mapped_column(ForeignKey("errores.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    usuario: Mapped[str] = mapped_column(Unicode(40), default="")
    request_id: Mapped[str] = mapped_column(Unicode(16), default="", index=True)
    metodo: Mapped[str] = mapped_column(Unicode(8), default="")
    ruta: Mapped[str] = mapped_column(Unicode(200), default="")
    status: Mapped[int] = mapped_column(Integer, default=0)
    contexto: Mapped[str] = mapped_column(UnicodeText, default="")                      # JSON: vista, navegador, parámetros sin datos sensibles

    error_ref: Mapped[ErrorLog] = relationship(back_populates="ocurrencias")
