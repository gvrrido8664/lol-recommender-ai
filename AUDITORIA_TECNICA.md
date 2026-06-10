# AUDITORÍA TÉCNICA — NEXUS v2.0

---

## `src/lcu_api.py`

### [CRÍTICO] — Bug: jugadores duplicados en `obtener_summoners_partida`
**Líneas 142-145**

El método `_extraer_de_team` para `teamTwo` se llama **dos veces** cuando `teamOne` no tiene datos:
- Línea 144: asigna `teamTwo` a `players` (sobrescribiendo)
- Línea 145: **siempre** concatena `teamTwo` de nuevo

Si hay 5 jugadores en teamTwo, el resultado tendrá 10 (duplicados). Además, da igual que `teamOne` tenga datos — la línea 145 siempre se ejecuta incondicionalmente, y si `teamOne` falla y `teamTwo` existe, se duplica.

**Solución:**
```python
players_one = self._extraer_de_team(game_data, "teamOne", "ORDER")
if players_one:
    players += players_one
players += self._extraer_de_team(game_data, "teamTwo", "CHAOS")
```

---

### [MODERADO] — `import ctypes` redundante en `nativeEvent`
**Líneas 1, 208 (overlay.py)**

`ctypes` ya está importado a nivel de módulo (línea 1). Se vuelve a importar dentro de `nativeEvent` en cada mensaje de Windows recibido (cientos por segundo durante gameplay). Impacto mínimo pero es basura.

**Solución:** eliminar `import ctypes` de la línea 208 de `overlay.py`.

---

### [LIMPIEZA] — `_extraer_de_team` llamada redundante como fallback
**Líneas 143-144**

Si `teamOne` no tiene jugadores, `players` se asigna desde `teamTwo` y luego la línea 145 vuelve a concatenar `teamTwo`. La intención era clara (fallback), pero la implementación está rota (ver [CRÍTICO] arriba).

---

## `app.py`

### [CRÍTICO] — Conexiones DB nuevas por jugador en cada poll de partida en vivo
**Líneas 4638, 4692, 4717, 4755**

En `_llenar_tabla_partida`, `_llenar_tabla_partida_lcu`, y `_comentar_jugador_partida` se abre/cierra **una conexión SQLite nueva por cada jugador**. Con 10 jugadores y polling cada 4s = ~2.5 conexiones/segundo constantes. `_comentar_jugador_partida` abre **dos** conexiones por llamada (línea 4717 para stats + línea 4755 para racha).

Esto fragmenta el pool de file descriptors y añade latencia innecesaria de `PRAGMA` por cada `obtener_conexion()`.

**Solución:** Refactorizar para pasar una conexión compartida desde el caller o usar una connection pool thread-safe:

```python
# En _llenar_tabla_partida — 1 conexión para TODOS los jugadores
conn = obtener_conexion()
cur = conn.cursor()
try:
    for j in jugadores:
        cname = ...
        cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=?", (cname,))
        r = cur.fetchone()
        wr = f"{r[0]}%" if r and r[0] else "--"
        # ...
finally:
    conn.close()
```

Lo mismo para `_llenar_tabla_partida_lcu` y `_comentar_jugador_partida`.

---

### [CRÍTICO] — Conexión DB por iteración en bucle de radar
**Líneas 4095-4103**

Dentro del bucle `for champ, pos, idx in enemigos_procesados:` se abre y cierra una conexión por cada candidato para obtener `COUNT(*)`. Hasta 5 conexiones por poll de radar (cada 1.5s).

**Solución:** misma refactorización — abrir una conexión fuera del bucle y reutilizarla.

---

### [MODERADO] — `QTimer` re-arrancado sin verificar si ya estaba corriendo
**Línea 3914**

```python
self.timer_lcu.start()
```

Si el timer ya estaba corriendo y se llama `start()` de nuevo, Qt reinicia el intervalo pero no lanza excepción. Puede causar que se acumulen callbacks si se llama en quick succession (ej: reconexiones rápidas). Debería ser:

```python
if not self.timer_lcu.isActive():
    self.timer_lcu.start()
```

---

### [OPTIMIZACIÓN] — `cargar_tags()` llama a re-leer JSON del disco en CADA acceso
**`src/tags_champions.py` líneas 722-729**

`obtener_tag(campeon)` llama a `cargar_tags()` que lee `tags_campeones.json` del disco **cada vez**. Como cada helper (`obtener_dano`, `es_tanque`, `obtener_nivel_cc`, etc.) llama a `obtener_tag`, y en un ciclo de radar se llaman **cientos de veces** a estas funciones (por cada champ del draft × análisis de composición × picks × counters × bans × build), el JSON se lee del disco cientos de veces por segundo.

