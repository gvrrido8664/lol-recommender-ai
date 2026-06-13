# Plan 003: Suite pytest sobre rutas críticas (sin BD real)

> **Instrucciones para el ejecutor**: Seguí este plan paso a paso. Corré cada
> comando de verificación y confirmá el resultado antes de avanzar. Si ocurre
> algo de "Condiciones STOP", pará y reportá — no improvises. Al terminar,
> actualizá la fila de este plan en `plans/README.md`.
>
> **Chequeo de drift (correr primero)**:
> `git diff --stat e31df97..HEAD -- src/recomendador.py src/coach.py tests/ tests.py`
> Si alguno cambió, compará las firmas de "Estado actual" con el código vivo
> antes de escribir tests; si no coinciden, es STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `e31df97`, 2026-06-13

## Por qué importa

La única red de seguridad es `tests.py`: 13 asserts estilo script, algunos
re-implementan la lógica en vez de llamarla (p.ej. el parsing del Live Client).
Ya existe el andamiaje pytest (`tests/conftest.py` con la fixture `mock_db`) pero
**cero tests pytest**. El código se está refactorizando activamente (esta sesión
movió ~5000 líneas), así que una suite pytest real sobre las rutas críticas
—análisis de composición, contrato del coach, winrate 5v5— da la malla para
refactorizar sin miedo. Este plan crea esa suite enfocándose en funciones que
**no requieren PostgreSQL** (las que ya funcionan offline, demostrado por los 13
tests actuales).

## Estado actual

Firmas reales (confirmadas en el código):

- `src/recomendador.py:369` — `def analizar_composicion(aliados):` → devuelve
  `(pct_ad, pct_ap, tank_count)`. Pura: usa `src/tags_champions.py`, **sin BD**.
  Bug histórico ya corregido: usa `round()` (no `int()`), líneas 387-388.
- `src/coach.py:160` — `def generar_reporte_coach(historial_games,
  nombre_invocador="Invocador", datos_perfil=None, datos_fatiga=None):` → devuelve
  un dict con claves `secciones`, `resumen`, `consejo_final`. Funciona con una
  lista de partidas en memoria, **sin BD** (lo prueban los tests de coaching
  actuales que pasan offline).
- `src/recomendador.py:507` — `def calcular_winrate_5v5(aliados, enemigos,
  pos_aliados=None, pos_enemigos=None):`. ⚠️ Puede consultar la BD internamente;
  ver STOP más abajo.

Patrón de los tests actuales (`tests.py`), ejemplo a imitar para los datos de
entrada (pero usando aserciones pytest, no `print("PASS")`):

```python
def test_coaching_anti_contradiction():
    from app import generar_reporte_coach   # <- en pytest, importar de src.coach
    fake = []
    for i in range(20):
        fake.append({"gameMode": "CLASSIC", "gameDuration": 1800,
            "participants": [{"championId": str((i%15)+1), "stats": {"win": i%2==0,
            "kills":5, "deaths":3, "assists":7, "totalMinionsKilled":150,
            "neutralMinionsKilled":20}}]})
    r = generar_reporte_coach(fake)
    assert len(r.get("secciones", [])) >= 1
```

Fixture disponible: `tests/conftest.py` define `mock_db` (SQLite en memoria que
monkeypatchea `src.db_manager.obtener_conexion`).

> **GOTCHA crítico del mock_db**: `src/db_manager.py` usa placeholders `%s`
> (psycopg2), pero SQLite usa `?`. Por eso las funciones que ESCRIBEN/LEEN la BD
> (guardar_draft, etc.) **fallarán** contra `mock_db` sin una capa de traducción.
> Este plan NO testea funciones de BD por eso (ver Fuera de alcance y STOP).

Comando de tests actual: `python tests.py` → `13/13 pasaron`. pytest **no está
instalado** ni en `requirements.txt`.

## Comandos que vas a necesitar

| Propósito | Comando | Esperado |
|-----------|---------|----------|
| Baseline actual | `python tests.py` | `13/13 pasaron` |
| Instalar pytest (en tu worktree) | `python -m pip install pytest` | exit 0 |
| Correr suite nueva | `python -m pytest tests/ -q` | todos pasan |
| Correr un archivo | `python -m pytest tests/test_composicion.py -q` | pasa |

## Alcance

**En alcance** (crear estos archivos):
- `tests/test_composicion.py` (nuevo)
- `tests/test_coaching.py` (nuevo)
- `requirements-dev.txt` (nuevo) — con `pytest` (no metas pytest en el
  `requirements.txt` de runtime).

**Fuera de alcance** (NO tocar):
- `tests.py` — dejarlo como está; sigue siendo el baseline (`13/13`). No lo borres
  ni lo migres entero en este plan.
- `tests/conftest.py` — no modificarlo salvo que el GOTCHA del `%s`/`?` te bloquee
  (en cuyo caso es STOP, no improvisar un parche).
- Cualquier `src/*.py` o `app.py` — este plan solo agrega tests, no cambia código
  de producción.
- Tests de funciones que tocan la BD (`guardar_draft`, `completar_draft_resultado`,
  `obtener_historial_drafts`, y cualquier cosa que llame `obtener_conexion`):
  fuera por el GOTCHA del placeholder. Son un follow-up.

## Git workflow

