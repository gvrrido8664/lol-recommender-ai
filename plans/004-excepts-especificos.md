# Plan 004: Reemplazar `except:` desnudos por `except Exception` + logging

> **Instrucciones para el ejecutor**: Seguí este plan paso a paso. Corré cada
> verificación antes de avanzar. Si ocurre algo de "Condiciones STOP", pará y
> reportá. Al terminar, actualizá la fila de este plan en `plans/README.md`.
>
> **Chequeo de drift (correr primero)**:
> `git grep -nE "except:\s*$" -- app.py ui/ src/`
> Compará la lista resultante con la de "Estado actual". Si las ubicaciones
> difieren mucho (el código derivó), reconciliá por contenido, no por número de
> línea: buscá cada `except:` desnudo que exista hoy.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/003-suite-pytest.md (red de seguridad; si no está hecho,
  usá `python tests.py` como verificación — más débil, anotalo)
- **Category**: bug
- **Planned at**: commit `e31df97`, 2026-06-13

## Por qué importa

Hay ~21 cláusulas `except:` desnudas que capturan **toda** excepción, incluidas
`KeyboardInterrupt` y `SystemExit` (no se debería), y silencian errores reales
sin loguearlos. El caso más dañino: `cargar_settings`/`guardar_settings` en
`ui/helpers.py` — si guardar la config falla, el usuario pierde sus ajustes sin
ningún aviso. Cambiar `except:` por `except Exception:` (y agregar logging donde
el fallo importa) hace que Ctrl+C funcione, que los errores sean diagnosticables
y que los fallos silenciosos dejen rastro. Es un cambio de bajo riesgo y alto
valor de robustez.

## Estado actual

Ubicaciones exactas de `except:` desnudos (21), confirmadas con
`git grep -nE "except:\s*$"`:

```
app.py:361, 703, 717, 721
ui/helpers.py:367, 373, 388
ui/tabs/tab_partida.py:202, 250, 514, 570, 645, 652, 987
ui/tabs/tab_perfil.py:843
src/analizador_fatiga.py:47, 165
src/lcu_api.py:388
src/overlay.py:249, 349
src/recomendador.py:328
```

Caso prioritario — `ui/helpers.py` (settings, fallo silencioso):

```python
def cargar_settings():
    try:
        with open(os.path.join(CONFIG_DIR, "config.json"), "r", encoding="utf-8") as f:
            saved = json.load(f)
            return {**DEFAULT_SETTINGS, **saved.get("user_settings", {})}
    except:                                  # <- línea 367
        try:
            with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
                saved = json.load(f)
                return {**DEFAULT_SETTINGS, **saved.get("user_settings", {})}
        except:                              # <- línea 373
            return dict(DEFAULT_SETTINGS)

def guardar_settings(settings):
    try:
        ...
        return True
    except:                                  # <- línea 388  (fallo silencioso de guardado)
        return False
```

Convención de logging del repo: módulos usan `from src.logger import get_logger`
y `log = get_logger(__name__)`. En `app.py` ya existe `log`; en `ui/helpers.py`
NO hay logger todavía (habría que importarlo). En módulos sin logger, `print(...)`
ya se usa en varios sitios como fallback aceptable.

## Comandos que vas a necesitar

| Propósito | Comando | Esperado |
|-----------|---------|----------|
| Baseline tests | `python tests.py` | `13/13 pasaron` |
| Suite pytest (si 003 hecho) | `python -m pytest tests/ -q` | todos pasan |
| Localizar excepts | `git grep -nE "except:\s*$" -- app.py ui/ src/` | la lista de arriba |
| Confirmar 0 restantes | `git grep -nE "except:\s*$" -- app.py ui/ src/` | sin salida tras el fix |
| Compilar | `python -m py_compile app.py ui/*.py ui/**/*.py src/*.py` | exit 0 |

## Alcance

**En alcance** (modificar solo estos archivos, solo las líneas `except:`):
- `app.py`, `ui/helpers.py`, `ui/tabs/tab_partida.py`, `ui/tabs/tab_perfil.py`,
  `src/analizador_fatiga.py`, `src/lcu_api.py`, `src/overlay.py`,
  `src/recomendador.py`

**Fuera de alcance** (NO tocar):
- La LÓGICA dentro de los bloques try/except — solo cambiás la línea `except:`
  (y, en `cargar_settings`/`guardar_settings`, agregás una línea de log). No
  reescribas el flujo, no "mejores" el código de paso.
- `except Exception:` o `except SomeError:` que YA existen — no los toques.
- Cualquier otro archivo.

## Git workflow

