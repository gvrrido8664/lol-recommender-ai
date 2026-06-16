# Plan 006: Rediseño UX/UI — NEXUS LoL Recommender v2

Fecha: 2026-06-16 | Prioridad: P2-P3 | Esfuerzo: L | Depende de: ninguno

---

## 1. Resumen Ejecutivo

Auditoría completa de la capa visual de NEXUS. Se identificaron **73+ colores hex hardcodeados**
fuera de `theme.py`, **5 pestañas sin empty state visual**, **7+ patrones de error inconsistentes**,
**nombres de constantes engañosos**, y **0 indicadores de carga** en operaciones asíncronas.
El plan prioriza por impacto en el usuario final.

---

## 2. Análisis Heurístico por Pestaña

### 2.1 Tab: MI PERFIL (`tab_perfil.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Jerarquía visual plana** | Alta | Las 4 stat cards (WR, KDA, +Jugado, Mejor WR) tienen el mismo peso visual que los labels de rango. El ojo no sabe dónde mirar primero. |
| **Color `#8fa3b8` hardcodeado** | Media | Se usa como "muted" en 6+ lugares pero NO es `TEXT_MUTED` (`#a39a93`). Dos grises diferentes sin razón. |
| **Season table sin empty state** | Media | La tabla `tb_season_champs` se muestra vacía (filas cero) sin mensaje cuando no hay datos. Solo hay un `lbl_season_stats` oculto. |
| **ProgressBar indeterminada** | Baja | `pb_historial.setRange(0,0)` al iniciar no comunica nada útil al usuario. |
| **Error Riot inline sin CTA** | Media | `lbl_riot_error` muestra error en rojo y se auto-oculta en 15s, pero no dice qué hacer (ir a Settings, reintentar, etc). |
| **Fatiga: barra de 4px invisible** | Alta | `lbl_fatiga_barra` tiene 4px de alto + fondo `#2f2535` sobre fondo oscuro — prácticamente invisible. No hay porcentaje ni label numérico. |
| **WR por Línea: texto sin contraste** | Media | Labels de línea usan `font-size: 10px; color: #8fa3b8` — demasiado chicos y grises para la importancia que tienen. |

**Mejoras propuestas:**

- **Stat cards con jerarquía**: Valor en `26px bold` (ya existe), pero agregar subtítulo descriptivo debajo (ej: "Winrate de SoloQ" vs "Winrate Global") y borde inferior de color por estado (verde >50%, rojo <50%).
- **Unificar muted**: Reemplazar todos los `#8fa3b8` por `TEXT_MUTED` (`#a39a93`) o crear `TEXT_MUTED_ALT` semántico si realmente se necesita un segundo nivel.
- **Empty state para season table**: QStackedLayout igual que historial — mostrar ilustración + "Juega partidas ranked para ver tus stats de temporada".
- **Fatiga: barra visible**: Aumentar a 8-10px, agregar borde, label numérico (ej: "67%") y animación degradada según nivel (verde → amarillo → rojo).
- **Error Riot con CTA**: Agregar link/botón "Abrir Configuración" dentro del banner de error, además del auto-hide.
- **WR por Línea: mini badges**: Cada rol como badge con fondo de color tenue y texto blanco, no solo texto gris.

### 2.2 Tab: RADAR EN VIVO (`tab_vivo.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **`time.sleep(1.5)` en hilo principal** | Crítica | Congela la UI al detectar LCU por primera vez. El usuario ve la app congelada. |
| **WR 42px sin contexto** | Media | Número gigante sin label que diga "Winrate de Composición" o similar. Nuevo usuario no sabe qué significa. |
| **Skill cells 18x18px** | Alta | Celdas de habilidad demasiado pequeñas para leer o hacer click en pantalla normal. |
| **Matchup tips: colores hardcodeados** | Baja | `#1a1200`, `#3d2e00` para fondo/borde deberían usar `BG_DARK_YELLOW` y `BG_DARK_BROWN` de theme.py. |
| **"Sin recomendaciones" en gray** | Media | Texto plano sin icono ni estilo cuando no hay bans sugeridos. |
| **Panel "Counters vs Rival" cambia título** | Baja | El título del panel se muta dinámicamente ("COUNTERS (esperando rival...)") — confuso vs tener un subtítulo/placeholder interno. |

