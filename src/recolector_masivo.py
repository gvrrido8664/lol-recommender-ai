"""
LOLLECT v4 — Motor de Recolección Masiva de Partidas de LoL
═══════════════════════════════════════════════════════════════
Producción-grade. Construido para ser rápido, resiliente y observable.

Mejoras v4:
  • Multi-región en paralelo (americas/europe/asia/sea) — cada host de Riot
    tiene su propio presupuesto de rate limit ⇒ ~4× throughput con dev key
  • Ventana de IDs de N días (no solo hoy): cada request de IDs rinde hasta
    100 partidas en vez de ~5 (el filtro de parche al descargar se mantiene)
  • Crawling de participantes: los 10 PUUIDs de cada partida descargada
    alimentan la cola — sin requests extra y la cola nunca se agota
  • Cooldown global en 429 + detección de API key expirada (401/403)

Mejoras v3:
  • Rate limiters por endpoint (match, league, timeline) — sin lock contention
  • Pipeline continuo de PUUIDs (sin esperas bloqueantes entre grupos)
  • Conexiones PG persistentes (sin reconexión por lote)
  • Auto-detección de tier de API key (development / production)
  • Inserción batch optimizada en PostgreSQL
  • Re-seeding inteligente por plataforma
  • Reintentos de PUUIDs fallidos
  • Deduplicación thread-safe de match IDs + restricción UNIQUE en participantes

Características heredadas de v2:
  • Rate limiter adaptativo con token bucket + backoff exponencial
  • Descarga paralela de partidas (ThreadPool + batch processing)
  • Persistencia de cola en PostgreSQL (resume automático tras reinicio)
  • Barra de progreso enriquecida con ETA, RPM, throughput
  • Muestreo high elo (Challenger / Grandmaster / Master)
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
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from datetime import datetime, timedelta, timezone as tz
from contextlib import contextmanager

from psycopg2.extras import execute_values
from .db_manager import obtener_conexion, inicializar_db, DATA_DIR, purgar_parches_antiguos
from .riot_api import cargar_objetos

# La consola de Windows usa cp1252 por defecto y los caracteres ═/█ crashean el script.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
# CONEXIÓN THREAD-LOCAL  (1 PG conn por worker — persistente)
# ═══════════════════════════════════════════════════════════════

_pg_local = threading.local()
_pg_connections = set()
_pg_conn_lock = threading.Lock()


def _get_thread_conn():
    conn = getattr(_pg_local, "conn", None)
    if conn is None or conn.closed:
        conn = obtener_conexion()
        _pg_local.conn = conn
        with _pg_conn_lock:
            _pg_connections.add(conn)
    return conn


def _close_thread_connections():
    with _pg_conn_lock:
        for conn in list(_pg_connections):
            try:
                if not conn.closed:
                    conn.close()
            except Exception:
                pass
        _pg_connections.clear()


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

def _cargar_config():
    try:
        config_paths = ["config.json", os.path.join("..", "config.json")]
        for p in config_paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass
    return {}

CONFIG = _cargar_config()
API_KEY = CONFIG.get("API_KEY", os.environ.get("RIOT_API_KEY", ""))

COLLECTOR_CFG = CONFIG.get("collector_settings", {})
API_KEY_TIER = COLLECTOR_CFG.get("api_key_tier", "development")

# Mapa región de routing (match-v5) → plataformas (league-v4) para la siembra.
# Los límites de Riot son POR HOST, así que cada región aporta su PROPIO
# presupuesto de 20/1s + 100/120s: recolectar de las 4 en paralelo ≈ 4× throughput.
REGIONES_DEFAULT = {
    "americas": ["la2", "la1", "na1", "br1"],
    "europe": ["euw1", "eun1", "tr1"],
    "asia": ["kr", "jp1"],
    "sea": ["oc1", "sg2", "tw2", "vn2"],
}


def _cargar_regiones() -> dict:
    regiones = COLLECTOR_CFG.get("regiones")
    if isinstance(regiones, dict) and regiones:
        return regiones
    # Compatibilidad con la config antigua de una sola región
    routing = COLLECTOR_CFG.get("region_routing")
    platforms = COLLECTOR_CFG.get("platforms")
    if routing and platforms:
        return {routing: platforms}
    return REGIONES_DEFAULT


REGIONES = _cargar_regiones()

HEADERS = {"X-Riot-Token": API_KEY}
ITEMS_DATA = cargar_objetos()
ITEMS_SUPP_FINAL = {"3866", "3867", "3869", "3870", "3871", "3873", "3874"}

PARCHE_ACTUAL = "0.0"
VERSION_COMPLETA = "0.0.0"

MAX_WORKERS = 10
BATCH_SIZE = 30
CHECKPOINT_EVERY = 500
COUNT_POR_JUGADOR = 100
PLAYER_FETCH_WORKERS = 5

USAR_TIMELINE = False

JUGADORES_SEMILLA = 500
SEMILLA_POR_PLATAFORMA = 20
RE_SEED_FRACCION = 3

# Ventana de búsqueda de match IDs por jugador. Pedir varios días (en vez de
# solo hoy) hace que cada request de IDs rinda hasta 100 partidas en lugar de
# ~5, reduciendo drásticamente el overhead. Las partidas de parches anteriores
# que entren en la ventana se rechazan al descargar (una sola vez, quedan
# marcadas como vistas).
DIAS_VENTANA_IDS = COLLECTOR_CFG.get("dias_ventana_ids", 7)

# Tope de jugadores pendientes por región: el crawling de participantes
# alimenta la cola solo, esto evita que crezca sin límite.
MAX_COLA_POR_REGION = 1500

# Señal global de parada (meta alcanzada, Ctrl+C o key inválida).
DETENER = threading.Event()


# ═══════════════════════════════════════════════════════════════
# RIOT RATE LIMITER  —  Sin lock contention durante sleep
# ═══════════════════════════════════════════════════════════════

class RiotRateLimiter:
    """Token bucket con dos ventanas. El sleep ocurre FUERA del lock."""

    def __init__(self, short_rate: int = 20, short_window: float = 1.0,
                 long_rate: int = 100, long_window: float = 120.0):
        self.short_rate = short_rate
        self.short_window = short_window
        self.long_rate = long_rate
        self.long_window = long_window
        self.short_timestamps: deque[float] = deque()
        self.long_timestamps: deque[float] = deque()
        self.cooldown_until = 0.0
        self.lock = threading.Lock()

    def _clean_old(self, timestamps: deque, window: float, now: float):
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()

    def set_cooldown(self, seconds: float):
        """Pausa global tras un 429: todos los threads esperan, no solo el que lo recibió."""
        with self.lock:
            self.cooldown_until = max(self.cooldown_until, time.monotonic() + seconds)

    def acquire(self) -> bool:
        """Retorna True al obtener un slot, False si se pidió detener mientras esperaba."""
        while True:
            if DETENER.is_set():
                return False
            with self.lock:
                now = time.monotonic()
                self._clean_old(self.short_timestamps, self.short_window, now)
                self._clean_old(self.long_timestamps, self.long_window, now)

                long_wait = 0.0
                if len(self.long_timestamps) >= self.long_rate:
                    long_wait = self.long_timestamps[0] + self.long_window - now

                short_wait = 0.0
                if len(self.short_timestamps) >= self.short_rate:
                    short_wait = self.short_timestamps[0] + self.short_window - now

                wait_time = max(long_wait, short_wait, self.cooldown_until - now, 0.0)

                if wait_time <= 0:
                    self.short_timestamps.append(now)
                    self.long_timestamps.append(now)
                    return True

            time.sleep(min(wait_time + 0.005, 5.0))

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


# Los límites de aplicación de Riot son POR HOST (americas, la2, la1, ...):
# cada host tiene su propio presupuesto de 20/1s + 100/120s con dev key.
# Un limiter por host aprovecha el máximo sin que la siembra de ligas
# (hosts de plataforma) consuma el presupuesto de match-v5 (host regional).
_limiters: dict[str, RiotRateLimiter] = {}
_limiters_lock = threading.Lock()


def _nuevo_limiter() -> RiotRateLimiter:
    if API_KEY_TIER == "production":
        return RiotRateLimiter(500, 10.0, 30000, 600.0)
    # Ventanas con un pequeño margen (1.05s / 121s) para absorber la deriva
    # entre nuestro reloj y el contador de Riot y evitar 429 en los bordes.
    return RiotRateLimiter(20, 1.05, 100, 121.0)


def _limiter_for(url: str) -> RiotRateLimiter:
    try:
        host = url.split("/", 3)[2].split(".", 1)[0]
    except IndexError:
        host = "default"
    with _limiters_lock:
        lim = _limiters.get(host)
        if lim is None:
            lim = _nuevo_limiter()
            _limiters[host] = lim
        return lim


# ═══════════════════════════════════════════════════════════════
# COLA PERSISTENTE  (PostgreSQL)
# ═══════════════════════════════════════════════════════════════

class ColaPersistente:
    def __init__(self):
        self.lock = threading.Lock()
        self._conn = None
        self._size_cache: dict[str, tuple[int, float]] = {}
        self._init_db()

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = obtener_conexion()
        return self._conn

    def _reset_conn(self):
        try:
            if self._conn and not self._conn.closed:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    def _init_db(self):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cola (
                puuid TEXT PRIMARY KEY,
                fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                procesado INTEGER DEFAULT 0,
                region TEXT DEFAULT 'americas'
            )
        """)
        cur.execute("ALTER TABLE cola ADD COLUMN IF NOT EXISTS region TEXT DEFAULT 'americas'")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cola_region ON cola(region, procesado)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_descargadas INTEGER DEFAULT 0,
                total_errores INTEGER DEFAULT 0,
                fecha_checkpoint TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("SELECT 1 FROM checkpoint")
        if not cur.fetchone():
            cur.execute("INSERT INTO checkpoint(id, total_descargadas, total_errores) VALUES(1, 0, 0)")
        conn.commit()

    def push(self, puuid: str, region: str = "americas"):
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO cola(puuid, region) VALUES(%s, %s) ON CONFLICT (puuid) DO NOTHING",
                    (puuid, region)
                )
                conn.commit()
            except Exception:
                self._reset_conn()

    def push_many(self, puuids: list, region: str):
        """Inserta varios PUUIDs en un solo roundtrip (crawling de participantes).
        Los ya conocidos (incluso procesados) se ignoran."""
        if not puuids:
            return
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                execute_values(cur,
                    "INSERT INTO cola(puuid, region) VALUES %s ON CONFLICT (puuid) DO NOTHING",
                    [(p, region) for p in puuids])
                conn.commit()
            except Exception:
                self._reset_conn()

    def pop(self, region: str | None = None) -> str | None:
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                if region:
                    cur.execute(
                        "SELECT puuid FROM cola WHERE procesado=0 AND region=%s "
                        "ORDER BY fecha_agregado LIMIT 1", (region,))
                else:
                    cur.execute("SELECT puuid FROM cola WHERE procesado=0 ORDER BY fecha_agregado LIMIT 1")
                row = cur.fetchone()
                if row:
                    puuid = row[0]
                    cur.execute("UPDATE cola SET procesado=1 WHERE puuid=%s", (puuid,))
                    conn.commit()
                    return puuid
            except Exception:
                self._reset_conn()
        return None

    def push_back(self, puuid: str, region: str = "americas"):
        """Re-encola un PUUID cuyo fetch falló (al final de la cola)."""
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO cola(puuid, procesado, region) VALUES(%s, 0, %s) "
                    "ON CONFLICT (puuid) DO UPDATE "
                    "SET procesado=0, fecha_agregado=CURRENT_TIMESTAMP",
                    (puuid, region)
                )
                conn.commit()
            except Exception:
                self._reset_conn()

    def size(self, region: str | None = None) -> int:
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                if region:
                    cur.execute("SELECT COUNT(*) FROM cola WHERE procesado=0 AND region=%s", (region,))
                else:
                    cur.execute("SELECT COUNT(*) FROM cola WHERE procesado=0")
                return cur.fetchone()[0]
            except Exception:
                self._reset_conn()
                return 0

    def pendientes_aprox(self, region: str) -> int:
        """Tamaño de cola con cache de 60s — evita un COUNT remoto por lote."""
        ahora = time.monotonic()
        cacheado = self._size_cache.get(region)
        if cacheado is not None and ahora - cacheado[1] < 60:
            return cacheado[0]
        n = self.size(region)
        self._size_cache[region] = (n, ahora)
        return n

    def checkpoint(self, descargadas: int, errores: int):
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE checkpoint SET total_descargadas=%s, total_errores=%s, "
                    "fecha_checkpoint=CURRENT_TIMESTAMP WHERE id=1",
                    (descargadas, errores)
                )
                conn.commit()
            except Exception:
                self._reset_conn()

    def get_checkpoint(self) -> tuple:
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SELECT total_descargadas, total_errores FROM checkpoint")
                row = cur.fetchone()
                return (row[0], row[1]) if row else (0, 0)
            except Exception:
                self._reset_conn()
                return (0, 0)

    def stats(self) -> dict:
        with self.lock:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM cola")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM cola WHERE procesado=0")
                pendientes = cur.fetchone()[0]
                return {"total": total, "pendientes": pendientes, "procesados": total - pendientes}
            except Exception:
                self._reset_conn()
                return {"total": 0, "pendientes": 0, "procesados": 0}

    def close(self):
        with self.lock:
            self._reset_conn()


