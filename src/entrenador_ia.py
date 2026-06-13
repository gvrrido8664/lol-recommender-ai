import pandas as pd
import numpy as np
import joblib
import os
import sys
import time
import warnings
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

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

_EARLY_MAP = {"weak": 1, "neutral": 2, "strong": 3}
_SCALING_MAP = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
_DAMAGE_MAP = {"AD": 0, "AP": 1, "HYBRID": 2}
_CLASSES = ["Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"]
_CLASS_DICT = {c: i for i, c in enumerate(_CLASSES)}

N_FEATS_COMPARATIVAS = 15
N_FEATS_EQUIPO = 15


def extraer_features_equipo(champs):
    """Features agregadas de un equipo: CC, movilidad, balance de dano, clases, escalado."""
    n = max(len(champs), 1)
    feats = np.zeros(N_FEATS_EQUIPO, dtype=np.float32)

    cc_sum, mob_sum, early_sum, scale_sum = 0, 0, 0, 0
    ad_c, ap_c, hy_c = 0, 0, 0
    tank_c, fighter_c, assassin_c, mage_c, marksman_c, support_c = 0, 0, 0, 0, 0, 0
    hyper_c, early_strong_c = 0, 0

    for champ in champs:
        tag = obtener_tag(champ)
        cc_sum += tag.get("cc_level", 1)
        mob_sum += tag.get("mobility", 2)
        early_sum += _EARLY_MAP.get(tag.get("early_power", "neutral"), 2)
        scale_sum += _SCALING_MAP.get(tag.get("scaling", "mid"), 2)

        dmg = tag.get("damage_type", "AD")
        if dmg == "AD":
            ad_c += 1
        elif dmg == "AP":
            ap_c += 1
        else:
            hy_c += 1

        cls = tag.get("champion_class", "Fighter")
        if cls == "Tank":
            tank_c += 1
        elif cls == "Fighter":
            fighter_c += 1
        elif cls == "Assassin":
            assassin_c += 1
        elif cls == "Mage":
            mage_c += 1
        elif cls == "Marksman":
            marksman_c += 1
        elif cls == "Support":
            support_c += 1

        if tag.get("scaling") == "hyper":
            hyper_c += 1
        if tag.get("early_power") == "strong":
            early_strong_c += 1

    feats[0] = cc_sum
    feats[1] = cc_sum / n
    feats[2] = mob_sum / n
    feats[3] = early_sum / n
    feats[4] = scale_sum / n
    feats[5] = ad_c
    feats[6] = ap_c
    feats[7] = hy_c
    feats[8] = tank_c
    feats[9] = fighter_c
    feats[10] = assassin_c
    feats[11] = mage_c
    feats[12] = marksman_c
    feats[13] = support_c
    feats[14] = hyper_c

    return feats


def extraer_features_comparativas(aliado, enemigo):
    tag_a = obtener_tag(aliado)
    tag_e = obtener_tag(enemigo)

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
    profile_a = tag_a.get("damage_profile", "dps")

    features = np.zeros(N_FEATS_COMPARATIVAS, dtype=np.float32)

    features[0] = cc_a - cc_e
    features[1] = mob_a - mob_e
    features[2] = early_a - early_e
    features[3] = scale_a - scale_e
    features[4] = 1.0 if class_a == "Tank" else 0.0
    features[5] = 1.0 if class_e == "Tank" else 0.0
    features[6] = 1.0 if cc_a >= 4 else 0.0
    features[7] = 1.0 if cc_e >= 4 else 0.0
    features[8] = 1.0 if (profile_a == "burst" and class_e == "Tank") else 0.0
    tank_melters = {"Assassin", "Fighter"}
    features[9] = 1.0 if (class_a == "Tank" and class_e in tank_melters) else 0.0
    features[10] = 1.0 if (dmg_a == dmg_e and dmg_a != "HYBRID") else 0.0
    features[11] = 1.0 if tag_a.get("early_power") == "strong" else 0.0
    features[12] = 1.0 if tag_e.get("early_power") == "strong" else 0.0
    features[13] = 1.0 if tag_a.get("scaling") == "hyper" else 0.0
    features[14] = 1.0 if tag_e.get("scaling") == "hyper" else 0.0

    return features


