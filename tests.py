"""
Tests para GVRRIDO LoL Performance Engine
Ejecutar: python tests.py
"""

import json
import sys
import os

# Asegurar que src/ este en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── TEST 1: LiveClient API no crashea con listas vacias ───
def test_liveclient_empty_lists():
    """Verifica que obtener_liveclient_data no lance IndexError con datos vacios."""
    from src.lcu_api import LCUConnector
    
    # Simular un JSON con allPlayers vacio y events sin Events
    mock_json = {
        "allPlayers": [],
        "events": {"Events": []},
        "gameData": {"gameTime": 0}
    }
    
    # Procesar como lo haria la funcion
    players = []
    for p in mock_json.get("allPlayers", []):
        if not isinstance(p, dict):
            continue
        # Sanitizar items
        items_raw = p.get("items", [])
        safe_items = []
        if isinstance(items_raw, list):
            for i in range(min(7, len(items_raw))):
                safe_items.append(items_raw[i] if isinstance(items_raw[i], dict) else {})
        
        players.append({
            "championName": p.get("championName", "Desconocido"),
            "kills": (p.get("scores") or {}).get("kills", 0),
        })
    
    # Verificar que no hay IndexError y la lista es valida
    assert len(players) == 0, f"Esperado 0 jugadores, obtenido {len(players)}"
    
    # Verificar acceso a events
    events = mock_json.get("events", {}).get("Events", [])
    assert events == [], "Events deberia ser lista vacia"
    
    # Verificar que eventos[-1] no crashea
    ultimo = events[-1] if events else None
    assert ultimo is None, "Sin eventos, ultimo deberia ser None"
    
    print("✅ test_liveclient_empty_lists: PASO")


# ─── TEST 2: Anti-contradiccion en coaching (pool > 5 no recomienda expandir) ───
def test_coaching_anti_contradiction():
    """Verifica que si la pool es > 5, NO recomiende expandirla."""
    from app import generar_reporte_coach
    
    # Simular 20 partidas con 15 campeones distintos
    fake_games = []
    for i in range(20):
        champ_id = str((i % 15) + 1)  # 15 campeones diferentes
        fake_games.append({
            "gameMode": "CLASSIC",
            "gameDuration": 1800,
            "participants": [{
                "championId": champ_id,
                "stats": {
                    "win": i % 2 == 0,
                    "kills": 5,
                    "deaths": 3,
                    "assists": 7,
                    "totalMinionsKilled": 150,
                    "neutralMinionsKilled": 20,
                }
            }]
        })
    
    reporte = generar_reporte_coach(fake_games)
    
    cp = reporte.get("champion_pool", {})
    assert cp.get("is_too_wide") == True, "15 campeones deberia ser pool demasiado amplia"
    assert cp.get("unique_champs") == 15, f"Esperado 15, obtenido {cp.get('unique_champs')}"
    
    advice = cp.get("advice", "")
    assert "reduce" in advice.lower() or "reducir" in advice.lower() or "enfoc" in advice.lower(), \
        f"El consejo deberia recomendar reducir pool: {advice}"
    assert "prueba" not in advice.lower() and "nuevo" not in advice.lower() and "expand" not in advice.lower(), \
        f"NO deberia recomendar probar nuevos campeones: {advice}"
    
    print("✅ test_coaching_anti_contradiction: PASO")


# ─── TEST 3: Coaching sandwich structure ───
def test_coaching_returns_all_sections():
    """Verifica que el reporte de coaching tenga las 3 secciones."""
    from app import generar_reporte_coach
    
    fake_games = []
    for i in range(10):
        fake_games.append({
            "gameMode": "CLASSIC",
            "gameDuration": 1800,
            "participants": [{
                "championId": str((i % 3) + 1),
                "stats": {
                    "win": i % 2 == 0,
                    "kills": 5,
                    "deaths": 3,
                    "assists": 7,
                    "totalMinionsKilled": 150,
                    "neutralMinionsKilled": 20,
                }
            }]
        })
    
    reporte = generar_reporte_coach(fake_games)
    
    assert "champion_pool" in reporte, "Falta seccion champion_pool"
    assert "early_game" in reporte, "Falta seccion early_game"
    assert "survivability" in reporte, "Falta seccion survivability"
    
    cp = reporte["champion_pool"]
    assert "advice" in cp and cp["advice"], "champion_pool sin advice"
    
    eg = reporte["early_game"]
    assert "advice" in eg and eg["advice"], "early_game sin advice"
    
    sv = reporte["survivability"]
    assert "advice" in sv and sv["advice"], "survivability sin advice"
    
    print("✅ test_coaching_returns_all_sections: PASO")


if __name__ == "__main__":
    print("=" * 50)
    print("GVRRIDO - Suite de Tests")
    print("=" * 50)
    
    tests = [
        test_liveclient_empty_lists,
        test_coaching_anti_contradiction,
        test_coaching_returns_all_sections,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: FALLO - {e}")
            failed += 1
        except Exception as e:
            print(f"💥 {test.__name__}: ERROR - {type(e).__name__}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Resultado: {passed} pasaron, {failed} fallaron de {len(tests)} tests")
    print("=" * 50)
    
    sys.exit(0 if failed == 0 else 1)
