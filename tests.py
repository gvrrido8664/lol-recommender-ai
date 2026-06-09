import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_liveclient_empty_lists():
    from src.lcu_api import LCUConnector
    mock = {"allPlayers": [], "events": {"Events": []}, "gameData": {"gameTime": 0}}
    players = []
    for p in mock.get("allPlayers", []):
        if not isinstance(p, dict): continue
        items_raw = p.get("items", [])
        safe_items = []
        if isinstance(items_raw, list):
            for i in range(min(7, len(items_raw))):
                safe_items.append(items_raw[i] if isinstance(items_raw[i], dict) else {})
        players.append({"championName": p.get("championName", "unknown")})
    assert len(players) == 0
    events = mock.get("events", {}).get("Events", [])
    assert events == []
    assert (events[-1] if events else None) is None
    print("PASS: test_liveclient_empty_lists")

def test_coaching_anti_contradiction():
    from app import generar_reporte_coach
    fake = []
    for i in range(20):
        fake.append({"gameMode": "CLASSIC", "gameDuration": 1800,
            "participants": [{"championId": str((i%15)+1), "stats": {"win": i%2==0, "kills":5, "deaths":3, "assists":7, "totalMinionsKilled":150, "neutralMinionsKilled":20}}]})
    r = generar_reporte_coach(fake)
    sects = r.get("secciones", [])
    assert len(sects) >= 1
    cp = ""
    for sec in sects:
        if "CHAMPION" in sec.get("titulo", "").upper(): cp = sec.get("html", ""); break
    assert cp
    assert "15" in cp or "demasiados" in cp.lower()
    assert "reduce" in cp.lower() or "reducir" in cp.lower() or "enfoc" in cp.lower()
    print("PASS: test_coaching_anti_contradiction")

def test_coaching_returns_all_sections():
    from app import generar_reporte_coach
    fake = []
    for i in range(10):
        fake.append({"gameMode": "CLASSIC", "gameDuration": 1800,
            "participants": [{"championId": str((i%3)+1), "stats": {"win": i%2==0, "kills":5, "deaths":3, "assists":7, "totalMinionsKilled":150, "neutralMinionsKilled":20}}]})
    r = generar_reporte_coach(fake)
    for k in ("secciones", "resumen", "consejo_final"):
        assert k in r, f"Missing key: {k}"
    for sec in r["secciones"]:
        assert "titulo" in sec and "html" in sec
    print("PASS: test_coaching_returns_all_sections")

def test_liveclient_partial_data():
    mock = {"allPlayers": [{"championName":"Aatrox","team":"ORDER"}, {"championName":"Zed","team":"CHAOS","scores":{"kills":5}}, {}, None], "gameData": {"gameTime": 300}}
    players = []
    for p in mock.get("allPlayers", []):
        if not isinstance(p, dict) or not p: continue
        team_raw = p.get("team", "")
        team = "ORDER" if isinstance(team_raw, str) and team_raw.upper() in ("ORDER","BLUE") else "CHAOS"
        scores = p.get("scores") or {}
        players.append({"championName": p.get("championName",""), "kills": scores.get("kills",0)})
    assert len(players) == 2
    assert players[0]["championName"] == "Aatrox"
    assert players[1]["kills"] == 5
    print("PASS: test_liveclient_partial_data")

if __name__ == "__main__":
    tests = [test_liveclient_empty_lists, test_coaching_anti_contradiction,
             test_coaching_returns_all_sections, test_liveclient_partial_data]
    passed = 0
    for t in tests:
        try: t(); passed += 1
        except AssertionError as e: print(f"FAIL: {t.__name__}: {e}")
        except Exception as e: print(f"ERROR: {t.__name__}: {type(e).__name__}: {e}")
    total = len(tests)
    print(f"\n{passed}/{total} pasaron")
    sys.exit(0 if passed == total else 1)
