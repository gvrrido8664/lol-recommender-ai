# 🤖 LoL Recommender v1.0 — Asistente de Draft con IA

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![Version](https://img.shields.io/badge/version-1.0-gold)

Sistema inteligente para **League of Legends** que analiza partidas para ofrecerte:

- Counter picks en tiempo real | Analisis 1v1 con ML + datos reales | Setup optimo con botas inteligentes | Radar en vivo conectado al cliente | Recomendacion de bans | WR 5v5 por linea | Perfil completo con historial, WR por linea, maestrias y ligas

---

## 🚀 Instalacion rapida

```bash
git clone https://github.com/tu_usuario/lol-recommender-v2.git
cd lol-recommender-v2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python setup.py
python app.py
```

---

## 🎮 Uso

| Pestana | Funcion |
|---------|---------|
| Mi Perfil | Nombre, nivel, ligas, maestrias, historial, WR por linea, filtro por champ y modo |
| Radar en Vivo | Draft en tiempo real: counters, builds con botas adaptativas, bans, WR 5v5 por matchup |
| Meta & Builds | Analisis de matchups y builds optimas |
| Simulador 1v1 | Prediccion ML + datos reales + consejos tacticos por clase de campeon |
| Tier List de Bans | Mejores bans por linea |

---

## 🛠️ Estructura

```
├── app.py              # Interfaz principal (PySide6)
├── setup.py            # Instalador de datos iniciales
├── requirements.txt    # Dependencias
├── config.json         # API Key (no incluido en git)
├── src/
│   ├── lcu_api.py      # Conexion con el cliente de LoL
│   ├── riot_api.py     # Data Dragon y Riot API
│   ├── recomendador.py # Algoritmos de recomendacion
│   ├── db_manager.py   # Base de datos SQLite
│   ├── motor_ia.py     # Modelo ML Random Forest
│   ├── entrenador_ia.py
│   └── recolector_masivo.py
├── assets/             # Iconos (auto-descargados)
└── data/               # Base de datos y modelos
```

---

## 📝 Notas

- La primera ejecucion descarga automaticamente los iconos de Data Dragon
- El radar en vivo requiere tener League of Legends abierto
- Los datos de ligas usan primero la LCU con fallback a Riot API
- No subas tu `config.json` a GitHub (esta en `.gitignore`)
