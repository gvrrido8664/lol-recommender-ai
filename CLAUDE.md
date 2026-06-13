# NEXUS - LoL Recommender v2

App de escritorio **PySide6** (Python 3.14) para League of Legends: perfil de jugador,
coaching pro, radar de draft en vivo, partida en vivo, meta/builds, simulador 1v1,
tier list de bans. Backend **PostgreSQL** en Render; APIs Riot y LCU.

## Comandos

```bash
python app.py                  # ejecutar la app
python tests.py                # 13 tests (baseline)
powershell ./build_exe.ps1     # build PyInstaller (onedir -> build_onedir/NEXUS/)
python -m pytest tests/ -q     # suite pytest (si esta instalada)
```

## Arquitectura

```
app.py              ~870 lineas, entry point, hereda 7 mixins de pestana
ui/contexto.py      imports compartidos + datos cargados una vez (ITEMS_DICT, RUNAS_DICT, MAPEO_IDS_CAMPEONES...)
ui/design.py        paleta de colores NEXUS (importa src/theme.py)
ui/theme_qss.py     hoja QSS global
ui/tema_moderno.py  base visual qdarktheme
ui/helpers.py       funciones puras (settings, jungla, shards, tips)
ui/dialogs/         settings_dialog, lp_graph, postgame_dialog
ui/tabs/            7 mixins: tab_perfil, tab_coaching, tab_vivo, tab_partida,
                    tab_counters, tab_ia, tab_bans
src/                logica: db_manager, recomendador, coach, riot_api, lcu_api,
                    tags_champions, roles, config, paths, theme, entrenador_ia...
```

**Patron clave**: `LoLRecommenderApp` hereda los 7 mixins de pestana. Todos comparten
`from ui.contexto import *`. Las senales Qt se declaran en la clase final (app.py),
no en los mixins. Trabajo bloqueante (red/BD) va en hilos que emiten senales
(patron `Signal` + `threading.Thread` + `.emit()`). Ver `_fetch_perfil` /
`_inicializar_db_background`.

## Base de datos

Pool de conexiones en `src/db_manager.py`. Usar `obtener_conexion()` que devuelve
una conexion del pool; `.close()` la devuelve al pool (no cierra el socket).
**Nunca** abrir psycopg2 directo. Statement timeout configurado a 30s.

Tablas principales: `matches`, `participantes`, `estado_emocional`, `lp_history`,
`drafts_history`, `cola`, `checkpoint`.

## Convenciones

- **Commits**: conventional commits en espanol (`fix(ui):`, `feat(src):`, `perf:`...)
  + trailer `Co-Authored-By: ...`
- **Naming**: codigo en espanol (variables, funciones, comentarios)
- **UI**: reutilizar constantes de `ui/design.py` y `hoja_estilos_global()` en vez de
  colores hardcodeados
- **Ramas**: `advisor/NNN-descripcion` para planes de mejora

## Seguridad

- `config.json` esta **gitignored** y contiene secretos reales (API key Riot,
  DATABASE_URL). **NUNCA** commitearlo.
- `config.example.json` es la plantilla sin valores reales.
- Preferir variable de entorno `DATABASE_URL` sobre config.json cuando este disponible.

## Tests

- **Actual**: `python tests.py` (13 tests script). Cubre LiveClient, coaching, tags, logros.
- **Pytest**: `tests/conftest.py` tiene fixture `mock_db` (SQLite en memoria).
  Suite pytest en `tests/` para composicion y coaching (plan 003).
- **GOTCHA**: `mock_db` usa placeholder `?` de SQLite pero `db_manager.py` usa `%s`
  de psycopg2. No testear funciones de BD directo contra mock_db sin capa de
  traduccion.
