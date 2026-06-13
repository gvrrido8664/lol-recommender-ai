"""
Diagnóstico de la base de datos local de NEXUS Recommender.
Uso: python -m src.estado_db
"""
import json

from .db_manager import obtener_conexion


def _barra(valor: int, maximo: int, ancho: int = 20) -> str:
    filled = int(ancho * min(valor / max(maximo, 1), 1.0))
    return "█" * filled + "░" * (ancho - filled)


def _pct_icon(pct: float) -> str:
    return "✅" if pct >= 85 else "⚠️ " if pct >= 60 else "❌"


def _fetchone(col: int = 0):
    """Devuelve una función que ejecuta SQL y retorna el valor de una columna."""
    def _inner(cur, sql, params=None):
        cur.execute(sql, params)
        return cur.fetchone()[col]
    return _inner


def _fetchval(sql, cur, col=0):
    cur.execute(sql)
    return cur.fetchone()[col]


def generar_reporte_completo():
    CHAMP_COUNT = len(json.load(open("data/champ_ids.json", encoding="utf-8")))
    conn = obtener_conexion()
    cur = conn.cursor()

    SEP = "═" * 60
    print(f"\n{SEP}")
    print("  📊 ESTADO DE LA BD — NEXUS RECOMMENDER")
    print(SEP)

    # ── 1. RESUMEN GENERAL ──────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM matches")
    total_matches = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM participantes")
    total_parts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT champion) FROM participantes")
    total_champs = cur.fetchone()[0]
    cur.execute("SELECT pg_database_size(current_database())")
    db_mb = cur.fetchone()[0] / (1024 * 1024)

    print(f"\n💾 RESUMEN GENERAL")
    print(f"  Tamaño  : {db_mb:.1f} MB")
    print(f"  Partidas: {total_matches:,}  |  Registros: {total_parts:,}  |  Campeones: {total_champs}/{CHAMP_COUNT}")

    # ── 2. DISTRIBUCIÓN POR PARCHE ──────────────────────────────
    cur.execute("""
        SELECT m.patch, COUNT(p.id) as n
        FROM matches m
        LEFT JOIN participantes p ON m.match_id = p.match_id
        WHERE m.patch IS NOT NULL AND m.patch != ''
        GROUP BY m.patch
        ORDER BY n DESC
        LIMIT 6
    """)
    parches = cur.fetchall()

    if parches:
        print(f"\n📦 DISTRIBUCIÓN POR PARCHE")
        max_p = parches[0]["n"] if parches else 1
        for row in parches:
            pct = row["n"] / max(total_parts, 1) * 100
            bar = _barra(row["n"], max_p)
            print(f"  {row['patch']:8}  {row['n']:6,} regs ({pct:5.1f}%)  |{bar}|")

    # ── 3. CALIDAD DE DATOS ─────────────────────────────────────
    cur.execute(
        "SELECT COUNT(*) FROM participantes "
        "WHERE items IS NOT NULL AND items != '' AND items != '0,0,0,0,0,0,0'"
    )
    con_items = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM participantes "
        "WHERE runes IS NOT NULL AND runes != '' AND runes != 'null'"
    )
    con_runes = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM participantes "
        "WHERE spells IS NOT NULL AND spells != '' AND spells != 'null'"
    )
    con_spells = cur.fetchone()[0]
    cur.execute("SELECT ROUND(AVG(win) * 100, 1) FROM participantes")
    avg_wr = float(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM matches WHERE game_duration > 1500")
    largas = cur.fetchone()[0]

    pi = con_items  / max(total_parts, 1) * 100
    pr = con_runes  / max(total_parts, 1) * 100
    ps = con_spells / max(total_parts, 1) * 100
    pl = largas     / max(total_matches, 1) * 100
    wr_ok = "✅" if 45 <= avg_wr <= 55 else "⚠️ "

    print(f"\n🎯 CALIDAD DE DATOS")
    print(f"  Ítems registrados   : {pi:5.1f}%  {_pct_icon(pi)}  ({con_items:,} registros)")
    print(f"  Runas registradas   : {pr:5.1f}%  {_pct_icon(pr)}")
    print(f"  Hechizos registrados: {ps:5.1f}%  {_pct_icon(ps)}")
    print(f"  Win rate promedio   : {avg_wr}%  {wr_ok}  (sanity: debe ser ~50%)")
    print(f"  Partidas >25 min    : {pl:5.1f}%  {_pct_icon(pl)}  ({largas:,} builds de 6 ítems)")

    # ── 4. COBERTURA POR POSICIÓN ───────────────────────────────
    cur.execute("""
        SELECT team_position, COUNT(*) as n
        FROM participantes
        WHERE team_position != ''
        GROUP BY team_position
        ORDER BY n DESC
    """)
    posiciones = cur.fetchall()

    if posiciones:
        print(f"\n📍 COBERTURA POR POSICIÓN")
        max_pos = max(r["n"] for r in posiciones)
        for row in posiciones:
            bar = _barra(row["n"], max_pos)
            print(f"  {row['team_position']:8}  {row['n']:6,}  |{bar}|")

    # ── 5. READINESS DEL RECOMENDADOR ──────────────────────────
    cur.execute("""
        SELECT champion, COUNT(*) as n, ROUND(AVG(win)*100, 1) as wr
        FROM participantes
        GROUP BY champion
        ORDER BY n DESC
    """)
    readiness = cur.fetchall()

    excelente = sum(1 for r in readiness if r["n"] >= 100)
    bueno     = sum(1 for r in readiness if 50 <= r["n"] < 100)
    basico    = sum(1 for r in readiness if 20 <= r["n"] < 50)
    insuf     = max(0, CHAMP_COUNT - excelente - bueno - basico)

    print(f"\n🤖 RECOMENDADOR — READINESS ({total_champs}/{CHAMP_COUNT} campeones con datos)")
    print(f"  🟢 Excelente  (100+ partidas): {excelente:3} campeones")
    print(f"  🟡 Bueno      (50–99)        : {bueno:3} campeones")
    print(f"  🟠 Básico     (20–49)        : {basico:3} campeones")
    print(f"  🔴 Insuficiente (<20/sin data): {insuf:3} campeones")

    if readiness:
        print(f"\n  TOP 10 MEJOR CUBIERTOS:")
        top_n = readiness[0]["n"]
        for i, r in enumerate(readiness[:10], 1):
            bar = _barra(r["n"], top_n, 15)
            print(f"  {i:2}. {r['champion']:14}  {r['n']:4} partidas  WR: {r['wr']:5.1f}%  |{bar}|")

    # ── 6. CAMPEONES CON DATOS INSUFICIENTES ────────────────────
    pocos = [r for r in readiness if r["n"] < 20]
    if pocos:
        nombres = ", ".join(r["champion"] for r in pocos[:20])
        extra   = f" (+{len(pocos) - 20} más)" if len(pocos) > 20 else ""
        print(f"\n⚠️  CAMPEONES CON <20 PARTIDAS: {len(pocos)}")
        print(f"  {nombres}{extra}")

    # ── 7. ESTADO EMOCIONAL (si hay datos) ─────────────────────
    try:
        cur.execute("""
            SELECT estado, COUNT(*) as n
            FROM estado_emocional
            GROUP BY estado
            ORDER BY n DESC
        """)
        emocional = cur.fetchall()
        total_em = sum(r["n"] for r in emocional)
        if total_em > 0:
            print(f"\n🧠 ESTADO EMOCIONAL ({total_em} registros)")
            for row in emocional:
                pct = row["n"] / total_em * 100
                bar = _barra(row["n"], emocional[0]["n"])
                print(f"  {row['estado']:12}  {row['n']:4}  ({pct:4.1f}%)  |{bar}|")
    except Exception:
        pass

    print(f"\n{SEP}\n")
    conn.close()


if __name__ == "__main__":
    generar_reporte_completo()