**Mejoras propuestas:**

- **Eliminar sleep(1.5)**: Mover a un QTimer.singleShot o hacer que el primer fetch use reintentos internos en el hilo secundario.
- **Label de contexto para WR**: Agregar `lbl_wr_label` encima del número grande: "WINRATE DE COMPOSICIÓN" en `9px bold TEXT_MUTED`.
- **Skill cells más grandes**: 24x24px mínimo, con 9px → 11px de font para el número de nivel.
- **Colores del theme**: Reemplazar `#1a1200` → `BG_DARK_YELLOW`, `#3d2e00` → `BG_DARK_BROWN`.
- **Empty states con icono**: "Sin bans sugeridos" con icono o placeholder visual, no solo texto gris.
- **Título fijo + subtítulo dinámico**: Panel siempre dice "COUNTERS VS RIVAL", subtítulo interior dice "(esperando rival...)" en muted.

### 2.3 Tab: PARTIDA EN VIVO (`tab_partida.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Empty state básico** | Media | Solo texto "Esperando partida..." sin icono ni orientación. |
| **Tablas sin header labels descriptivos** | Baja | "Jugador", "Rango", "KDA", "CS", "Perfil" son genéricos. "Perfil" es ambiguo. |
| **Colores hardcodeados** | Media | `#0d0b10` (aliados) y `#1a0a0f` (enemigos) deberían ser `BG_DARK` y `BG_DARK_RED` de theme.py. |
| **Sin indicador de "TÚ"** | Alta | En la tabla de aliados, no hay forma de distinguir cuál eres tú vs los otros 4. |

**Mejoras propuestas:**

- **Empty state enriquecido**: Icono grande + "Esperando partida" + "Los datos aparecerán cuando entres a la Grieta" + texto secundario "Asegúrate de que el cliente de LoL esté abierto".
- **Resaltar fila del jugador**: Tu fila en la tabla aliados con borde izquierdo verde (`GREEN_WR`) y fondo sutil `BG_DARK_GREEN`.
- **Tabla: "Perfil" → "Main/WR"**: Renombrar columna para ser más claro.
- **Colores del theme**: `#0d0b10` → `BG_DARK`, `#1a0a0f` → `BG_DARK_RED`.

### 2.4 Tab: META & BUILDS (`tab_counters.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Sin empty state inicial** | Alta | Tabla completamente vacía antes de ANALIZAR. Sin orientación. |
| **Sin loading state** | Alta | Botón ANALIZAR no muestra progreso. Si la query tarda, parece que no hizo nada. |
| **Inline QSS hardcodeado** | Media | `#251d2b`, `#1b1620`, `#e63946` en la tabla deberían usar constantes. |
| **Build panel vacío** | Media | `frame_setup_visual` está vacío hasta que el usuario hace click en una fila. No hay hint de "Selecciona un campeón de la tabla". |

**Mejoras propuestas:**

- **Empty state inicial**: Placeholder con icono + "Selecciona línea y rival, luego ANALIZAR" antes de cualquier query.
- **Loading state**: Deshabilitar botón + mostrar spinner/progressbar mientras `_fetch_meta_builds` corre.
- **Hint en build panel**: QLabel "Haz click en un campeón de la tabla para ver su setup óptimo" en muted.
- **Colores del theme**: Reemplazar los 3 hex inline por `BG_CARD_HOVER`, `BG_CARD`, `ACCENT_RED`.

