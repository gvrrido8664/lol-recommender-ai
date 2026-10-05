from src import recomendador
from src.db_manager import ConexionDBError

def test_role_pool_without_database(monkeypatch):
    def unavailable():
        raise ConexionDBError('No database configured')
    recomendador.invalidar_cache_campeones_por_rol()
    monkeypatch.setattr(recomendador,'obtener_conexion',unavailable)
    assert recomendador.obtener_campeones_por_rol('TOP') == []
