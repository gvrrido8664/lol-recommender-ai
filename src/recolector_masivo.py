"""
LOLLECT v2 — Motor de Recolección Masiva de Partidas de LoL
═══════════════════════════════════════════════════════════════
Producción-grade. Construido para ser rápido, resiliente y observable.

Características:
  • Rate limiter adaptativo con token bucket + backoff exponencial
  • Descarga paralela de partidas (ThreadPool + batch processing)
  • Persistencia de cola en SQLite (resume automático tras reinicio)
  • Barra de progreso enriquecida con ETA, RPM, throughput
  • Muestreo inteligente multi-MMR (Challenger → Diamond)
  • Stats en tiempo real: partidas/min, rate limits, errores, cobertura
  • Checkpoint automático cada N partidas

Uso:
  python -m src.recolector_masivo          # default: meta=20000
  python -m src.recolector_masivo 50000    # meta personalizada
  python -m src.recolector_masivo --reset  # reiniciar cola y DB
"""
import requests
import time
import random
import json
import os
import sys
import sqlite3
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from contextlib import contextmanager

from .db_manager import obtener_conexion, inicializar_db, DATA_DIR
from .riot_api import cargar_objetos

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

def _cargar_config():
    try:
        config_paths = ["config.json", os.path.join("..", "config.json")]
        for p in config_paths:
            if os.path.exists(p):
                with open(p, "r") as f: return json.load(f)
    except: pass
    return {}

CONFIG = _cargar_config()
API_KEY = CONFIG.get("API_KEY", os.environ.get("RIOT_API_KEY", ""))
REGION_ROUTING = "americas"
PLATFORMS = ["la2", "la1", "na1", "br1"]
HEADERS = {"X-Riot-Token": API_KEY}
ITEMS_DATA = cargar_objetos()
ITEMS_SUPP_FINAL = {"3866", "3867", "3869", "3870", "3871", "3873", "3874"}
COLA_DB_PATH = os.path.join(DATA_DIR, "cola_exploracion.db")

PARCHE_ACTUAL = "0.0"
VERSION_COMPLETA = "0.0.0"

MAX_WORKERS = 5
BATCH_SIZE = 10
CHECKPOINT_EVERY = 500
RATE_LIMIT_RPS = 18

# ═══════════════════════════════════════════════════════════════
# TOKEN BUCKET RATE LIMITER
# ═══════════════════════════════════════════════════════════════

class TokenBucket:
    def __init__(self, rate: float, burst: int = 5):
        self.rate = rate; self.burst = burst
        self.tokens = float(burst); self.last_refill = time.monotonic()
        self.lock = threading.Lock()
    def acquire(self):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.burst, self.tokens + (now - self.last_refill) * self.rate)
            self.last_refill = now
            if self.tokens < 1:
                time.sleep((1 - self.tokens) / self.rate)
                self.tokens = 0
            else: self.tokens -= 1

RATE_LIMITER = TokenBucket(RATE_LIMIT_RPS)

# ═══════════════════════════════════════════════════════════════
# COLA PERSISTENTE
# ═══════════════════════════════════════════════════════════════

class ColaPersistente:
    def __init__(self, path=COLA_DB_PATH):
        self.path = path; self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock(); self._init_db()
    def _init_db(self):
        with self.lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS cola(puuid TEXT PRIMARY KEY, fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP, procesado INTEGER DEFAULT 0)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), total_descargadas INTEGER DEFAULT 0, total_errores INTEGER DEFAULT 0, fecha_checkpoint TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            if not self.conn.execute("SELECT 1 FROM checkpoint").fetchone():
                self.conn.execute("INSERT INTO checkpoint(id,total_descargadas,total_errores) VALUES(1,0,0)")
            self.conn.commit()
    def push(self, puuid: str):
        with self.lock:
            try: self.conn.execute("INSERT OR IGNORE INTO cola(puuid) VALUES(?)", (puuid,)); self.conn.commit()
            except: pass
    def pop(self) -> str | None:
        with self.lock:
            row = self.conn.execute("SELECT puuid FROM cola WHERE procesado=0 ORDER BY fecha_agregado LIMIT 1").fetchone()
            if row: self.conn.execute("UPDATE cola SET procesado=1 WHERE puuid=?", (row[0],)); self.conn.commit(); return row[0]
        return None
    def size(self) -> int:
        with self.lock: return self.conn.execute("SELECT COUNT(*) FROM cola WHERE procesado=0").fetchone()[0]
    def checkpoint(self, descargadas: int, errores: int):
        with self.lock: self.conn.execute("UPDATE checkpoint SET total_descargadas=?, total_errores=?, fecha_checkpoint=CURRENT_TIMESTAMP WHERE id=1", (descargadas, errores)); self.conn.commit()
    def get_checkpoint(self) -> tuple:
        with self.lock:
            row = self.conn.execute("SELECT total_descargadas, total_errores FROM checkpoint").fetchone()
            return (row[0], row[1]) if row else (0, 0)
    def stats(self) -> dict:
        with self.lock:
            total = self.conn.execute("SELECT COUNT(*) FROM cola").fetchone()[0]
            pendientes = self.conn.execute("SELECT COUNT(*) FROM cola WHERE procesado=0").fetchone()[0]
            return {"total": total, "pendientes": pendientes, "procesados": total - pendientes}
    def close(self): self.conn.close()

