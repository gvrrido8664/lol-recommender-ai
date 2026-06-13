# NEXUS — Asistente de Draft con IA para League of Legends

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![DB](https://img.shields.io/badge/DB-PostgreSQL-336791)

Aplicación de escritorio que se conecta al cliente de League of Legends para
ofrecer recomendaciones en tiempo real durante la selección de campeones y la
partida, además de un análisis de coaching personalizado de tu juego.

## Características

- **Mi Perfil** — Estadísticas completas: winrate por línea/campeón, historial de partidas, ligas, maestrías, gráfica de LP, fatiga y estado mental.
- **Coaching Pro** — Reporte personalizado por sub-pestañas (Resumen, Filosofía, Campeones, Rendimiento, Hábitos, Gestión): tablero de métricas por partida, fortalezas/áreas de mejora, auditoría de champion pool, daño/economía/visión, gestión de sesiones y filosofía de juego.
- **Radar en Vivo** — Draft en tiempo real: counter picks, runas, hechizos, items y orden de habilidades recomendados; bans sugeridos; winrate estimado 5v5; análisis de composición.
- **Partida en Vivo** — Datos de la partida en curso (equipos, KDA, CS, WR de cada jugador) y resumen post-partida.
- **Meta & Builds** — Análisis de matchups y builds óptimas por campeón y rol.
- **Simulador 1v1** — Predicción con ML + datos reales + consejos tácticos por clase.
- **Tier List de Bans** — Mejores bans por línea (global o personalizada con tu historial).
- **Importación Automática** — Runas, hechizos, orden de habilidades y sets de objetos directamente al cliente de LoL.
- **Overlay en Partida** — Datos en vivo superpuestos sobre el juego.

## Instalación

```bash
git clone https://github.com/tu_usuario/nexus-lol-assistant.git
cd nexus-lol-assistant
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python setup.py    # descarga inicial de datos y modelos
python app.py
```

> Requiere un `config.json` con `DATABASE_URL` (PostgreSQL) y `API_KEY` de Riot.
> Copia `config.example.json` a `config.json` y completa tus valores. **Nunca
> subas `config.json`** (ya está en `.gitignore`).

## Pestañas

| Pestaña | Función |
|---------|---------|
| Mi Perfil | Nombre, nivel, ligas, maestrías, historial, WR por línea y campeón, gráfica de LP |
| Coaching Pro | Reporte personalizado: tablero de métricas, fortalezas/debilidades, hábitos y filosofía |
| Radar en Vivo | Draft en tiempo real: counters, runas, hechizos, items, bans, WR 5v5 |
| Partida en Vivo | Datos de la partida en curso y resumen post-partida |
| Meta & Builds | Matchups y builds óptimas |
| Simulador 1v1 | ML + datos reales + consejos tácticos |
| Tier List de Bans | Mejores bans por línea (global o personal) |

## Arquitectura

`app.py` es el punto de entrada y orquestador (ventana principal). La interfaz
vive en el paquete `ui/` y cada pestaña es un *mixin* que `LoLRecommenderApp`
combina por herencia. La lógica de dominio vive en `src/`.

```
├── app.py                # Ventana principal (orquestador): __init__, señales, timers, __main__
├── setup.py              # Descarga inicial de datos/modelos
├── build_exe.ps1         # Compila el .exe (PyInstaller)
├── ui/                   # Capa de interfaz (PySide6)
│   ├── contexto.py       # Superficie compartida: imports y datos cargados una vez
│   ├── design.py         # Paleta de color NEXUS (Rojo + Oro)
│   ├── theme_qss.py      # Hoja de estilos global (QSS)
│   ├── helpers.py        # Utilidades y datos puros (settings, jungla, matchups)
│   ├── dialogs/          # settings_dialog, lp_graph, postgame_dialog
│   └── tabs/             # Una pestaña = un mixin (perfil, coaching, vivo, partida, counters, ia, bans)
├── src/
│   ├── db_manager.py     # PostgreSQL con pool de conexiones
│   ├── recomendador.py   # Algoritmos de recomendación
│   ├── coach.py          # Generación del reporte de Coaching Pro
│   ├── lcu_api.py        # Conexión con el cliente de LoL (LCU + Live Client)
│   ├── motor_ia.py / entrenador_ia.py  # Modelo ML (Random Forest)
│   ├── roles.py, theme.py, paths.py, config.py  # Centralización (roles, paleta, rutas, config)
│   └── overlay.py, logros.py, discord_rpc.py, ...  # Módulos auxiliares
├── plans/                # Planes de mejora priorizados (skill /improve)
├── assets/               # Iconos (auto-descargados por Data Dragon)
└── data/                 # Modelos y datos descargados por setup.py
```

## Desarrollo

```bash
python app.py        # ejecutar la app
python tests.py      # 13 tests (deben pasar 13/13)
powershell ./build_exe.ps1   # compilar el ejecutable (Windows)
```

- Base de datos: **PostgreSQL** (Render) a través de un pool de conexiones en `src/db_manager.py`. Las consultas usan `obtener_conexion()`; nunca abras psycopg2 directo.
- Tema: lo define el QSS propio (`ui/theme_qss.py` + `ui/design.py`). Identidad **Rojo + Oro** sobre fondo oscuro cálido. Reutiliza las constantes de color, no hardcodees hex nuevos.
- Concurrencia: el trabajo bloqueante (red/BD) corre en hilos que emiten señales Qt (`Signal` + `threading.Thread` + `.emit()`); ver `_fetch_perfil` / `_inicializar_db_background`.

## Notas

- El arranque inicializa la BD en segundo plano: la ventana aparece al instante.
- La primera ejecución descarga automáticamente los iconos de Data Dragon.
- El Radar y la Partida en vivo requieren tener League of Legends abierto.
- No subas tu `config.json` a GitHub (ya está en `.gitignore`).
