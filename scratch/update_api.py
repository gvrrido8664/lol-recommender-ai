import os

api_path = r"C:\Users\User\Desktop\angel\lol-recommender-ai\api.py"

with open(api_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports
new_imports = """from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import joblib
import numpy as np
from src.entrenador_ia import extraer_features_comparativas, interpretar_features
from src.db_manager import obtener_historial_drafts, obtener_counters
from src.recomendador import recomendar_picks_vivo, analizar_composicion, obtener_tag, obtener_nivel_cc
"""

content = content.replace(
    "from fastapi import FastAPI, WebSocket, WebSocketDisconnect",
    new_imports
)

# 2. Add global model loading after logger setup
model_loading = """
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
modelo_1v1 = {}
try:
    ruta_modelo = os.path.join(BASE_DIR, "data", "modelo_1v1.pkl")
    if os.path.exists(ruta_modelo):
        modelo_1v1 = joblib.load(ruta_modelo)
        logger.info(f"Modelo 1v1 cargado en la API: {len(modelo_1v1)} roles")
except Exception as e:
    logger.error(f"Error cargando modelo 1v1: {e}")

nombres_campeones_global = [c["id"] for c in cargar_campeones().values()]
"""

content = content.replace(
    "app = FastAPI(title=\"Nexus API\", description=\"Wrapper para la lógica nativa del recomendador\")",
    model_loading + "\napp = FastAPI(title=\"Nexus API\", description=\"Wrapper para la lógica nativa del recomendador\")"
)

# 3. Replace the simular_matchup endpoint
old_endpoint = """@app.post("/api/simulador")
def simular_matchup(req: SimuladorRequest):
    \"\"\"
    Endpoint para el Simulador 1v1.
    Nota: Temporalmente devuelve datos estáticos para validar la conexión Axios.
    En el siguiente paso conectaremos la lógica real de predecir_ia.
    \"\"\"
    try:
        # Aquí inyectaremos el código de predecir_ia y modelo_1v1
        return {
            "status": "success",
            "data": {
                "probabilidad": 44.9,
                "nivel_texto": "⚠️ MATCHUP DESFAVORABLE",
                "stats_comparativas": []
            }
        }
    except Exception as e:
        logger.error(f"Error en simulador: {e}")
        return {"status": "error", "message": str(e)}"""

new_endpoint = """@app.post("/api/simulador")
def simular_matchup(req: SimuladorRequest):
    try:
        aliado = req.aliado
        enemigo = req.enemigo
        
        # Mapeo de roles a API (Si envian TOP, lo transformamos si hace falta)
        rol_api = req.rol
        if rol_api == "MID": rol_api = "MIDDLE"
        if rol_api == "BOTTOM" or rol_api == "ADC": rol_api = "BOTTOM"
        if rol_api == "SUPPORT": rol_api = "UTILITY"

        # Validaciones de modelo
        if not aliado or not enemigo or not modelo_1v1.get(rol_api):
            return {"status": "error", "message": "Modelo no disponible para ese rol o faltan datos."}

        # Extracción de Features (copiado de app.py)
        n = len(nombres_campeones_global)
        N_COMP = 15
        X = np.zeros(n * 2 + N_COMP)
        if aliado in nombres_campeones_global: 
            X[nombres_campeones_global.index(aliado)] = 1
        if enemigo in nombres_campeones_global: 
            X[n + nombres_campeones_global.index(enemigo)] = 1
        try:
            feats = extraer_features_comparativas(aliado, enemigo)
            X[n * 2:] = feats
        except Exception:
            pass

        # Predicción Base
        prob = modelo_1v1[rol_api].predict_proba(X.reshape(1, -1))[0][1] * 100

        # Datos de la DB
        counters = obtener_counters(rol_api, enemigo, min_partidas=10)
        wr_real = None
        partidas_real = 0
        for c_name, wr, p in counters:
            if c_name == aliado:
                wr_real = wr
                partidas_real = p
                break

        if wr_real is not None:
            prob_base = (prob * 0.4) + (wr_real * 0.6)
        else:
            prob_base = prob

        # Varianza
        prob_final = 50 + ((prob_base - 50) * 1.8)
        prob_final = max(0, min(100, prob_final))

        # Textos y niveles
        if prob_final > 54:
            color = "#10b981"
            texto = "🔥 HARD COUNTER (Ventaja Absoluta)"
        elif prob_final >= 51.5:
            color = "#10b981"
            texto = "✅ VENTAJA LIGERA"
        elif prob_final >= 48.5:
            color = "#f59e0b"
            texto = "⚔️ MATCHUP DE HABILIDAD (50/50)"
        else:
            color = "#e63946"
            texto = "⚠️ MATCHUP DESFAVORABLE"

        # Barras comparativas
        try:
            t_a = obtener_tag(aliado)
            t_e = obtener_tag(enemigo)
            
            cc_a = obtener_nivel_cc(aliado)
            cc_e = obtener_nivel_cc(enemigo)
            
            mob_a = t_a.get("mobility", 2)
            mob_e = t_e.get("mobility", 2)
            
            _EM = {"weak": 1, "neutral": 2, "strong": 3}
            early_a = _EM.get(t_a.get("early_power", "neutral"), 2)
            early_e = _EM.get(t_e.get("early_power", "neutral"), 2)
            
            _SM = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
            scale_a = _SM.get(t_a.get("scaling", "mid"), 2)
            scale_e = _SM.get(t_e.get("scaling", "mid"), 2)

            stats = {
                "cc": {"aliado": cc_a, "enemigo": cc_e, "max": 5},
                "movilidad": {"aliado": mob_a, "enemigo": mob_e, "max": 5},
                "early": {"aliado": early_a, "enemigo": early_e, "max": 3},
                "escalado": {"aliado": scale_a, "enemigo": scale_e, "max": 4}
            }

            info_aliado = {"clase": t_a.get('champion_class','?'), "dano": t_a.get('damage_type','?')}
            info_enemigo = {"clase": t_e.get('champion_class','?'), "dano": t_e.get('damage_type','?')}
        except Exception:
            stats = {}
            info_aliado = {}
            info_enemigo = {}

        # Interpretar features para la caja final
        insights_res = []
        try:
            insights = interpretar_features(aliado, enemigo)
            for ins in insights:
                if "Desventaja" in ins or "Déficit" in ins or "contra" in ins:
                    c = "#e63946"
                elif "Ventaja" in ins or "Dominio" in ins or "mejor" in ins or "dicta" in ins:
                    c = "#10b981"
                elif "hyper-carry" in ins:
                    c = "#f59e0b"
                else:
                    c = "#64748b"
                insights_res.append({"texto": ins, "color": c})
        except Exception:
            pass

        return {
            "status": "success",
            "data": {
                "probabilidad": round(prob_final, 1),
                "nivel_texto": texto,
                "nivel_color": color,
                "wr_real": wr_real,
                "partidas_real": partidas_real,
                "stats": stats,
                "info_aliado": info_aliado,
                "info_enemigo": info_enemigo,
                "insights": insights_res
            }
        }
    except Exception as e:
        import traceback
        logger.error(f"Error en simulador: {e}\\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}"""

content = content.replace(old_endpoint, new_endpoint)

with open(api_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("api.py actualizado exitosamente.")
