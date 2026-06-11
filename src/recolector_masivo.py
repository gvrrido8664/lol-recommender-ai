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

from .db_manager import obtener_conexion, inicializar_db, DATA_DIR, purgar_parches_antiguos
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

MAX_WORKERS = 10       # 5 → 10: más workers aprovechan mejor el rate limit
BATCH_SIZE = 5         # pequeño en días de parche (pocos IDs/jugador), aumentar a 20 en días normales
CHECKPOINT_EVERY = 500
RATE_LIMIT_RPS = 18
COUNT_POR_JUGADOR = 100  # max permitido por Riot (mismo costo de API call que 20)
PLAYER_FETCH_WORKERS = 5  # jugadores procesados en paralelo en el loop principal

# Desactivar timeline: la API v5 incluye SIEMPRE los 6 slots de ítems en el match summary.
# El timeline añadía 1 API call extra por partida (30-50% del total). Desactivar = 1.5-2× más rápido.
USAR_TIMELINE = False

# Días hacia atrás para filtrar partidas (evita descargar partidas de parches viejos)
DIAS_RECIENTES = 1
# Cuántos jugadores semillar de high elo (aumentar a inicio de season)
JUGADORES_SEMILLA = 500

# ═══════════════════════════════════════════════════════════════
# RIOT RATE LIMITER DUAL (Development API Key)
#   • Límite corto: 20 req / 1 segundo
#   • Límite largo: 100 req / 120 segundos
# ═══════════════════════════════════════════════════════════════

class RiotRateLimiter:
    def __init__(self, short_rate: int = 20, short_window: float = 1.0,
                 long_rate: int = 100, long_window: float = 120.0):
        self.short_rate = short_rate
        self.short_window = short_window
        self.long_rate = long_rate
        self.long_window = long_window
        self.short_timestamps: deque[float] = deque()
        self.long_timestamps: deque[float] = deque()
        self.lock = threading.Lock()

    def _clean_old(self, timestamps: deque, window: float, now: float):
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()

    def acquire(self):
        """Bloquea hasta que sea seguro hacer una petición."""
        with self.lock:
            now = time.monotonic()
            self._clean_old(self.short_timestamps, self.short_window, now)
            self._clean_old(self.long_timestamps, self.long_window, now)

            # Si el límite largo está al tope, esperar hasta que se libere el más antiguo
            if len(self.long_timestamps) >= self.long_rate:
                wait = self.long_timestamps[0] + self.long_window - now
                if wait > 0:
                    time.sleep(wait)
                    now = time.monotonic()
                    self._clean_old(self.long_timestamps, self.long_window, now)
                    self._clean_old(self.short_timestamps, self.short_window, now)

            # Si el límite corto está al tope, esperar
            if len(self.short_timestamps) >= self.short_rate:
                wait = self.short_timestamps[0] + self.short_window - now
                if wait > 0:
                    time.sleep(wait)
                    now = time.monotonic()
                    self._clean_old(self.short_timestamps, self.short_window, now)
                    self._clean_old(self.long_timestamps, self.long_window, now)

            # Registrar esta petición
            self.short_timestamps.append(now)
            self.long_timestamps.append(now)

    @property
    def short_used(self) -> int:
        with self.lock:
            self._clean_old(self.short_timestamps, self.short_window, time.monotonic())
            return len(self.short_timestamps)

    @property
    def long_used(self) -> int:
        with self.lock:
            self._clean_old(self.long_timestamps, self.long_window, time.monotonic())
            return len(self.long_timestamps)

RATE_LIMITER = RiotRateLimiter()

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

def epoch_dias_atras(dias: int) -> int:
    """Devuelve epoch timestamp en segundos de hace N días."""
    return int((datetime.utcnow() - timedelta(days=dias)).timestamp())

