from src.recomendador import analizar_composicion


def test_ad_heavy_composition():
    pct_ad, pct_ap, tanks = analizar_composicion(["Aatrox", "Darius", "Garen", "Renekton", "Sett"])
    assert pct_ad > pct_ap
    assert tanks >= 0


def test_ap_heavy_composition():
    pct_ad, pct_ap, tanks = analizar_composicion(["Ahri", "Lux", "Orianna", "Syndra", "Zoe"])
    assert pct_ap > pct_ad


def test_rounding_consistency():
    pct_ad, pct_ap, tanks = analizar_composicion(["Aatrox", "Darius", "Ahri"])
    assert pct_ad + pct_ap >= 99
    assert abs(pct_ad + pct_ap - 100) <= 1


def test_empty_list():
    pct_ad, pct_ap, tanks = analizar_composicion([])
    assert pct_ad == 50
    assert pct_ap == 50
    assert isinstance(tanks, int)


def test_unknown_champion_no_crash():
    pct_ad, pct_ap, tanks = analizar_composicion(["ChampQueNoExiste12345", "Aatrox"])
    assert isinstance(pct_ad, int)
    assert isinstance(pct_ap, int)


def test_hybrid_champion():
    pct_ad, pct_ap, tanks = analizar_composicion(["Jax"])
    assert pct_ad >= 0
    assert pct_ap >= 0


def test_tank_detection():
    pct_ad, pct_ap, tanks = analizar_composicion(["Malphite", "Ornn", "Sion", "Ahri", "Lux"])
    assert tanks >= 2