def interpretar_features(aliado, enemigo):
    feats = extraer_features_comparativas(aliado, enemigo)
    insights = []

    delta_cc = int(feats[0])
    delta_mob = int(feats[1])
    delta_early = int(feats[2])
    delta_scale = int(feats[3])

    if delta_cc >= 3:
        insights.append(f"+{delta_cc} CC: {aliado} anula las opciones de {enemigo}")
    elif delta_cc >= 1:
        insights.append(f"+{delta_cc} CC: {aliado} controla mejor las peleas")
    elif delta_cc <= -3:
        insights.append(f"{delta_cc} CC: {enemigo} te supera ampliamente en control")
    elif delta_cc <= -1:
        insights.append(f"{delta_cc} CC: {enemigo} tiene mejor control de masas")

    if delta_mob >= 3:
        insights.append(f"+{delta_mob} Movilidad: {aliado} dicta el ritmo")
    elif delta_mob >= 1:
        insights.append(f"+{delta_mob} Movilidad: {aliado} puede esquivar mejor")
    elif delta_mob <= -2:
        insights.append(f"{delta_mob} Movilidad: {enemigo} es mas agil")

    if delta_early >= 1:
        insights.append(f"+{delta_early} Early: {aliado} domina el early game")
    elif delta_early <= -1:
        insights.append(f"{delta_early} Early: {enemigo} es mas fuerte al inicio")

    if delta_scale >= 1:
        insights.append(f"+{delta_scale} Escalado: {aliado} supera a {enemigo} en late game")
    elif delta_scale <= -1:
        insights.append(f"{delta_scale} Escalado: {enemigo} escala mejor. Cierra la partida pronto")

    if feats[8] == 1.0:
        insights.append(f"{aliado} es burst vs Tanque: {enemigo} absorbe tu dano")
    if feats[9] == 1.0:
        insights.append(f"{enemigo} counterea tanques naturalmente")
    if feats[10] == 1.0:
        insights.append("Ambos comparten tipo de dano: builds defensivas mas eficientes")
    if feats[13] == 1.0:
        insights.append(f"{aliado} es hyper-carry: juega seguro y escala imparable")
    if feats[14] == 1.0:
        insights.append(f"{enemigo} es hyper-carry: acaba antes de que escale")
    if not insights:
        insights.append("Enfrentamiento equilibrado: habilidad > counter")

    return insights


def obtener_lista_campeones():
    champs_dict = cargar_campeones()
    return sorted(list(set([data["nombre"] for data in champs_dict.values()])))


def _construir_vector_multiclase(enemigos, nombre_a_idx, n_global):
    v_enemigos = np.zeros(n_global, dtype=np.float32)
    for champ in enemigos:
        if champ in nombre_a_idx:
            v_enemigos[nombre_a_idx[champ]] = 1.0

    f_enemigos = extraer_features_equipo(enemigos)

    return np.concatenate([v_enemigos, f_enemigos])


