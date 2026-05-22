# 🤖 LoL Recommender AI – Asistente de Draft con Machine Learning

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-green)
![Scikit-learn](https://img.shields.io/badge/ML-Random%20Forest-orange)

Sistema inteligente de recomendación para **League of Legends** que analiza miles de partidas de alto elo para ofrecerte:

- ✅ **Counter picks** en tiempo real para tu línea
- ✅ **Análisis 1v1** con predicción de winrate basada en machine learning
- ✅ **Setup óptimo** (runas, hechizos, items) basado en datos estadísticos
- ✅ **Radar en vivo** que se conecta al cliente de LoL durante el draft
- ✅ **Recomendación de bans** para tu rol
- ✅ **Análisis de composición de equipo** (balance AD/AP, tanques)

Todo esto con una interfaz moderna, oscura y estilizada estilo **Hextech**.

---

## 📋 Paso 1: Clona el repositorio

Abre una terminal y ejecuta:

```bash
git clone https://github.com/tu_usuario/lol-recommender-ai.git
cd lol-recommender-ai
(Reemplaza tu_usuario con tu nombre de usuario de GitHub)

📋 Paso 2: Crea y activa un entorno virtual
En Windows:
bash
python -m venv venv
venv\Scripts\activate
En Linux / Mac:
bash
python3 -m venv venv
source venv/bin/activate
📋 Paso 3: Ejecuta el instalador automático
bash
python setup.py
Este comando hará lo siguiente:

✅ Instalará todas las dependencias (requests, scikit-learn, pandas, numpy, pillow, gdown, customtkinter)

✅ Descargará una base de datos pre-entrenada (+9,000 partidas de High Elo) y los modelos de IA desde Google Drive

✅ Extraerá los archivos en las carpetas correctas y eliminará el ZIP temporal

⚠️ Nota: No necesitas una API Key de Riot para usar la aplicación con los datos pre-entrenados. Solo necesitas la API Key si quieres recolectar tus propias partidas (Paso 6).

📋 Paso 4: Inicia la aplicación
Una vez que el instalador termine, ejecuta:

bash
python app.py
La interfaz gráfica se abrirá automáticamente.

📋 Paso 5: Cómo usar la aplicación (Guía rápida)
La aplicación tiene 4 pestañas principales:

🔹 Pestaña "📡 RADAR EN VIVO"
Se conecta automáticamente al cliente de LoL cuando entras en una partida.

Muestra tu rol asignado, los picks enemigos y la composición de equipo (balance AD/AP, tanques).

Calcula el winrate estimado de la partida.

Te sugiere counter picks con su setup completo (runas, hechizos, items de inicio y core).

Recomienda bans basados en tu rol y en el campeón que estás jugando.

🔹 Pestaña "📊 META & BUILDS"
Selecciona una línea (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY).

Selecciona un campeón enemigo.

Haz clic en "ANALIZAR".

Se mostrarán los mejores counter picks en una tabla.

Haz clic en cualquier campeón de la tabla para ver su setup óptimo (runas, hechizos, items de inicio y core).

🔹 Pestaña "🤖 ANÁLISIS 1v1"

Selecciona tu línea.

Selecciona tu campeón.

Selecciona el campeón enemigo.

Haz clic en "SIMULAR".

La IA te dará el porcentaje de winrate esperado y un análisis textual del matchup.

🔹 Pestaña "🔒 BANS RECOMENDADOS"

Selecciona tu línea.

Haz clic en "ANALIZAR BANS".

Se mostrarán los campeones con mayor banrate para esa línea, basados en datos reales.

📋 Paso 6: (Opcional) Recolecta tus propios datos
Si deseas entrenar el modelo con tus propias partidas (o ampliar la base de datos), necesitas una API Key de Riot Games.

Solicita tu API Key en el Portal de Desarrolladores de Riot Games.

Crea un archivo llamado config.json en la raíz del proyecto con el siguiente contenido:

json
{
    "API_KEY": "TU_API_KEY_AQUI"
}
Ejecuta el recolector masivo:

bash
python -m src.recolector_masivo
El recolector descargará partidas desde Challenger/Grandmaster/Master en LAS, LAN, NA y BR. Puedes ajustar la meta de partidas (ej. meta=20000) editando el código en src/recolector_masivo.py.

⚠️ Importante: No subas tu config.json a GitHub. Ya está incluido en .gitignore para tu seguridad.

📋 Paso 7: (Opcional) Entrena el modelo con tus datos
Una vez que hayas recolectado suficientes partidas (al menos 500 por línea), entrena los modelos:

bash
python -m src.entrenador_ia
Esto generará los archivos data/modelo_ia.pkl (predicción multiclase) y data/modelo_1v1.pkl (predicción 1v1).

📁 Estructura del proyecto
text
lol-recommender-ai/
├── assets/               # Imágenes de campeones, runas, objetos y hechizos
│   ├── champs/
│   ├── runas/
│   ├── items/
│   └── campeones.json    # Mapeo de IDs a nombres
├── data/                 # Datos estáticos y base de datos
│   ├── lol_data.db       # Base de datos SQLite con partidas
│   ├── modelo_ia.pkl     # Modelo de IA entrenado (multiclase)
│   ├── modelo_1v1.pkl    # Modelo de IA entrenado (1v1)
│   └── champion_data.json # Etiquetas por campeón (roles, etc.)
├── src/                  # Código fuente
│   ├── db_manager.py     # Gestión de la base de datos
│   ├── recolector_masivo.py # Crawler de partidas desde Riot API
│   ├── entrenador_ia.py  # Entrenamiento de los modelos Random Forest
│   ├── motor_ia.py       # Motor de inferencia (predicción de counters)
│   ├── recomendador.py   # Lógica de builds, runas, counters y bans
│   ├── lcu_api.py        # Conexión con el cliente de LoL (LCU)
│   ├── riot_api.py       # Descarga de datos de Data Dragon
│   └── app.py            # Interfaz gráfica CustomTkinter
├── setup.py              # Instalador automático
├── requirements.txt      # Dependencias de Python
└── README.md
🛠️ Tecnologías utilizadas
Python 3.10+

CustomTkinter – Interfaz gráfica moderna y oscura

SQLite3 – Base de datos local

Scikit-learn – Modelos Random Forest para predicción multiclase y 1v1

Pandas & NumPy – Procesamiento de datos

Requests – Llamadas a la API de Riot y Data Dragon

Pillow – Manejo de imágenes

ThreadPoolExecutor – Recolección masiva concurrente

📌 Requisitos previos
League of Legends instalado (para usar el radar en vivo)

Python 3.10 o superior

Conexión a Internet (para descargar los datos iniciales y actualizar assets)

🤝 Contribuciones
Si quieres mejorar el proyecto, ¡eres bienvenido! Algunas ideas:

Añadir soporte para otros modos (ARAM, Clash)

Implementar más métricas de análisis (KDA por campeón, control de visión)

Optimizar la interfaz para resolución móvil

Agregar más visualizaciones de datos (gráficos de winrate por parche)

Integración con Discord bot para consultas en vivo

Para contribuir, abre un issue o envía un pull request.

📄 Licencia
MIT – Libre para uso personal y educativo. No incluye los datos de Riot Games como propios.

💬 Soporte
Si tienes problemas o preguntas, abre un issue en GitHub. ¡Buena suerte en la Grieta! 🏆