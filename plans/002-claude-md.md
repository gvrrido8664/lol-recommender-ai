# Plan 002: Crear CLAUDE.md (arquitectura + comandos para agentes)

> **Instrucciones para el ejecutor**: Seguí este plan paso a paso. Corré cada
> comando de verificación. Si ocurre algo de "Condiciones STOP", pará y reportá.
> Al terminar, actualizá la fila de este plan en `plans/README.md`.
>
> **Chequeo de drift (correr primero)**:
> `git diff --stat e31df97..HEAD -- app.py ui/ src/ build_exe.ps1`
> Si la estructura de `ui/` cambió mucho, verificá los nombres de archivo del
> Step 1 contra la realidad (`ls ui/ ui/tabs/ ui/dialogs/`) antes de escribir.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `e31df97`, 2026-06-13

## Por qué importa

Este repositorio se opera con agentes (hay commits de agente en el historial y
este mismo conjunto de planes fue generado por uno). No existe `CLAUDE.md` ni
`AGENTS.md`, así que cada tarea de agente vuelve a descubrir desde cero la
arquitectura (que acaba de cambiar mucho: `app.py` pasó de ~6000 a ~870 líneas y
la UI se repartió en `ui/`), los comandos de ejecución/test/build y las
convenciones. Un `CLAUDE.md` conciso y correcto hace que cada tarea futura
arranque orientada y reduce errores. Es barato y sin riesgo (archivo nuevo).

## Estado actual

Arquitectura real tras el refactor (confirmá con `ls` si dudás):

- `app.py` (~870 líneas) — entry point. Hace `init_logging()`, luego
  `from ui.contexto import *`, define `LoLRecommenderApp(QMainWindow)` que **hereda
  7 mixins de pestaña**, y el bloque `if __name__ == "__main__"`.
- `ui/contexto.py` — **superficie compartida**: centraliza imports (Qt, `src.*`,
  diseño, helpers) y datos cargados una vez (`ITEMS_DICT`, `RUNAS_DICT`,
  `SPELLS_DICT`, `MAPEO_IDS_CAMPEONES`, `modelo_1v1`). app.py y los mixins hacen
  `from ui.contexto import *`.
- `ui/design.py` — constantes de color/paleta NEXUS (importa de `src/theme.py`).
- `ui/theme_qss.py` — `hoja_estilos_global()`: la hoja QSS global.
- `ui/tema_moderno.py` — base visual qdarktheme (acento rojo) bajo el QSS propio.
- `ui/helpers.py` — funciones/datos puros (settings, jungla, shards, matchup tips).
- `ui/dialogs/` — `settings_dialog.py`, `lp_graph.py`, `postgame_dialog.py`.
- `ui/tabs/` — un mixin por pestaña: `tab_perfil.py`, `tab_coaching.py`,
  `tab_vivo.py`, `tab_partida.py`, `tab_counters.py`, `tab_ia.py`, `tab_bans.py`.
- `src/` — lógica de dominio: `db_manager.py` (pool PG + `obtener_conexion`),
  `recomendador.py`, `coach.py`, `riot_api.py`, `lcu_api.py`, `tags_champions.py`,
  `roles.py`, `config.py`, `paths.py`, `theme.py`, `entrenador_ia.py`, etc.
- `tests.py` — 13 tests estilo script (`python tests.py`).
- `tests/conftest.py` — fixture pytest `mock_db` (SQLite en memoria); aún sin tests.
- `build_exe.ps1` — build PyInstaller (onedir) → `build_onedir/NEXUS/`.

Comandos verificados en recon:
- Ejecutar: `python app.py`
- Tests: `python tests.py` → `13/13 pasaron`
- Build: `powershell ./build_exe.ps1`

Convenciones observadas (`git log --oneline`): conventional commits en español
(`fix(ui):`, `refactor(ui):`, `feat(ui):`, `perf:`) + trailer
`Co-Authored-By: ...`. Naming de código mayormente en español. Secretos en
`config.json` (gitignored) o env `DATABASE_URL`; nunca commitear `config.json`.

## Comandos que vas a necesitar

| Propósito | Comando | Esperado |
|-----------|---------|----------|
| Tests baseline | `python tests.py` | `13/13 pasaron` |
| Listar estructura ui | `ls ui ui/tabs ui/dialogs` | los archivos del "Estado actual" |
| Confirmar que no existe CLAUDE.md | `ls CLAUDE.md` | "No such file" antes; el archivo después |

## Alcance

**En alcance** (único archivo a crear):
- `CLAUDE.md` (en la raíz del repo).

