# Implementation Plans

Generados por el skill `improve` el 2026-06-13 contra el commit `e31df97`.
Ejecutar en el orden de abajo salvo que las dependencias digan otra cosa. Cada
ejecutor: leer el plan completo antes de empezar, respetar sus condiciones STOP,
y actualizar su fila al terminar.

Contexto del repo (común a todos los planes): app de escritorio **PySide6**
(Python 3.14) para League of Legends; backend PostgreSQL en Render; APIs Riot/LCU.
- Ejecutar la app: `python app.py`
- Baseline de tests actual: `python tests.py` → imprime `13/13 pasaron`
- Build del .exe: `powershell ./build_exe.ps1` (PyInstaller)
- venv: `venv/Scripts/python.exe` (o `python` del sistema; ambos 3.14.6)
- Convención de commits (ver `git log`): conventional commits en español
  (`fix(...)`, `refactor(...)`, `feat(...)`) + trailer `Co-Authored-By`.

## Orden de ejecución y estado

| Plan | Título | Prioridad | Esfuerzo | Depende de | Estado |
|------|--------|-----------|----------|------------|--------|
| 001  | Rotar y purgar secretos expuestos | P1 | M | — | TODO |
| 002  | Crear CLAUDE.md (arquitectura + comandos) | P2 | S | — | TODO |
| 003  | Suite pytest sobre conftest existente | P1 | M | — | TODO |
| 004  | Reemplazar `except:` desnudos por específicos | P2 | M | 003 | TODO |
| 005  | Eliminar dependencias muertas | P3 | S | — | TODO |

Valores de estado: TODO | IN PROGRESS | DONE | BLOCKED (con motivo) | REJECTED (con motivo)

## Notas de dependencias

- **004 requiere 003**: reemplazar `except:` por excepciones específicas es un
  cambio de comportamiento sutil; la suite pytest de 003 da la red de seguridad
  para verificar que no se rompe nada. Si 003 no está hecho, 004 se apoya solo
  en `python tests.py` (13 tests) — aceptable pero más débil; anótalo.
- 001, 002, 005 son independientes entre sí y del resto.

## Hallazgos considerados y rechazados (para no re-auditar)

- **Radar N+1 (PLAN_DE_MEJORAS P3)**: `_on_radar_listo` aún abre varias conexiones
  por refresh, pero el pool de conexiones (ya implementado) elimina el handshake
  TLS, así que el impacto es bajo. No vale el esfuerzo ahora.
- **Naming mixto español/inglés (P20)** y **`from ui.contexto import *`**: deuda
  cosmética sin payoff claro; no planificar.
- **Casi todo PLAN_DE_MEJORAS.md (P1–P19) ya está implementado** (pool, draft_id,
  reintentos LCU, round, train/test split, locks de caché, coach/roles/config/theme,
  limpieza de caché, código muerto). No re-planificar.

## Qué NO se auditó (esfuerzo estándar)

Corrección algorítmica profunda de `razonador.py`/`motor_ia.py`/`perfil_jugador.py`,
robustez de parsing LCU/Live Client más allá de lo ya cubierto, y rendimiento de
render de tablas grandes. Candidatos para una pasada `deep` futura.