- Rama: `advisor/004-excepts-especificos`
- Commit: `fix: reemplazar except desnudos por except Exception + logging`
- No pushear ni abrir PR salvo que el operador lo pida.

## Steps

### Step 1: Reemplazo mecánico `except:` → `except Exception:`

En cada una de las 21 ubicaciones, cambiá exactamente `except:` por
`except Exception:`, preservando indentación y el cuerpo. Es el cambio
load-bearing: deja de tragar `KeyboardInterrupt`/`SystemExit`.

NO uses un sed ciego global que pueda tocar strings o comentarios; cambiá cada
sitio confirmando que es una cláusula `except:` real. Trabajá archivo por archivo.

**Verify**:
- `git grep -nE "except:\s*$" -- app.py ui/ src/` → **sin salida**
- `python -m py_compile app.py ui/*.py ui/dialogs/*.py ui/tabs/*.py src/*.py` → exit 0

### Step 2: Logging en los fallos silenciosos de settings

En `ui/helpers.py`:
- Agregá al inicio del módulo (junto a los otros imports):
  `from src.logger import get_logger` y `log = get_logger(__name__)`.
- En el `except Exception:` de `guardar_settings` (antes `return False`), agregá
  antes del return: `log.warning("No se pudo guardar settings: %s", e)` — para eso
  cambiá la cláusula a `except Exception as e:`.
- En el `except Exception:` externo de `cargar_settings` (el de línea ~367), está
  bien que caiga al fallback silenciosamente (config.json puede no existir en
  primer arranque), así que NO es obligatorio loguear ahí; opcional
  `log.debug(...)`. El fallback final (línea ~373) puede quedar silencioso.

**Verify**: `python -c "from ui.helpers import cargar_settings, guardar_settings;
print(type(cargar_settings()))"` → imprime `<class 'dict'>` sin traza.

### Step 3: Verificación global

**Verify**:
- `python tests.py` → `13/13 pasaron`
- Si 003 está hecho: `python -m pytest tests/ -q` → todos pasan
- Arranque humo (offscreen): en un entorno con Qt,
  `QT_QPA_PLATFORM=offscreen python -c "from PySide6.QtWidgets import QApplication; QApplication([]); import app; print('ok')"`
  → imprime `ok` (no obligatorio si el entorno no tiene Qt; entonces basta py_compile).

## Test plan

No se agregan tests nuevos (cambio de robustez sin cambio de contrato observable).
La verificación es:
- 0 `except:` desnudos restantes (`git grep`).
- Todo compila (`py_compile`).
- `python tests.py` sigue en `13/13` y, si existe, la suite pytest pasa.
- `guardar_settings`/`cargar_settings` siguen devolviendo `bool`/`dict`.

Si querés blindarlo más (opcional): un test pytest que monkeypatchee `open` para
lanzar y verifique que `guardar_settings(...)` devuelve `False` y loguea, en
`tests/test_settings.py`. Solo si 003 ya creó la infraestructura pytest.

## Done criteria

TODAS deben cumplirse:

- [ ] `git grep -nE "except:\s*$" -- app.py ui/ src/` no devuelve nada
- [ ] `python -m py_compile app.py ui/*.py ui/dialogs/*.py ui/tabs/*.py src/*.py` exit 0
- [ ] `ui/helpers.py` loguea el fallo en `guardar_settings`
- [ ] `python tests.py` imprime `13/13 pasaron`
- [ ] Solo se modificaron los 8 archivos del alcance (`git status`)
- [ ] Fila de 004 actualizada en `plans/README.md`

## Condiciones STOP

Pará y reportá si:

- Tras cambiar a `except Exception:`, `python tests.py` baja de `13/13` o la suite
  pytest falla: algún bloque dependía de capturar `SystemExit`/`KeyboardInterrupt`
  (raro). Identificá cuál (por el test que rompe) y reportá; no lo revertás a
  `except:` sin más — puede ser un patrón intencional puntual que merece
  `except (Exception, KeyboardInterrupt)` explícito y comentado.
- Una ubicación de la lista ya no es un `except:` desnudo (el código derivó):
  saltala y anotalo; no fuerces.
- `from src.logger import get_logger` falla en `ui/helpers.py` por import circular:
  usá `print(...)` como fallback y reportá el circular.

## Notas de mantenimiento

- Regla para el futuro: prohibido `except:` desnudo; usar `except Exception` o el
  tipo específico. Considerar una regla de lint (ruff `E722`) en un plan futuro de
  tooling.
- Revisor: confirmar que solo cambiaron las cláusulas `except` (y el logging de
  settings), no la lógica de los cuerpos.
