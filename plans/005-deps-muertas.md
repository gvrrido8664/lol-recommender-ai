# Plan 005: Eliminar dependencias muertas de requirements.txt

> **Instrucciones para el ejecutor**: Seguí este plan paso a paso. Corré cada
> verificación. Si ocurre algo de "Condiciones STOP", pará y reportá. Al
> terminar, actualizá la fila de este plan en `plans/README.md`.
>
> **Chequeo de drift (correr primero)**:
> `git diff --stat e31df97..HEAD -- requirements.txt`
> Si cambió, reubicá las líneas por NOMBRE de paquete (no por número de línea).

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: deps
- **Planned at**: commit `e31df97`, 2026-06-13

## Por qué importa

`requirements.txt` lista 6 paquetes que el código **no importa en ningún lado**:
`customtkinter` (framework GUI viejo; la app usa PySide6), `fastapi`, `uvicorn`,
`starlette` (stack web no usado), `PyPDF2` (PDF) y `keyboard` (los hotkeys
globales se removieron — ver comentario "In-game timer and hotkeys removed" en
`app.py`). Arrastran tiempo de instalación, peso del build PyInstaller y
confusión sobre qué es realmente la app. Quitarlos es limpieza de bajo riesgo,
con la salvedad de verificar que ninguno sea dependencia transitiva de un paquete
que sí se usa.

## Estado actual

Confirmado: `grep -rilE "import X|from X" app.py ui/ src/` da **0 usos** para los
6 paquetes. Líneas en `requirements.txt` (commit `e31df97`):

```
10:customtkinter==5.2.2
12:fastapi==0.136.1
19:keyboard==0.13.5
30:PyPDF2==3.0.1
46:starlette==1.0.0
53:uvicorn==0.47.0
```

⚠️ **Cuidado con transitivas**: `customtkinter` depende de `darkdetect`, que
**SÍ se usa** (lo necesita `pyqtdarktheme`/`tema_moderno.py`) — `darkdetect` debe
QUEDARSE. `fastapi` arrastra `starlette`/`pydantic`/`anyio`; `uvicorn` arrastra
`click`/`h11`. Este plan quita solo los 6 de arriba (los de nivel superior y
claramente muertos); los transitivos que queden listados (pydantic, anyio, etc.)
son inofensivos y se tratan, si acaso, en un follow-up con verificación de venv
limpio.

La app se ejecuta con `python app.py`; tests con `python tests.py` (`13/13`).

## Comandos que vas a necesitar

| Propósito | Comando | Esperado |
|-----------|---------|----------|
| Confirmar 0 imports | `grep -rilE "import (customtkinter\|fastapi\|uvicorn\|starlette\|PyPDF2\|keyboard)\|from (customtkinter\|fastapi\|uvicorn\|starlette\|PyPDF2\|keyboard)" app.py ui/ src/` | sin salida |
| Quién depende de un pkg | `python -m pip show <pkg>` | mirar "Required-by" |
| Baseline tests | `python tests.py` | `13/13 pasaron` |
| Verificación en venv limpio | (ver Step 3) | app importa + tests pasan |

## Alcance

**En alcance** (único archivo):
- `requirements.txt` — quitar las 6 líneas listadas.

**Fuera de alcance** (NO tocar):
- `darkdetect` — se usa (transitiva viva de qdarktheme). NO quitar.
- Las transitivas que queden (pydantic, pydantic_core, annotated-types, anyio,
  h11, click, starlette si no la quitás, etc.) — no las toques en este plan.
- `build_exe.ps1` — sus `--exclude-module` de PySide6 no se relacionan con esto.
- Cualquier código `.py`.

## Git workflow

- Rama: `advisor/005-deps-muertas`
- Commit: `chore(deps): quitar dependencias no usadas (customtkinter, fastapi, uvicorn, starlette, PyPDF2, keyboard)`
- No pushear ni abrir PR salvo que el operador lo pida.

