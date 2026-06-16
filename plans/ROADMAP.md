# ROADMAP — Siguientes pasos a mejorar (NEXUS)

**Fecha:** 2026-06-16
**Estado:** fuente de verdad actual. Supera a `PLAN_DE_MEJORAS_2026-06_historico.md`,
que predata la modularización de `app.py` y tenía varias prioridades ya resueltas.

Este documento prioriza el trabajo pendiente en tres áreas: **Seguridad/Distribución**,
**Calidad/Tests** y **Funcionalidades/UX**. Cada ítem tiene un id estable (S/Q/F) para
referenciarlo en commits y ramas (`advisor/NNN-descripcion`).

---

## Ya resuelto (no re-hacer)

- ✅ **Pool de conexiones PostgreSQL** — `ThreadedConnectionPool` en `src/db_manager.py`
  (era P1 crítico del plan viejo).
- ✅ **Secretos fuera del repo** — `config.json` gitignored + cifrado embebido
  (`src/secretos.py`, `scripts/cifrar_secretos.py`, blob `secretos.bin` en el bundle).
- ✅ **Modularización del God Object** — `app.py` pasó de ~6640 a ~945 líneas; hereda
  7 mixins de pestaña en `ui/tabs/`.
- ✅ **Migración parcial a pytest** — `tests/` con `conftest.py` (fixture `mock_db`),
  `test_coaching.py`, `test_composicion.py`, más `tests.py` (11 baseline).

---

## Área 1 — Seguridad y distribución

| # | Pri | Ítem | Detalle |
|---|-----|------|---------|
| **S1** | Crítica | **Backend proxy** | Solución robusta al stopgap de cifrado actual (la clave de descifrado viaja en el binario y es extraíble). Montar un FastAPI en Render/Railway que guarde `API_KEY` y `DATABASE_URL` server-side; el cliente habla con el backend por HTTPS con un token de app. Los secretos dejan de viajar en el instalador. Endpoints a derivar de las funciones de `db_manager.py` (draft, lp, cache, emocional, counters) + un passthrough con rate-limit/caché para Riot (basado en `riot_public_api.py`). Cumple además los ToS de producción de Riot. |
| **S2** | Crítica (⚠️ flagged) | **Rotar credenciales + limpiar historial git** | La API key sigue expuesta en el historial (`git show 7d45c4c:config.json`). Pendiente de decisión del dueño: (1) regenerar API key Riot, (2) rotar password de Supabase, (3) `git filter-repo` sobre un clon espejo para purgar `config.json` (destructivo: reescribe historial compartido, requiere coordinar forks/clones). **No ejecutar sin OK explícito.** |
| **S3** | Alta | **RLS / mínimo privilegio en Supabase** | El cliente ejecuta DDL en runtime: `inicializar_db()` corre `CREATE TABLE`/`CREATE INDEX`/`ALTER`. Mover eso a una migración server-side y restringir el rol de BD a solo las operaciones necesarias (sin DDL). Si se monta S1, el proxy es el único con credenciales de escritura. |
| **S4** | Media | **Certificado de firma real (CA)** | Hoy `build_exe.ps1` firma self-signed → SmartScreen bloquea en otras PCs ("Windows protegió tu PC"). Para distribución amplia: certificado de code-signing de una CA (Sectigo/DigiCert) o EV. |
| **S5** | Baja | **Auto-update** | No existe. Evaluar un updater simple que descargue el nuevo setup y verifique su firma antes de aplicarlo. |

---

## Área 2 — Calidad de código y tests

