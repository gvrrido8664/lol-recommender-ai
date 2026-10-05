# NEXUS — análisis y recomendaciones

Proyecto personal de **Ignacio Garrido**, Ingeniero en Informática titulado. Desarrollo propio de la aplicación; librerías, plantillas, datos e imágenes de terceros conservan su autoría.

Aplicación Python/PySide6 con recomendaciones heurísticas, análisis de composiciones, coaching, persistencia y tareas de red en segundo plano. El dominio es League of Legends; el valor técnico está en integración de APIs, gestión de estado y separación de trabajo de red de la interfaz.

## Comprobación offline
Python 3.12+:
```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-offline.txt
.venv/Scripts/python -m pytest tests -q
```
Resultado verificado: **25 pruebas aprobadas**. Usan partidas ficticias y un adaptador SQLite en memoria; se bloquean las peticiones HTTP externas. No requieren Riot, PostgreSQL ni tokens. Los catálogos locales permiten analizar composiciones sin depender de descargas.

## Aplicación completa
```powershell
git clone https://github.com/gvrrido8664/lol-recommender-ai.git
```
Para utilizar esta entrega corregida, descomprime su paquete y trabaja en esa carpeta:
```powershell
python -m pip install -r requirements.txt
Copy-Item config.example.json config.json
python app.py
```
La aplicación se inicia mediante `app.py`; no existe `setup.py`. El arranque gráfico completo no se comprobó en esta revisión y requiere PySide6.

## Arquitectura y configuración
Coexisten el cliente HTTP `src/backend_client.py` (proxy backend y edge) y acceso PostgreSQL directo `src/db_manager.py` en módulos aún no migrados. Supabase puede alojar modelos e integración; no es una dependencia necesaria para las pruebas offline. Las URLs de la copia apuntan a localhost o deben configurarse con `SUPABASE_PROJECT_URL`, `NEXUS_BACKEND_URL` y `NEXUS_EDGE_URL`. Configura claves propias solo localmente; las variables de entorno tienen prioridad sobre `config.json`.

La entrega no incluye bases, replays, modelos privados ni credenciales embebidas. Se retiró el flujo de empaquetar secretos dentro del ejecutable. El historial original contiene una configuración con API_KEY: rota esa clave antes de compartir el historial existente. La copia tiene código sin `.git`.

## Límites
Las recomendaciones son heurísticas; no se afirma precisión predictiva ni mejora de victorias. El entrenamiento/inferencia completa de modelos y el proxy no se validaron. Datos e imágenes de Riot conservan sus derechos: [documentación Data Dragon](https://developer.riotgames.com/docs/lol#data-dragon).

English: desktop API integration, asynchronous network work and relational persistence; 25 isolated offline checks. Complete Qt/proxy integration remains to be exercised.