# ═══════════════════════════════════════════════════════════════
# DASHBOARD DE MÉTRICAS
# ═══════════════════════════════════════════════════════════════

class Dashboard:
    def __init__(self):
        self.lock = threading.Lock(); self.start_time = time.monotonic()
        self.matches = 0; self.errors = 0; self.rate_limits = 0; self.bytes_down = 0
        self.last_n_matches = []; self.champions_seen = set(); self.match_ids_seen = set()
    def add_match(self, match_id: str, champions: list, size_bytes: int = 0):
        with self.lock:
            self.matches += 1
            self.bytes_down += size_bytes
            self.last_n_matches.append(time.monotonic())
            if len(self.last_n_matches) > 100:
                self.last_n_matches.pop(0)
            for c in champions:
                self.champions_seen.add(c)
            self.match_ids_seen.add(match_id)

    def add_error(self):
        with self.lock:
            self.errors += 1

    def add_rate_limit(self):
        with self.lock:
            self.rate_limits += 1
    def snapshot(self) -> dict:
        with self.lock:
            elapsed = max(time.monotonic() - self.start_time, 1)
            rpm = len(self.last_n_matches) / min(elapsed / 60, 5) if self.last_n_matches else 0
            return {"matches": self.matches, "errors": self.errors, "rate_limits": self.rate_limits,
                    "rpm": round(rpm, 1), "elapsed": str(timedelta(seconds=int(elapsed))),
                    "champions": len(self.champions_seen), "bytes_mb": round(self.bytes_down / (1024*1024), 1)}

DASH = Dashboard()

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def obtener_version_riot() -> tuple:
    try:
        resp = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=5)
        v = resp.json()[0]; parts = v.split(".")
        return (".".join(parts[:2]), v)
    except: return ("14.10", "14.10.1")

def es_bota(item_id: str) -> bool:
    data = ITEMS_DATA.get(item_id, {})
    tags = data.get("tags", [])
    if not tags or "Consumable" in tags or "Vision" in tags or "Trinket" in tags: return False
    return "Boots" in tags

def es_item_supp_final(item_id: str) -> bool:
    return item_id in ITEMS_SUPP_FINAL

def peticion_segura(url: str) -> dict | None:
    for intento in range(4):
        try:
            RATE_LIMITER.acquire()
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200: return resp.json()
            if resp.status_code == 429:
                espera = int(resp.headers.get("Retry-After", 2 ** intento + 1))
                DASH.add_rate_limit(); time.sleep(espera); continue
            if resp.status_code in (500, 502, 503, 504): time.sleep(2 ** intento); continue
            return None
        except: time.sleep(1 + intento); continue
    DASH.add_error(); return None

def sembrar_desde_high_elo(cola: ColaPersistente, jugadores_max: int = 200) -> int:
    ligas = {"CHALLENGER": "challengerleagues", "GRANDMASTER": "grandmasterleagues", "MASTER": "masterleagues"}
    agregados = 0
    for platform in PLATFORMS:
        if agregados >= jugadores_max: break
        for nombre_liga, endpoint in ligas.items():
            if agregados >= jugadores_max: break
            print(f"  🏆 {platform.upper()} {nombre_liga}...", end=" ", flush=True)
            url = f"https://{platform}.api.riotgames.com/lol/league/v4/{endpoint}/by-queue/RANKED_SOLO_5x5"
            datos = peticion_segura(url)
            if not datos or "entries" not in datos: print("❌"); continue
            entradas = random.sample(datos["entries"], min(15, len(datos["entries"])))
            n = 0
            for e in entradas:
                if e.get("puuid"): cola.push(e["puuid"]); n += 1; agregados += 1
            print(f"+{n} jugadores")
    return agregados