### 2.5 Tab: SIMULADOR 1v1 (`tab_ia.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Sin badge "Tu Pick"** | Alta | La tarjeta aliada no indica que es TU campeón. Solo el selector arriba dice "Tu Pick". |
| **Swap button 38px** | Alta | Target de click demasiado pequeño. |
| **Sin loading state** | Media | Simular no muestra indicador de progreso. |
| **Colores hardcodeados en barras** | Media | `#3b1018`, `#5a1a28`, `#211a28` deberían usar `BG_DARK_RED2`, `RED_DARK_CARD`, `CARD_DARK_BLUE`. |
| **Placeholder genérico** | Baja | "Selecciona los campeones y presiona Simular." sin icono. |

**Mejoras propuestas:**

- **Badge "TU PICK"**: Agregar QLabel pill-badge verde entre la imagen y el nombre del campeón aliado en `_crear_columna_campeon()`. Parámetro `badge=""` en la firma; solo aliado lo usa.
- **Swap button más grande**: 48px de ancho mínimo, con tooltip mejorado.
- **Loading overlay**: QFrame semi-transparente sobre el HUD con spinner mientras se calcula.
- **Colores del theme**: Mapear los 3 hex inline a constantes existentes.
- **Placeholder con icono**: + "Selecciona campeones y presiona SIMULAR".

### 2.6 Tab: COACHING PRO (`tab_coaching.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Placeholder HTML hardcodeado** | Baja | Usa colores inline en HTML (`#e63946`, `#a39a93`, `#7a6f68`) en vez de f-strings con constantes. |
| **Cards solo con HTML** | Media | Todo el contenido es QLabel con RichText HTML. No hay widgets nativos (barras, sparklines, badges). |
| **Sección routing frágil** | Media | `_norm()` + string matching (`"FILOSOFIA" in t`) para rutar secciones a tabs. Si el coach cambia el texto, se rompe. |
| **Sin resumen visual** | Alta | No hay dashboard con métricas clave como widgets nativos — solo HTML en QLabel. |

**Mejoras propuestas:**

- **HTML → constantes**: Reemplazar colores inline en HTML por f-strings con constantes de theme.py.
- **Dashboard nativo**: Renderizar las métricas clave (WR, KDA, CS/min) como stat cards nativas con barras de progreso, no como tabla HTML.
- **Routing por clave**: Agregar campo `tab_key` en las secciones del coach, no depender del título.

### 2.7 Tab: TIER LIST DE BANS (`tab_bans.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Sin empty state visual** | Crítica | Tabla vacía sin placeholder. La pestaña se ve rota/incompleta antes de ANALIZAR. |
| **Sin loading indicator** | Alta | `buscar_baneos()` es síncrono y bloqueante. Sin feedback. |
| **Pestaña visualmente vacía** | Alta | Solo un dropdown + botón + tabla vacía. La pestaña menos rica de toda la app. |
| **Cross-tab coupling** | Media | `_cargar_logros()` accede a `self.fr_logros` que es de `tab_perfil.py`. |

**Mejoras propuestas:**

- **Empty state visual**: Placeholder con icono + "Selecciona una línea y ANALIZA para ver los bans del meta".
- **Tabla con placeholder row**: Si no hay datos, insertar 1 fila con span que diga "Sin datos — haz click en ANALIZAR".
- **Hacer la query asíncrona**: Mover `obtenermejoresbaneos` a hilo secundario con señal.
- **Enriquecer la pestaña**: Agregar summary stats arriba (top 3 bans rápidos, banrate promedio) antes de la tabla completa.

### 2.8 Diálogos

#### Settings Dialog (`settings_dialog.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Colores hardcodeados** | Media | `#251d2b`, `#2f2535`, `#2a2030`, `#16121c` en vez de constantes. |
| **`auto_deteccion: True` hardcodeado** | Baja | Nunca se puede desactivar desde la UI. El checkbox no existe. |
| **Sin margen outer** | Baja | Layout principal sin padding, se siente apiñado. |

**Mejoras:**
- Reemplazar todos los hex inline por constantes de theme.py.
- Agregar checkbox para `auto_deteccion` o eliminar la key si siempre es True.
- Margen exterior de 12px.

#### LP Graph (`lp_graph.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Hard-coded padding** | Media | 52px left fijos — no escala con DPI. |
| **Tier bands solapamiento** | Baja | Si el rango de LP es pequeño, los labels se superponen. |

