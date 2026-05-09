# 🤖 LoL Recommender V2 - Inteligencia Artificial

Asistente de Draft y Análisis de Meta para League of Legends, impulsado por Machine Learning (Random Forest) y la API oficial de Riot Games. 

Esta aplicación analiza miles de partidas en tiempo real para sugerir los mejores counters, calcular probabilidades de victoria en el carril (1v1) y generar builds analíticas filtrando la "basura estadística".

## 🛠️ Arquitectura y Tecnologías
*   **Lenguaje:** Python 3.10+
*   **Interfaz Gráfica:** Tkinter + Pillow (Patrón Maestro-Detalle)
*   **Base de Datos:** SQLite3 (Motor local rápido y ligero)
*   **Machine Learning:** Scikit-Learn + Numpy
*   **Extracción de Datos:** Peticiones concurrentes (`ThreadPoolExecutor`) a Riot API

---

## ⚠️ Sobre la Base de Datos (El problema de los "Datos Perdidos")

Por motivos de seguridad (evitar filtración de API Keys) y rendimiento (evitar subir archivos `.db` de más de 150MB), **este repositorio no incluye la base de datos de partidas ni el modelo de IA ya entrenado**.

Al clonar este proyecto, tu entorno estará "vacío". Como colaborador, debes ejecutar el Motor de Recolección para generar tus propios datos locales antes de poder usar la aplicación. Sigue las instrucciones de instalación a continuación.

---

## 🚀 Guía de Instalación (Setup de 1 Clic)

Hemos preparado un script automatizado que instala las dependencias y descarga la base de datos pre-entrenada (>9,000 partidas) para que no tengas que recolectar los datos desde cero.

1. Clona el repositorio y abre la terminal en la carpeta.
2. Crea y activa tu entorno virtual:
   `python -m venv venv`
   `venv\Scripts\activate` (En Windows)
3. Ejecuta el instalador automático:
   `python setup.py`
4. Inicia la aplicación:
   `python app.py`

*(Nota: Si deseas recolectar tus propios datos más adelante, recuerda configurar tu API Key en `src/recolector_masivo.py`).*