**Fuera de alcance** (NO tocar):
- Cualquier archivo `.py`, `build_exe.ps1`, `requirements.txt` — este plan es
  documentación pura. Si sentís la tentación de "arreglar algo de paso", no lo hagas.

## Git workflow

- Rama: `advisor/002-claude-md`
- Commit: `docs: agregar CLAUDE.md con arquitectura y comandos`
- No pushear ni abrir PR salvo que el operador lo pida.

## Steps

### Step 1: Escribir CLAUDE.md

Creá `CLAUDE.md` en la raíz con estas secciones (usá el "Estado actual" de arriba
como fuente de verdad; confirmá nombres con `ls` antes de escribir):

1. **Qué es** — app de escritorio PySide6 para LoL (perfil, coaching, radar de
   draft en vivo, partida en vivo, meta/builds, simulador 1v1, tier list de bans).
2. **Cómo correr / testear / buildear** — los 3 comandos verificados de arriba.
3. **Arquitectura** — la lista de `app.py` + `ui/` (contexto, design, theme_qss,
   tema_moderno, helpers, dialogs/, tabs/) + `src/`. Explicá el patrón clave:
   **`LoLRecommenderApp` hereda 7 mixins de pestaña** y todos comparten
   `from ui.contexto import *`; las señales Qt se declaran en la clase final, no
   en los mixins. El trabajo bloqueante (red/BD) va en hilos que emiten señales
   (patrón `Signal` + `threading.Thread` + `.emit()`); ver `_fetch_perfil` /
   `_inicializar_db_background`.
4. **Base de datos** — pool de conexiones en `src/db_manager.py`
   (`obtener_conexion()` devuelve conexión del pool; `.close()` la devuelve, no
   cierra el socket). Nunca abras psycopg2 directo.
5. **Convenciones** — conventional commits en español + trailer Co-Authored-By;
   naming en español; al editar la UI, reutilizar constantes de `ui/design.py` y
   `hoja_estilos_global()` en vez de colores hardcodeados.
6. **Seguridad** — `config.json` está gitignored y contiene secretos reales;
   NUNCA commitearlo; usar `config.example.json` como plantilla; preferir env
   `DATABASE_URL`.
7. **Tests** — actual: `python tests.py` (13 tests script). Migración a pytest en
   curso: `tests/conftest.py` tiene la fixture `mock_db`.

Mantenelo conciso (objetivo: 60-100 líneas). Es un mapa, no un manual.

**Verify**: `test -f CLAUDE.md && wc -l CLAUDE.md` → el archivo existe y tiene
contenido (decenas de líneas, no vacío).

### Step 2: Verificar que no se rompió nada

**Verify**: `python tests.py` → `13/13 pasaron` (no debería cambiar nada, pero
confirma que no tocaste código por accidente). `git status` → solo `CLAUDE.md`
nuevo.

## Test plan

Sin tests de código (documentación). Verificación:
- `CLAUDE.md` existe y cubre las 7 secciones.
- Cada comando citado en CLAUDE.md realmente funciona: probá `python tests.py`.
- `git status` muestra únicamente `CLAUDE.md` como cambio.

## Done criteria

TODAS deben cumplirse:

- [ ] `CLAUDE.md` existe en la raíz y contiene las secciones: qué es, comandos,
      arquitectura, base de datos, convenciones, seguridad, tests
- [ ] Los comandos documentados son los reales (`python app.py`, `python tests.py`,
      `powershell ./build_exe.ps1`)
- [ ] `python tests.py` imprime `13/13 pasaron`
- [ ] `git status` solo muestra `CLAUDE.md` (ningún otro archivo modificado)
- [ ] Fila de 002 actualizada en `plans/README.md`

## Condiciones STOP

Pará y reportá si:

- La estructura real de `ui/` (vía `ls`) no coincide con el "Estado actual" (el
  repo derivó): documentá la estructura real y reportá la discrepancia antes de
  escribir afirmaciones incorrectas.
- Algún comando documentado falla al probarlo (p.ej. `python tests.py` no da
  `13/13`): no documentes un comando roto; reportá.

## Notas de mantenimiento

- Cuando se agregue/quite una pestaña o cambie la lista de mixins en `app.py`,
  actualizar la sección Arquitectura de `CLAUDE.md`.
- Si la migración a pytest (plan 003) se completa, actualizar la sección Tests.
- Revisor: verificar que CLAUDE.md no contradiga el código actual (es peor un doc
  desactualizado que ninguno).