def entrenar_modelos():
    print("Iniciando entrenamiento multiclase (Prediccion de Picks por Composicion)...")
    t0 = time.time()
    conn = obtener_conexion()
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

    todos_campeones = obtener_lista_campeones()
    nombre_a_idx = {nombre: i for i, nombre in enumerate(todos_campeones)}
    n_global = len(todos_campeones)
    n_total_features = n_global + N_FEATS_EQUIPO

    MODEL_HPARAMS = [
        {"n_estimators": 25,  "max_depth": 12, "min_samples_leaf": 5},
        {"n_estimators": 50,  "max_depth": 12, "min_samples_leaf": 5},
        {"n_estimators": 50,  "max_depth": 15, "min_samples_leaf": 5},
        {"n_estimators": 100, "max_depth": 12, "min_samples_leaf": 5},
        {"n_estimators": 100, "max_depth": 15, "min_samples_leaf": 5},
    ]

    print(f"  {n_global} campeones unicos, {n_total_features} features por muestra")

    modelos_guardados = {}

    for rol in roles:
        t_rol = time.time()
        print(f"Construyendo dataset para {rol}...")

        query = """
            SELECT match_id, team, champion, team_position
            FROM participantes
            WHERE team_position IS NOT NULL AND team_position != ''
        """
        df_parts = pd.read_sql_query(query, conn)
        df_parts['champion'] = df_parts['champion'].apply(normalizar_nombre_champ)

        conteo = df_parts.groupby("match_id").size()
        match_ids_validos = conteo[conteo == 10].index
        df_parts = df_parts[df_parts["match_id"].isin(match_ids_validos)]

        dataset_filas = []
        campeones_vistos = set()

        for match_id, grupo in df_parts.groupby("match_id"):
            equipos = grupo["team"].unique()
            if len(equipos) != 2:
                continue

            for equipo_aliado in equipos:
                equipo_enemigo = equipos[1] if equipos[0] == equipo_aliado else equipos[0]

                aliados_rol = grupo[(grupo["team"] == equipo_aliado) & (grupo["team_position"] == rol)]
                if aliados_rol.empty:
                    continue

                enemigos = grupo[grupo["team"] == equipo_enemigo]["champion"].tolist()

                if len(enemigos) != 5:
                    continue

                for _, aliado in aliados_rol.iterrows():
                    pick_aliado = aliado["champion"]
                    vector = _construir_vector_multiclase(enemigos, nombre_a_idx, n_global)
                    dataset_filas.append((vector, pick_aliado))
                    campeones_vistos.add(pick_aliado)

        if len(dataset_filas) < 15:
            print(f"  Datos insuficientes para {rol} ({len(dataset_filas)} ejemplos). Saltando...")
            continue

        print(f"  {len(dataset_filas)} ejemplos, {len(campeones_vistos)} campeones distintos en {rol}")

        X = np.array([fila[0] for fila in dataset_filas], dtype=np.float32)
        y = [fila[1] for fila in dataset_filas]

        conteo = {}
        for etiqueta in y:
            conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
        mascara = [conteo[etiqueta] >= 2 for etiqueta in y]
        if not all(mascara):
            descartados = sum(1 for v in mascara if not v)
            print(f"  Filtrando {descartados} ejemplos de campeones con <2 apariciones")
            X = X[mascara]
            y = [etiqueta for etiqueta, m in zip(y, mascara) if m]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        mejor_modelo = None
        mejor_acc = -1
        mejor_params = None

        for params in MODEL_HPARAMS:
            modelo = RandomForestClassifier(
                **params,
                random_state=42,
                n_jobs=-1
            )
            modelo.fit(X_train, y_train)
            acc = modelo.score(X_test, y_test)
            if acc > mejor_acc:
                mejor_acc = acc
                mejor_modelo = modelo
                mejor_params = params

        print(f"  Mejor config: {mejor_params} -> acc test={mejor_acc:.4f}")

        y_pred = mejor_modelo.predict(X_test)
        report = classification_report(
            y_test, y_pred, labels=sorted(set(y_test)), zero_division=0
        )

        proba = mejor_modelo.predict_proba(X_test)
        try:
            auc = roc_auc_score(
                y_test, proba, multi_class='ovr', labels=sorted(set(y_test))
            )
        except ValueError:
            auc = None

        kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        try:
            cv_scores = cross_val_score(
                mejor_modelo, X, y, cv=kf, scoring='accuracy', n_jobs=-1
            )
            cv_mean = np.mean(cv_scores)
            cv_std = np.std(cv_scores)
        except Exception:
            cv_mean, cv_std = None, None

        auc_str = f"roc_auc={auc:.4f}" if auc else "roc_auc=N/A"
        print(f"     {rol}: train={len(X_train)} test={len(X_test)} "
              f"accuracy={mejor_acc:.4f} {auc_str}")
        if cv_mean is not None:
            print(f"     CV 5-fold: acc={cv_mean:.4f} +/- {cv_std:.4f}")
        print(f"        Classification report:\n{report}")

        modelos_guardados[rol] = {
            "model": mejor_modelo,
            "champs": sorted(campeones_vistos),
            "campeones_global": todos_campeones,
            "n_features_total": n_total_features,
            "n_global": n_global,
            "n_feats_equipo": N_FEATS_EQUIPO,
        }

        print(f"  {rol} completado en {time.time() - t_rol:.1f}s")

    conn.close()

    if modelos_guardados:
        joblib.dump(modelos_guardados, MODELO_PATH, compress=3)
        print(f"Modelo IA de Draft guardado en {MODELO_PATH}")
        print(f"Tiempo total: {time.time() - t0:.1f}s")
    else:
        print("No se pudo entrenar ningun modelo Draft.")


