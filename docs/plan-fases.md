# Plan por fases — Perfil, historial ranked, migración de BD y ejecutable

## Context

Pedido del usuario, a ejecutar **por fases** (cada una se implementa, verifica y commitea
por separado). Decisiones tomadas:
- Historial: descargar **solo ranked** (SoloQ 420 + Flex 440) y añadir un **selector de cola
  en la UI** (Todas las ranked / SoloQ / Flex).
- Hosting de BD: migrar de Render (se apaga por inactividad) a **Supabase** (gratis).
- Ejecutable de pruebas: build limpio **self-signed** (onedir, sin UPX, con icono y metadata);
  cert real queda para distribución futura.

**Entregable inicial:** copiar este plan a `docs/plan-fases.md` en el repo al empezar la
implementación, para que quede versionado.

---

## FASE 1 — Arreglos de UI en "Mi Perfil"

Archivo: [ui/tabs/tab_perfil.py](ui/tabs/tab_perfil.py); señal nueva en [app.py](app.py).

1. **Placeholder "Esperando datos del cliente" pegado**: el stack usa
   `QStackedLayout.StackAll` ([tab_perfil.py:249](ui/tabs/tab_perfil.py#L249)) que superpone
   tabla + placeholder. Cambiar a `setStackingMode(QStackedLayout.StackOne)` y **togglear el
   índice**: en `_renderizar_historial` (~816) mostrar la tabla (índice 0) si hay partidas, y
   el placeholder (índice 1) si está vacío. Guardar referencia al `hs_layout` (p. ej.
   `self.historial_stack_layout`) para poder llamar `setCurrentIndex`.

2. **Quitar filtro de temporadas**: eliminar `cb_filtro_season` y sus usos
   ([tab_perfil.py:233-237](ui/tabs/tab_perfil.py#L233), el poblado de años ~1015-1019, y la
   comparación en `filtrar_historial` ~1287/1304-1306).

3. **Combo de LP más ancho**: `cb_lp_queue.setFixedWidth(90)`
   ([tab_perfil.py:168](ui/tabs/tab_perfil.py#L168)) → `setFixedWidth(130)`.

4. **Barra de progreso de descarga de partidas**:
   - Nueva señal `season_progress = Signal(int, int)` en la clase principal ([app.py:41](app.py#L41) zona de señales).
   - `QProgressBar` (`self.pb_historial`) bajo el header "HISTORIAL DE PARTIDAS" (~244),
     oculto por defecto; texto "Descargando partidas… X/Y".
   - `_riot_fetch_match_ids` ya conoce el **total** (`len(all_ids)`); en `_riot_fetch_matches`
     (~466, ya cuenta `downloaded`) emitir `season_progress.emit(downloaded, total)`.
   - Conectar a un slot que actualice/visibilice la barra; **ocultarla** al terminar
     (downloaded≥total) y en `_on_perfil_listo`.
   - Mostrarla al disparar `refrescar_perfil` ([tab_perfil.py:676](ui/tabs/tab_perfil.py#L676)).

**Verificación F1:** abrir Mi Perfil con cliente conectado → el placeholder desaparece al
cargar; aparece barra de progreso que avanza y se oculta al terminar; no hay combo de
temporadas; el combo de LP no se ve apretado.

---

## FASE 2 — Historial solo ranked + selector de cola

Archivos: [ui/tabs/tab_perfil.py](ui/tabs/tab_perfil.py), [ui/tabs/tab_vivo.py](ui/tabs/tab_vivo.py)
(`_clasificar_modo_juego`).

1. **Descargar solo ranked**: en `_riot_fetch_match_ids` la URL
   ([tab_perfil.py:362](ui/tabs/tab_perfil.py#L362)) añadir `&type=ranked` (devuelve 420+440).
   Mantener el fallback sin `startTime` que ya existe.
2. **Capturar `queueId`**: en `_riot_convert_match`
   ([tab_perfil.py:435-442](ui/tabs/tab_perfil.py#L435)) añadir `"queueId": info.get("queueId", 0)`
   al dict devuelto. `_clasificar_modo_juego` ([tab_vivo.py:315](ui/tabs/tab_vivo.py#L315)) ya
   mapea 420→SoloQ / 440→Flex, así la columna MODO queda correcta.
3. **Selector de cola en UI**: reutilizar el espacio del filtro removido en F1. Cambiar/!añadir
   `cb_filtro_modo` con opciones **"Todas las ranked / SoloQ / Flex"** y filtrar en
   `filtrar_historial` (~1281) por `queueId` (∈{420,440}; SoloQ=420; Flex=440). Las partidas
   sin `queueId` (vinieron del LCU, sin filtro de cola) se ocultan por defecto al estar en modo
   ranked, o se reclasifican best-effort por `gameMode`.
4. **LCU**: `obtener_historial_extendido` no filtra por cola; como la descarga autoritativa es
   la de Riot API (con `type=ranked` + `queueId`), el historial mostrado/guardado queda ranked.

**Verificación F2:** el historial solo lista SoloQ/Flex (sin Normal/ARAM); la columna MODO
muestra SoloQ/Flex correctamente; el selector filtra entre Todas/SoloQ/Flex.

---

## FASE 3 — Migrar la BD a Supabase

Sin cambios de código de queries (es Postgres↔Postgres). Toca config/conexión.

1. **Crear proyecto Supabase** (free). Obtener la connection string del **Session pooler**
   (no la "Direct connection": en free suele ser solo IPv6; el pooler es IPv4 y persistente),
   formato `postgresql://postgres.<ref>:<pwd>@aws-...pooler.supabase.com:5432/postgres`.
2. **Migrar datos**: `pg_dump` desde Render → `psql/pg_restore` a Supabase (schema + tablas
   `matches`, `participantes`, `estado_emocional`, `player_cache`). Verificar índices (se
   recrean con `inicializar_db` igualmente).
3. **Apuntar la app**: actualizar `DATABASE_URL` (preferir variable de entorno; si no,
   `config.json`). `_obtener_db_url` ([src/db_manager.py:20](src/db_manager.py#L20)) ya prioriza
   env. No cambia el pool (`_PG_MINCONN=2/_PG_MAXCONN=10`) — Supabase free aguanta; si hay
   límite de conexiones, bajar `_PG_MAXCONN`.
4. **Keep-alive (Supabase pausa tras ~7 días sin uso)**: añadir un ping semanal — un **GitHub
   Action cron gratis** que ejecute `SELECT 1` (o el uso regular de la app lo mantiene activo).
   Documentarlo en `docs/`.

**Verificación F3:** con `DATABASE_URL` de Supabase, `python tests.py` (13/13) y la app cargan
datos del radar/perfil normalmente; medir latencia (`Radar DB compute` en `nexus.log`).

---

## FASE 4 — Ejecutable confiable para pruebas (anti-falsos-positivos)

No existe `build_exe.ps1` aún; PyInstaller ya está en `requirements-dev.txt`. La app ya maneja
rutas `frozen`/APPDATA ([src/paths.py](src/paths.py), [src/config.py](src/config.py)).

1. **Icono** `icono_app.ico` (multi-resolución) — generar con Pillow desde un PNG.
2. **`build_nexus.spec`** con **`version_info`** (CompanyName, ProductName, FileDescription,
   FileVersion = `CURRENT_VERSION` de [src/updater.py](src/updater.py)), `icon=icono_app.ico`,
   `console=False`, **`upx=False`**, modo **onedir** (`COLLECT`), `datas=[('assets','assets'),('data','data')]`,
   hiddenimports/collect-all (PySide6, sklearn, psycopg2, numpy, pandas, scipy, pypresence, requests).
3. **`build_exe.ps1`**: limpiar `build_onedir/`/`build_temp/`, correr `pyinstaller build_nexus.spec`,
   verificar `build_onedir/NEXUS/NEXUS.exe`, **firma self-signed opcional**
   (`New-SelfSignedCertificate -Type CodeSigning` + `Set-AuthenticodeSignature` con
   `-TimestampServer`), y recordatorio de VirusTotal.
4. **Documentar imports sensibles** para AV en `docs/` (por qué existen, todos envueltos en
   try/except): `ctypes.windll.dwmapi` (tema oscuro de la barra de título, [app.py:158](app.py#L158)),
   `urllib3 verify=False` (cert autofirmado del LCU local), `pypresence` (Discord RPC, opcional).
   **No** empaquetar `config.json` con secretos (va en APPDATA).
5. **Checklist anti-AV**: onedir (no onefile), sin UPX, con icono + metadata, firmado
   (self-signed por ahora), probado en VirusTotal. Para distribución pública: cert real
   (Azure Trusted Signing ~10 USD/mes o Sectigo/SSL.com) — fase futura, fuera de alcance ahora.

**Verificación F4:** correr `powershell ./build_exe.ps1`; ejecutar `build_onedir/NEXUS/NEXUS.exe`
→ abre la GUI, crea `%APPDATA%\LoLRecommender\` (assets/data/logs), sin errores en `nexus.log`;
subir el exe a VirusTotal y revisar que las detecciones sean mínimas/heurísticas.

---

## Notas transversales
- Cada fase es independiente y se commitea aparte (conventional commits en español).
- F1/F2 son de bajo riesgo (UI + un parámetro de query). F3 es config/infra. F4 crea archivos
  de build nuevos sin tocar la app.
- Reutilizar señales/patrones existentes (`season_partial`, `perfil_listo`, `_renderizar_historial`,
  `_clasificar_modo_juego`) y el manejo de rutas `frozen` ya presente.
- Guardar este documento como `docs/plan-fases.md` al iniciar la implementación.
