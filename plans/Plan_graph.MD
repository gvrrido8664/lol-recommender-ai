# Gráfica de evolución de LP — documentación del feature

> **Nota:** este archivo era originalmente un *prompt* para generar el gráfico de LP con
> **matplotlib + JSON local + API key inline**. Ese enfoque quedó **descartado** porque
> el feature ya está implementado en el proyecto de una forma mejor y compatible con el
> build. Abajo se documenta la implementación real. El prompt original se conserva al
> final como apéndice histórico.

## Qué hace

Muestra la evolución del LP (League Points) del jugador en SoloQ a lo largo del tiempo,
con bandas de tier de fondo, curva suavizada y el LP/tier actual.

## Implementación real (vigente)

### 1. Render — `ui/dialogs/lp_graph.py`
`LPGraphWidget(QWidget)` dibuja la gráfica con **QPainter nativo** (sin matplotlib):
- Curva bezier (`cubicTo`) sobre los puntos de LP.
- Bandas de tier de fondo (`TIER_BANDS`: Iron → Master+) con su color.
- Fill degradado bajo la curva (`QLinearGradient`, color `ACCENT_TEAL` de `ui/design.py`).
- Etiqueta de LP/tier actual en la esquina y fechas en el eje X.
- API del widget: `set_data(history: list)` y repinta en `paintEvent`.

Cada punto del `history` que consume el widget tiene las claves: `lp_total` (LP absoluto
para posicionar en Y), `lp`, `tier`, `division`, `fecha`.

### 2. Datos — `src/db_manager.py`
- `registrar_lp(tier, division, lp, wins, losses, queue_type="RANKED_SOLO_5x5")`
  (línea ~351): inserta un snapshot diario en la tabla **`lp_history`** de PostgreSQL
  (no en un JSON local). Idempotente por fecha.
- `obtener_historial_lp(queue_type="RANKED_SOLO_5x5") -> list` (línea ~372): lee el
  historial y calcula `lp_total` convirtiendo tier+división a un valor absoluto
  (`TIER_BASE` + `DIV_OFFSET`), que es lo que grafica el widget.

### 3. Secretos / API
Los datos de Riot (rango/LP) entran por la app a través de `cargar_config()` y
`src/riot_public_api.py` / `src/lcu_api.py`. **No** se hardcodea ninguna API key en este
flujo (ver `src/secretos.py` para el manejo de secretos).

## Por qué se descartó el enfoque original
- **matplotlib está excluido del build** (`build_nexus.spec` → `excludes=[... 'matplotlib' ...]`).
  Empaquetarlo rompería/engordaría el `.exe`. El render nativo con QPainter es coherente
  con el resto de la UI (PySide6) y más liviano.
- **JSON local por jugador** (`lp_history_*.json`) es frágil y no se sincroniza; la tabla
  `lp_history` en Postgres ya centraliza el historial y se comparte con otras vistas
  (coaching usa LP de los últimos 30 días).
- **API key inline** en el archivo contradice el modelo de secretos del proyecto.

## Mejoras futuras posibles (opcional)
- Tooltip al pasar el mouse sobre un punto (fecha + LP + W/L de ese día).
- Filtro SoloQ/Flex en la propia gráfica (hoy `queue_type` se fija al consultar).
- Marcar visualmente promociones/descensos de tier.

---

## Apéndice — prompt original (histórico, NO usar)

<details>
<summary>Spec original de generación con matplotlib + JSON local (obsoleto)</summary>

El prompt pedía generar funciones `get_puuid`, `get_summoner_id`, `get_current_lp`,
`load_lp_history`/`save_lp_history`/`update_lp_history` (persistencia en
`lp_history_{GAME_NAME}_{TAG_LINE}_{QUEUE_TYPE}.json`), `generate_lp_chart_png` con
`matplotlib` guardando un PNG en `charts/`, y `display_chart_in_label` para mostrarlo en
un `QLabel` del panel "Insights". Reemplazado por el render nativo + tabla `lp_history`
descritos arriba.

</details>