# ═══════════════════════════════════════════════════════════════
# DASHBOARD DE MÉTRICAS
# ═══════════════════════════════════════════════════════════════

class Dashboard:
    def __init__(self):
        self.lock = threading.Lock()
        self.start_time = time.monotonic()
        self.matches = 0
        self.errors = 0
        self.rate_limits = 0
        self.bytes_down = 0
        self.last_n_matches = []
        self.champions_seen = set()
        self.match_ids_seen = set()

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

    def is_match_known(self, match_id: str) -> bool:
        with self.lock:
            return match_id in self.match_ids_seen

    def mark_known(self, match_id: str):
        """Marca un match ID como visto aunque haya sido rechazado (parche viejo,
        partida corta, error). Evita gastar requests re-descargándolo."""
        with self.lock:
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
            return {
                "matches": self.matches,
                "errors": self.errors,
                "rate_limits": self.rate_limits,
                "rpm": round(rpm, 1),
                "elapsed": str(timedelta(seconds=int(elapsed))),
                "champions": len(self.champions_seen),
                "bytes_mb": round(self.bytes_down / (1024 * 1024), 1),
            }


DASH = Dashboard()


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def obtener_version_riot() -> tuple:
    try:
        resp = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=5)
        v = resp.json()[0]
        parts = v.split(".")
        return (".".join(parts[:2]), v)
    except Exception:
        return ("14.10", "14.10.1")


