import requests
import time
import os
import sqlite3
import random
from collections import deque
from .db_manager import obtener_conexion

# =============================================================================
# CONFIGURACIÓN DE LA API Y CRAWLER
# =============================================================================
API_KEY = "RGAPI-5426a7f5-d646-47a0-a8ad-669b115d599f" 
REGION_ROUTING = "americas" # Incluye NA, BR, LAN, LAS
HEADERS = {"X-Riot-Token": API_KEY}

def pausa_segura():
    """Hace una pausa para asegurar que nunca rompamos la regla de 100 peticiones / 2 mins."""
    time.sleep(1.25)

def obtener_puuid_semilla(game_name, tag_line):
    """Solo se usa una vez para arrancar el motor."""
    url = f"https://{REGION_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    try:
        respuesta = requests.get(url, headers=HEADERS)
        pausa_segura()
        respuesta.raise_for_status()
        return respuesta.json()["puuid"]
    except Exception as e:
        print(f"❌ Error obteniendo semilla inicial: {e}")
        return None

def obtener_historial_partidas(puuid, cantidad=10):
    url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count={cantidad}"
    try:
        respuesta = requests.get(url, headers=HEADERS)
        pausa_segura()
        if respuesta.status_code == 429: return []
        respuesta.raise_for_status()
        return respuesta.json()
    except:
        return []

def descargar_y_guardar_partida(match_id):
    """Descarga la partida, la guarda y retorna los PUUIDs de los 10 jugadores para seguir explorando."""
    conn = obtener_conexion()
    cur = conn.cursor()
    
    cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
    if cur.fetchone():
        conn.close()
        return [] # La partida ya existe, no devolvemos puuids para no hacer ciclos infinitos

    url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    try:
        respuesta = requests.get(url, headers=HEADERS)
        pausa_segura()
        if respuesta.status_code == 429: 
            time.sleep(10)
            return []
        respuesta.raise_for_status()
        datos = respuesta.json()
    except:
        conn.close()
        return []

    info = datos.get("info", {})
    duracion = info.get("gameDuration", 0)
    if duracion < 600:
        conn.close()
        return []

    nuevos_puuids = []
    try:
        cur.execute("INSERT INTO matches (match_id, game_version, game_duration) VALUES (?, ?, ?)", 
                    (match_id, info.get("gameVersion", "0"), duracion))
        
        for p in info.get("participants", []):
            puuid_jugador = p.get("puuid")
            if puuid_jugador:
                nuevos_puuids.append(puuid_jugador)

            champion = p.get("championName", "")
            if champion == "MonkeyKing": champion = "Wukong"
            
            items_list = [str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0]
            
            cur.execute("""
                INSERT INTO participantes (match_id, champion, team_position, team, win, items)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (match_id, champion, p.get("teamPosition", ""), p.get("teamId", 0), 
                  1 if p.get("win") else 0, ",".join(items_list)))
            
        conn.commit()
        print(f"✅ Partida {match_id} guardada. (+10 jugadores nuevos descubiertos)")
    except Exception as e:
        conn.rollback()
    finally:
        conn.close()
        
    return nuevos_puuids

def iniciar_crawler(meta_partidas=1000):
    """El motor de la bola de nieve."""
    # Arrancamos con tu cuenta o la de un amigo en LAS/LAN/NA para entrar a la red de 'americas'
    print("🌱 Plantando la semilla inicial...")
    puuid_actual = obtener_puuid_semilla("Gvrrido", "LUCKY") # Pon tu nombre y tag real de LAS aquí
    
    if not puuid_actual:
        print("❌ No se pudo iniciar el Crawler. Revisa el nombre semilla o tu API Key.")
        return

    # Usamos un Set para no revisar al mismo jugador dos veces
    puuids_vistos = set([puuid_actual])
    # Cola de jugadores por explorar
    cola_puuids = deque([puuid_actual])
    
    partidas_guardadas = 0

    print(f"🚀 Iniciando recolección masiva. Meta: {meta_partidas} partidas.")
    
    while cola_puuids and partidas_guardadas < meta_partidas:
        jugador_objetivo = cola_puuids.popleft()
        match_ids = obtener_historial_partidas(jugador_objetivo, cantidad=5)
        
        for match_id in match_ids:
            if partidas_guardadas >= meta_partidas: break
            
            puuids_descubiertos = descargar_y_guardar_partida(match_id)
            
            if puuids_descubiertos:
                partidas_guardadas += 1
                
                # Agregamos a los jugadores desconocidos a la cola para investigarlos después
                for nuevo_puuid in puuids_descubiertos:
                    if nuevo_puuid not in puuids_vistos:
                        puuids_vistos.add(nuevo_puuid)
                        cola_puuids.append(nuevo_puuid)
        
        # Para evitar que la cola se haga infinita y consuma RAM, la mezclamos y podamos de vez en cuando
        if len(cola_puuids) > 5000:
            lista_temp = list(cola_puuids)
            random.shuffle(lista_temp)
            cola_puuids = deque(lista_temp[:1000])
            
    print(f"🎉 ¡Crawler terminado! Se descargaron {partidas_guardadas} partidas de jugadores aleatorios.")

if __name__ == "__main__":
    if API_KEY == "RGAPI-PON-TU-API-KEY-AQUI":
        print("⚠️ ¡ATENCIÓN! Coloca tu API Key.")
    else:
        # Puedes cambiar el 100 por el número de partidas que quieras descargar (ej. 500, 1000)
        iniciar_crawler(meta_partidas=100)