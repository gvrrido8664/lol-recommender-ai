import pandas as pd
import numpy as np
import joblib
import os
import sys
import warnings
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

# Añadir el directorio raíz al path para evitar errores de importación al ejecutarlo directamente
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.db_manager import obtener_conexion, DATA_DIR
from src.riot_api import cargar_campeones, normalizar_nombre_champ
from src.tags_champions import (
    obtener_tag, obtener_nivel_cc, obtener_dano, obtener_poder_temprano,
    obtener_escalado, es_tanque, es_mago, es_tirador, es_asesino, es_luchador, es_soporte
)

MODELO_PATH = os.path.join(DATA_DIR, "modelo_ia.pkl")
MODELO_1V1_PATH = os.path.join(DATA_DIR, "modelo_1v1.pkl")

# ═══════════════════════════════════════════════════════════════
# FEATURE ENGINEERING — CONVERSIÓN CATEGÓRICA → NUMÉRICA
# ═══════════════════════════════════════════════════════════════

_EARLY_MAP = {"weak": 1, "neutral": 2, "strong": 3}
_SCALING_MAP = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
_DAMAGE_MAP = {"AD": 0, "AP": 1, "HYBRID": 2}
# Orden para one-hot de clase
_CLASSES = ["Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"]
_CLASS_DICT = {c: i for i, c in enumerate(_CLASSES)}  # Tank=0, Fighter=1, ...

# ═══════════════════════════════════════════════════════════════
# FEATURE ENGINEERING — VECTOR COMPARATIVO
# ═══════════════════════════════════════════════════════════════

def extraer_features_comparativas(aliado: str, enemigo: str) -> np.ndarray:
    """
    Construye un vector de características comparativas entre dos campeones.
    
    Features (15 dimensiones):
      0: delta_cc          (cc_aliado - cc_enemigo)
      1: delta_mobility    (movilidad_aliado - movilidad_enemigo)
      2: delta_early       (early_power_aliado - early_power_enemigo)
      3: delta_scaling     (scaling_aliado - scaling_enemigo)
      4: aliado_es_tanque  (1/0)
      5: enemigo_es_tanque (1/0)
      6: aliado_tiene_cc_alto (cc >= 4)
      7: enemigo_tiene_cc_alto (cc >= 4)
      8: aliado_burst_vs_tanque (aliado burst y enemigo es tanque)
      9: aliado_tank_vs_true_dmg (aliado es tanque y enemigo tiene daño verdadero implícito)
     10: mismo_tipo_dano  (1 si ambos son AD o ambos AP)
     11: aliado_early_strong (1 si early_power == strong)
     12: enemigo_early_strong
     13: aliado_hiperescala (1 si scaling == hyper)
     14: enemigo_hiperescala
    """
    tag_a = obtener_tag(aliado)
    tag_e = obtener_tag(enemigo)

    # Extraer valores base
    cc_a = tag_a.get("cc_level", 1)
    cc_e = tag_e.get("cc_level", 1)
    mob_a = tag_a.get("mobility", 2)
    mob_e = tag_e.get("mobility", 2)
    early_a = _EARLY_MAP.get(tag_a.get("early_power", "neutral"), 2)
    early_e = _EARLY_MAP.get(tag_e.get("early_power", "neutral"), 2)
    scale_a = _SCALING_MAP.get(tag_a.get("scaling", "mid"), 2)
    scale_e = _SCALING_MAP.get(tag_e.get("scaling", "mid"), 2)
    dmg_a = tag_a.get("damage_type", "AD")
    dmg_e = tag_e.get("damage_type", "AD")
    class_a = tag_a.get("champion_class", "Fighter")
    class_e = tag_e.get("champion_class", "Fighter")
    sub_a = tag_a.get("sub_class", "")
    sub_e = tag_e.get("sub_class", "")
    profile_a = tag_a.get("damage_profile", "dps")
    profile_e = tag_e.get("damage_profile", "dps")

    features = np.zeros(15, dtype=np.float32)

    # 0-3: Deltas
    features[0] = cc_a - cc_e
    features[1] = mob_a - mob_e
    features[2] = early_a - early_e
    features[3] = scale_a - scale_e

    # 4-5: Es tanque
    features[4] = 1.0 if class_a == "Tank" else 0.0
    features[5] = 1.0 if class_e == "Tank" else 0.0

    # 6-7: CC alto (>=4)
    features[6] = 1.0 if cc_a >= 4 else 0.0
    features[7] = 1.0 if cc_e >= 4 else 0.0

    # 8: Aliado burst vs enemigo tanque
    features[8] = 1.0 if (profile_a == "burst" and class_e == "Tank") else 0.0

    # 9: Aliado tanque vs enemigo con daño verdadero (clases que counterean tanks)
    tank_melters = {"Assassin", "Fighter"}
    features[9] = 1.0 if (class_a == "Tank" and class_e in tank_melters) else 0.0

    # 10: Mismo tipo de daño (los dos AD o los dos AP)
    features[10] = 1.0 if (dmg_a == dmg_e and dmg_a != "HYBRID") else 0.0

    # 11-12: Early strong
    features[11] = 1.0 if tag_a.get("early_power") == "strong" else 0.0
    features[12] = 1.0 if tag_e.get("early_power") == "strong" else 0.0

    # 13-14: Hiperescala
    features[13] = 1.0 if tag_a.get("scaling") == "hyper" else 0.0
    features[14] = 1.0 if tag_e.get("scaling") == "hyper" else 0.0

    return features

