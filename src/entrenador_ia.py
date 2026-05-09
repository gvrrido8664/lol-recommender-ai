import sqlite3
import pandas as pd
import numpy as np
import pickle
import os
import json
from sklearn.ensemble import RandomForestClassifier
from .db_manager import obtener_conexion, DATA_DIR

MODELO_PATH = os.path.join(DATA_DIR, "modelo_ia.pkl")

def cargar_lista_global_champs():
    """Devuelve la lista ordenada de los 172 campeones desde el JSON."""
    ruta_json = os.path.join("assets", "campeones.json")
    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return sorted(datos.values())  # nombres oficiales

def entrenar_modelos():
    print("🧠 Iniciando entrenamiento multiclase (predicción de counter)...")
    
    conn = obtener_conexion()
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    
    # Lista global de campeones para el one-hot
    todos_campeones = cargar_lista_global_champs()
    nombre_a_idx = {nombre: i for i, nombre in enumerate(todos_campeones)}
    n_global = len(todos_campeones)
    
    modelos_guardados = {}
    
    for rol in roles:
        print(f"📊 Construyendo dataset para {rol}...")
        
        # Obtenemos todas las partidas con el campeón aliado y la lista de enemigos.
        # Para cada match, agrupamos los participantes por equipo y posición.
        query = """
            SELECT match_id, team, champion, team_position
            FROM participantes
            WHERE team_position IS NOT NULL AND team_position != ''
        """
        df_parts = pd.read_sql_query(query, conn)
        
        # Filtrar solo partidas donde haya exactamente 10 jugadores (para evitar remakes)
        conteo = df_parts.groupby("match_id").size()
        match_ids_validos = conteo[conteo == 10].index
        df_parts = df_parts[df_parts["match_id"].isin(match_ids_validos)]
        
        # Separar aliados y enemigos según el rol
        dataset_filas = []
        campeones_vistos = set()
        
        for match_id, grupo in df_parts.groupby("match_id"):
            # Determinar los dos equipos
            equipos = grupo["team"].unique()
            if len(equipos) != 2:
                continue
            equipo_azul = equipos[0]  # podríamos ordenarlos pero da igual
            equipo_rojo = equipos[1]
            
            # Para cada equipo, vemos si tiene un jugador en el rol actual
            for equipo_aliado, equipo_enemigo in [(equipo_azul, equipo_rojo), (equipo_rojo, equipo_azul)]:
                aliados_rol = grupo[(grupo["team"] == equipo_aliado) & (grupo["team_position"] == rol)]
                if aliados_rol.empty:
                    continue
                # Puede haber múltiples entradas (en teoría una por match, pero por si acaso)
                for _, aliado in aliados_rol.iterrows():
                    pick_aliado = aliado["champion"]
                    # Los enemigos son todos los jugadores del otro equipo
                    enemigos = grupo[grupo["team"] == equipo_enemigo]["champion"].tolist()
                    if len(enemigos) != 5:
                        continue  # partida incompleta, ignorar
                    
                    # Vector one-hot de enemigos
                    vector = np.zeros(n_global)
                    for champ in enemigos:
                        if champ in nombre_a_idx:
                            vector[nombre_a_idx[champ]] = 1
                    
                    dataset_filas.append((vector, pick_aliado))
                    campeones_vistos.add(pick_aliado)
        
        if len(dataset_filas) < 50:
            print(f"  ⚠️ Datos insuficientes para {rol} ({len(dataset_filas)} ejemplos). Saltando...")
            continue
        
        print(f"  ✅ {len(dataset_filas)} ejemplos, {len(campeones_vistos)} campeones distintos")
        
        X = np.array([fila[0] for fila in dataset_filas])
        y = [fila[1] for fila in dataset_filas]  # strings
        
        modelo = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        modelo.fit(X, y)  # y son nombres → model.classes_ será lista de strings ordenada
        
        modelos_guardados[rol] = {
            "model": modelo,
            "champs": sorted(campeones_vistos)
        }
    
    conn.close()
    
    if modelos_guardados:
        with open(MODELO_PATH, "wb") as f:
            pickle.dump(modelos_guardados, f)
        print(f"🎉 Modelo multiclase guardado en {MODELO_PATH}")
    else:
        print("❌ No se pudo entrenar ningún modelo. Revisa los datos.")

def entrenar_modelo_1v1():
    print("🧠 Entrenando modelo binario (1v1)...")
    conn = obtener_conexion()
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    modelos_binarios = {}

    with open(os.path.join("assets", "campeones.json"), "r", encoding="utf-8") as f:
        todos = json.load(f)
    lista_global = sorted(todos.values())
    n = len(lista_global)

    for rol in roles:
        query = """
            SELECT p1.champion AS aliado, p2.champion AS enemigo, p1.win
            FROM participantes p1
            JOIN participantes p2 ON p1.match_id = p2.match_id
            WHERE p1.team_position = ? 
              AND p2.team_position = ?
              AND p1.team != p2.team
        """
        df = pd.read_sql_query(query, conn, params=(rol, rol))
        if len(df) < 50:
            print(f"  ⚠️ Datos insuficientes para {rol} ({len(df)}). Saltando...")
            continue

        print(f"  ✅ Entrenando {rol} con {len(df)} enfrentamientos 1v1...")
        X = np.zeros((len(df), n * 2))
        y = df['win'].values

        for idx, row in df.iterrows():
            if row['aliado'] in lista_global:
                X[idx, lista_global.index(row['aliado'])] = 1
            if row['enemigo'] in lista_global:
                X[idx, n + lista_global.index(row['enemigo'])] = 1

        modelo = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        modelo.fit(X, y)
        modelos_binarios[rol] = modelo

    conn.close()
    with open(os.path.join(DATA_DIR, "modelo_1v1.pkl"), "wb") as f:
        pickle.dump(modelos_binarios, f)
    print("🎉 Modelo 1v1 guardado en modelo_1v1.pkl")

if __name__ == "__main__":
    entrenar_modelos()         # multiclase para draft
    entrenar_modelo_1v1()      # binario para 1v1