**Mejoras:** Padding proporcional (5% del ancho). Ocultar tier bands si rango < 100.

#### Postgame Dialog (`postgame_dialog.py`)

| Problema | Severidad | Detalle |
|----------|-----------|---------|
| **Ancho fijo 500px** | Media | Demasiado angosto en HDPI. |

**Mejoras:** `setMinimumWidth(500)` en vez de fixed.

---

## 3. Jerarquía Visual — Principios

### 3.1 Orden de lectura propuesto (por pestaña)

**Perfil**: Icono+Nombre → Rangos → Stat Cards → Fatiga → Historial
- Cambio: Agregar **borde inferior colorizado** a las stat cards (verde/rojo según valor).

**Radar en Vivo**: WR → Role → Picks → Setup → Skills
- Cambio: Label "COMPOSICIÓN" encima del WR.

**Partida en Vivo**: Tu KDA → Timer → Tablas
- Cambio: Tu fila se distingue con borde verde.

**Simulador 1v1**: Tu Pick (badge) → WR → Barras → Insights → Consejos
- Cambio: Badge "TU PICK" en tarjeta aliada.

**Bans**: Línea → Tabla
- Cambio: La pestaña ya no se ve vacía al entrar.

### 3.2 Tipografía sugerida

| Elemento | Actual | Propuesto |
|----------|--------|-----------|
| Hero numbers (WR%) | Impact 42px | Mantener |
| Panel titles | Segoe UI 11px bold | Segoe UI 12px bold + letter-spacing 0.5px |
| Stat card values | 26px / 20px bold | Mantener + borde inferior de color |
| Body text | 11-12px | 12px mínimo |
| Muted/secondary | 10-11px #8fa3b8 | 11px TEXT_MUTED — unificar |
| Skill cells | 7px labels, 10px ability | 9px labels, 11px ability |

### 3.3 Espaciado

- Panel padding: 14px (mantener) + margin-bottom 6px entre paneles.
- Card spacing: 8px uniforme.
- Stat card gap: 6px → 8px.

---

## 4. Empty States y Manejo de Errores

### 4.1 Sistema de Empty States (propuesta unificada)

Crear helper `_crear_empty_state(icono, titulo, descripcion)` que devuelva un QWidget estilizado:

```
┌─────────────────────────────────┐
│          [Emoji 36px]           │
│     TÍTULO (14px bold, RED)     │
│  Descripción (11px, TEXT_MUTED) │
│     [CTA Button opcional]       │
└─────────────────────────────────┘
```

**Dónde aplicarlo:**

| Pestaña | Empty State Actual | Propuesto |
|---------|--------------------|-----------|
| Perfil - Season | Tabla vacía | "Stats de Temporada" + "Juega ranked para desbloquear" |
| Perfil - Historial | Ya tiene | Mantener, migrar a helper |
| Perfil - Insights | Texto plano | "Conecta al cliente" + CTA |
| Radar - Bans | "Sin recomendaciones" texto | Icono + "Sin bans sugeridos" + "Prueba otra línea" |
| Radar - Counters | "Sin datos" texto | "Esperando rival de línea..." |
| Partida | Texto plano | Icono + "Esperando partida" + CTA |
| Counters - Tabla | Vacía total | "Selecciona línea y rival, luego ANALIZAR" |
| Counters - Build | Vacío | "Selecciona un campeón de la tabla" |
| Bans - Tabla | Vacía total | "Selecciona una línea y ANALIZA" |
| IA - Insights | Texto plano | "Simula un enfrentamiento para ver análisis" |
| Coaching | Ya tiene | Mantener, migrar a helper |

### 4.2 Sistema de Errores (propuesta unificada)

3 niveles:

| Nivel | UI | Duración | Ejemplo |
|-------|-----|----------|---------|
| **Banner inline** | QFrame rojo con icono + texto + CTA | Hasta resolver o 30s | API key inválida |
| **Toast** | QFrame amarillo inferior, auto-fade 5s | 5s | "Runas importadas" |
| **Modal** | QMessageBox (solo fatales) | Hasta dismiss | "Cliente no detectado" |

