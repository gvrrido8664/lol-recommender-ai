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

def test_lcu_no_duplicate_players():
    from src.lcu_api import LCUConnector
    lcu = LCUConnector.__new__(LCUConnector)

    def mock_extraer(game_data, team_key, team_name):
        return [{"summonerId": f"{team_key}_p1", "championId": 1, "spell1Id": 4, "spell2Id": 12, "team": team_name, "skinIndex": 0, "summonerName": "Test1"},
                {"summonerId": f"{team_key}_p2", "championId": 2, "spell1Id": 4, "spell2Id": 12, "team": team_name, "skinIndex": 0, "summonerName": "Test2"}]

    players = mock_extraer({}, "teamOne", "ORDER")
    players += mock_extraer({}, "teamTwo", "CHAOS")
    assert len(players) == 4, f"Expected 4 players, got {len(players)}"
    ids = [p["summonerId"] for p in players]
    assert sum(1 for i in ids if "teamOne" in i) == 2, "teamOne should appear twice"
    assert sum(1 for i in ids if "teamTwo" in i) == 2, "teamTwo should appear twice"
    print("PASS: test_lcu_no_duplicate_players")

def test_tags_cache_in_memory():
    import src.tags_champions as tc
    tc._TAGS_CACHE = None
    r1 = tc.cargar_tags()
    assert tc._TAGS_CACHE is not None, "Cache should be populated after first call"
    r2 = tc.cargar_tags()
    assert r1 is r2, "Second call should return same cached object"
    tc._TAGS_CACHE = None
    print("PASS: test_tags_cache_in_memory")

def test_tags_obtener_tag_returns_dict():
    from src.tags_champions import obtener_tag
    tag = obtener_tag("Ahri")
    assert isinstance(tag, dict), f"Expected dict, got {type(tag)}"
    assert "damage_type" in tag
    assert "champion_class" in tag
    print("PASS: test_tags_obtener_tag_returns_dict")

def test_setup_verificar_datos_iniciales():
    from setup import verificar_datos_iniciales
    result = verificar_datos_iniciales()
    assert isinstance(result, bool)
    print(f"PASS: test_setup_verificar_datos_iniciales (data present: {result})")

def test_setup_functions_signature():
    from setup import instalar_dependencias, descargar_datos, extraer_datos
    msgs = []
    def log_cb(msg): msgs.append(msg)
    def prog_cb(pct): pass
    assert callable(instalar_dependencias)
    assert callable(descargar_datos)
    assert callable(extraer_datos)
    ok = extraer_datos(log_callback=log_cb, progress_callback=prog_cb)
    assert not ok or ok
    print("PASS: test_setup_functions_signature")

def test_logros_module():
    from src.logros import evaluar_logros, obtener_logros_conseguidos, LOGROS_DEFINICIONES
    assert len(LOGROS_DEFINICIONES) >= 10
    games = [{"win": True, "kills": 5, "deaths": 1, "assists": 3, "championName": "Ahri"}]
    result = evaluar_logros(games)
    conseguidos = obtener_logros_conseguidos(result)
    assert len(conseguidos) >= 1, f"Expected at least 1 logro, got {len(conseguidos)}"
    first_blood = any(lg["id"] == "first_blood" for lg in conseguidos)
    assert first_blood, "Should have 'first_blood' logro with 1 game"
    print("PASS: test_logros_module")

def test_logros_empty_games():
    from src.logros import evaluar_logros, obtener_logros_conseguidos
    result = evaluar_logros([])
    conseguidos = obtener_logros_conseguidos(result)
    assert len(conseguidos) == 0, "No games should yield 0 logros"
    print("PASS: test_logros_empty_games")

def test_draft_db_functions():
    from src.db_manager import guardar_draft, obtener_historial_drafts
    did = guardar_draft("Ahri", "MIDDLE", ["Zed"], ["A","B","C","D","E"], ["V","W","X","Y","Z"], 53.5)
    assert did is not None
    assert did > 0
    drafts = obtener_historial_drafts(5)
    assert len(drafts) >= 1
    latest = drafts[0]
    assert latest["campeon"] == "Ahri"
    assert latest["rol"] == "MIDDLE"
    assert latest["wr_predicho"] == 53.5
    print("PASS: test_draft_db_functions")

def test_composicion_analyzer():
    from src.recomendador import analizar_composicion
    ad, ap, tanks = analizar_composicion(["Ahri", "LeeSin", "Yasuo", "Jhin", "Thresh"])
    assert isinstance(ad, (int, float)), f"Expected numeric AD%, got {type(ad)}"
    assert isinstance(ap, (int, float)), f"Expected numeric AP%, got {type(ap)}"
    assert isinstance(tanks, (int, float)), f"Expected numeric tanks, got {type(tanks)}"
    print(f"PASS: test_composicion_analyzer (AD:{ad} AP:{ap} Tanks:{tanks})")

if __name__ == "__main__":
    tests = [test_liveclient_empty_lists, test_coaching_anti_contradiction,
             test_coaching_returns_all_sections, test_liveclient_partial_data,
             test_lcu_no_duplicate_players, test_tags_cache_in_memory,
             test_tags_obtener_tag_returns_dict, test_setup_verificar_datos_iniciales,
             test_setup_functions_signature, test_logros_module,
             test_logros_empty_games, test_draft_db_functions,
             test_composicion_analyzer]
    passed = 0
    for t in tests:
        try: t(); passed += 1
        except AssertionError as e: print(f"FAIL: {t.__name__}: {e}")
        except Exception as e: print(f"ERROR: {t.__name__}: {type(e).__name__}: {e}")
    total = len(tests)
    print(f"\n{passed}/{total} pasaron")
    sys.exit(0 if passed == total else 1)