def epoch_medianoche_hoy() -> int:
    """Devuelve epoch timestamp de la medianoche de hoy (00:00:00 UTC).
    Ideal para filtrar partidas del día actual con startTime."""
    from datetime import timezone as tz
    hoy = datetime.now(tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(hoy.timestamp())

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
    """Semilla la cola con jugadores de high elo usando peticiones paralelas (4 workers).
    Antes era secuencial (12 API calls en serie). Ahora se hacen en paralelo: ~3× más rápido."""
    ligas = {"CHALLENGER": "challengerleagues", "GRANDMASTER": "grandmasterleagues", "MASTER": "masterleagues"}

    # Construir lista de tareas (platform, nombre_liga, url)
    tareas = []
    for platform in PLATFORMS:
        for nombre_liga, endpoint in ligas.items():
            url = f"https://{platform}.api.riotgames.com/lol/league/v4/{endpoint}/by-queue/RANKED_SOLO_5x5"
            tareas.append((platform, nombre_liga, url))

    def _fetch_liga(args):
        platform, nombre_liga, url = args
        datos = peticion_segura(url)
        return platform, nombre_liga, datos

    resultados = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_liga, t): t for t in tareas}
        for f in as_completed(futures):
            try:
                resultados.append(f.result())
            except Exception:
                pass

    # Procesar resultados y agregar a la cola
    agregados = 0
    for platform, nombre_liga, datos in resultados:
        if agregados >= jugadores_max: break
        if not datos or "entries" not in datos:
            print(f"  ⚠️ {platform.upper()} {nombre_liga}: sin datos")
            continue
        entradas = random.sample(datos["entries"], min(20, len(datos["entries"])))
        n = 0
        for e in entradas:
            if e.get("puuid") and agregados < jugadores_max:
                cola.push(e["puuid"]); n += 1; agregados += 1
        print(f"  ✅ {platform.upper()} {nombre_liga}: +{n} jugadores")
    return agregados

@contextmanager
def transaction(conn):
    try: yield; conn.commit()
    except: conn.rollback(); raise

# ═══════════════════════════════════════════════════════════════
# PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

def procesar_jugador(puuid: str, start_time: int = 0, count: int = COUNT_POR_JUGADOR) -> list:
    """Obtiene los match IDs de un jugador. count=20 (doble del original) — misma API call."""
    base = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count={count}"
    if start_time > 0:
        base += f"&startTime={start_time}"
    match_ids = peticion_segura(base)
    return match_ids if match_ids else []

