import requests
import time
import os
import random
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from .db_manager import obtener_conexion

# =============================================================================
# CONFIGURACIÓN PRO
# =============================================================================
API_KEY = "RGAPI-5426a7f5-d646-47a0-a8ad-669b115d599f"
REGION_ROUTING = "americas" 
HEADERS = {"X-Riot-Token": API_KEY}

# Cola de jugadores pendientes y set de control para no repetir
cola_exploracion = deque()
jugadores_visitados = set()

def peticion_segura(url):
    """Maneja los límites de Riot (429) y errores de red de forma automática."""
    while True:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                espera = int(resp.headers.get("Retry-After", 10))
                print(f"⏳ Límite alcanzado. Esperando {espera}s...")
                time.sleep(espera)
            elif resp.status_code in [500, 502, 503, 504]:
                time.sleep(5)
            else:
                return None
        except Exception as e:
            time.sleep(2)
            continue

def procesar_jugador(puuid):
    """Descarga el historial de un jugador y procesa sus partidas."""
    url_historial = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count=10"
    match_ids = peticion_segura(url_historial)
    
    if not match_ids:
        return 0

    partidas_nuevas = 0
    for m_id in match_ids:
        if descargar_partida(m_id):
            partidas_nuevas += 1
    return partidas_nuevas

def descargar_partida(match_id):
    """Descarga y guarda la partida, alimentando la cola de exploración."""
    conn = obtener_conexion()
    cur = conn.cursor()
    
    # Evitar duplicados en la base de datos
    cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
    if cur.fetchone():
        conn.close()
        return False

    url_match = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    data = peticion_segura(url_match)
    
    if not data or "info" not in data:
        conn.close()
        return False

    info = data["info"]
    # Ignorar remakes
    if info.get("gameDuration", 0) < 600:
        conn.close()
        return False

    try:
        cur.execute("INSERT INTO matches (match_id, game_version, game_duration) VALUES (?, ?, ?)",
                    (match_id, info.get("gameVersion", "0"), info.get("gameDuration", 0)))
        
        for p in info.get("participants", []):
            # Alimentar la cola con nuevos jugadores encontrados
            p_puuid = p.get("puuid")
            if p_puuid and p_puuid not in jugadores_visitados:
                cola_exploracion.append(p_puuid)
                jugadores_visitados.add(p_puuid)

            champ = p.get("championName", "Wukong" if p.get("championName") == "MonkeyKing" else p.get("championName"))
            items = ",".join([str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0])
            
            cur.execute("""
                INSERT INTO participantes (match_id, champion, team_position, team, win, items)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (match_id, champ, p.get("teamPosition", ""), p.get("teamId", 0), 1 if p.get("win") else 0, items))
        
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        conn.close()

def ejecutar_recoleccion_masiva(nombre_inicio, tag_inicio, meta=5000):
    """Orquestador multihilo."""
    print(f"🌟 Iniciando gran recolección desde {nombre_inicio}#{tag_inicio}")
    
    # Obtener PUUID inicial
    url_id = f"https://{REGION_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{nombre_inicio}/{tag_inicio}"
    semilla = peticion_segura(url_id)
    
    if not semilla:
        print("❌ No se pudo encontrar al jugador semilla.")
        return

    cola_exploracion.append(semilla["puuid"])
    jugadores_visitados.add(semilla["puuid"])
    
    total_descargado = 0
    
    # Usamos ThreadPoolExecutor para procesar varios jugadores a la vez
    # 3 hilos es un balance seguro para no quemar la API Key de desarrollo rápidamente
    with ThreadPoolExecutor(max_workers=3) as executor:
        while total_descargado < meta and cola_exploracion:
            # Tomamos al siguiente jugador
            actual = cola_exploracion.popleft()
            
            # Mandamos la tarea al hilo
            futuro = executor.submit(procesar_jugador, actual)
            resultado = futuro.result()
            
            total_descargado += resultado
            print(f"📈 Total partidas en BD: {total_descargado} / {meta} (En cola: {len(cola_exploracion)})")
            
            # Pausa para respirar entre ciclos de hilos
            time.sleep(2)

if __name__ == "__main__":
    # Sustituye con tu nombre y etiqueta real en LAS/NA/LAN
    ejecutar_recoleccion_masiva("Gvrrido", "LUCKY", meta=20000)