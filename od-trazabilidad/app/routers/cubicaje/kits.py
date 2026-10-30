"""Listado de kits: carga desde Excel, plantilla y borrado."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ...db import get_session
from ._comun import _commit

router = APIRouter()


@router.get("/kits")
def get_kits(buscar: str = "", limite: int = 100, s: Session = Depends(get_session)):
    from ...integrations import kits as kits_mod
    return kits_mod.listar(s, buscar, limite)


@router.post("/kits/importar")
def importar_kits(file: UploadFile = File(...), s: Session = Depends(get_session)):
    """Carga masiva del listado de kits (una fila por componente): agrega los nuevos y reemplaza los que vienen."""
    from ...integrations import kits as kits_mod
    if Path(file.filename or "").suffix.lower() not in (".xlsx", ".xlsm"):
        raise HTTPException(422, "El archivo debe ser .xlsx")
    try:
        filas = kits_mod.leer_archivo(file.file)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"No se pudo leer el archivo: {str(e)[:200]}") from e
    if not filas:
        raise HTTPException(422, "No se encontraron filas: usa la plantilla (columnas Kit código SAP, "
                                 "Descripción del kit, Componente código SAP, Cantidad por kit).")
    r = kits_mod.importar(s, filas)
    _commit(s)
    return {**r.__dict__, "problemas": r.problemas[:20], **kits_mod.listar(s, "", 100)}


@router.get("/kits/plantilla")
def plantilla_kits():
    from io import BytesIO

    from fastapi.responses import StreamingResponse

    from ...integrations import kits as kits_mod
    return StreamingResponse(BytesIO(kits_mod.plantilla()),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="Plantilla_Kits.xlsx"'})


@router.delete("/kits/{sku}")
def borrar_kit(sku: str, s: Session = Depends(get_session)):
    from ...integrations import kits as kits_mod
    if not kits_mod.borrar(s, sku):
        raise HTTPException(404, "Ese kit no existe.")
    _commit(s)
    return {"ok": True}