def entrenar_modelo_1v1():
    print("\nEntrenando modelo binario (Prediccion 1v1 y Winrate predictivo)...")
    print("   FEATURE ENGINEERING: stats comparativas de tags_champions + RandomizedSearchCV")
    t0 = time.time()
    conn = obtener_conexion()
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    modelos_binarios = {}

    todos_campeones = obtener_lista_campeones()
    n = len(todos_campeones)

    for rol in roles:
        t_rol = time.time()
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
            print(f"  Datos insuficientes para {rol} ({len(df)}). Saltando...")
            continue

        print(f"  Entrenando {rol} con {len(df)} enfrentamientos directos...")

        X = np.zeros((len(df), n * 2 + N_FEATS_COMPARATIVAS), dtype=np.float32)
        y = df['win'].values

        for idx, row in df.iterrows():
            aliado = row['aliado']
            enemigo = row['enemigo']

            if aliado in todos_campeones:
                X[idx, todos_campeones.index(aliado)] = 1
            if enemigo in todos_campeones:
                X[idx, n + todos_campeones.index(enemigo)] = 1

            try:
                feats = extraer_features_comparativas(aliado, enemigo)
                X[idx, n * 2:] = feats
            except Exception:
                pass

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        HPARAMS_1V1 = [
            {"n_estimators": 100, "max_depth": 10, "min_samples_leaf": 5},
            {"n_estimators": 100, "max_depth": 15, "min_samples_leaf": 3},
            {"n_estimators": 200, "max_depth": 12, "min_samples_leaf": 5},
            {"n_estimators": 200, "max_depth": 18, "min_samples_leaf": 3},
            {"n_estimators": 300, "max_depth": 15, "min_samples_leaf": 5},
        ]

        mejor_modelo = None
        mejor_acc = -1
        mejor_params = None

        for params in HPARAMS_1V1:
            modelo = RandomForestClassifier(
                **params,
                random_state=42,
                n_jobs=-1
            )
            modelo.fit(X_train, y_train)
            acc = modelo.score(X_test, y_test)
            if acc > mejor_acc:
                mejor_acc = acc
                mejor_modelo = modelo
                mejor_params = params

        print(f"     Mejor config: {mejor_params} -> acc test={mejor_acc:.4f}")

        acc = accuracy_score(y_test, y_pred=mejor_modelo.predict(X_test))
        proba = mejor_modelo.predict_proba(X_test)
        try:
            auc = roc_auc_score(y_test, proba[:, 1])
        except ValueError:
            auc = None

        kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        try:
            cv_scores = cross_val_score(
                mejor_modelo, X, y, cv=kf, scoring='accuracy', n_jobs=-1
            )
            cv_mean = np.mean(cv_scores)
            cv_std = np.std(cv_scores)
        except Exception:
            cv_mean, cv_std = None, None

        print(f"     {rol}: train={len(X_train)} test={len(X_test)} "
              f"accuracy={acc:.4f} roc_auc={auc:.4f}" if auc else f"     {rol}: train={len(X_train)} test={len(X_test)} accuracy={acc:.4f} roc_auc=N/A")
        if cv_mean is not None:
            print(f"     CV 5-fold: acc={cv_mean:.4f} +/- {cv_std:.4f}")

        modelos_binarios[rol] = mejor_modelo
        print(f"  {rol} completado en {time.time() - t_rol:.1f}s")

    conn.close()

    if modelos_binarios:
        joblib.dump(modelos_binarios, MODELO_1V1_PATH, compress=3)
        print(f"Modelo IA 1v1 guardado en {MODELO_1V1_PATH}")
        print(f"Tiempo total: {time.time() - t0:.1f}s\n")
    else:
        print("No se pudo entrenar el modelo 1v1.\n")


if __name__ == "__main__":
    entrenar_modelos()
    entrenar_modelo_1v1()