## Steps

### Step 1: Confirmar 0 imports (no asumir)

Corré el grep de "Comandos". Debe dar **sin salida**. Si algún paquete aparece
importado, sacalo de la lista a borrar y reportá.

**Verify**: el grep no devuelve nada.

### Step 2: Quitar las 6 líneas de requirements.txt

Borrá exactamente las líneas de `customtkinter`, `fastapi`, `keyboard`, `PyPDF2`,
`starlette`, `uvicorn` en `requirements.txt`. No toques `darkdetect` ni ninguna
otra.

**Verify**: `grep -nE "^(customtkinter|fastapi|uvicorn|starlette|PyPDF2|keyboard)==" requirements.txt`
→ sin salida. `grep -n "^darkdetect==" requirements.txt` → sigue presente.

### Step 3: Verificar en un venv limpio (verificación de oro)

Para probar que ninguno era necesario en runtime, instalá `requirements.txt` en
un entorno limpio y confirmá que la app importa y los tests pasan:

```
python -m venv .venv_check
.venv_check/Scripts/python.exe -m pip install -r requirements.txt   # (Linux/mac: .venv_check/bin/python)
QT_QPA_PLATFORM=offscreen .venv_check/Scripts/python.exe -c "import app; print('IMPORT OK')"
.venv_check/Scripts/python.exe tests.py
```

**Verify**: el import imprime `IMPORT OK` y `tests.py` imprime `13/13 pasaron`.
Borrá `.venv_check/` al terminar (no commitearlo; debe estar gitignored o lo
eliminás a mano).

> Si no podés crear un venv en tu entorno, hacé la verificación mínima en el
> entorno actual: `QT_QPA_PLATFORM=offscreen python -c "import app; print('ok')"`
> y `python tests.py`. Anotá que la verificación de venv limpio quedó pendiente.

### Step 4: Limpieza

Asegurate de que `.venv_check/` no quede en el árbol (`git status` no debe
mostrarlo). Si aparece, borralo.

**Verify**: `git status` muestra solo `requirements.txt` modificado.

## Test plan

Sin tests de código. Verificación:
- 0 imports de los 6 paquetes (grep).
- En venv limpio con el nuevo `requirements.txt`: `import app` OK y `tests.py` en
  `13/13`.
- `git status` limpio salvo `requirements.txt`.

## Done criteria

TODAS deben cumplirse:

- [ ] Las 6 líneas quitadas de `requirements.txt`; `darkdetect` sigue presente
- [ ] `import app` funciona en venv limpio instalado desde el nuevo requirements
      (o, fallback, en el entorno actual) — imprime OK
- [ ] `python tests.py` imprime `13/13 pasaron`
- [ ] `.venv_check/` no quedó en el árbol
- [ ] Solo `requirements.txt` modificado (`git status`)
- [ ] Fila de 005 actualizada en `plans/README.md`

## Condiciones STOP

Pará y reportá si:

- El grep encuentra que alguno de los 6 SÍ se importa: ese paquete no está muerto;
  sacalo del borrado y reportá.
- En el venv limpio, `import app` o `tests.py` fallan por un `ModuleNotFoundError`
  de algo que quitaste o de su transitiva: significa que era necesario (directa o
  indirectamente). Reincorporá esa línea y reportá cuál era.
- `pip show <pkg>` muestra en "Required-by" un paquete que la app usa: es
  transitiva viva; no la quites.

## Notas de mantenimiento

- Follow-up opcional: tras quitar fastapi/uvicorn, sus transitivas (starlette,
  pydantic, anyio, h11, click, etc.) podrían también quitarse, pero solo con la
  verificación de venv limpio del Step 3 — algunas pueden ser usadas por otra
  herramienta (p.ej. `click` por varios CLIs). No las quites a ciegas.
- Revisor: confirmar que `darkdetect` sigue en requirements (lo necesita el tema).
