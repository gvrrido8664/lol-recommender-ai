import sqlite3
import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from .db_manager import obtener_conexion, DATA_DIR

# Archivo donde guardaremos el "cerebro" entrenado
MODELO_PATH = os.path.join(DATA_DIR, "modelo_ia.pkl")

def entrenar_modelos():
    """Entrena un modelo predictivo por cada línea usando los datos recolectados."""
    print("🧠 Iniciando entrenamiento de la Inteligencia Artificial...")
    
    conn = obtener_conexion()
    
    # Roles oficiales de la API de Riot
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    modelos_guardados = {}
    
    for rol in roles:
        print(f"📊 Procesando datos para el carril: {rol}...")
        
        # Buscamos partidas donde se enfrentaron dos campeones en el mismo rol (equipos diferentes)
        query = """
            SELECT p1.champion AS aliado, p2.champion AS enemigo, p1.win
            FROM participantes p1
            JOIN participantes p2 ON p1.match_id = p2.match_id
            WHERE p1.team_position = ? 
              AND p2.team_position = ?
              AND p1.team != p2.team
        """
        df = pd.read_sql_query(query, conn, params=(rol, rol))
        
        # Si no hay suficientes partidas (mínimo unas 50 para que no falle), saltamos este rol
        if len(df) < 50:
            print(f"  ⚠️ Datos insuficientes para {rol} (solo {len(df)} enfrentamientos). Saltando...")
            continue
            
        print(f"  ✅ Entrenando {rol} con {len(df)} enfrentamientos...")
        
        # Obtenemos la lista de todos los campeones únicos que se jugaron en este rol
        campeones_unicos = pd.concat([df['aliado'], df['enemigo']]).unique().tolist()
        campeones_unicos.sort()
        n = len(campeones_unicos)
        
        # Creamos matrices de ceros (One-Hot Encoding)
        # Tamaño = (Número de partidas, Número de campeones * 2)
        X = np.zeros((len(df), n * 2))
        y = df['win'].values
        
        # Llenamos la matriz: Un 1 en la posición del aliado, y un 1 en la posición del enemigo
        for idx, row in df.iterrows():
            idx_aliado = campeones_unicos.index(row['aliado'])
            idx_enemigo = campeones_unicos.index(row['enemigo'])
            
            X[idx, idx_aliado] = 1                # Marca el campeón aliado
            X[idx, n + idx_enemigo] = 1           # Marca el campeón enemigo
            
        # Entrenamos el Random Forest
        # 100 "árboles de decisión" votando para predecir quién gana
        modelo = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        modelo.fit(X, y)
        
        # Guardamos el modelo y la lista de campeones exacta de este rol
        modelos_guardados[rol] = {
            "model": modelo,
            "champs": campeones_unicos
        }
        
    conn.close()
    
    # Exportamos el cerebro completo a un archivo .pkl
    if modelos_guardados:
        with open(MODELO_PATH, 'wb') as f:
            pickle.dump(modelos_guardados, f)
        print(f"🎉 ¡Entrenamiento exitoso! Cerebro IA guardado en {MODELO_PATH}")
    else:
        print("❌ No se pudo entrenar la IA. Necesitas recolectar más partidas primero.")

if __name__ == "__main__":
    entrenar_modelos()