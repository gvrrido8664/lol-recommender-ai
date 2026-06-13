import os
import joblib
import json
import numpy as np

from src.tags_champions import obtener_tag

_EARLY_MAP = {"weak": 1, "neutral": 2, "strong": 3}
_SCALING_MAP = {"early": 1, "mid": 2, "late": 3, "hyper": 4}


def extraer_features_equipo(champs):
    n = max(len(champs), 1)
    feats = np.zeros(15, dtype=np.float32)
    cc_sum, mob_sum, early_sum, scale_sum = 0, 0, 0, 0
    ad_c, ap_c, hy_c = 0, 0, 0
    tank_c, fighter_c, assassin_c, mage_c, marksman_c, support_c = 0, 0, 0, 0, 0, 0
    hyper_c = 0

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


class MotorIA:
    def __init__(self, ruta_modelo="data/modelo_ia.pkl"):
        self.ruta_modelo = ruta_modelo
        self.todos_los_modelos = {}
        self.modelo_actual = None
        self.lista_campeones_global = []
        self.lista_nombres_salida = []
        self.rol_activo = "MIDDLE"
        self._preparar_columnas_globales()
        self.cargar_todo_el_diccionario()

    def _preparar_columnas_globales(self):
        ruta_json = os.path.join("assets", "campeones.json")
        if os.path.exists(ruta_json):
            with open(ruta_json, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                self.lista_campeones_global = sorted(datos.values())

    def cargar_todo_el_diccionario(self):
        if os.path.exists(self.ruta_modelo):
            self.todos_los_modelos = joblib.load(self.ruta_modelo)
            self.cambiar_rol_activo("MIDDLE")

    def cambiar_rol_activo(self, nuevo_rol):
        bloque_rol = self.todos_los_modelos.get(nuevo_rol)
        if isinstance(bloque_rol, dict):
            self.modelo_actual = bloque_rol.get('model')
            self.rol_activo = nuevo_rol
            self.n_global = bloque_rol.get('n_global', len(self.lista_campeones_global))
            self.n_feats_equipo = bloque_rol.get('n_feats_equipo', 15)

            if self.lista_campeones_global:
                self.nombre_a_idx = {nombre: i for i, nombre in enumerate(self.lista_campeones_global)}
            else:
                campeones_global = bloque_rol.get('campeones_global', [])
                self.nombre_a_idx = {nombre: i for i, nombre in enumerate(campeones_global)}

            clases = self.modelo_actual.classes_
            if isinstance(clases[0], str):
                self.lista_nombres_salida = list(clases)
            else:
                lista_original = bloque_rol.get('champs', [])
                if lista_original:
                    self.lista_nombres_salida = sorted(lista_original)
                else:
                    self.lista_nombres_salida = []

    def predecir_counters(self, enemigos):
        if self.modelo_actual is None:
            return []

        columnas_entrada = self.modelo_actual.n_features_in_
        input_vector = np.zeros(columnas_entrada, dtype=np.float32)

        offset_tags = self.n_global

        for nombre in enemigos:
            if nombre in self.nombre_a_idx:
                idx = self.nombre_a_idx[nombre]
                if idx < self.n_global:
                    input_vector[idx] = 1.0

        feats_enemigos = extraer_features_equipo(enemigos)
        input_vector[offset_tags:offset_tags + self.n_feats_equipo] = feats_enemigos

        X = input_vector.reshape(1, -1)
        probabilidades = self.modelo_actual.predict_proba(X)[0]

        clases = self.modelo_actual.classes_
        bloque_rol = self.todos_los_modelos.get(self.rol_activo, {})
        champs_del_rol = bloque_rol.get('champs', [])

        if isinstance(clases[0], str):
            idx_to_name = list(clases)
        else:
            if not champs_del_rol:
                return []
            nombres_ordenados = sorted(champs_del_rol)
            idx_to_name = [nombres_ordenados[i] for i in clases]

        resultados = []
        set_champs_rol = set(champs_del_rol)
        for i, nombre in enumerate(idx_to_name):
            if nombre in set_champs_rol:
                winrate = probabilidades[i] * 100
                resultados.append((nombre, winrate))

        resultados.sort(key=lambda x: x[1], reverse=True)
        top3 = resultados[:3]
        return [{"campeon": nombre, "winrate": prob} for nombre, prob in top3]