El JSON de tags pesa ~85 KB y tiene ~170+ entradas.

**Solución:** caché en memoria a nivel de módulo:

```python
_TAGS_CACHE = None

def cargar_tags():
    global _TAGS_CACHE
    if _TAGS_CACHE is not None:
        return _TAGS_CACHE
    if os.path.exists(TAGS_PATH):
        with open(TAGS_PATH, "r", encoding="utf-8") as f:
            _TAGS_CACHE = json.load(f)
        return _TAGS_CACHE
    _TAGS_CACHE = _generar_tags()
    return _TAGS_CACHE
```

---

### [OPTIMIZACIÓN] — Widgets Qt creados en cada iteración de radar aunque no cambien
**Líneas 4130-4131, 4142, 4161-4187**

En `_on_radar_listo`, aunque `picks_al == self.last_aliados` y `picks_en == self.last_enemigos`, el código siempre recalcula `analizar_composicion` (línea 4137-4140) y ejecuta queries SQL de `mostrar_picks_vivo` (línea 4142). Esto son 3-4 queries SQL y recomposición de layouts por poll incluso cuando nada cambió.

Ya existe el guard `if picks_al != self.last_aliados or picks_en != self.last_enemigos:` en línea 4127, pero las líneas 4137-4140 de composición están **fuera** del guard. Moverlas dentro.

---

### [LIMPIEZA] — `QShortcut`, `QKeySequence` importados pero no usados
**Línea 17**

Importados pero nunca referenciados en el código. QAction sí se usa (system tray). Eliminar `QShortcut` y `QKeySequence` del import.

---

## `src/tags_champions.py`

### [CRÍTICO] — Sin caché, re-lectura de JSON en cada acceso (ver arriba)
**Líneas 607-611, 722-729**

Mismo hallazgo detallado en app.py [OPTIMIZACIÓN]. Impacta a TODOS los módulos que usan las funciones helper.

---

### [MODERADO] — `_generar_tags()` usa rutas relativas que fallan según CWD
**Líneas 618, 691**

```python
ruta_champs = os.path.join(DATA_DIR, "champion_data.json")  # L618: bien, usa DATA_DIR
ruta_campeones = os.path.join(DATA_DIR, "..", "assets", "campeones.json")  # L691: path relativo frágil
```

La línea 691 usa `..` para salir de `data/` hacia `assets/`. Si `DATA_DIR` se resuelve a una ruta absoluta (lo cual hace), `os.path.join` con `..` debería funcionar, pero `os.path.normpath` no se aplica. Mejor usar `_get_base_dir()` consistentemente:

```python
ruta_campeones = os.path.join(_get_base_dir(), "assets", "campeones.json")
```

---

## `src/recomendador.py`

### [LIMPIEZA] — `_get_runas_data()` definida pero nunca usada
**Líneas 22-26**

La función existe y mantiene un cache global `_RUNAS_DATA`, pero **nadie la llama**. Código muerto.

**Solución:** eliminar `_get_runas_data()` y `_RUNAS_DATA`.

---

### [MODERADO] — `calcular_winrate_5v5` cierra la conexión antes del feature engineering
**Líneas 580-622**

La conexión se cierra en línea 580 (`conn.close()`). Luego el bloque `try` (583-622) hace feature engineering con `obtener_tag` que no necesita DB, así que no es un bug. Pero si en el futuro se añade una query dentro de ese bloque, fallará con "Cannot operate on a closed database". Estructuralmente frágil. Mejor usar `with` o un `try/finally`.

---

## `src/db_manager.py`

### [MODERADO] — `registrar_lp` puede crear duplicados porque no hay UNIQUE real
**Líneas 333-353**

```sql
INSERT INTO lp_history ... ON CONFLICT DO NOTHING
```

La tabla `lp_history` tiene `PRIMARY KEY (id)` autoincremental, pero **no tiene constraint UNIQUE en (fecha, queue_type)**. El `ON CONFLICT` nunca se activa porque cada INSERT genera un nuevo `id`. Resultado: registros duplicados para el mismo día si `registrar_lp` se llama más de una vez. El UPDATE posterior sí actualiza el último insertado, pero los duplicados quedan.