def epoch_inicio_ventana() -> int:
    """Epoch desde el que se piden match IDs (DIAS_VENTANA_IDS días atrás)."""
    return int(time.time()) - DIAS_VENTANA_IDS * 86400


def es_bota(item_id: str) -> bool:
    data = ITEMS_DATA.get(item_id, {})
    tags = data.get("tags", [])
    if not tags or "Consumable" in tags or "Vision" in tags or "Trinket" in tags:
        return False
    return "Boots" in tags


def es_item_supp_final(item_id: str) -> bool:
    return item_id in ITEMS_SUPP_FINAL


# Señal de aborto cuando la API key es rechazada (401/403). Las dev keys de
# Riot expiran cada 24h: sin esto el recolector falla silenciosamente en TODO.
API_KEY_INVALIDA = threading.Event()

_http_local = threading.local()


def _get_session() -> requests.Session:
    s = getattr(_http_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _http_local.session = s
    return s


def peticion_segura(url: str) -> dict | list | None:
    if API_KEY_INVALIDA.is_set() or DETENER.is_set():
        return None
    limiter = _limiter_for(url)
    for intento in range(4):
        try:
            if not limiter.acquire():
                return None
            resp = _get_session().get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                if not API_KEY_INVALIDA.is_set():
                    API_KEY_INVALIDA.set()
                    print(
                        "\n\nERROR FATAL: la API key fue rechazada por Riot "
                        f"(HTTP {resp.status_code}).\n"
                        "Las development keys expiran cada 24 horas — renueva la tuya en "
                        "https://developer.riotgames.com y actualiza config.json.\n"
                    )
                return None
            if resp.status_code == 429:
                try:
                    espera = float(resp.headers.get("Retry-After", 2 ** intento + 1))
                except (TypeError, ValueError):
                    espera = 2 ** intento + 1
                DASH.add_rate_limit()
                limiter.set_cooldown(espera)
                time.sleep(espera)
                continue
            if resp.status_code in (500, 502, 503, 504):
                time.sleep(2 ** intento)
                continue
            return None
        except Exception:
            time.sleep(1 + intento)
            continue
    DASH.add_error()
    return None


@contextmanager
def transaction(conn):
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ═══════════════════════════════════════════════════════════════
# SIEMBRA  —  Re-seeding inteligente por plataforma
# ═══════════════════════════════════════════════════════════════

def sembrar_desde_high_elo(cola: ColaPersistente, region: str, platforms: list,
                           jugadores_max: int = 200) -> int:
    """Siembra jugadores de Master/GM/Challenger de las plataformas de una región."""
    ligas = {
        "CHALLENGER": "challengerleagues",
        "GRANDMASTER": "grandmasterleagues",
        "MASTER": "masterleagues",
    }

    tareas = []
    for platform in platforms:
        for nombre_liga, endpoint in ligas.items():
            url = f"https://{platform}.api.riotgames.com/lol/league/v4/{endpoint}/by-queue/RANKED_SOLO_5x5"
            tareas.append((platform, nombre_liga, url))

    def _fetch_liga(args):
        platform, nombre_liga, url = args
        datos = peticion_segura(url)
        return platform, nombre_liga, datos

    resultados = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures_map = {pool.submit(_fetch_liga, t): t for t in tareas}
        for f in as_completed(futures_map):
            try:
                resultados.append(f.result())
            except Exception:
                pass

    agregados = 0
    for platform, nombre_liga, datos in resultados:
        if agregados >= jugadores_max:
            break
        if not datos or "entries" not in datos:
            print(f"  [{region}] {platform.upper()} {nombre_liga}: sin datos")
            continue
        muestra = min(SEMILLA_POR_PLATAFORMA, len(datos["entries"]))
        entradas = random.sample(datos["entries"], muestra)
        puuids = [e["puuid"] for e in entradas if e.get("puuid")]
        puuids = puuids[: jugadores_max - agregados]
        cola.push_many(puuids, region)
        agregados += len(puuids)
        print(f"  [{region}] {platform.upper()} {nombre_liga}: +{len(puuids)} jugadores")
    return agregados


# ═══════════════════════════════════════════════════════════════
# PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════

def procesar_jugador(puuid: str, region: str, start_time: int = 0) -> list | None:
    """Retorna la lista de match IDs (puede ser [] si el jugador no jugó en la
    ventana) o None si la petición falló — el caller decide si re-encolar."""
    base = (
        f"https://{region}.api.riotgames.com/lol/match/v5/matches/"
        f"by-puuid/{puuid}/ids?queue=420&start=0&count={COUNT_POR_JUGADOR}"
    )
    if start_time > 0:
        base += f"&startTime={start_time}"
    match_ids = peticion_segura(base)
    if match_ids is None:
        return None
    return match_ids if isinstance(match_ids, list) else []


def descargar_partida(match_id: str, region: str) -> tuple | None:
    """Descarga y valida una partida.
    Retorna (match_row, participants_rows, champions, data_bytes, puuids) o None."""
    try:
        url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        data = peticion_segura(url)
        if not data or "info" not in data:
            return None
        info = data["info"]
        if info.get("gameDuration", 0) < 600:
            return None

        version = info.get("gameVersion", "0")
        parts = version.split(".")
        patch = ".".join(parts[:2]) if len(parts) >= 2 else "0.0"
        if patch != PARCHE_ACTUAL:
            return None

        boots_map, supp_map = {}, {}
        if USAR_TIMELINE:
            necesita_timeline = False
            for p in info.get("participants", []):
                items_slots = [str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0]
                pos = p.get("teamPosition", "")
                if not any(es_bota(i) for i in items_slots) or (
                    pos == "UTILITY" and not any(es_item_supp_final(i) for i in items_slots)
                ):
                    necesita_timeline = True
                    break
            if necesita_timeline:
                url_tl = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
                timeline = peticion_segura(url_tl)
                if timeline and "info" in timeline:
                    for frame in timeline["info"].get("frames", []):
                        for ev in frame.get("events", []):
                            if ev.get("type") != "ITEM_PURCHASED":
                                continue
                            pid = ev.get("participantId")
                            iid = str(ev.get("itemId", 0))
                            if not pid or iid == "0":
                                continue
                            if es_bota(iid):
                                boots_map[pid] = iid
                            elif es_item_supp_final(iid):
                                supp_map[pid] = iid

        champions = []
        participants_rows = []
        for p in info.get("participants", []):
            raw = p.get("championName")
            champ = raw if raw != "MonkeyKing" else "Wukong"
            champions.append(champ)

            items = [str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0]
            pid_p = p.get("participantId")
            pos = p.get("teamPosition", "")
            if pid_p in boots_map and not any(es_bota(i) for i in items):
                items.append(boots_map[pid_p])
            if pos == "UTILITY" and pid_p in supp_map and not any(es_item_supp_final(i) for i in items):
                items.append(supp_map[pid_p])

            styles = p.get("perks", {}).get("styles", [])
            runas = []
            for s in styles:
                runas.append(str(s.get("style")))
                for sel in s.get("selections", []):
                    runas.append(str(sel.get("perk")))
            sp = p.get("perks", {}).get("statPerks", {})
            if sp:
                for k in ("defense", "flex", "offense"):
                    runas.append(str(sp.get(k, "")))
            runas_str = ",".join(r for r in runas if r)
            spells = f"{p.get('summoner1Id', 0)},{p.get('summoner2Id', 0)}"

            participants_rows.append((
                match_id, champ, pos, p.get("teamId", 0), 1 if p.get("win") else 0,
                ",".join(items), runas_str, spells,
                p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
            ))

        match_row = (match_id, version, info.get("gameDuration", 0), patch)
        data_bytes = len(json.dumps(data))
        # PUUIDs de los 10 participantes: alimentan la cola (crawling) sin
        # gastar requests extra — son jugadores del mismo nivel que la partida.
        puuids = data.get("metadata", {}).get("participants", [])
        return (match_row, participants_rows, champions, data_bytes, puuids)
    except Exception:
        return None


def insertar_lote_datos(datos: list) -> int:
    """Inserta en batch: matches + participantes. Retorna cuántas partidas NUEVAS se insertaron."""
    if not datos:
        return 0
    conn = _get_thread_conn()
    try:
        with transaction(conn):
            cur = conn.cursor()
            match_rows = []
            all_parts = []
            for match_row, parts_rows, *_ in datos:
                match_rows.append(match_row)
                all_parts.extend(parts_rows)

            execute_values(cur,
                """INSERT INTO matches(match_id, game_version, game_duration, patch)
                   VALUES %s ON CONFLICT (match_id) DO NOTHING""",
                match_rows)

            if all_parts:
                execute_values(cur,
                    """INSERT INTO participantes(match_id, champion, team_position, team, win,
                       items, runes, spells, kills, deaths, assists)
                       VALUES %s ON CONFLICT (match_id, champion, team) DO NOTHING""",
                    all_parts)

        return len(datos)
    except Exception:
        return 0


def descargar_lote(match_ids: list, region: str) -> tuple[int, list]:
    """Descarga un lote de partidas en paralelo y las inserta en batch.
    Retorna (cuántas nuevas, PUUIDs de participantes para el crawling)."""
    descargados = []
    puuids_vistos = set()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures_map = {pool.submit(descargar_partida, mid, region): mid for mid in match_ids}
        for future in as_completed(futures_map):
            mid = futures_map[future]
            DASH.mark_known(mid)
            try:
                result = future.result()
                if result:
                    descargados.append(result)
                    DASH.add_match(mid, result[2], result[3])
                    puuids_vistos.update(result[4])
            except Exception:
                DASH.add_error()

    if not descargados:
        return 0, []

    return insertar_lote_datos(descargados), list(puuids_vistos)


# ═══════════════════════════════════════════════════════════════
# ORQUESTADOR
# ═══════════════════════════════════════════════════════════════

def ejecutar_recoleccion_masiva(meta: int = 20000, reset: bool = False):
    global PARCHE_ACTUAL, VERSION_COMPLETA

    print("\n" + "═" * 55)
    print("  LOLLECT v4 — Motor de Recolección Masiva Multi-Región")
    print("═" * 55)

    PARCHE_ACTUAL, VERSION_COMPLETA = obtener_version_riot()
    inicio_ventana = epoch_inicio_ventana()
    tier_label = "Production" if API_KEY_TIER == "production" else "Development"

    print(f"  Parche activo: {PARCHE_ACTUAL} ({VERSION_COMPLETA})")
    print(f"  Ventana de IDs: últimos {DIAS_VENTANA_IDS} días — solo se guarda el parche activo")
    print(f"  API Key tier: {tier_label}")
    if API_KEY_TIER == "production":
        print(f"  Rate Limiter:    500 req/10s + 30000 req/10min POR HOST")
    else:
        print(f"  Rate Limiter:    20 req/s + 100 req/120s POR HOST (Dev Key)")
    print(f"  Meta: {meta:,} partidas  |  Workers/región: {MAX_WORKERS}  |  Batch: {BATCH_SIZE}")
    tl_mode = "activo (2× más lento)" if USAR_TIMELINE else "desactivado (2× más rápido)"
    print(f"  Checkpoint: {CHECKPOINT_EVERY}  |  Timeline: {tl_mode}  |  IDs/jugador: {COUNT_POR_JUGADOR}")
    for region, plats in REGIONES.items():
        print(f"  Región {region}: {', '.join(plats)}")
    print()

    if not API_KEY:
        print("ERROR: API_KEY no encontrada en config.json ni en variable RIOT_API_KEY.")
        return

    print(f"Verificando base de datos para el parche {PARCHE_ACTUAL}...")
    eliminadas, _ = purgar_parches_antiguos(PARCHE_ACTUAL)
    if eliminadas == 0:
        print("  No hay partidas de parches antiguos. BD limpia.")
    print()

    cola = ColaPersistente()
    if reset:
        print("Reseteando cola...")
        conn_reset = obtener_conexion()
        cur_reset = conn_reset.cursor()
        cur_reset.execute("DELETE FROM cola")
        cur_reset.execute("DELETE FROM checkpoint")
        cur_reset.execute("INSERT INTO checkpoint(id,total_descargadas,total_errores) VALUES(1,0,0)")
        conn_reset.commit()
        conn_reset.close()

    total_base, _ = cola.get_checkpoint()
    print(f"  Cola: {cola.size()} pendientes | Base descargadas: {total_base:,}")

    print("  Cargando IDs de partidas existentes en memoria...", end=" ", flush=True)
    try:
        _conn_init = obtener_conexion()
        _cur_init = _conn_init.cursor()
        _cur_init.execute("SELECT match_id FROM matches")
        _existing = set(r[0] for r in _cur_init.fetchall())
        _conn_init.close()
        with DASH.lock:
            DASH.match_ids_seen.update(_existing)
        print(f"{len(_existing):,} IDs cargados")
    except Exception:
        print("(no disponibles)")

    # ── Estado compartido entre las regiones ──
    estado_lock = threading.Lock()
    estado = {"total": total_base, "checkpoint": total_base, "jugadores": 0}
    DETENER.clear()

    def _total() -> int:
        with estado_lock:
            return estado["total"]

    def _registrar(n: int):
        toca_checkpoint = False
        with estado_lock:
            estado["total"] += n
            if estado["total"] >= meta:
                DETENER.set()
            if estado["total"] - estado["checkpoint"] >= CHECKPOINT_EVERY:
                estado["checkpoint"] = estado["total"]
                toca_checkpoint = True
        if toca_checkpoint:
            cola.checkpoint(_total(), DASH.snapshot()["errors"])

    def _worker_region(region: str, platforms: list):
        """Pipeline completo de una región: siembra → IDs por jugador → descarga.
        Cada región corre en paralelo con su PROPIO presupuesto de rate limit."""
        buffer_ids: list = []
        ultimo_reseed = 0.0
        reseeds_inutiles = 0

        def _fetch_ids(puuid):
            ids = procesar_jugador(puuid, region, start_time=inicio_ventana)
            if ids is None:
                # Fallo real de la petición → reintentar más tarde (al final de la cola).
                cola.push_back(puuid, region)
                return []
            # [] legítimo (sin partidas en la ventana): NO re-encolar, sería un
            # bucle infinito quemando el rate limit.
            return ids

        def _procesar_lotes(force: bool = False):
            umbral = 1 if force else BATCH_SIZE
            while len(buffer_ids) >= umbral and not DETENER.is_set():
                lote = buffer_ids[:BATCH_SIZE]
                del buffer_ids[:BATCH_SIZE]
                n, puuids = descargar_lote(lote, region)
                # Crawling: los participantes de cada partida alimentan la cola
                # (mismo nivel high elo, cero requests extra).
                if puuids and cola.pendientes_aprox(region) < MAX_COLA_POR_REGION:
                    cola.push_many(puuids, region)
                _registrar(n)

        try:
            if cola.size(region) < 50 and not DETENER.is_set():
                sembrar_desde_high_elo(cola, region, platforms, JUGADORES_SEMILLA)

            with ThreadPoolExecutor(max_workers=PLAYER_FETCH_WORKERS) as pool:
                activos = {}

                def _fill() -> bool:
                    """Rellena el pool de jugadores. Retorna False si la cola se agotó."""
                    while len(activos) < PLAYER_FETCH_WORKERS and not DETENER.is_set():
                        p = cola.pop(region)
                        if not p:
                            return False
                        activos[pool.submit(_fetch_ids, p)] = p
                    return True

                _fill()
                while not DETENER.is_set() and not API_KEY_INVALIDA.is_set():
                    if not activos:
                        # Cola de la región agotada: bajar lo que haya y re-sembrar.
                        _procesar_lotes(force=True)
                        ahora = time.monotonic()
                        if ahora - ultimo_reseed >= 90:
                            ultimo_reseed = ahora
                            print(f"\n  [{region}] re-sembrando cola...")
                            sembrar_desde_high_elo(cola, region, platforms,
                                                   max(100, JUGADORES_SEMILLA // RE_SEED_FRACCION))
                            if _fill() or activos:
                                reseeds_inutiles = 0
                                continue
                            reseeds_inutiles += 1
                            if reseeds_inutiles >= 3:
                                break  # región sin jugadores nuevos que procesar
                            continue
                        if DETENER.wait(10):
                            break
                        _fill()
                        continue

                    done, _ = wait(set(activos.keys()), return_when=FIRST_COMPLETED, timeout=10)
                    for f in done:
                        try:
                            ids = f.result()
                            for mid in ids:
                                if not DASH.is_match_known(mid):
                                    buffer_ids.append(mid)
                        except Exception:
                            DASH.add_error()
                        activos.pop(f, None)
                        with estado_lock:
                            estado["jugadores"] += 1

                    _procesar_lotes()
                    _fill()

                # Descargar lo que quedó en el buffer (< BATCH_SIZE).
                if not API_KEY_INVALIDA.is_set():
                    _procesar_lotes(force=True)
        except Exception:
            DASH.add_error()

    hilos = []
    for region, plats in REGIONES.items():
        t = threading.Thread(target=_worker_region, args=(region, plats),
                             daemon=True, name=f"region-{region}")
        t.start()
        hilos.append(t)

    try:
        while any(t.is_alive() for t in hilos):
            time.sleep(2)
            s = DASH.snapshot()
            with estado_lock:
                tot, jug = estado["total"], estado["jugadores"]
            print(
                f"\r ⏳ {tot}/{meta} partidas | {s['rpm']} rpm | {jug} jugadores | "
                f"{s['errors']} err | {s['rate_limits']} × 429   ",
                end="", flush=True,
            )
    except KeyboardInterrupt:
        print("\n\nPausado. Guardando checkpoint...")
        DETENER.set()
        for t in hilos:
            t.join(timeout=20)
    finally:
        DETENER.set()
        cola.checkpoint(_total(), DASH.snapshot()["errors"])
        cola.close()
        _close_thread_connections()

    total_descargadas = _total()

    s = DASH.snapshot()
    print("\n\n" + "═" * 55)
    print("  RECOLECCIÓN COMPLETADA")
    print("═" * 55)
    print(f"  Partidas: {total_descargadas:,}  |  Errores: {s['errors']}  |  Rate limits: {s['rate_limits']}")
    print(f"  Campeones: {s['champions']}  |  Datos: {s['bytes_mb']} MB  |  {s['elapsed']}  |  {s['rpm']} rpm")
    print("═" * 55)

    print("\nCompactando BD...")
    try:
        conn = obtener_conexion()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("VACUUM")
        conn.close()
        print("   Optimizada.")
    except Exception:
        pass


if __name__ == "__main__":
    meta = 20000
    reset = False
    for a in sys.argv[1:]:
        if a == "--reset":
            reset = True
        elif a.isdigit():
            meta = int(a)
    inicializar_db()
    ejecutar_recoleccion_masiva(meta=meta, reset=reset)
