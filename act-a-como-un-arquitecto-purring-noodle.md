# Plan: Auditoría profunda + documento `PLAN_DE_MEJORAS.md` en la raíz

## Contexto

El usuario pidió una auditoría completa del proyecto (recomendador de drafts / coaching en tiempo real para LoL: app PySide6 de ~6.600 líneas en `app.py`, módulos en `src/`, PostgreSQL remoto en Render, tests en `tests.py`) y que el resultado se guarde como un **Plan Completo de Mejoras en un MD en la raíz del repo**, estructurado obligatoriamente en 8 pasos.

La auditoría ya está hecha (3 agentes de exploración + 1 agente de diseño verificaron hallazgos contra el código real). **El único cambio a ejecutar es escribir un archivo nuevo: `PLAN_DE_MEJORAS.md` en la raíz.** No se modifica ningún código.

## Entregable

Crear `c:\Users\Nacho\Desktop\lol-recommender-ai\PLAN_DE_MEJORAS.md` (en español, con referencias `archivo:línea` reales) con esta estructura:

**Cabecera:** título, fecha (2026-06-11), alcance (app.py + 21 módulos src/, ~12.000 líneas propias), índice.

### Sección 1 — Arquitectura y patrones de diseño
- Diagnóstico: `app.py` es un God Object (GUI + threading + DB + APIs + dominio). Peores funciones: `generar_reporte_coach` (app.py:861-1405, ~545 líneas), `_renderizar_historial` (3798-4008), `_on_radar_listo` (4638-4770), `armar_tab_perfil` (2736-3019).
- Contraste positivo: `recolector_masivo.py` ya tiene patrones production-grade (RiotRateLimiter 123-189, conexiones thread-local 50-73, cola persistente, 429/Retry-After) que deben exportarse al resto.
- Arquitectura objetivo por capas: `ui/` → `servicios/` → `repositorios/` → `infra/`.
- Tabla de patrones concretos: **Singleton** (pool PG + `_TAGS_CACHE` con lock), **Repository** (extraer SQL de recomendador/db_manager), **Observer** (formalizar señales Qt en un `MonitorFases`), **Factory** (`FuenteDatosPartida.crear(fase)` → LCU / Live Client / Riot API), **Strategy** (reglas de coaching).

### Sección 2 — Calidad de código / Clean Code
- Código muerto: `AP_EXCEPTIONS`/`AP_TANKS`/`FRONTLANE_EXCLUDE` (recomendador.py:72-86).
- Duplicación: `_cargar_config()` duplicada (db_manager.py:40-49 y recolector_masivo.py:80-89); normalización "MonkeyKing" duplicada (entrenador_ia.py:207 y 294); patrón query+fallback repetido 6× en recomendador.py.
- 4 mapeos de roles dispersos (UI_ROLES/ROL_TO_API/API_TO_ROL + `pos_equivalentes` en recomendador.py:544) → `src/roles.py`.
- `except Exception` genéricos (lcu_api.py:65, 87, 356, 376, 389, 540; app.py:2293; recomendador.py:625).
- Números mágicos (min_partidas 5/10/20/50, factor bayesiano 3, pesos 0.8/0.6/0.5/1.5/1.2), 60+ colores hex → `src/theme.py`, naming español/inglés mixto.

### Sección 3 — Rendimiento y caché
- **Problema central: sin pool de conexiones** — `obtener_conexion()` (db_manager.py:63-97) abre socket TLS nuevo a Render por llamada; un refresh de radar = 8-10 conexiones; límite Render free ~20.
- Cachés: `_TAGS_CACHE` ok pero carga lazy sin lock; `season_cache_{puuid}.json` (24h) nunca se limpia; `_cache_imagenes` (app.py:1744, 2270-2294) sin lock desde hilos; `_cache_rol_tipico` nunca se invalida (TTL por parche).
- N+1: `recomendar_picks_vivo` (recomendador.py:435-520) ~100 round-trips por recomendación → query agregada con GROUP BY; `_on_radar_listo` abre 5+ conexiones en bucle.