**Regla**: NUNCA QMessageBox para errores recuperables. SIEMPRE banner con CTA.

### 4.3 Loading States (propuesta unificada)

| Operación | Actual | Propuesto |
|-----------|--------|-----------|
| Perfil fetch | ProgressBar indeterminado | ProgressBar con % + texto |
| Radar DB compute | Nada | Overlay "Analizando draft..." |
| Meta Builds | Nada | Botón disabled + "Cargando..." |
| Bans query | Nada (síncrono) | Botón disabled + spinner |
| IA simulación | Nada | Overlay "Calculando matchup..." |
| Season download | Ya tiene ProgressBar | Mantener |

---

## 5. Estilo y Componentes

### 5.1 Paleta — Correcciones

**Renombrar constantes engañosas** (con alias backward-compat):

| Constante Actual | Valor Real | Nombre Propuesto |
|-----------------|------------|------------------|
| `ACCENT_TEAL` | `#f0b232` (ámbar) | `ACCENT_GOLD` |
| `TEAL_DARK` | `#c89b3c` (oro) | `GOLD_DARK` |
| `TEAL_EMERALD` | `#f0b232` (ámbar) | `AMBER_ACCENT` |
| `GREEN_TEAL` | `#22c55e` (verde) | `GREEN_SUCCESS` (ya existe) |

**Agregar a `theme.py`:**

```python
ACCENT_GOLD = TEAL_EMERALD     # #f0b232
GOLD_DARK = TEAL_DARK          # #c89b3c
AMBER_ACCENT = TEAL_EMERALD    # #f0b232
TEXT_MUTED_ALT = "#8fa3b8"     # El gray distinto a TEXT_MUTED
BG_TABLE_HEADER = "#1b1620"
BORDER_TABLE_ITEM = "#1f1a26"
```

### 5.2 Migración de Colores Hardcodeados (~30 reemplazos)

| Archivo | Hex | Constante |
|---------|-----|-----------|
| `tab_perfil.py` | `#8fa3b8` (6 usos) | `TEXT_MUTED_ALT` |
| `tab_perfil.py` | `#1b1620` | `BG_TABLE_HEADER` |
| `tab_perfil.py` | `#c89b3c` | `GOLD_DARK` |
| `tab_perfil.py` | `#1f1a26` | `BORDER_TABLE_ITEM` |
| `tab_perfil.py` | `#2f2535` | `BG_CARD_ELEVATED` |
| `tab_vivo.py` | `#1a1200` | `BG_DARK_YELLOW` |
| `tab_vivo.py` | `#3d2e00` | `BG_DARK_BROWN` |
| `tab_vivo.py` | `#1a3a3a` | `BG_DARK_TEAL` |
| `tab_partida.py` | `#0d0b10` | `BG_DARK` |
| `tab_partida.py` | `#1a0a0f` | `BG_DARK_RED` |
| `tab_partida.py` | `#1a2236` | `CARD_DARK_BLUE` |
| `tab_ia.py` | `#3b1018` | `BG_DARK_RED2` |
| `tab_ia.py` | `#5a1a28` | `RED_DARK_CARD` |
| `tab_ia.py` | `#211a28` | `CARD_DARK_BLUE` |
| `tab_counters.py` | `#251d2b` | `BG_CARD_HOVER` |
| `tab_counters.py` | `#1b1620` | `BG_CARD` |
| `settings_dialog.py` | 4 hex | Constantes correspondientes |

### 5.3 Componentes Reutilizables (nuevo `ui/components.py`)

1. **`EmptyStateWidget(icon, title, description, cta_text, cta_callback)`**
2. **`StatCardWidget(title, value, color, subtitle)`**
3. **`BadgeLabel(text, color)`** — pill-badge para "TU PICK", roles, rangos
4. **`LoadingOverlay(parent, message)`** — QFrame semi-transparente con spinner
5. **`ErrorBanner(message, cta_text, cta_callback)`** — banner rojo con CTA

