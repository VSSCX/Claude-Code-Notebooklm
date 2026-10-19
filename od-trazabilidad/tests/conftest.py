import pytest


@pytest.fixture(autouse=True)
def _sin_usuario_de_windows(monkeypatch):
    """Las pruebas no dependen de quién las ejecuta: sin nombre en la petición, el historial no lleva autor."""
    from app import usuarios
    monkeypatch.setattr(usuarios, "usuario_del_sistema", lambda: "")


@pytest.fixture(autouse=True)
def _sin_control_de_calidad_real(monkeypatch):
    """Control de calidad sale de SQL Server: las pruebas no lo consultan salvo que lo simulen."""
    from app.integrations import bases
    monkeypatch.setattr(bases, "control_calidad", lambda fresco=False: {})