### Sección 4 — Resiliencia APIs externas
- LCU: sin reintentos, sin relectura de lockfile al reiniciar el cliente, `verify=False` (inevitable, documentar y acotar).
- Live Client (2999): timeout 2s ok, pero "Entrando a la Grieta" infinito si Live Client y LCU fallan → contador de intentos + estado de error accionable.
- Plan de contingencia: datos parciales/listas vacías (parsing defensivo ya existe en obtener_liveclient_data:490-525, formalizarlo), jugadores duplicados, desconexiones (lockfile stale).
- Reutilizar `peticion_segura` del recolector (429/Retry-After/backoff) en riot_api/lcu_api.
- Seguridad: API key y DATABASE_URL en texto plano en config.json → env vars + config.example.json + rotación.

### Sección 5 — Lógica de dominio y precisión
- `analizar_composicion` (recomendador.py:384-407): `int()` trunca (2 AD + 1 AP → 66/33, suma 99) y sesga umbrales ≥60 de `_score_pick` → `round()`.
- `calcular_winrate_5v5` (522-630): pesos a mano, clamp [35,65], escalones de ponderación de muestras → constantes nombradas + suavizado bayesiano uniforme `(wr·n + 50·K)/(n+K)` + calibración empírica usando `wr_predicho` vs `ganada` que ya se guarda en drafts_history.
- `entrenador_ia.py`: RandomForest sin train/test split (accuracy inflada) → split 80/20 estratificado + roc_auc.

### Sección 6 — Integridad del coaching / anti-contradicciones
- Extraer `generar_reporte_coach` a `src/coach.py` con Strategy: `ReglaCoach(tema, prioridad, evaluar)` → `Hallazgo`, más un `ResolutorContradicciones` con tabla de temas mutuamente excluyentes (agresividad vs seguridad, farmeo vs roaming, pool amplio vs especialización) que conserva el de mayor severidad.
- Garantía de respuesta completa: contrato `{secciones, resumen, consejo_final}` siempre presente (ya testeado en tests.py:39-50; ampliar).

### Sección 7 — Cobertura de tests
- Estado: 13 tests estilo script; algunos re-implementan lógica en vez de llamarla.
- Plan: migrar a pytest + `conftest.py` con fixture que monkeypatchea `obtener_conexion`; casos borde nuevos: composición vacía, redondeo suma 100, campeón desconocido → `_DEFAULT_TAG`, equipos incompletos en 5v5, clamp WR, stats malformadas del liveclient, `completar_draft_resultado` con id None, validación de `wr_predicho` guardado.

### Sección 8 — Plan de acción
- Tabla de ~20 filas con **Prioridad (Crítica/Alta/Media/Baja) | Archivo:función | Problema | Justificación | Solución con bloque de código**. Críticas: (1) pool de conexiones, (2) `completar_draft_resultado` por fecha → race condition, usar el `id` que `guardar_draft` ya devuelve, (3) `_on_radar_listo` conexiones en bucle, (4) reintentos LCU + relectura lockfile, (5) secretos en config.json.
- Bloques de código refactorizados ya diseñados y verificados contra firmas reales (incluirlos en el doc):
  - **P1**: `ThreadedConnectionPool` con proxy `_ConexionPooled` cuyo `close()` devuelve al pool — mantiene intacto el contrato `conn = obtener_conexion(); ...; conn.close()` de los ~40 call sites, + context manager `conexion()` para código nuevo.
  - **P2**: `completar_draft_resultado(draft_id, ganada)` + guardar `self._draft_id_actual` en app.py:4798.
  - **P3**: `LCUConnector.request` con reintentos/backoff y `reconnect()` ante ConnectionError.
  - **P4**: excepciones específicas en `conectar` (`(OSError, IndexError, ValueError)`).
  - **P5**: `round()` en analizar_composicion.
  - **P6**: `threading.Lock` + escritura atómica `os.replace` en `descargar_imagen`.
  - **P7**: batería de tests pytest de casos borde.
- Roadmap: Fase 1 estabilidad crítica (ítems 1-5) → Fase 2 corrección/robustez (6-11) → Fase 3 deuda técnica (12-17) → Fase 4 pulido (18-20). Regla: nada de Fase 2+ sin el pool en producción.

## Verificación
- El MD se crea en la raíz y renderiza correctamente (tabla de prioridades, bloques de código con sintaxis Python).
- Las referencias archivo:línea citadas fueron verificadas durante la auditoría (spot-check hecho en db_manager.py y recomendador.py:384-407).
- No se toca ningún archivo de código: `git status` solo debe mostrar el nuevo `PLAN_DE_MEJORAS.md`.
