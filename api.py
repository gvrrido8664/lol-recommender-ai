import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import joblib
import numpy as np
from src.entrenador_ia import extraer_features_comparativas, interpretar_features
from src.db_manager import obtener_historial_drafts, obtener_conexion
from src.recomendador import recomendar_picks_vivo, analizar_composicion, obtener_tag, obtener_nivel_cc, obtener_counters, obtener_top_items, obtener_top_runas, obtener_top_hechizos, obtenermejoresbaneos

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importamos la lógica de negocio existente
from src.riot_api import cargar_campeones, cargar_mapeo_ids, cargar_runas, cargar_hechizos
from src.recomendador import recomendar_picks_vivo, analizar_composicion
from src.db_manager import obtener_historial_drafts
from src.coaching_ia import generar_reporte_coach
from src.analizador_fatiga import analizar_fatiga
from src.perfil_jugador import analizar_personalidad, detectar_habitos, generar_objetivos_semanales, analizar_emocional_vs_wr
from src.lcu_api import LCUConnector

# Configurar logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus-api")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
modelo_1v1 = {}
try:
    ruta_modelo = os.path.join(BASE_DIR, "data", "modelo_1v1.pkl")
    if os.path.exists(ruta_modelo):
        modelo_1v1 = joblib.load(ruta_modelo)
        logger.info(f"Modelo 1v1 cargado en la API: {len(modelo_1v1)} roles")
except Exception as e:
    logger.error(f"Error cargando modelo 1v1: {e}")

nombres_campeones_global = sorted(list(set([c["nombre"] for c in cargar_campeones().values()])))

nombre_a_id = {}
for k, c in cargar_campeones().items():
    nombre_a_id[c["nombre"]] = k
nombre_a_id["Wukong"] = "MonkeyKing"
nombre_a_id["Maestro Yi"] = "MasterYi"
nombre_a_id["Kha'Zix"] = "Khazix"

app = FastAPI(title="NEXUS Local API", version="1.0.0")

# Permitir conexiones desde cualquier Frontend local (React/Vite usualmente corren en 5173 o 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── RUTAS DE DATOS ESTÁTICOS ─────────────────────────────────

@app.get("/api/campeones")
def get_campeones():
    """Devuelve el diccionario completo de campeones cargado desde el caché/Riot"""
    campeones = cargar_campeones()
    ids = cargar_mapeo_ids()
    data = {}
    for num_id, str_id in ids.items():
        if str_id in campeones:
            data[num_id] = campeones[str_id]
            data[num_id]["key"] = num_id
    return {"status": "success", "data": data}

# ─── RUTAS DEL RECOMENDADOR (WRAPPER DIRECTO) ─────────────────

class DraftRequest(BaseModel):
    aliados: list[str]
    enemigos: list[str]
class SimuladorRequest(BaseModel):
    aliado: str
    enemigo: str
    rol: str

