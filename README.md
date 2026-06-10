# NEXUS — Asistente de Draft con IA para League of Legends

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)

Sistema inteligente que se conecta al cliente de League of Legends para ofrecer recomendaciones en tiempo real durante la seleccion de campeones y la partida.

## Caracteristicas

- **Radar en Vivo** — Draft en tiempo real: counter picks, runas, hechizos, items y orden de habilidades recomendados; bans sugeridos; winrate estimado 5v5; analisis de composicion
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

## v2.1 — Correcciones de rendimiento y bugs (Junio 2026)

- **Bug fix:** Jugadores duplicados en `obtener_summoners_partida` (teamTwo se concatenaba 2 veces)
- **Rendimiento:** 1 conexion SQLite compartida por poll en lugar de 1 por jugador
- **Rendimiento:** Cache en memoria para `tags_campeones.json`
- **DB:** Indice unico en `lp_history(fecha, queue_type)` para evitar duplicados
- **Overlay:** Correccion de DPI scaling en monitores 4K con escalado
- **Limpieza:** Codigo muerto eliminado en `recomendador.py`, `itemizador_dinamico.py`, `app.py`

## Notas

- La primera ejecucion descarga automaticamente los iconos de Data Dragon
- El radar en vivo requiere tener League of Legends abierto
- No subas tu `config.json` a GitHub (ya esta en `.gitignore`)
- Ejecuta `python tests.py` para verificar el correcto funcionamiento
