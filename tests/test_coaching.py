from src.coach import generar_reporte_coach


def _fake_games(n=20, champion_ids=None):
    if champion_ids is None:
        champion_ids = [str((i % 15) + 1) for i in range(n)]
    games = []
    for i in range(n):
        games.append({
            "gameId": str(i),
            "gameMode": "CLASSIC",
            "gameDuration": 1800,
            "gameCreation": 1781139650.0 + i * 86400,
            "participants": [{
                "championId": int(champion_ids[i]),
                "teamPosition": "TOP",
                "stats": {
                    "win": i % 2 == 0,
                    "kills": 5,
                    "deaths": 3,
                    "assists": 7,
                    "totalMinionsKilled": 150,
                    "neutralMinionsKilled": 20,
                    "totalDamageDealtToChampions": 20000,
                    "totalDamageTaken": 18000,
                    "goldEarned": 11000,
                    "visionScore": 20,
                    "visionWardsBoughtInGame": 1,
                }
            }]
        })
    return games


def test_contract_keys():
    r = generar_reporte_coach(_fake_games(20))
    assert "secciones" in r
    assert "resumen" in r
    assert "consejo_final" in r
    assert "nivel" in r
    assert "metricas" in r


def test_sections_well_formed():
    r = generar_reporte_coach(_fake_games(20))
    assert len(r["secciones"]) >= 1
    for sec in r["secciones"]:
        assert "titulo" in sec
        assert "html" in sec
        assert isinstance(sec["titulo"], str)
        assert isinstance(sec["html"], str)
        assert len(sec["titulo"]) > 0
        assert len(sec["html"]) > 0


def test_empty_history():
    r = generar_reporte_coach([])
    assert r["secciones"] == []
    assert "Necesito al menos 3 partidas" in r["resumen"]


def test_small_history():
    r = generar_reporte_coach(_fake_games(2))
    assert r["secciones"] == []
    assert "Necesito al menos 3 partidas" in r["resumen"]


def test_anti_contradiction_wide_pool():
    many_ids = [str(i + 1) for i in range(12)] * 2
    r = generar_reporte_coach(_fake_games(24, champion_ids=many_ids[:24]))
    html_full = ""
    for sec in r["secciones"]:
        html_full += sec["html"]
    assert "demasiados" in html_full.lower() or "enfoc" in html_full.lower() or "reduc" in html_full.lower() or "2 campeones" in html_full.lower()


def test_anti_contradiction_narrow_pool():
    few_ids = ["266", "266", "266", "266", "266", "266", "103", "103", "103", "103",
               "103", "103", "103", "84", "84", "84", "84", "84", "84", "84"]
    r = generar_reporte_coach(_fake_games(20, champion_ids=few_ids))
    html_full = ""
    for sec in r["secciones"]:
        html_full += sec["html"]
    assert "demasiados" not in html_full.lower()


def test_metrics_valid():
    r = generar_reporte_coach(_fake_games(20))
    m = r["metricas"]
    assert 0 <= m["wr"] <= 100
    assert m["avg_cs"] >= 0
    assert m["unique_champs"] >= 1


def test_generates_multiple_sections():
    r = generar_reporte_coach(_fake_games(20))
    assert len(r["secciones"]) >= 3