@contextmanager
def transaction(conn):
    try: yield; conn.commit()
    except: conn.rollback(); raise

# ═══════════════════════════════════════════════════════════════
# PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

def procesar_jugador(puuid: str) -> list:
    url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count=50"
    match_ids = peticion_segura(url)
    return match_ids if match_ids else []

def descargar_partida(match_id: str) -> bool:
    """Descarga una partida y la guarda en BD. Cada hilo usa su propia conexión."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM matches WHERE match_id=?", (match_id,))
        if cur.fetchone(): return False

        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        data = peticion_segura(url)
        if not data or "info" not in data: return False
        info = data["info"]
        if info.get("gameDuration", 0) < 600: return False

        version = info.get("gameVersion", "0")
        parts = version.split(".")
        patch = ".".join(parts[:2]) if len(parts) >= 2 else "0.0"
        if patch != PARCHE_ACTUAL: return False

        url_tl = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        timeline = peticion_segura(url_tl)
        boots_map, supp_map = {}, {}
        if timeline and "info" in timeline:
            for frame in timeline["info"].get("frames", []):
                for ev in frame.get("events", []):
                    if ev.get("type") != "ITEM_PURCHASED": continue
                    pid = ev.get("participantId"); iid = str(ev.get("itemId", 0))
                    if not pid or iid == "0": continue
                    if es_bota(iid): boots_map[pid] = iid
                    elif es_item_supp_final(iid): supp_map[pid] = iid

        champions = []
        with transaction(conn):
            cur.execute("INSERT INTO matches(match_id,game_version,game_duration,patch) VALUES(?,?,?,?)",
                        (match_id, version, info.get("gameDuration", 0), patch))
            for p in info.get("participants", []):
                raw = p.get("championName")
                champ = raw if raw != "MonkeyKing" else "Wukong"
                champions.append(champ)

                items = [str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0]
                pid_p = p.get("participantId"); pos = p.get("teamPosition", "")
                if pid_p in boots_map and not any(es_bota(i) for i in items): items.append(boots_map[pid_p])
                if pos == "UTILITY" and pid_p in supp_map and not any(es_item_supp_final(i) for i in items): items.append(supp_map[pid_p])

                styles = p.get("perks", {}).get("styles", [])
                runas = []
                for s in styles:
                    runas.append(str(s.get("style")))
                    for sel in s.get("selections", []): runas.append(str(sel.get("perk")))
                sp = p.get("perks", {}).get("statPerks", {})
                if sp:
                    for k in ("defense", "flex", "offense"): runas.append(str(sp.get(k, "")))
                runas_str = ",".join(r for r in runas if r)
                spells = f"{p.get('summoner1Id',0)},{p.get('summoner2Id',0)}"

                cur.execute("""INSERT INTO participantes(match_id,champion,team_position,team,win,items,runes,spells,kills,deaths,assists)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                            (match_id, champ, pos, p.get("teamId", 0), 1 if p.get("win") else 0,
                             ",".join(items), runas_str, spells, p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)))
        DASH.add_match(match_id, champions, len(json.dumps(data)))
        return True
    except Exception:
        return False
    finally:
        conn.close()

def descargar_lote(match_ids: list) -> int:
    descargadas = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(descargar_partida, mid): mid for mid in match_ids}
        for future in as_completed(futures):
            try:
                if future.result(): descargadas += 1
            except: DASH.add_error()
    return descargadas

def _progress_bar(current: int, total: int, s: dict, width: int = 40) -> str:
    pct = min(current / max(total, 1), 1.0)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return (f"\r📦 [{bar}] {current}/{total} | ⏱️ {s['elapsed']} | 📊 {s['rpm']} rpm | "
            f"👤 {s['champions']} champs | ❌ {s['errors']} err")

# ═══════════════════════════════════════════════════════════════
# ORQUESTADOR
# ═══════════════════════════════════════════════════════════════