- Rama: `advisor/003-suite-pytest`
- Commit: `test: suite pytest para composicion y contrato de coaching`
- No pushear ni abrir PR salvo que el operador lo pida.

## Steps

### Step 1: Crear requirements-dev.txt e instalar pytest

Creá `requirements-dev.txt` con una línea: `pytest` (sin pin, o el pin que
prefieras). Instalalo en tu entorno.

**Verify**: `python -m pip install -r requirements-dev.txt` → exit 0; luego
`python -m pytest --version` → imprime una versión.

### Step 2: tests/test_composicion.py — función pura analizar_composicion

Creá `tests/test_composicion.py` que importe `from src.recomendador import
analizar_composicion` y cubra:
- **Happy path**: una lista de aliados conocidos AD-pesada → `pct_ad > pct_ap`.
- **Regresión del bug de redondeo**: con 2 campeones AD + 1 AP, `pct_ad + pct_ap`
  no debe sumar 99 por truncamiento; verificá que la suma sea coherente (>= 99 y
  consistente con `round`). (El fix usa `round()`; este test lo protege.)
- **Borde - lista vacía**: `analizar_composicion([])` → no debe crashear; según el
  código devuelve `(50, 50, ...)` cuando no hay daño total (línea 390). Afirmá ese
  contrato exacto leyendo primero qué devuelve.
- **Campeón desconocido**: un nombre que no esté en tags → no crashea.

Usá nombres de campeones reales (mirá `src/tags_champions.py` o los que usa
`tests.py`). Si no estás seguro del valor exacto que devuelve un caso borde,
**corré la función en un REPL primero** y afirmá el valor observado (no inventes).

**Verify**: `python -m pytest tests/test_composicion.py -q` → todos pasan.

### Step 3: tests/test_coaching.py — contrato de generar_reporte_coach

Creá `tests/test_coaching.py` que importe `from src.coach import
generar_reporte_coach` (NO `from app import ...`: importar `app` arranca todo el
módulo de UI). Cubrí:
- **Contrato**: con 20 partidas fake (usá el patrón del excerpt de arriba), el
  resultado tiene las claves `secciones`, `resumen`, `consejo_final`.
- **Cada sección bien formada**: cada item de `secciones` tiene `titulo` y `html`
  no vacíos (confirmá los nombres de campos leyendo `src/coach.py` primero).
- **Borde - historial vacío**: `generar_reporte_coach([])` no crashea y devuelve
  el contrato (afirmá lo que realmente devuelve; si lanza, ajustá el test a
  esperar el comportamiento real, no lo "deseado").
- **Anti-contradicción** (port del test existente): con un pool de >10 campeones,
  el reporte sugiere reducir/enfocar, no ampliar.

**Verify**: `python -m pytest tests/test_coaching.py -q` → todos pasan.

### Step 4: Confirmar que el baseline viejo sigue verde

**Verify**: `python tests.py` → `13/13 pasaron` (no tocaste código de producción).
`python -m pytest tests/ -q` → todos los tests nuevos pasan.

## Test plan

- `tests/test_composicion.py`: happy path AD-heavy, regresión de redondeo, lista
  vacía, campeón desconocido. Patrón estructural: tests pytest simples con
  `assert`, sin fixtures de BD (función pura).
- `tests/test_coaching.py`: contrato de claves, secciones bien formadas, historial
  vacío, anti-contradicción. Datos de entrada en memoria (patrón del excerpt).
- Verificación: `python -m pytest tests/ -q` → todos pasan; `python tests.py`
  sigue en `13/13`.

## Done criteria

TODAS deben cumplirse:

- [ ] `python -m pytest tests/ -q` pasa con al menos 6 tests nuevos
- [ ] `tests/test_composicion.py` y `tests/test_coaching.py` existen y importan de
      `src.*` (no de `app`)
- [ ] `requirements-dev.txt` existe con `pytest`
- [ ] `python tests.py` sigue imprimiendo `13/13 pasaron`
- [ ] No se modificó ningún archivo en `src/`, `ui/` ni `app.py` (`git status`)
- [ ] Fila de 003 actualizada en `plans/README.md`

## Condiciones STOP

Pará y reportá si:

- Al testear cualquier función aparece un error de placeholder SQL (`%s` vs `?`)
  o un intento de conexión real a PostgreSQL: significa que la función toca la BD;
  sacala del alcance y reportá (NO parchees `conftest.py` ni `db_manager.py` para
  forzarlo — eso es otro plan).
- `generar_reporte_coach([])` o `analizar_composicion([])` lanzan en vez de
  devolver: documentá el comportamiento real y reportá si parece un bug (podría
  ser un finding nuevo), en vez de "arreglar" el código (fuera de alcance).
- `import src.coach` falla por dependencias pesadas: reportá la traza.

## Notas de mantenimiento

- Follow-up natural (otro plan): resolver el GOTCHA `%s`/`?` del `mock_db` para
  poder testear `guardar_draft`/`completar_draft_resultado` (P2 del histórico ya
  cambió la firma a `draft_id`, así que sus tests valdrían la pena).
- Cuando esta suite crezca, considerar mover los 13 tests de `tests.py` a pytest y
  retirar `tests.py` (no en este plan).
- Revisor: verificar que los tests afirman valores observados del código real, no
  comportamiento idealizado; y que ningún test toca red/BD real.