@app.post("/api/simulador")
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

        # Datos de la DB (usando IDs internos)
        enemigo_db = nombre_a_id.get(enemigo, enemigo)
        aliado_db = nombre_a_id.get(aliado, aliado)
        
        counters = obtener_counters(rol_api, enemigo_db, min_partidas=10)
        wr_real = None
        partidas_real = 0
        for c_name, wr, p in counters:
            if c_name == aliado_db:
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
        logger.error(f"Error en simulador: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

@app.post("/api/recomendacion/vivo")
def get_recomendacion_vivo(req: DraftRequest):
    """
    Ruta wrapper que delega la ejecución a la lógica de negocio base.
    """
    try:
        # Ejecutamos el módulo recomendador
        recomendaciones = recomendar_picks_vivo(req.aliados, req.enemigos, req.mi_rol)
        return {"status": "success", "data": recomendaciones}
    except Exception as e:
        logger.error(f"Error en recomendar_picks_vivo: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/recomendacion/composicion")
def get_analisis_composicion(req: DraftRequest):
    try:
        # Ejecutamos el análisis
        analisis = analizar_composicion(req.aliados, req.enemigos)
        return {"status": "success", "data": analisis}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/meta-builds")
def get_meta_builds(linea: str, vs: str):
    """
    Retorna los counters y builds óptimas para un matchup.
    """
    try:
        rol_api = linea
        if rol_api == "MID": rol_api = "MIDDLE"
        if rol_api == "ADC": rol_api = "BOTTOM"
        if rol_api == "SUPPORT": rol_api = "UTILITY"
        if rol_api == "JUNGLA": rol_api = "JUNGLE"
        
        nombre_a_id = {v["nombre"]: k for k, v in cargar_campeones().items()}
        vs_db = nombre_a_id.get(vs, vs)
        # Fixes para campeones con IDs diferentes
        if vs == "Wukong": vs_db = "MonkeyKing"
        if vs == "Renata Glasc": vs_db = "Renata"
        if vs == "Nunu y Willump": vs_db = "Nunu"
        
        resultados = obtener_counters(rol_api, vs_db, min_partidas=20)
        matchups = []
        conn = obtener_conexion()
        
        runas_dict = cargar_runas()
        spells_dict = cargar_hechizos()
        
        id_a_nombre = {k: v["nombre"] for k, v in cargar_campeones().items()}
        id_a_nombre["MonkeyKing"] = "Wukong"
        
        for champ, winrate, partidas in resultados:
            if winrate <= 50:
                continue
                
            ids_start, ids_fin = obtener_top_items(champ, rol_api, enemigos=[vs_db], conn=conn)
            runas_raw = obtener_top_runas(champ, rol_api, conn=conn)
            spells_raw = obtener_top_hechizos(champ, rol_api, conn=conn)
            
            runas_urls = []
            for r in runas_raw:
                icono = runas_dict.get(str(r), {}).get("icono", "")
                if not icono:
                    runas_urls.append("")
                else:
                    runas_urls.append(f"https://ddragon.leagueoflegends.com/cdn/img/{icono}")
                    
            spells_urls = []
            for s in spells_raw:
                icono = spells_dict.get(str(s), {}).get("icono", "")
                if icono:
                    spells_urls.append(f"https://ddragon.leagueoflegends.com/cdn/14.10.1/img/spell/{icono}")
                else:
                    spells_urls.append("")
            
            champ_name = id_a_nombre.get(champ, champ)
            
            matchups.append({
                "id": champ,
                "name": champ_name,
                "wr": winrate,
                "matches": partidas,
                "build": {
                    "starters": ids_start,
                    "finales": ids_fin,
                    "runas": runas_urls,
                    "spells": spells_urls
                }
            })
            
        conn.close()
        return {"status": "success", "data": matchups}
    except Exception as e:
        logger.error(f"Error en /api/meta-builds: {e}")
        return {"status": "error", "message": str(e)}

from collections import Counter

@app.get("/api/bans")
def get_bans(linea: str, tipo: str = "global"):
    """
    Retorna la tier list de bans, global o personal.
    """
    try:
        rol_api = linea
        if rol_api == "MID": rol_api = "MIDDLE"
        if rol_api == "ADC": rol_api = "BOTTOM"
        if rol_api == "SUPPORT": rol_api = "UTILITY"
        if rol_api == "JUNGLA": rol_api = "JUNGLE"
        
        id_a_nombre = {k: v["nombre"] for k, v in cargar_campeones().items()}
        id_a_nombre["MonkeyKing"] = "Wukong"
        
        bans = []
        
        if tipo == "personal":
            lcu = LCUConnector()
            try:
                fase = lcu.obtener_fase_juego()
            except Exception:
                fase = None
                
            if not fase:
                return {"status": "error", "message": "No se pudo conectar al cliente de LoL para obtener tu historial personal."}
            
            # Obtener últimas 20 partidas
            historial = lcu.obtener_historial_extendido(cantidad=20)
            if not historial:
                return {"status": "error", "message": "No se encontró historial personal suficiente."}
                
            champ_vs = Counter()
            for g in historial:
                role = (g.get("role") or g.get("lane") or "").upper()
                api_role = role
                if role in ("SUPPORT",): api_role = "UTILITY"
                elif role in ("BOT", "ADC"): api_role = "BOTTOM"
                elif role in ("JUNGLA",): api_role = "JUNGLE"
                elif role in ("MID",): api_role = "MIDDLE"
                
                if api_role != rol_api:
                    continue
                    
                champ_list = g.get("enemyTeam", [])
                if not champ_list:
                    continue
                    
                for c in champ_list:
                    name = c.get("championName") or c.get("championId", "")
                    if name:
                        champ_vs[name] += 1
                        
            total = sum(champ_vs.values())
            if total < 3:
                return {"status": "error", "message": "No tienes suficientes partidas recientes contra este rol para un análisis personal preciso."}
                
            for champ, count in champ_vs.most_common(15):
                rate = round(count / total * 100, 1)
                champ_name = id_a_nombre.get(champ, champ)
                bans.append({
                    "id": champ,
                    "name": champ_name,
                    "banrate": rate,
                    "matches": count
                })
        else:
            # Global
            resultados = obtenermejoresbaneos(rol_api, min_partidas=20)
            if not resultados:
                return {"status": "error", "message": "No hay suficientes datos globales para esta línea."}
                
            for champ, banrate, partidas in resultados[:15]:
                champ_name = id_a_nombre.get(champ, champ)
                bans.append({
                    "id": champ,
                    "name": champ_name,
                    "banrate": banrate,
                    "matches": partidas
                })
                
        return {"status": "success", "data": bans}
    except Exception as e:
        logger.error(f"Error en /api/bans: {e}")
        return {"status": "error", "message": str(e)}

# ─── SERVIDOR LOCAL PARA PRUEBAS (Opcional) ───────────────────────────────────

# ─── RUTAS DE BASE DE DATOS ───────────────────────────────────

@app.get("/api/historial/drafts")
def get_historial_drafts():
    """Ejecuta la consulta a PostgreSQL de la base de datos remota"""
    try:
        historial = obtener_historial_drafts()
        return {"status": "success", "data": historial}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── WEBSOCKETS (PARA EL RADAR EN TIEMPO REAL) ────────────────

@app.websocket("/ws/radar")
async def websocket_radar(websocket: WebSocket):
    """
    Endpoint para conectar el Frontend web y recibir eventos del LCU en tiempo real.
    """
    await websocket.accept()
    lcu = LCUConnector()
    mapeo_ids = cargar_mapeo_ids()
    API_TO_ROL = {"TOP": "TOP", "JUNGLE": "JUNGLA", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}

    def procesar_nombre(cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0":
            nombre = mapeo_ids.get(final_id, "Desconocido")
            return "Wukong" if nombre == "MonkeyKing" else nombre
        return None

    try:
        while True:
            try:
                draft = lcu.obtener_sesion_draft()
            except Exception:
                draft = None
            
            if not draft:
                await websocket.send_json({"isActive": False})
            else:
                rol_api = lcu.obtener_mi_rol(draft)
                rol_es = API_TO_ROL.get(rol_api, "MID")
                
                picks_al = []
                picks_en = []
                
                for j in draft.get("myTeam", []):
                    champ = procesar_nombre(j.get("championId", 0), j.get("championPickIntent", 0))
                    if champ: picks_al.append(champ)
                
                for j in draft.get("theirTeam", []):
                    champ = procesar_nombre(j.get("championId", 0), j.get("championPickIntent", 0))
                    if champ: picks_en.append(champ)
                
                try:
                    sugerencias = recomendar_picks_vivo(rol_es, picks_al, picks_en)
                except Exception as e:
                    logger.error(f"Error generando sugerencias: {e}")
                    sugerencias = {}

                await websocket.send_json({
                    "isActive": True,
                    "myRole": rol_es,
                    "allyPicks": picks_al,
                    "enemyPicks": picks_en,
                    "suggestions": sugerencias
                })
                
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        logger.info("Cliente Frontend desconectado del Radar")
    except Exception as e:
        logger.error(f"Error en websocket_radar: {e}")

@app.websocket("/ws/ingame")
async def websocket_ingame(websocket: WebSocket):
    await websocket.accept()
    lcu = LCUConnector()
    
    def get_champ_name(raw_name):
        if not raw_name: return "Desconocido"
        return "Wukong" if raw_name == "MonkeyKing" else raw_name

    try:
        while True:
            try:
                fase = lcu.obtener_fase_juego()
            except Exception:
                fase = None

            if fase not in ("InProgress", "GameStart"):
                await websocket.send_json({"isActive": False})
            else:
                jugadores, game_info = lcu.obtener_liveclient_data()
                if not jugadores or (isinstance(game_info, dict) and game_info.get("status") == "loading"):
                    await websocket.send_json({"isActive": True, "isLoading": True})
                else:
                    game_time = game_info.get("gameTime", 0) if isinstance(game_info, dict) else 0
                    blue_team = []
                    red_team = []
                    
                    for p in jugadores:
                        team = p.get("team", "ORDER")
                        champ = get_champ_name(p.get("championName", ""))
                        scores = p.get("scores", {})
                        items = [{"id": it.get("itemID"), "name": it.get("displayName", "")} for it in p.get("items", [])]
                        
                        player_data = {
                            "summonerName": p.get("summonerName", ""),
                            "championName": champ,
                            "kills": scores.get("kills", 0),
                            "deaths": scores.get("deaths", 0),
                            "assists": scores.get("assists", 0),
                            "cs": scores.get("creepScore", 0),
                            "items": items,
                        }
                        
                        if team == "ORDER":
                            blue_team.append(player_data)
                        else:
                            red_team.append(player_data)
                    
                    a_nombres = [p["championName"] for p in blue_team]
                    e_nombres = [p["championName"] for p in red_team]
                    
                    compBlue = {"ad": 0, "ap": 0, "tanks": 0}
                    compRed = {"ad": 0, "ap": 0, "tanks": 0}
                    
                    if len(a_nombres) > 0:
                        try:
                            ad_a, ap_a, tk_a = analizar_composicion(a_nombres)
                            compBlue = {"ad": ad_a, "ap": ap_a, "tanks": tk_a}
                        except: pass
                    if len(e_nombres) > 0:
                        try:
                            ad_e, ap_e, tk_e = analizar_composicion(e_nombres)
                            compRed = {"ad": ad_e, "ap": ap_e, "tanks": tk_e}
                        except: pass
                        
                    await websocket.send_json({
                        "isActive": True,
                        "isLoading": False,
                        "gameTime": game_time,
                        "blueTeam": blue_team,
                        "redTeam": red_team,
                        "compBlue": compBlue,
                        "compRed": compRed
                    })
            
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        logger.info("Cliente Frontend desconectado de InGame")
    except Exception as e:
        logger.error(f"Error en websocket_ingame: {e}")

# ─── RUTAS DE PERFIL Y COACHING ───────────────────────────────

@app.get("/api/perfil")
def get_perfil_y_coaching():
    try:
        identidad = None
        historial = []
        lcu = LCUConnector()
        
        # Intentamos obtener datos reales del LCU
        if lcu.conectar():
            logger.info("LCU conectado. Obteniendo perfil en vivo...")
            perfil_lcu = lcu.obtener_perfil()
            if perfil_lcu:
                ligas_lcu = lcu.obtener_ligas()
                puuid = perfil_lcu.get("puuid")
                summonerId = perfil_lcu.get("summonerId")
                
                # Nombre real (Riot ID)
                nombre_real = perfil_lcu.get("gameName") or perfil_lcu.get("displayName") or "Invocador"
                tag_line = perfil_lcu.get("tagLine")
                if tag_line and nombre_real != "Invocador":
                    nombre_real = f"{nombre_real}#{tag_line}"
                
                # Formatear Identidad
                identidad = {
                    "nombre": nombre_real,
                    "nivel": perfil_lcu.get("summonerLevel", 30),
                    "icono": perfil_lcu.get("profileIconId", 29),
                    "soloq": {"tier": "UNRANKED", "division": "", "lp": 0, "wins": 0, "losses": 0},
                    "flex": {"tier": "UNRANKED", "division": "", "lp": 0, "wins": 0, "losses": 0}
                }
                if ligas_lcu and "queues" in ligas_lcu:
                    for q in ligas_lcu["queues"]:
                        tipo = q.get("queueType", "")
                        data = {
                            "tier": q.get("tier", "UNRANKED"),
                            "division": q.get("division", ""),
                            "lp": q.get("leaguePoints", 0),
                            "wins": q.get("wins", 0),
                            "losses": q.get("losses", 0)
                        }
                        if "SOLO" in tipo:
                            identidad["soloq"] = data
                        elif "FLEX" in tipo:
                            identidad["flex"] = data

                # Obtener Historial (15 partidas)
                historial_bruto = lcu.obtener_historial_extendido(puuid, 0, 15)
                queue_map = {
                    420: "Ranked Solo", 440: "Ranked Flex", 400: "Normal Draft", 
                    430: "Blind Pick", 480: "Quickplay", 490: "Quickplay", 450: "ARAM", 
                    700: "Clash", 830: "Bots", 840: "Bots", 850: "Bots", 900: "URF", 
                    1090: "TFT", 1700: "Arena", 1900: "URF", 3140: "Práctica", 0: "Custom"
                }
                for match in historial_bruto:
                    try:
                        participant_data = match.get("participants", [{}])[0]
                        # Buscar el participantId correcto del local player
                        if summonerId:
                            pid = 1
                            for pi in match.get("participantIdentities", []):
                                player = pi.get("player", {})
                                if str(player.get("summonerId", "")) == str(summonerId) or str(player.get("accountId", "")) == str(summonerId) or str(player.get("puuid", "")) == str(puuid):
                                    pid = pi.get("participantId")
                                    break
                            for p in match.get("participants", []):
                                if p.get("participantId") == pid:
                                    participant_data = p
                                    break
                        
                        queue_id = match.get("queueId", 0)
                        game_mode = queue_map.get(queue_id, "Personalizada" if queue_id == 0 else f"Especial ({queue_id})")
                        
                        historial.append({
                            "gameId": match.get("gameId", 0),
                            "gameDuration": match.get("gameDuration", 0),
                            "gameCreation": match.get("gameCreation", 0),
                            "gameMode": game_mode,
                            "participants": [
                                {
                                    "championId": participant_data.get("championId", 0),
                                    "stats": participant_data.get("stats", {})
                                }
                            ]
                        })
                    except Exception as ex:
                        logger.error(f"Error procesando partida en LCU: {ex}")

        # Si falló el LCU o no hay datos, usamos el Fallback (mock_data.json)
        if not identidad or not historial:
            logger.info("Fallo al obtener datos del LCU. Usando mock_data de fallback.")
            mock_path = os.path.join(BASE_DIR, "src", "mock_data.json")
            if not os.path.exists(mock_path):
                return {"status": "error", "message": "No hay datos del LCU ni mock_data."}
            with open(mock_path, "r", encoding="utf-8") as f:
                mock_data = json.load(f)
            historial = mock_data.get("historial", [])
            identidad = mock_data.get("identidad", {})
        
        # Generamos datos del coach
        datos_fatiga = analizar_fatiga(historial)
        
        datos_extra = {
            "personalidad": analizar_personalidad(historial),
            "insights": detectar_habitos(historial),
            "objetivos": generar_objetivos_semanales(historial),
            "emocional": analizar_emocional_vs_wr(historial)
        }
        
        reporte_coach = generar_reporte_coach(historial, identidad.get("nombre", "Invocador"), datos_extra, datos_fatiga)
        
        # Payload final para el frontend (Súper Dashboard)
        return {
            "status": "success",
            "data": {
                "identidad": identidad,
                "historial": historial,
                "fatiga": datos_fatiga,
                "insights": datos_extra,
                "coaching_report": reporte_coach
            }
        }
    except Exception as e:
        import traceback
        logger.error(f"Error en perfil: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Iniciamos el servidor en el puerto 8000
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