def ejecutar_recoleccion_masiva(meta: int = 20000, reset: bool = False):
    global PARCHE_ACTUAL, VERSION_COMPLETA

    print("\n" + "═" * 55)
    print("  🚀 LOLLECT v2 — Motor de Recolección Masiva")
    print("═" * 55)

    PARCHE_ACTUAL, VERSION_COMPLETA = obtener_version_riot()
    print(f"  📅 Parche activo: {PARCHE_ACTUAL} ({VERSION_COMPLETA})")
    print(f"  🎯 Meta: {meta:,} partidas  |  🧵 Workers: {MAX_WORKERS}  |  📦 Batch: {BATCH_SIZE}")
    print(f"  💾 Checkpoint: cada {CHECKPOINT_EVERY} partidas")
    print()

    if not API_KEY: print("❌ ERROR: API_KEY no encontrada."); return

    cola = ColaPersistente()
    if reset:
        print("🔄 Reseteando cola...")
        cola.conn.execute("DELETE FROM cola"); cola.conn.execute("DELETE FROM checkpoint")
        cola.conn.execute("INSERT INTO checkpoint(id,total_descargadas,total_errores) VALUES(1,0,0)")
        cola.conn.commit()

    total_base, _ = cola.get_checkpoint()
    print(f"  📋 Cola: {cola.size()} pendientes | 📈 Base descargadas: {total_base:,}")

    if cola.size() < 50:
        print("\n🌱 Sembrando cola desde High Elo (Challenger/GM/Master)...")
        sembrados = sembrar_desde_high_elo(cola, 200)
        print(f"   ✅ {sembrados} jugadores agregados\n")

    if cola.size() == 0: print("❌ Cola vacía."); return

    conn = obtener_conexion()
    total_descargadas = total_base
    buffer_match_ids = []
    last_checkpoint = total_descargadas

    try:
        while total_descargadas < meta and cola.size() > 0:
            puuid = cola.pop()
            if not puuid: break
            match_ids = procesar_jugador(puuid)
            if not match_ids: continue

            # Filtrar partidas ya existentes
            cur = conn.cursor()
            existing, batch = set(), []
            for mid in match_ids:
                if mid in DASH.match_ids_seen: continue
                batch.append(mid)
                if len(batch) >= BATCH_SIZE * 3:
                    placeholders = ",".join(["?"] * len(batch))
                    cur.execute(f"SELECT match_id FROM matches WHERE match_id IN ({placeholders})", batch)
                    existing.update(r[0] for r in cur.fetchall())
                    buffer_match_ids.extend(m for m in batch if m not in existing)
                    batch = []
            if batch:
                placeholders = ",".join(["?"] * len(batch))
                cur.execute(f"SELECT match_id FROM matches WHERE match_id IN ({placeholders})", batch)
                existing.update(r[0] for r in cur.fetchall())
                buffer_match_ids.extend(m for m in batch if m not in existing)

            while len(buffer_match_ids) >= BATCH_SIZE and total_descargadas < meta:
                lote = buffer_match_ids[:BATCH_SIZE]
                buffer_match_ids = buffer_match_ids[BATCH_SIZE:]
                n = descargar_lote(lote)
                total_descargadas += n
                if total_descargadas - last_checkpoint >= CHECKPOINT_EVERY:
                    last_checkpoint = total_descargadas
                    cola.checkpoint(total_descargadas, DASH.snapshot()["errors"])
                print(_progress_bar(total_descargadas, meta, DASH.snapshot()), end="")

            if cola.size() < 50 and total_descargadas < meta:
                print(f"\n🔄 Re-sembrando cola ({cola.size()} pendientes)...")
                sembrar_desde_high_elo(cola, 100)

    except KeyboardInterrupt:
        print("\n\n⏸️  Pausado. Guardando checkpoint...")
    finally:
        cola.checkpoint(total_descargadas, DASH.snapshot()["errors"]); cola.close(); conn.close()

    s = DASH.snapshot()
    print("\n\n" + "═" * 55)
    print("  ✅ RECOLECCIÓN COMPLETADA")
    print("═" * 55)
    print(f"  📦 Partidas: {total_descargadas:,}  |  ❌ Errores: {s['errors']}  |  ⚡ Rate limits: {s['rate_limits']}")
    print(f"  👤 Campeones: {s['champions']}  |  💾 Datos: {s['bytes_mb']} MB  |  ⏱️  {s['elapsed']}  |  📊 {s['rpm']} rpm")
    print("═" * 55)

    print("\n🧹 Compactando BD...")
    try:
        dbc = sqlite3.connect(os.path.join(DATA_DIR, "lol_data.db"))
        dbc.execute("VACUUM"); dbc.close()
        print("   ✅ Optimizada.")
    except: pass

if __name__ == "__main__":
    meta = 20000; reset = False
    for a in sys.argv[1:]:
        if a == "--reset": reset = True
        elif a.isdigit(): meta = int(a)
    inicializar_db()
    ejecutar_recoleccion_masiva(meta=meta, reset=reset)