| # | Pri | Ítem | Detalle |
|---|-----|------|---------|
| **Q1** | Crítica | **CI en GitHub Actions** | Solo existe `.github/workflows/keepalive-db.yml`. Añadir un workflow que en push/PR corra `python tests.py` + `python -m pytest tests/ -q`. Base para todo lo demás. |
| **Q2** | Alta | **Resolver gotcha `mock_db` + tests de BD** | `tests/conftest.py` usa placeholder `?` (SQLite) y `db_manager.py` usa `%s` (psycopg2): hoy no se pueden testear funciones de BD contra el mock sin traducción. Añadir capa de traducción en el fixture (o un adaptador) y escribir tests de `guardar_draft`, `completar_draft_resultado`, `registrar_lp`, `obtener_historial_lp`. |
| **Q3** | Alta | **Cerrar `except` silenciosos** | 2 `except: pass` desnudos en `src/lcu_api.py:368,387` + ~20 `except Exception:` sin log repartidos. Acotar a excepciones esperadas y loguear con `src/logger.py`. Incluye el parsing frágil del lockfile en `lcu_api.py` (split por `:` sin validar longitud). |
| **Q4** | Alta | **Linter/formatter** | No hay ninguno configurado. Añadir `ruff` (y `black` opcional) con `pyproject.toml`, y meterlo al CI (Q1). |
| **Q5** | Media | **Refactor `generar_reporte_coach`** | Función monstruo (~762 líneas) en `src/coach.py`. Dividir con patrón Strategy (reglas pluggables `ReglaCoach` → `Hallazgo`, con resolutor de contradicciones). Habilita tests unitarios por regla. |
| **Q6** | Media | **Helper de threading + locks** | Patrón `threading.Thread(target=..., daemon=True).start()` repetido (~8 sitios en `app.py` + mixins). Extraer a un helper (p.ej. `ejecutar_en_hilo(fn, signal_done)`). Revisar caches compartidos sin lock (`_cache_imagenes`, `_TAGS_CACHE`, `_cache_rol_tipico`). |
| **Q7** | Media | **Dependencias** | Fijar `psycopg2-binary` explícito (el código hace `import psycopg2`); documentar el pin de Python 3.14; vigilar el `InconsistentVersionWarning` de sklearn — los `.pkl` están atados a la versión que los serializó, re-entrenar/re-serializar al subir sklearn. |
| **Q8** | Baja | **Type hints + naming** | Ampliar type hints (hoy parciales) y decidir idioma canónico (mezcla español/inglés). Aplicar de forma progresiva. |

---

## Área 3 — Funcionalidades y UX

| # | Pri | Ítem | Detalle |
|---|-----|------|---------|
| **F1** | Alta | **Cerrar features a medio camino** | Decidir por cada una: completar o retirar. Auto-import de items (frágil ante cambios de formato LCU), export de skill order (depende de API key local, inestable), etiquetado emocional (hoy manual, casi nadie lo usa → automatizar inferencia o quitar), timeline en post-game (depende de Riot Public API disponible). |
| **F2** | Media | **Feedback visual** | Skeleton/loaders durante el precompute del radar (hoy es invisible para el usuario), toasts en vez de labels de error, y explicitar los fallbacks silenciosos ("sin datos por X") para que el usuario entienda por qué falta info. |
| **F3** | Media | **Tier list de bans más útil** | `ui/tabs/tab_bans.py` es solo lectura de tabla. Añadir contexto de meta/elo y refresco; hoy no se adapta a lo que está en meta. |
| **F4** | Baja | **Ajustes configurables** | Exponer umbrales en settings (min partidas, elo, season) y una opción de re-descargar/refrescar datos puntuales. |
| **F5** | Baja | **Export de reportes** | Coaching/perfil a PDF o imagen para compartir. |

---

## Secuencia sugerida

```
Fase 1 — Fundaciones (red de seguridad antes de tocar lógica)
  ├── Q1  CI en GitHub Actions
  ├── Q4  Linter/formatter (ruff)
  └── Q3  Cerrar except silenciosos

Fase 2 — Seguridad real
  ├── S1  Backend proxy
  ├── S3  Mínimo privilegio en Supabase
  └── S2  (decisión) rotación + limpieza de historial

Fase 3 — Robustez
  ├── Q2  Tests de BD (gotcha mock_db)
  ├── Q5  Refactor coach.py
  ├── Q6  Helper threading + locks
  └── Q7  Dependencias

Fase 4 — Producto
  ├── F1  Cerrar features a medio camino
  ├── F2  Feedback visual
  └── F3–F5  Bans, ajustes, export

Distribución (cuando crezca la base de usuarios)
  ├── S4  Certificado de firma real
  └── S5  Auto-update
```

**Regla:** nada de Fase 2+ entra sin la red de seguridad de Fase 1 (CI + linter).
