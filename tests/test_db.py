"""Tests de funciones de BD contra mock_db (SQLite con adaptador).

Verifica que el adaptador %s→? funciona y que las funciones
guardar_draft, completar_draft_resultado, registrar_lp, obtener_historial_lp
operan correctamente sin PostgreSQL real.
"""

import pytest


@pytest.mark.usefixtures("mock_db")
class TestDraftsDB:
    def test_guardar_draft_retorna_id(self):
        from src.db_manager import guardar_draft

        did = guardar_draft("Ahri", "MIDDLE", ["Zed"], ["LeeSin"], ["Yasuo"], 53.5)
        assert did is not None
        assert did > 0

    def test_guardar_y_obtener_historial(self):
        from src.db_manager import guardar_draft, obtener_historial_drafts

        guardar_draft("Ahri", "MIDDLE", ["Zed"], ["LeeSin"], ["Yasuo"], 53.5)
        drafts = obtener_historial_drafts(5)
        assert len(drafts) >= 1
        assert drafts[0]["campeon"] == "Ahri"
        assert drafts[0]["rol"] == "MIDDLE"
        assert drafts[0]["wr_predicho"] == 53.5

    def test_completar_draft_resultado_con_ganada(self):
        from src.db_manager import guardar_draft, completar_draft_resultado, obtener_historial_drafts

        did = guardar_draft("Ahri", "MIDDLE", [], [], [], 50.0)
        completar_draft_resultado(did, True)
        drafts = obtener_historial_drafts(1)
        assert drafts[0]["resultado"] == "victoria"
        assert drafts[0]["ganada"] == 1

    def test_completar_draft_sin_ganada(self):
        from src.db_manager import guardar_draft, completar_draft_resultado, obtener_historial_drafts

        did = guardar_draft("Zed", "MIDDLE", [], [], [], 48.0)
        completar_draft_resultado(did, None)
        drafts = obtener_historial_drafts(1)
        assert drafts[0]["resultado"] == "completada"

    def test_historial_respeta_limite(self):
        from src.db_manager import guardar_draft, obtener_historial_drafts

        for i in range(5):
            guardar_draft(f"Champ{i}", "TOP", [], [], [], 50.0)
        drafts = obtener_historial_drafts(3)
        assert len(drafts) == 3


@pytest.mark.usefixtures("mock_db")
class TestLPDB:
    def test_registrar_lp_unranked_skipped(self):
        from src.db_manager import registrar_lp

        registrar_lp("UNRANKED", "I", 0)
        # No deberia crashear ni insertar nada

    def test_registrar_y_obtener_lp(self):
        from src.db_manager import registrar_lp, obtener_historial_lp

        registrar_lp("GOLD", "II", 75, 10, 8)
        historial = obtener_historial_lp()
        assert len(historial) >= 1
        assert historial[0]["tier"] == "GOLD"
        assert historial[0]["lp"] == 75

    def test_lp_total_calculation(self):
        from src.db_manager import registrar_lp, obtener_historial_lp

        registrar_lp("SILVER", "III", 50, 5, 5)
        historial = obtener_historial_lp()
        assert len(historial) >= 1
        assert historial[0]["lp_total"] > 0
        # Silver III = 800 base + 1*100 (div bonus) + 50 lp = 950 aprox
        assert 900 <= historial[0]["lp_total"] <= 1000


@pytest.mark.usefixtures("mock_db")
class TestEmocionalDB:
    def test_etiquetar_y_obtener_estado(self):
        from src.db_manager import etiquetar_estado_emocional, obtener_estado_emocional

        etiquetar_estado_emocional("LA2_12345", "Concentrado", "test-puuid", "Ahri")
        estado = obtener_estado_emocional("LA2_12345")
        assert estado == "Concentrado"

    def test_obtener_estado_inexistente(self):
        from src.db_manager import obtener_estado_emocional

        estado = obtener_estado_emocional("NO_EXISTE")
        assert estado is None
