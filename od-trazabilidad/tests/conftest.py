import pytest


@pytest.fixture(autouse=True)
def _sin_usuario_de_windows(monkeypatch):
    """Las pruebas no dependen de quién las ejecuta: sin nombre en la petición, el historial no lleva autor."""
    from app import usuarios
    monkeypatch.setattr(usuarios, "usuario_del_sistema", lambda: "")
