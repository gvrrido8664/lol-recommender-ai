import sqlite3
import pandas as pd
import numpy as np
import joblib
import os
import sys
from sklearn.ensemble import RandomForestClassifier

# Añadir el directorio raíz al path para evitar errores de importación al ejecutarlo directamente
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.db_manager import obtener_conexion, DATA_DIR
from src.riot_api import cargar_campeones

MODELO_PATH = os.path.join(DATA_DIR, "modelo_ia.pkl")
MODELO_1V1_PATH = os.path.join(DATA_DIR, "modelo_1v1.pkl")

def obtener_lista_campeones():
    """Obtiene la lista global y ordenada de campeones, idéntica a app.py para evitar desajustes de matrices."""
    champs_dict = cargar_campeones()
    return sorted(list(set([data["nombre"] for data in champs_dict.values()])))

def entrenar_modelos():
    print("🧠 Iniciando entrenamiento multiclase (Predicción de Picks por Composición)...")
    conn = obtener_conexion()
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    
    todos_campeones = obtener_lista_campeones()
    nombre_a_idx = {nombre: i for i, nombre in enumerate(todos_campeones)}
    n_global = len(todos_campeones)
    
    modelos_guardados = {}
    
    for rol in roles:
        print(f"📊 Construyendo dataset para {rol}...")
        
        query = """
            SELECT match_id, team, champion, team_position
            FROM participantes
            WHERE team_position IS NOT NULL AND team_position != ''
        """
        df_parts = pd.read_sql_query(query, conn)
        
        # Limpieza de nombres heredada de Riot
        df_parts['champion'] = df_parts['champion'].replace('MonkeyKing', 'Wukong')
        
        conteo = df_parts.groupby("match_id").size()
        match_ids_validos = conteo[conteo == 10].index
        df_parts = df_parts[df_parts["match_id"].isin(match_ids_validos)]
        
        dataset_filas = []
        campeones_vistos = set()
        
        for match_id, grupo in df_parts.groupby("match_id"):
            equipos = grupo["team"].unique()
            if len(equipos) != 2: continue
            
            for equipo_aliado in equipos:
                equipo_enemigo = equipos[1] if equipos[0] == equipo_aliado else equipos[0]
                
                aliados_rol = grupo[(grupo["team"] == equipo_aliado) & (grupo["team_position"] == rol)]
                if aliados_rol.empty: continue
                
                for _, aliado in aliados_rol.iterrows():
                    pick_aliado = aliado["champion"]
                    enemigos = grupo[grupo["team"] == equipo_enemigo]["champion"].tolist()
                    
                    if len(enemigos) != 5: continue
                    
                    vector = np.zeros(n_global)
                    for champ in enemigos:
                        if champ in nombre_a_idx:
                            vector[nombre_a_idx[champ]] = 1
                    
                    dataset_filas.append((vector, pick_aliado))
                    campeones_vistos.add(pick_aliado)
        
        # Con 800 partidas globales, 15 ejemplos es un límite sano por línea
        if len(dataset_filas) < 15:
            print(f"  ⚠️ Datos insuficientes para {rol} ({len(dataset_filas)} ejemplos). Saltando...")
            continue
        
        print(f"  ✅ {len(dataset_filas)} ejemplos, {len(campeones_vistos)} campeones distintos en {rol}")
        
        X = np.array([fila[0] for fila in dataset_filas])
        y = [fila[1] for fila in dataset_filas]
        
        # Modelo optimizado: menos árboles + profundidad limitada = archivo mucho más pequeño
        modelo = RandomForestClassifier(
            n_estimators=25,        # 100→25 (75% menos árboles)
            max_depth=12,           # limita profundidad de cada árbol
            min_samples_leaf=5,     # evita hojas con pocas muestras
            random_state=42,
            n_jobs=-1
        )
        modelo.fit(X, y)
        
        modelos_guardados[rol] = {
            "model": modelo,
            "champs": sorted(campeones_vistos)
        }
    
    conn.close()
    
    if modelos_guardados:
        # joblib con compresión 3 (gzip máxima) → reduce 10-50x vs pickle
        joblib.dump(modelos_guardados, MODELO_PATH, compress=3)
        print(f"🎉 Modelo IA de Draft guardado en {MODELO_PATH}")
    else:
        print("❌ No se pudo entrenar ningún modelo Draft.")

def entrenar_modelo_1v1():
    print("\n🧠 Entrenando modelo binario (Predicción 1v1 y Winrate predictivo)...")
    conn = obtener_conexion()
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    modelos_binarios = {}

    todos_campeones = obtener_lista_campeones()
    n = len(todos_campeones)

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
        df['aliado'] = df['aliado'].replace('MonkeyKing', 'Wukong')
        df['enemigo'] = df['enemigo'].replace('MonkeyKing', 'Wukong')

        if len(df) < 15:
            print(f"  ⚠️ Datos insuficientes para {rol} ({len(df)}). Saltando...")
            continue

        print(f"  ✅ Entrenando {rol} con {len(df)} enfrentamientos directos...")
        X = np.zeros((len(df), n * 2))
        y = df['win'].values

        for idx, row in df.iterrows():
            if row['aliado'] in todos_campeones:
                X[idx, todos_campeones.index(row['aliado'])] = 1
            if row['enemigo'] in todos_campeones:
                X[idx, n + todos_campeones.index(row['enemigo'])] = 1

        modelo = RandomForestClassifier(
            n_estimators=25,        # 100→25
            max_depth=12,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        modelo.fit(X, y)
        modelos_binarios[rol] = modelo

    conn.close()
    
    if modelos_binarios:
        joblib.dump(modelos_binarios, MODELO_1V1_PATH, compress=3)
        print(f"🎉 Modelo IA 1v1 guardado en {MODELO_1V1_PATH}\n")
    else:
        print("❌ No se pudo entrenar el modelo 1v1.\n")

if __name__ == "__main__":
    entrenar_modelos()         
    entrenar_modelo_1v1()