# ═══════════════════════════════════════════════════════════════
# INTERPRETE MATEMÁTICO
# ═══════════════════════════════════════════════════════════════

def interpretar_features(aliado: str, enemigo: str) -> list:
    """
    Lee el vector comparativo y devuelve una lista de ventajas/desventajas
    clave en lenguaje humano.
    """
    feats = extraer_features_comparativas(aliado, enemigo)
    insights = []

    delta_cc = int(feats[0])
    delta_mob = int(feats[1])
    delta_early = int(feats[2])
    delta_scale = int(feats[3])

    if delta_cc >= 3:
        insights.append(f"🔒 Dominio total de CC (+{delta_cc}): {aliado} anula las opciones de {enemigo}")
    elif delta_cc >= 1:
        insights.append(f"🔒 Ventaja de CC (+{delta_cc}): {aliado} controla mejor las peleas")
    elif delta_cc <= -3:
        insights.append(f"⚠️ Déficit crítico de CC ({delta_cc}): {enemigo} te supera ampliamente en control")
    elif delta_cc <= -1:
        insights.append(f"⚠️ Desventaja de CC ({delta_cc}): {enemigo} tiene mejor control de masas")

    if delta_mob >= 3:
        insights.append(f"👟 Dominio de movilidad (+{delta_mob}): {aliado} dicta el ritmo del enfrentamiento")
    elif delta_mob >= 1:
        insights.append(f"👟 Ventaja de movilidad (+{delta_mob}): {aliado} puede esquivar y reposicionarse mejor")
    elif delta_mob <= -2:
        insights.append(f"🐌 Desventaja de movilidad ({delta_mob}): {enemigo} es significativamente más ágil")

    if delta_early >= 1:
        insights.append(f"⚡ Pico de poder más temprano (+{delta_early}): {aliado} domina el early game")
    elif delta_early <= -1:
        insights.append(f"📉 Poder temprano inferior ({delta_early}): {enemigo} es más fuerte al inicio")

    if delta_scale >= 1:
        insights.append(f"📈 Mejor escalado (+{delta_scale}): {aliado} supera a {enemigo} en late game")
    elif delta_scale <= -1:
        insights.append(f"⏳ Escalado inferior ({delta_scale}): {enemigo} escala mejor que tú. Cierra la partida rápido")

    # Tanque vs burst
    if feats[8] == 1.0:
        insights.append(f"🛡️ {aliado} es burst vs Tanque: {enemigo} absorbe tu daño inicial con facilidad")
    if feats[9] == 1.0:
        insights.append(f"⚔️ {enemigo} counterea tanques: tu armadura/resistencia natural es menos efectiva")

    if feats[10] == 1.0:
        insights.append(f"🔄 Ambos comparten tipo de daño — las builds defensivas son más eficientes")

    if feats[13] == 1.0:
        insights.append(f"🐉 {aliado} es hyper-carry: juega seguro en early y escala imparable")
    if feats[14] == 1.0:
        insights.append(f"🐉 {enemigo} es hyper-carry: acaba la partida antes de que escale")

    if not insights:
        insights.append("⚖️ Enfrentamiento equilibrado: la habilidad individual y el macro decidirán")

    return insights

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
        df_parts['champion'] = df_parts['champion'].apply(normalizar_nombre_champ)
        
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

        conteo = {}
        for etiqueta in y:
            conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
        mascara = [conteo[etiqueta] >= 2 for etiqueta in y]
        if not all(mascara):
            descartados = sum(1 for v in mascara if not v)
            print(f"  🧹 Filtrando {descartados} ejemplos de campeones con <2 apariciones")
            X = X[mascara]
            y = [etiqueta for etiqueta, m in zip(y, mascara) if m]
        
        # Modelo optimizado: menos arboles + profundidad limitada = archivo mucho mas pequeño
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        modelo = RandomForestClassifier(
            n_estimators=25,
            max_depth=12,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        modelo.fit(X_train, y_train)

        y_pred = modelo.predict(X_test)
        report = classification_report(y_test, y_pred, labels=sorted(set(y_test)), zero_division=0)
        proba = modelo.predict_proba(X_test)
        try:
            auc = roc_auc_score(y_test, proba, multi_class='ovr', labels=sorted(set(y_test)))
        except ValueError:
            auc = None
        print(f"     📊 {rol}: samples={len(X_train)}/{len(X_test)}, "
              f"accuracy={round(modelo.score(X_test, y_test), 3)}, "
              f"roc_auc={round(auc, 3) if auc else 'N/A'}")
        print(f"        Classification report:\n{report}")
        
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
    print("   ⚡ FEATURE ENGINEERING: usando stats comparativas de tags_champions")
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
            WHERE p1.team_position = %s
              AND p2.team_position = %s
              AND p1.team != p2.team
        """
        df = pd.read_sql_query(query, conn, params=(rol, rol))
        df['aliado'] = df['aliado'].apply(normalizar_nombre_champ)
        df['enemigo'] = df['enemigo'].apply(normalizar_nombre_champ)

        if len(df) < 15:
            print(f"  ⚠️ Datos insuficientes para {rol} ({len(df)}). Saltando...")
            continue

        print(f"  ✅ Entrenando {rol} con {len(df)} enfrentamientos directos...")

        # FEATURE VECTOR: one-hot campeones (aliado + enemigo) + 15 features comparativas
        n_features_comparativas = 15
        X = np.zeros((len(df), n * 2 + n_features_comparativas), dtype=np.float32)
        y = df['win'].values

        for idx, row in df.iterrows():
            aliado = row['aliado']
            enemigo = row['enemigo']

            # One-hot de campeones
            if aliado in todos_campeones:
                X[idx, todos_campeones.index(aliado)] = 1
            if enemigo in todos_campeones:
                X[idx, n + todos_campeones.index(enemigo)] = 1

            # Features comparativas (deltas + interacciones)
            try:
                feats = extraer_features_comparativas(aliado, enemigo)
                X[idx, n * 2:] = feats
            except Exception:
                pass  # Si falla por campeón desconocido, deja features en 0

        modelo = RandomForestClassifier(
            n_estimators=30,        # 25→30 con más features
            max_depth=14,           # más profundidad para capturar interacciones
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        modelo.fit(X, y)
        modelos_binarios[rol] = modelo
        print(f"     📊 {rol}: {n_features_comparativas} features comparativas añadidas a {n*2} de one-hot")

    conn.close()
    
    if modelos_binarios:
        joblib.dump(modelos_binarios, MODELO_1V1_PATH, compress=3)
        print(f"🎉 Modelo IA 1v1 (con feature engineering) guardado en {MODELO_1V1_PATH}\n")
    else:
        print("❌ No se pudo entrenar el modelo 1v1.\n")

if __name__ == "__main__":
    entrenar_modelos()         
    entrenar_modelo_1v1()