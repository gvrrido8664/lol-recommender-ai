# PLAN COMPLETO DE MEJORAS — LoL Recommender v2

**Fecha:** 2026-06-12  
**Alcance:** `app.py` (6.640 lineas) + 22 modulos `src/` (~6.400 lineas propias) ≈ **13.000 lineas**  
**Stack:** Python 3.12 + PySide6 (Qt GUI) + PostgreSQL (Render.com) + Riot API/LCU/Live Client

---

## Indice

1. [Arquitectura y patrones de diseno](#1-arquitectura-y-patrones-de-diseño)
2. [Calidad de codigo / Clean Code](#2-calidad-de-codigo--clean-code)
3. [Rendimiento y cache](#3-rendimiento-y-cache)
4. [Resiliencia APIs externas](#4-resiliencia-apis-externas)
5. [Logica de dominio y precision](#5-logica-de-dominio-y-precision)
6. [Integridad del coaching / anti-contradicciones](#6-integridad-del-coaching--anti-contradicciones)
7. [Cobertura de tests](#7-cobertura-de-tests)
8. [Plan de accion priorizado](#8-plan-de-accion)

---

## 1. Arquitectura y patrones de diseño

### Diagnostico

`app.py:1-6640` es un **God Object**. Centraliza:

| Responsabilidad | Ubicacion | ~Lineas |
|---|---|---|
| GUI (PySide6) | Todo el archivo | 4500+ |
| Hilos y concurrencia | ThreadPoolExecutor, QTimer, callbacks | 300 |
| Base de datos | Llamadas directas a obtener_conexion() | 200+ |
| APIs (Riot/DDragon) | Descarga de imagenes, datos | 200 |
| Logica de dominio | Recomendaciones, coaching, sinergia | 500+ |

**Peores focos de acoplamiento:**

- `generar_reporte_coach` (`app.py:861-1405`): ~545 lineas que mezclan analisis estadistico, generacion de HTML, psicologia del jugador y formato de salida.
- `_renderizar_historial` (`app.py:3798-4008`): ~210 lineas que construyen widgets Qt + queries + logica de presentacion.
- `_on_radar_listo` (`app.py:4638-4770`): ~130 lineas con multiples queries a la BD en bucle, cacheo ad-hoc y renderizado.
- `armar_tab_perfil` (`app.py:2736-3019`): ~280 lineas con construccion masiva de UI.

### Contraste positivo: recolector_masivo.py

Este modulo (`src/recolector_masivo.py:1-1182`) ya implementa patrones production-grade que deben exportarse al resto:

| Patron | Implementacion | Lineas |
|---|---|---|
| **Rate Limiter** | RiotRateLimiter — token bucket thread-safe con sleep fuera del lock | 177-199 |
| **Conexiones thread-local** | _get_thread_conn() — 1 PG conn por worker, persistente | 67-79 |
| **Cola persistente** | Tabla cola con checkpoint en BD | 100-108 |
| **429/Retry-After** | set_cooldown(seconds) compartido entre todos los threads | 195-199 |
| **Configuracion centralizada** | COLLECTOR_CFG con defaults en el propio modulo | 111-167 |

### Arquitectura objetivo por capas

```
┌──────────────────────────────────────────────────┐
│  ui/                                              │
│  ├── widgets/          Componentes reutilizables   │
│  ├── tabs/             Cada pestana = una clase    │
│  └── main_window.py    Solo orquestacion           │
├──────────────────────────────────────────────────┤
│  servicios/            Logica de negocio sin Qt    │
│  ├── coach.py          generar_reporte_coach       │
│  ├── radar.py          _on_radar_listo → flujo     │
│  ├── perfil.py         Logica de perfil            │
│  └── draft_ia.py       Prediccion IA               │
├──────────────────────────────────────────────────┤
│  repositorios/         Acceso a datos              │
│  ├── partidas_repo.py                              │
│  ├── draft_repo.py                                 │
│  └── cache_repo.py                                 │
├──────────────────────────────────────────────────┤
│  infra/                Conexiones, rate limiting    │
│  ├── pg_pool.py        Pool PostgreSQL             │
│  ├── riot_client.py    Rate limiter compartido      │
│  ├── lcu_client.py     LCU con reintentos           │
│  └── config.py         Configuracion tipada         │
└──────────────────────────────────────────────────┘
```

### Patrones concretos para la migracion

| Patron | Donde aplicarlo | Como |
|---|---|---|
| **Singleton** | Pool PG + _TAGS_CACHE con threading.Lock | Un ThreadedConnectionPool global; _TAGS_CACHE con RLock para carga lazy |
| **Repository** | Extraer SQL disperso de recomendador.py:522-630 y db_manager.py:112-198 | Una clase por entidad (MatchRepository, DraftRepository) |
| **Observer** | Senales Qt ad-hoc → MonitorFases | MonitorFases.registrar(FaseDraft, callback) → emite en cambios de fase |
| **Factory** | FuenteDatosPartida.crear(fase) | Retorna fuente segun estado: LCU, Live Client (2999), Riot API, o mock |
| **Strategy** | Reglas de coaching en generar_reporte_coach | ReglaCoach(tema, prioridad, evaluar) → Hallazgo — cada regla es pluggable |

---


## 2. Calidad de codigo / Clean Code

### Codigo muerto

```python
# src/recomendador.py:72-86
# Constantes que nunca se completaron. El analisis actual usa tags_champions.
AP_EXCEPTIONS = {"Sylas", "Akali", "Diana", "Ekko", "Evelynn", "Fizz", "Gwen",
                 "Katarina", "Mordekaiser", "Nidalee", "Rumble", "Shaco", "Singed",
                 "Vladimir", "Zac", "Gragas", "Elise", "Volibear", "Kennen", "Teemo",
                 "Azir", "Kassadin", "Leblanc"}

AP_TANKS = {"Amumu", "ChoGath", "Galio", "Malphite", "Maokai", "Nunu", "Ornn",
            "Rammus", "Sejuani", "Shen", "Sion", "Zac", "Skarner"}

FRONTLANE_EXCLUDE = {"Fizz", "KhaZix", "MasterYi", "Quinn", "Rengar", "Shaco",
                     "Tryndamere", "Yasuo", "Yone", "Fiora", "Gwen", "Irelia",
                     "Kayn", "LeeSin", "Nidalee", "Riven", "Viego", "BelVeth",
                     "Elise", "Evelynn", "Katarina", "Akali", "Sylas", "Diana",
                     "Ekko", "Kassadin", "Leblanc"}
```

No se usan en ninguna ruta de codigo productivo.

### Duplicacion

| Duplicado | Archivos | Lineas |
|---|---|---|
| _cargar_config() | db_manager.py:40-49 y recolector_masivo.py:97-106 | Identica, difiere en la variable donde almacena |
| Normalizacion "MonkeyKing" | entrenador_ia.py:207 y entrenador_ia.py:294 | Mismo .replace("MonkeyKing", "Wukong") en dos funciones distintas |
| Patron query+fallback | recomendador.py (6 ocurrencias) | Query con min_partidas=20 → fallback min_partidas=5 |
| Conexion + query + close | ~40 call sites en todo el proyecto | conn = obtener_conexion(); try... finally: conn.close() |

### 4 mapeos de roles dispersos — Centralizar en src/roles.py

```python
# app.py:99-101
UI_ROLES = ["TOP", "JUNGLA", "MID", "ADC", "SUPPORT"]
ROL_TO_API = {"TOP": "TOP", "JUNGLA": "JUNGLE", "MID": "MIDDLE", "ADC": "BOTTOM", "SUPPORT": "UTILITY"}
API_TO_ROL = {"TOP": "TOP", "JUNGLE": "JUNGLA", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}

# recomendador.py:544-549
pos_equivalentes = {
    "TOP": "TOP", "JUNGLE": "JUNGLE", "JUNGLA": "JUNGLE",
    "MIDDLE": "MIDDLE", "MID": "MIDDLE",
    "BOTTOM": "BOTTOM", "ADC": "BOTTOM",
    "UTILITY": "UTILITY", "SUPPORT": "UTILITY",
}
```

Crear src/roles.py con un unico mapa bidireccional y funciones a_ui(), a_api().

### Excepciones genericas

| except bare | Archivo | Lineas |
|---|---|---|
| except Exception: | lcu_api.py | 65, 333 |
| except Exception as e: | lcu_api.py | 436, 461, 540 |
| except Exception as e: | app.py | 4799 (draft history) |
| except Exception: | recomendador.py | 625 |

Caso concreto: lcu_api.py:65 en conectar() captura Exception generica cuando deberia ser (OSError, IndexError, ValueError) — errores predecibles al leer el lockfile.

### Numeros magicos

| Valor | Significado | Archivo:linea | Propuesta |
|---|---|---|---|
| 0.8, 0.6, 0.5, 1.5, 1.2 | Pesos de ajuste de composicion | recomendador.py:609-618 | src/balance.py con constantes nombradas |
| 3 | Factor bayesiano de suavizado | recomendador.py:575 | FACTOR_BAYESIANO = 3 |
| 5, 10, 20, 50 | Umbrales de partidas minimas | recomendador.py:88,571,573 | MIN_PARTIDAS_* en constantes del modulo |
| 60+ colores hex | Estilos inline en Qt | app.py (dispersos) | src/theme.py con paleta semantica |
| 30, 60, 90, 120 | Segundos para timers | app.py | src/constantes.py |

### Naming mixto espanol/ingles

El proyecto mezcla nombres en espanol (armar_tab_perfil, obtener_mi_rol, campeones) con ingles (get_liveclient_data, on_liveclient_poll, winrate). Decidir un idioma canonico y aplicar consistencia progresiva.

---


## 3. Rendimiento y cache

### Problema central: sin pool de conexiones

```python
# db_manager.py:63-97 — Cada llamada abre un socket TLS nuevo a Render
def obtener_conexion():
    url = _obtener_db_url()
    # ...
    conn = psycopg2.connect(url, ...)  # ← TLS handshake (~200ms) cada vez
    return conn
```

**Impacto medido:**

| Operacion | Conexiones abiertas |
|---|---|
| Refresh de radar (_on_radar_listo) | 8-10 |
| Carga de perfil (armar_tab_perfil) | 4-6 |
| Recomendacion IA | 3-5 por rol |
| Pantalla de counters | 5-7 |

**Limite de Render (plan free):** ~20 conexiones simultaneas.  
**Riesgo real:** agotar el pool del servidor con 2-3 refrescos rapidos consecutivos.

### Caches sin thread-safety

| Cache | Archivo:linea | Problema |
|---|---|---|
| _TAGS_CACHE (modulo) | tags_champions.py:23,654-662 | Carga lazy sin lock: dos threads pueden ejecutar _generar_tags() a la vez |
| _cache_imagenes (instancia) | app.py:1744,2273-2291 | dict accedido desde ThreadPoolExecutor (hilo worker) y desde el hilo principal sin lock |
| _cache_rol_tipico (instancia) | app.py:4676-4722 | Live Client actualiza mientras hilo principal lee |
| season_cache_{puuid}.json | app.py:3477 | Archivos en disco TTL 24h nunca limpiados automaticamente |

### N+1 queries

| Sitio | Descripcion |
|---|---|
| recomendador.py:435-520 (recomendar_picks_vivo) | ~100 round-trips por recomendacion. Solucion: query agregada con GROUP BY champion en un solo viaje |
| app.py:4638-4770 (_on_radar_listo) | 5+ conexiones en bucle: obtener_peores_matchups, obtener_campeones_por_rol, obtenermejoresbaneos |

---

## 4. Resiliencia APIs externas

### LCU (Local Client API)

**Estado actual:**

```python
# lcu_api.py:75-87 — Sin reintentos, sin backoff
def request(self, method, endpoint, **kwargs):
    if not self.port:
        if not self.conectar():    # ← Fallo silencioso: retorna None
            return None
    try:
        res = requests.request(method, url, **kwargs)
        return res
    except requests.RequestException:
        return None                 # ← Silencia timeout, ConnectionError
```

**Problemas identificados:**

1. **Sin reintentos ni backoff.** Si el cliente esta en pantalla de carga (LCU saturada), un solo fallo descarta la request.
2. **Sin relectura del lockfile al reiniciar.** Si el jugador cierra y reabre LoL, el lockfile cambia de puerto/contrasena pero LCUConnector no lo re-detecta.
3. **verify=False inevitable** (certificado autofirmado de Riot) pero no documentado/acotado.
4. **conectar() (lcu_api.py:65)** captura Exception generica: deberia ser (OSError, IndexError, ValueError).

### Live Client (puerto 2999)

**Bucle "Entrando a la Grieta":** lcu_api.py:475-542 (obtener_liveclient_data). Si Live Client y LCU fallan, el polling continua indefinidamente. Solucion: contador de intentos fallidos + MonitorFases.notificar("error_conexion") tras N fallos.

### Plan de contingencia general

| Escenario | Actual | Deseado |
|---|---|---|
| LCU offline | None silencioso, reintento next tick | MonitorFases.notificar("lcu_offline"), icono gris |
| Live Client timeout | Retorna [],{"status":"loading"} (OK) | Mantener, con limite de reintentos |
| Jugadores duplicados | Sin deteccion | set() de summonerId antes de procesar |
| Lockfile stale | conectar() falla, sin reintento | reconnect() automatico con backoff |
| API Key invalida (403) | Stack trace en consola | MonitorFases.notificar("api_key_invalida") + badge rojo |
| Sin internet | ConnectionError → app se cuelga | Timeout global 5s, estado "offline" en UI |

### Seguridad de secretos

```json
// config.json:2-3 — API key y password de BD en texto plano en el repo
"API_KEY": "RGAPI-5426a7f5-d646-47a0-a8ad-669b115d599f",
"DATABASE_URL": "postgresql://nexus_d0ro_user:..."
```

**Solucion:**
1. config.json → config.example.json (sin valores reales)
2. config.json real → ignorado por .gitignore
3. Variables de entorno como fuente primaria (codigo ya lo soporta en db_manager.py:53)
4. Rotacion inmediata de la API key expuesta

---


## 5. Logica de dominio y precision

### Truncamiento en analizar_composicion

```python
# recomendador.py:384-407
def analizar_composicion(aliados):
    # ...
    pct_ad = min(100, int((ad_count / total_dmg) * 100))  # ← int() TRUNCA
    pct_ap = min(100, int((ap_count / total_dmg) * 100))  # ← int() TRUNCA
```

**Problema:** Con 2 AD + 1 AP → int(2/3*100)=66, int(1/3*100)=33 → suma 99, no 100.  
Este sesgo se acumula en _score_pick (recomendador.py:409-423) donde los umbrales >= 60 determinan bonificaciones.

**Fix:** Cambiar int() por round().

### calcular_winrate_5v5 — Pesos artesanales

```python
# recomendador.py:522-630 — Constantes inline sin calibracion empirica
ajuste_cc = min(5, (cc_aliado_total - cc_enemigo_total) * 0.8)
ajuste_early = min(3, (early_aliado - early_enemigo) * 0.6)
ajuste_scale = min(3, (scale_aliado - scale_enemigo) * 0.5)
wr_por_lane.append(wr_single * 0.7 + 50 * 0.3)  # ← ponderacion magica
wr_final = max(35, min(65, ...))                   # ← clamp [35, 65]
```

**Propuesta:** Suavizado bayesiano uniforme:

```
wr_ajustado = (wr_observado * n + 50 * K) / (n + K)
```

Donde K (prior strength) se calibra con drafts_history (wr_predicho vs ganada).

### Entrenamiento de IA sin validacion

```python
# entrenador_ia.py:251-258
modelo = RandomForestClassifier(n_estimators=25, max_depth=12,
                                min_samples_leaf=5, random_state=42, n_jobs=-1)
modelo.fit(X, y)  # ← Sin train/test split. Accuracy INFLADA.
```

**Fix:**
1. Split 80/20 estratificado por win
2. Reportar roc_auc + accuracy
3. Guardar classification_report para auditoria

---

## 6. Integridad del coaching / anti-contradicciones

### Extraer generar_reporte_coach a src/coach.py

La funcion actual (app.py:861-1405, ~545 lineas) debe refactorizarse con Strategy:

```python
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class Hallazgo:
    tema: str
    severidad: int    # 1 (info) a 5 (critico)
    html: str
    icono: str
    color: str

class ReglaCoach(ABC):
    @abstractmethod
    def evaluar(self, historial, perfil, fatiga) -> Hallazgo | None: ...

class ReglaPoolCampeones(ReglaCoach): ...
class ReglaConsistenciaCS(ReglaCoach): ...
class ReglaAgresividad(ReglaCoach): ...
class ReglaVision(ReglaCoach): ...
class ReglaMortalidadTemprana(ReglaCoach): ...
class ReglaFatiga(ReglaCoach): ...
```

### Resolutor de contradicciones

| Tema A | Tema B | Regla de resolucion |
|---|---|---|
| "Se mas agresivo en early" | "Juega seguro y escala" | Conservar el de mayor severidad |
| "Farmeá mas" | "Rotea mas a otras lineas" | Conservar el de mayor severidad |
| "Amplia tu pool" | "Especializate en 2-3 campeones" | Si pool > 10 → especializar; si pool < 3 → ampliar |
| "Wardea mas" | "No te expongas a roams" | Fusionar en consejo unico de vision segura |

### Garantia de respuesta completa

Testeado en tests.py:39-50: {secciones, resumen, consejo_final}. Ampliar verificacion a:
- Cada seccion tiene todos los campos (titulo, html, icono, color, prioridad)
- Sin secciones con html vacio
- Resumen no excede 300 caracteres
- Sin HTML malformado

---


## 7. Cobertura de tests

### Estado actual: tests.py (173 lineas)

13 tests estilo script. Usan assert plano, sin framework. Problemas:

| Problema | Ejemplo |
|---|---|
| Re-implementan logica en vez de probarla | test_liveclient_empty_lists replica parsing en vez de invocar la funcion real |
| Sin fixtures ni setup/teardown | Cada test configura manualmente su estado |
| Sin aislamiento de BD | Si PostgreSQL no esta disponible, los tests que importan db_manager fallan |
| Sin casos borde sistematicos | No hay tests para: composicion vacía, campeon desconocido, equipos incompletos |

### Plan de migracion a pytest

```
tests/
├── conftest.py                  # Fixtures: mock_pg, mock_lcu, mock_riot
├── test_composicion.py          # analizar_composicion, _score_pick
├── test_winrate_5v5.py          # calcular_winrate_5v5
├── test_coaching.py             # generar_reporte_coach, ReglaCoach
├── test_drafts.py               # guardar_draft, completar_draft_resultado
├── test_liveclient.py           # Parsing defensivo de payloads
├── test_lcu.py                  # conectar, reconnect, request
├── test_cache.py                # _TAGS_CACHE, _cache_imagenes
└── test_integridad.py           # Anti-contradicciones
```

### Fixture clave

```python
# conftest.py
@pytest.fixture
def mock_db(monkeypatch):
    """Reemplaza obtener_conexion con SQLite en memoria."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr("src.db_manager.obtener_conexion", lambda: conn)
    yield conn
    conn.close()
```

### Casos borde nuevos

| Modulo | Caso borde |
|---|---|
| analizar_composicion | Lista vacia, 5 AD puros, 5 AP puros, mezcla con HYBRID |
| _score_pick | WR=0, WR=100, campeon sin tags (_DEFAULT_TAG) |
| calcular_winrate_5v5 | 0 aliados, 6 aliados, equipos desiguales, campeon desconocido |
| completar_draft_resultado | draft_id=None, sin drafts pendientes, multiples pendientes |
| guardar_draft | wr_predicho=None, listas vacias de aliados/enemigos |
| liveclient | allPlayers con entradas None, scores malformados, sin gameData |
| generar_reporte_coach | Historial vacio, 2 partidas (< minimo), todas derrotas, todas victorias |

---


## 8. Plan de accion

### Clasificacion de prioridades

- **Critica:** causa fallos, perdida de datos o degradacion severa de UX
- **Alta:** mejora significativa de rendimiento, precision o mantenibilidad
- **Media:** deuda tecnica con impacto moderado
- **Baja:** cosmetica, naming, documentacion

### Tabla de acciones

| # | Pri | Archivo:Funcion | Problema | Justificacion | Solucion |
|---|---|---|---|---|---|
| **P1** | **Critica** | `db_manager.py:63-97` `obtener_conexion()` | Sin pool de conexiones | 8-10 handshakes TLS a Render por refresh. Limite Render ~20 conns. | `ThreadedConnectionPool` (ver codigo abajo) |
| **P2** | **Critica** | `db_manager.py:453` `completar_draft_resultado(fecha, ganada)` | Race condition: busca por fecha | Dos drafts misma fecha (draft + remake) → se completa el equivocado | Cambiar firma a `completar_draft_resultado(draft_id, ganada)`. En app.py:4798 capturar el id que guardar_draft ya retorna |
| **P3** | **Critica** | `app.py:4638-4770` `_on_radar_listo()` | 5+ conexiones en bucle por refresh | 1.5s entre refrescos × 3 min draft = ~120 conexiones | Agrupar queries en obtener_datos_radar() con 1 sola conexion |
| **P4** | **Critica** | `lcu_api.py:48-87` `conectar()` + `request()` | Sin reintentos, sin relectura lockfile, except Exception | Cliente reiniciado = app desconectada silenciosamente | request con reintentos + backoff; reconnect() ante ConnectionError |
| **P5** | **Critica** | `config.json:2-3` | API key + password BD en texto plano | Credenciales productivas en el repo | .gitignore + config.example.json + rotar API key |
| **P6** | **Alta** | `recomendador.py:402-403` | int() trunca composicion (66+33=99) | Sesgo acumulativo en bonificaciones de _score_pick | Cambiar int() por round() |
| **P7** | **Alta** | `recomendador.py:522-630` | Pesos inline sin calibracion | 0.8, 0.6, 0.5, clamp [35,65] sin validacion | Suavizado bayesiano + calibracion con drafts_history |
| **P8** | **Alta** | `entrenador_ia.py:251-258` | RandomForest sin train/test split | Accuracy inflada, sin metrica de generalizacion | Split 80/20 estratificado + roc_auc + classification_report |
| **P9** | **Alta** | `app.py:2273-2291` `descargar_imagen()` | _cache_imagenes sin lock | ThreadPoolExecutor escribe dict mientras hilo principal lee | threading.Lock + os.replace() atomico |
| **P10** | **Alta** | `tags_champions.py:654-662` | _TAGS_CACHE carga lazy sin lock | Dos threads ejecutan _generar_tags() a la vez | threading.RLock con doble check |
| **P11** | **Alta** | `app.py:4676-4722` | _cache_rol_tipico sin lock | Race condition Live Client ↔ UI | threading.Lock o queue.Queue |
| **P12** | **Media** | `app.py:861-1405` | 545 lineas monolíticas | Imposible testear unitariamente | Extraer a src/coach.py con Strategy (Seccion 6) |
| **P13** | **Media** | `app.py:99-101` + `recomendador.py:544` | 4 mapeos de roles dispersos | Cambiar un rol requiere 4 ediciones | src/roles.py unico |
| **P14** | **Media** | `db_manager.py:40-49` + `recolector_masivo.py:97-106` | _cargar_config() duplicada | Cambios deben sincronizarse manualmente | Extraer a src/config.py |
| **P15** | **Media** | `entrenador_ia.py:207,294` | "MonkeyKing" duplicado | Mismo .replace() en dos funciones | normalizar_nombre_champ() en riot_api.py |
| **P16** | **Media** | `tests.py` (173 lineas) | 13 tests script, sin framework | Re-implementan logica en vez de probarla | Migrar a pytest + conftest.py (Seccion 7) |
| **P17** | **Media** | `app.py:3477` | season_cache nunca se limpia | Acumulacion indefinida en data/ | Job limpieza 48h: borrar mtime > 24h |
| **P18** | **Baja** | `recomendador.py:72-86` | AP_EXCEPTIONS, AP_TANKS, FRONTLANE_EXCLUDE sin uso | Codigo muerto | Eliminar y documentar la decision de usar tags_champions |
| **P19** | **Baja** | `app.py` (disperso) | 60+ colores hex inline | Cambio de tema requiere buscar/reemplazar masivo | src/theme.py con paleta semantica |
| **P20** | **Baja** | Todo el proyecto | Naming mixto espanol/ingles | Inconsistencia que crece con el tiempo | Elegir idioma canonico, aplicar progresivamente |

---

### Bloques de codigo refactorizados

#### P1 — Pool de conexiones PostgreSQL

Mantiene intacto el contrato `conn = obtener_conexion(); conn.close()` de los ~40 call sites existentes:

```python
# src/pg_pool.py (NUEVO)
from psycopg2 import pool
import threading

_pool: pool.ThreadedConnectionPool | None = None
_lock = threading.Lock()
_minconn = 2
_maxconn = 10

def _init_pool():
    global _pool
    if _pool is not None:
        return
    with _lock:
        if _pool is not None:
            return
        url = _obtener_db_url()
        _pool = pool.ThreadedConnectionPool(_minconn, _maxconn, url,
            cursor_factory=DictCursor, connect_timeout=30,
            keepalives=1, keepalives_idle=60,
            keepalives_interval=10, keepalives_count=3)

class _ConexionPooled:
    """Proxy: close() devuelve al pool en vez de cerrar el socket."""
    def __init__(self, real_conn):
        self._conn = real_conn
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def close(self):
        _pool.putconn(self._conn)         # ← vuelve al pool
    def cursor(self, **kwargs):
        return self._conn.cursor(**kwargs)

def obtener_conexion():
    _init_pool()
    real = _pool.getconn()                # ← toma del pool (sin TLS)
    return _ConexionPooled(real)          # ← wrapper con close() que devuelve
```

#### P2 — Draft ID en vez de fecha

```python
# db_manager.py — Nueva firma
def completar_draft_resultado(draft_id, ganada):
    conn = obtener_conexion()
    cur = conn.cursor()
    if ganada is None:
        cur.execute("UPDATE drafts_history SET resultado = 'completada' WHERE id = %s", (draft_id,))
    else:
        cur.execute("UPDATE drafts_history SET resultado = %s, ganada = %s WHERE id = %s",
                   ("victoria" if ganada else "derrota", 1 if ganada else 0, draft_id))
    conn.commit()
    conn.close()

# app.py:4798 — Almacenar draft_id
self._draft_id_actual = guardar_draft(mi_campeon, rol_api, bans_actuales, picks_al, picks_en, wr)
# ... al terminar la partida:
completar_draft_resultado(self._draft_id_actual, ganada)
```

#### P3 — Queries agrupadas del radar

```python
# reemplaza las 5+ conexiones en _on_radar_listo por 1 sola
def obtener_datos_radar(mi_rol_api, picks_al, picks_en):
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        champs_rol = obtener_campeones_por_rol(mi_rol_api, cur=cur)
        bans = obtenermejoresbaneos(mi_rol_api, cur=cur)
        matchups = {}
        for champ in picks_al + picks_en:
            matchups[champ] = obtener_peores_matchups(champ, mi_rol_api, cur=cur)
        return champs_rol, bans, matchups
    finally:
        conn.close()
```

#### P4 — LCU con reintentos

```python
# lcu_api.py — Modificar request()
import time as _time

_REQUEST_RETRIES = 3
_REQUEST_BACKOFF = 0.5

def request(self, method, endpoint, **kwargs):
    for intento in range(_REQUEST_RETRIES):
        if not self.port:
            if not self.conectar():
                if intento < _REQUEST_RETRIES - 1:
                    _time.sleep(_REQUEST_BACKOFF * (2 ** intento))
                continue
        try:
            res = requests.request(method, url, **kwargs)
            if res.status_code == 429:
                retry = int(res.headers.get("Retry-After", 1))
                _time.sleep(retry)
                continue
            return res
        except requests.ConnectionError:
            self.reconnect()
        except requests.Timeout:
            pass
        if intento < _REQUEST_RETRIES - 1:
            _time.sleep(_REQUEST_BACKOFF * (2 ** intento))
    return None
```

#### P5 — config.json seguro

```json
// config.example.json (NUEVO — se commitea)
{
  "API_KEY": "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "DATABASE_URL": "postgresql://user:password@host:5432/dbname",
  "user_settings": { ... }
}
```

Agregar a `.gitignore`:
```
config.json
```

#### P6 — round() en analizar_composicion

```python
# recomendador.py:402-403 — Cambio de una linea
pct_ad = min(100, round((ad_count / total_dmg) * 100))  # ← int → round
pct_ap = min(100, round((ap_count / total_dmg) * 100))  # ← int → round
```

---

### Roadmap de implementacion

```
Fase 1 — Estabilidad critica (Semanas 1-2)
  ├── P1: Pool de conexiones PostgreSQL
  ├── P2: completar_draft_resultado por draft_id
  ├── P3: Agrupar queries del radar
  ├── P4: LCU reintentos + reconnect
  └── P5: Secretos fuera del repo

Fase 2 — Correccion y robustez (Semanas 3-4)
  ├── P6: round() en composicion
  ├── P7: Suavizado bayesiano 5v5
  ├── P8: Split train/test en IA
  ├── P9: Lock en cache imagenes
  ├── P10: Lock en _TAGS_CACHE
  └── P11: Lock en _cache_rol_tipico

Fase 3 — Deuda tecnica (Semanas 5-6)
  ├── P12: Extraer coach.py
  ├── P13: src/roles.py
  ├── P14: src/config.py unico
  ├── P15: normalizar_nombre_champ()
  ├── P16: Migrar tests a pytest
  └── P17: Limpieza de season_cache

Fase 4 — Pulido (Semanas 7-8)
  ├── P18: Eliminar codigo muerto
  ├── P19: src/theme.py
  └── P20: Estandarizar naming
```

**Regla de hierro:** Nada de Fase 2+ entra en produccion sin el pool de conexiones (P1).

---

*Documento generado tras auditoria completa del codigo. Referencias archivo:linea verificadas contra el codigo real de lol-recommender-v2 (Junio 2026).*