**Solución:**
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_lp_unique ON lp_history(fecha, queue_type);
```

---

## `src/itemizador_dinamico.py`

### [LIMPIEZA] — `recomendar_item_defensivo` definida pero sin referencias
**Líneas 402-405**

La función `recomendar_item_defensivo` es un alias backward-compat que **nadie importa ni llama**. Código muerto.

---

### [LIMPIEZA] — `_HEALING_CHAMPS` tiene "Aatrox" duplicado
**Línea 73**

```python
"Aatrox", "DrMundo", ..., "Aatrox",
```

Aparece dos veces. Inofensivo (es un set) pero sucio.

---

## `src/overlay.py`

### [MODERADO] — `_center_bottom_right` no maneja DPI scaling en multi-monitor
**Líneas 187-193**

`self.screen().availableGeometry()` no aplica factor de escala de Windows (125%, 150%, etc.). En monitores 4K con scaling, el overlay puede aparecer parcialmente fuera de pantalla.

**Solución:**
```python
def _center_bottom_right(self):
    screen = self.screen()
    if screen:
        geo = screen.availableGeometry()
        ratio = screen.devicePixelRatio()
        w = int(self.width() * ratio)
        h = int(self.height() * ratio)
        x = geo.right() - w - 40
        y = geo.bottom() - h - 100
        self.move(x, y)
```

---

### [MODERADO] — `nativeEvent` llama `import ctypes` dentro del hot path
**Línea 208**

Cada mensaje de Windows dispara un `import ctypes` — en una aplicación de escritorio esto puede ocurrir decenas de miles de veces por minuto. `ctypes` ya está importado en línea 1. El `import` interno es completamente redundante.

**Solución:** eliminar `import ctypes` de la línea 208.

---

## `src/entrenador_ia.py`

### [OPTIMIZACIÓN] — `obtener_lista_campeones()` llama a `cargar_campeones()` que puede disparar `actualizar_datos_riot()` si no hay caché
**Líneas 178-181**

Cada llamada a `cargar_campeones()` verifica `if not os.path.exists(CACHE_CHAMPS): actualizar_datos_riot()`. Si el JSON no está cacheado (primer run), esto descarga de Data Dragon **sincrónicamente**, bloqueando el entrenamiento. No es crítico porque `entrenador_ia.py` se ejecuta offline, pero la función `cargar_campeones` se llama múltiples veces sin caché intermedio.

---

## `src/razonador.py`

### [OPTIMIZACIÓN] — `razonar_pick` recalcula stats de aliados/enemigos sin caché
**Líneas 65-144**

Cada llamada recalcula `ap_enemigos`, `ad_enemigos`, `cc_enemigo_total`, `ap_aliados`, `ad_aliados` con llamadas repetidas a `obtener_dano()` y `obtener_nivel_cc()`. Para 5 aliados + 5 enemigos = 10+ llamadas a `obtener_tag` → 10 re-lecturas de JSON (hasta que se aplique la corrección de caché).

---

## `setup.py`

### [MODERADO] — Hardcoded Google Drive FILE_ID sin mecanismo de fallback
**Línea 7**

Si el archivo deja de estar disponible o Google Drive cambia la API, el setup falla sin alternativas. Sería mejor tener múltiples mirrors o un checksum.

---

## `tests.py`

### [MODERADO] — Tests no cubren los bugs reales encontrados
**4 tests existentes**

Los tests actuales validan parsing de LiveClient con listas vacías y que el reporte de coaching tenga secciones. No hay tests para:
- El bug de duplicación en `obtener_summoners_partida` (lcu_api.py:142-145)
- Conexiones DB (ningún test de integración con BD real)
- `registrar_lp` con duplicados
- `cargar_tags` con caché
- Radar con draft vacío

---

## Resumen de prioridad

| # | Severidad | Archivo | Problema |
|---|-----------|---------|----------|
| 1 | [CRÍTICO] | `lcu_api.py:142-145` | Duplicación de jugadores teamTwo |
| 2 | [CRÍTICO] | `app.py:4638-4760` | 1 conexión DB por jugador por poll |
| 3 | [CRÍTICO] | `tags_champions.py:722` | JSON leído del disco en cada `obtener_tag()` |
| 4 | [MODERADO] | `db_manager.py:333` | Duplicados en `lp_history` |
| 5 | [OPTIMIZACIÓN] | `app.py:4137` | `analizar_composicion` recalculado innecesariamente |
| 6 | [MODERADO] | `overlay.py:193` | DPI scaling no considerado |
| 7 | [LIMPIEZA] | `recomendador.py:22` | `_get_runas_data` código muerto |
| 8 | [LIMPIEZA] | `itemizador_dinamico.py:403` | `recomendar_item_defensivo` sin referencias |
| 9 | [LIMPIEZA] | `app.py:17` | `QShortcut`, `QKeySequence` importados sin uso |