def descargar_partida(match_id: str) -> bool:
    """Descarga una partida y la guarda en BD. Cada hilo usa su propia conexión."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM matches WHERE match_id=%s", (match_id,))
        if cur.fetchone(): return False

        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        data = peticion_segura(url)
        if not data or "info" not in data: return False
        info = data["info"]
        if info.get("gameDuration", 0) < 600: return False

        version = info.get("gameVersion", "0")
        parts = version.split(".")
        patch = ".".join(parts[:2]) if len(parts) >= 2 else "0.0"
        try:
            p_major, p_minor = map(int, PARCHE_ACTUAL.split("."))
            parches_permitidos = [PARCHE_ACTUAL, f"{p_major}.{p_minor - 1}"]
        except:
            parches_permitidos = [PARCHE_ACTUAL]
        
        if patch not in parches_permitidos: return False

        # La API v5 incluye los 6 slots de ítems en el match summary.
        # USAR_TIMELINE=False elimina 1 API call extra por partida (30-50% del total).
        boots_map, supp_map = {}, {}
        if USAR_TIMELINE:
            necesita_timeline = False
            for p in info.get("participants", []):
                items_slots = [str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0]
                pos = p.get("teamPosition", "")
                if not any(es_bota(i) for i in items_slots) or (pos == "UTILITY" and not any(es_item_supp_final(i) for i in items_slots)):
                    necesita_timeline = True
                    break
            if necesita_timeline:
                url_tl = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
                timeline = peticion_segura(url_tl)
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
            cur.execute("INSERT INTO matches(match_id,game_version,game_duration,patch) VALUES(%s,%s,%s,%s)",
                        (match_id, version, info.get("gameDuration", 0), patch))
            for p in info.get("participants", []):
                raw = p.get("championName")
                champ = raw if raw != "MonkeyKing" else "Wukong"
                champions.append(champ)

                # Leer los 7 slots de ítems directamente del summary (siempre presentes en v5)
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
                               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (match_id, champ, pos, p.get("teamId", 0), 1 if p.get("win") else 0,
                             ",".join(items), runas_str, spells, p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)))
        DASH.add_match(match_id, champions, len(json.dumps(data)))
        return True
    except Exception as e:
        print(f"\n[DEBUG] Error en descargar_partida: {e}")
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
    start_time = epoch_dias_atras(DIAS_RECIENTES)
    print(f"  📅 Parche activo: {PARCHE_ACTUAL} ({VERSION_COMPLETA})")
    print(f"  ⏪ Filtrando partidas de los últimos {DIAS_RECIENTES} días (parche {PARCHE_ACTUAL} y anterior)")
    print(f"  🛡️ Rate Limiter: 20 req/s + 100 req/120s (Riot Dev Key)")
    print(f"  🎯 Meta: {meta:,} partidas  |  🧵 Workers: {MAX_WORKERS}  |  📦 Batch: {BATCH_SIZE}")
    tl_mode = "activo" if USAR_TIMELINE else "desactivado (2× más rápido)"
    print(f"  💾 Checkpoint: {CHECKPOINT_EVERY}  |  ⚡ Timeline: {tl_mode}  |  📋 IDs/jugador: {COUNT_POR_JUGADOR}")
    print()

    if not API_KEY: print("❌ ERROR: API_KEY no encontrada."); return

    # ─── PURGA AUTOMÁTICA DE PARCHES ANTIGUOS ───
    print(f"🧹 Verificando base de datos para el parche {PARCHE_ACTUAL}...")
    eliminadas, _ = purgar_parches_antiguos(PARCHE_ACTUAL)
    if eliminadas == 0:
        print(f"  ✅ No hay partidas de parches antiguos. BD limpia.")
    print()

    cola = ColaPersistente()
    if reset:
        print("🔄 Reseteando cola...")
        cola.conn.execute("DELETE FROM cola"); cola.conn.execute("DELETE FROM checkpoint")
        cola.conn.execute("INSERT INTO checkpoint(id,total_descargadas,total_errores) VALUES(1,0,0)")
        cola.conn.commit()

    total_base, _ = cola.get_checkpoint()
    print(f"  📋 Cola: {cola.size()} pendientes | 📈 Base descargadas: {total_base:,}")

    # Pre-cargar todos los match_ids existentes en memoria → dedup O(1), sin queries DB por lote
    print("  📂 Cargando IDs de partidas existentes en memoria...", end=" ", flush=True)
    try:
        _conn_init = obtener_conexion()
        _cur_init = _conn_init.cursor()
        _cur_init.execute("SELECT match_id FROM matches")
        _existing = set(r[0] for r in _cur_init.fetchall())
        _conn_init.close()
        DASH.match_ids_seen.update(_existing)
        print(f"{len(_existing):,} IDs cargados", flush=True)
    except Exception as e:
        print(f"(no disponibles: {e})", flush=True)

    if cola.size() < 50:
        print(f"\n🌱 Sembrando cola desde High Elo (Challenger/GM/Master, max {JUGADORES_SEMILLA})...")
        sembrados = sembrar_desde_high_elo(cola, JUGADORES_SEMILLA)
        print(f"   ✅ {sembrados} jugadores agregados\n")

    if cola.size() == 0: print("❌ Cola vacía."); return

    total_descargadas = total_base
    buffer_match_ids = []
    last_checkpoint = total_descargadas

    def _fetch_player_ids(puuid):
        return procesar_jugador(puuid, start_time=start_time)

    try:
        with ThreadPoolExecutor(max_workers=PLAYER_FETCH_WORKERS) as player_pool:
            while total_descargadas < meta and cola.size() > 0:
                # Sacar hasta PLAYER_FETCH_WORKERS jugadores y buscar sus IDs en paralelo
                puuids = []
                for _ in range(PLAYER_FETCH_WORKERS):
                    p = cola.pop()
                    if p: puuids.append(p)
                if not puuids: break

                futures_p = {player_pool.submit(_fetch_player_ids, p): p for p in puuids}
                for fp in as_completed(futures_p):
                    try:
                        ids = fp.result()
                        for mid in (ids or []):
                            if mid not in DASH.match_ids_seen:
                                buffer_match_ids.append(mid)
                    except Exception:
                        DASH.add_error()

                # Dedup O(1) contra el set en memoria (pre-cargado al inicio + actualizado en cada descarga)
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
                    sembrar_desde_high_elo(cola, max(100, JUGADORES_SEMILLA // 3))

    except KeyboardInterrupt:
        print("\n\n⏸️  Pausado. Guardando checkpoint...")
    finally:
        cola.checkpoint(total_descargadas, DASH.snapshot()["errors"]); cola.close()

    s = DASH.snapshot()
    print("\n\n" + "═" * 55)
    print("  ✅ RECOLECCIÓN COMPLETADA")
    print("═" * 55)
    print(f"  📦 Partidas: {total_descargadas:,}  |  ❌ Errores: {s['errors']}  |  ⚡ Rate limits: {s['rate_limits']}")
    print(f"  👤 Campeones: {s['champions']}  |  💾 Datos: {s['bytes_mb']} MB  |  ⏱️  {s['elapsed']}  |  📊 {s['rpm']} rpm")
    print("═" * 55)

    print("\n🧹 Compactando BD...")
    try:
        from .db_manager import compactar_base_de_datos
        compactar_base_de_datos()
    except Exception as e:
        print(f"   ⚠️ Error al compactar: {e}")

if __name__ == "__main__":
    meta = 20000; reset = False
    for a in sys.argv[1:]:
        if a == "--reset": reset = True
        elif a.isdigit(): meta = int(a)
    inicializar_db()
    ejecutar_recoleccion_masiva(meta=meta, reset=reset)
