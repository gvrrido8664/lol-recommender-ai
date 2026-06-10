# NEXUS — Asistente de Draft con IA para League of Legends

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)

Sistema inteligente que se conecta al cliente de League of Legends para ofrecer recomendaciones en tiempo real durante la seleccion de campeones y la partida.

## Caracteristicas

- **Radar en Vivo** — Draft en tiempo real: counter picks, runas, hechizos, items y orden de habilidades recomendados; bans sugeridos; winrate estimado 5v5; analisis de composicion ESTO ES UNA NOTA
- **Mi Perfil** — Estadisticas completas: winrate por linea/campeon, historial de partidas, ligas, maestrias, fatiga y estado mental
- **Coaching Pro** — Reporte personalizado con analisis de habitos, champion pool, objetivos y filosofia de juego
- **Overlay en Partida** — Datos en vivo (KDA, CS, temporizador, alertas) superpuestos sobre el juego
- **Meta & Builds** — Analisis de matchups y builds optimas por campeon y rol
- **Simulador 1v1** — Prediccion con ML + datos reales + consejos tacticos por clase
- **Importacion Automatica** — Runas, hechizos, orden de habilidades y sets de objetos directamente al cliente de LoL

## Instalacion

```bash
git clone https://github.com/tu_usuario/nexus-lol-assistant.git
cd nexus-lol-assistant
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python setup.py
python app.py
```

## Uso

| Pestaña | Funcion |
|---------|---------|
| Mi Perfil | Nombre, nivel, ligas, maestrias, historial, WR por linea y campeon |
| Radar en Vivo | Draft en tiempo real: counters, runas, hechizos, items, bans, WR 5v5 |
| In-Game | Datos en vivo durante la partida |
| Coaching Pro | Reporte personalizado con analisis de rendimiento y objetivos |
| Meta & Builds | Matchups y builds optimas |
| Simulador 1v1 | ML + datos reales + consejos tacticos |
| Tier List de Bans | Mejores bans por linea |

## Estructura del proyecto

```
├── app.py              # Interfaz principal (PySide6)
├── setup.py            # Descarga inicial de datos
├── requirements.txt    # Dependencias
├── build_exe.ps1       # Script para compilar .exe
├── src/
│   ├── lcu_api.py      # Conexion con el cliente de LoL
│   ├── recomendador.py # Algoritmos de recomendacion
│   ├── db_manager.py   # Base de datos SQLite
│   ├── overlay.py      # Overlay en partida
│   ├── motor_ia.py     # Modelo ML Random Forest
│   └── ...             # Modulos auxiliares
├── assets/             # Iconos (auto-descargados por Data Dragon)
└── data/               # Modelos y datos descargados por setup.py
```

## Atajos de teclado

| Atajo | Accion |
|-------|--------|
| Ctrl+G | Ir a pestaña IN-GAME |
| Ctrl+Shift+H | Mostrar/ocultar overlay |
| Ctrl+Shift+G | Ir a IN-GAME (global) |

## v2.2 — Auditoria + Nuevas Features (Junio 2026)

### 🔴 TIER 1 — Core
- **Setup Wizard:** Primer arranque automatico con wizard grafico (pip, descarga, extraccion). 2 mirrors de descarga.
- **Auto-Update Data Dragon:** Detecta nuevo parche y descarga datos automaticamente

### 🟡 TIER 2 — UX
- **Notificaciones de escritorio:** Toast al encontrar partida, empezar Champ Select, terminar partida
- **Auto-aceptar partida:** Acepta el ReadyCheck automaticamente (configurable)
- **Settings huérfanos arreglados:** Slider de frecuencia radar (500-3000ms), eliminados `overlay_auto`/`overlay_compacto` muertos

### 🟢 TIER 3 — Features nuevas
- **Historial de Drafts:** Guarda picks, bans, aliados, enemigos y WR predicho de cada draft. Tabla en Perfil.
- **Discord Rich Presence:** Muestra en Discord la fase del juego (en cola, champ select, en partida)
- **Tier List Personalizada:** Toggle Global/Personal en Tier List de Bans usando tu historial
- **Sistema de Logros:** 15 logros (Primera Sangre, En Rachaaa, Bibliotecario, etc.) visibles en Perfil

### ⚪ TIER 4 — Infraestructura
- **Sistema de Logging:** RotatingFileHandler (2MB, 3 backups), archivo `nexus.log`
- **Auto-Update App:** Checkea GitHub Releases y notifica si hay version nueva
- **Tests:** 13 tests automatizados (13/13 pasan) cubriendo bugs criticos

### 🔧 Fixes de la auditoria (v2.1)
- Bug fix: jugadores duplicados en `obtener_summoners_partida`
- Rendimiento: 1 conexion SQLite compartida por poll (~20 → ~2 conexiones/seg)
- Rendimiento: cache en memoria para `tags_campeones.json`
- DB: indice unico en `lp_history(fecha, queue_type)`
- Overlay: DPI scaling en monitores 4K
- Limpieza: codigo muerto eliminado, imports sin uso

## Notas

- La primera ejecucion descarga automaticamente los iconos de Data Dragon
- El radar en vivo requiere tener League of Legends abierto
- No subas tu `config.json` a GitHub (ya esta en `.gitignore`)
- Ejecuta `python tests.py` para verificar el correcto funcionamiento