### 5.4 Estilo de Botones (unificar 2 variantes)

| Variante | Uso | Estilo |
|----------|-----|--------|
| **Primary** | SIMULAR, ANALIZAR, Actualizar | `ACCENT_RED` bg, white, bold, 6px radius |
| **Secondary** | Exportar skills, Aplicar | `BG_CARD_ELEVATED` bg, `ACCENT_GOLD` border+text |

---

## 6. Plan de Implementación (por fase)

### Fase 1: Fundación (2-3h)
- [ ] Crear `ui/components.py` con `EmptyStateWidget`, `BadgeLabel`, `ErrorBanner`
- [ ] Agregar aliases y constantes nuevas a `src/theme.py` y `ui/design.py`
- [ ] Eliminar duplicado QSS scrollbar en `ui/theme_qss.py`

### Fase 2: Migración de colores (2h)
- [ ] Reemplazar ~30 hex hardcodeados en 6 archivos por constantes
- [ ] Renombrar `ACCENT_TEAL` → `ACCENT_GOLD` (con alias backward-compat)
- [ ] Unificar `#8fa3b8` → `TEXT_MUTED_ALT`

### Fase 3: Empty States (2h)
- [ ] Aplicar `EmptyStateWidget` en: Bans, Counters, Partida, Radar
- [ ] Agregar hint en build panel de Counters
- [ ] Agregar empty state en season table de Perfil

### Fase 4: Badges y jerarquía visual (1.5h)
- [ ] Badge "TU PICK" en tarjeta aliada del Simulador 1v1
- [ ] Resaltar fila del jugador en Partida en Vivo
- [ ] Bordes de color en stat cards de Perfil
- [ ] Label "COMPOSICIÓN" sobre WR del Radar
- [ ] Fatiga: barra 10px + label numérico + degradado color

### Fase 5: Loading y errores (2h)
- [ ] Crear `LoadingOverlay` en components.py
- [ ] Aplicar loading en: Meta Builds, Bans, Simulador IA
- [ ] Migrar `QMessageBox.critical` a `ErrorBanner` con CTA
- [ ] Agregar CTA en `lbl_riot_error`
- [ ] Eliminar `time.sleep(1.5)` en hilo principal del Radar

### Fase 6: Pulido (1.5h)
- [ ] Skill cells 18→24px, font 7→9px / 10→11px
- [ ] Swap button 38→48px
- [ ] Settings dialog: márgenes + constantes
- [ ] LP Graph: padding proporcional
- [ ] Postgame dialog: minimumWidth
- [ ] Coaching HTML → f-strings con constantes

---

## 7. Criterios de Aceptación

- [ ] Cero hex colors nuevos en código UI (todo via theme.py/design.py)
- [ ] Todas las pestañas tienen empty state visual con icono + descripción
- [ ] Ningún `time.sleep()` en hilo principal
- [ ] Ningún `QMessageBox` para errores recuperables
- [ ] Badge "TU PICK" visible en Simulador 1v1
- [ ] Fila del jugador resaltada en Partida en Vivo
- [ ] Loading visible en al menos 3 operaciones asíncronas
- [ ] `python tests.py` pasa sin regresiones
- [ ] `python app.py` arranca sin errores visuales

---

## 8. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Renombrar `ACCENT_TEAL` rompe imports | Alias backward-compat en design.py |
| `EmptyStateWidget` cambia layouts | Insertar en QStackedLayout existente |
| Loading overlay flicker | Solo mostrar después de 300ms (QTimer) |
| Migración colores typos | Buscar-reemplazar con verify visual |

---

## 9. NO incluido

- Rediseño completo de layout
- Animaciones sofisticadas (QPropertyAnimation)
- Toggle modo claro/oscuro
- Refactor de `_on_radar_listo` (código, no UX)
- Routing de coaching por clave (refactor)
- Responsive < 1080px (ya hay scroll)
