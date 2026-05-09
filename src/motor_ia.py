import os
import joblib
import json
import numpy as np

class MotorIA:
    def __init__(self, ruta_modelo="data/modelo_ia.pkl"):
        self.ruta_modelo = ruta_modelo
        self.todos_los_modelos = {}
        self.modelo_actual = None
        self.lista_campeones_global = []  # 172 campeones (alfabético)
        self.lista_nombres_salida = []    # Nombres del rol específico (sincronizada con model.classes_)
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

            # Sincronizar la lista de nombres con las clases internas del modelo
            clases = self.modelo_actual.classes_
            if isinstance(clases[0], str):
                # Las clases ya contienen los nombres directamente
                self.lista_nombres_salida = list(clases)
            else:
                # Las clases son números (0,1,2...) => asumimos orden alfabético de nombres
                lista_original = bloque_rol.get('champs', [])
                if lista_original:
                    self.lista_nombres_salida = sorted(lista_original)
                else:
                    self.lista_nombres_salida = []

    def predecir_counters(self, enemigos):
        if self.modelo_actual is None:
            return []

        # 1. Construir vector de entrada (sin cambios)
        columnas_entrada = self.modelo_actual.n_features_in_
        input_vector = np.zeros(columnas_entrada)
        for nombre in enemigos:
            if nombre in self.lista_campeones_global:
                idx = self.lista_campeones_global.index(nombre)
                if idx < columnas_entrada:
                    input_vector[idx] = 1

        X = input_vector.reshape(1, -1)
        probabilidades = self.modelo_actual.predict_proba(X)[0]  # array (n_clases_modelo,)
        print("=== DIAGNÓSTICO ===")
        print("Rol activo:", self.rol_activo)
        print("Clases del modelo:", self.modelo_actual.classes_)
        print("Cantidad de clases:", len(self.modelo_actual.classes_))
        bloque = self.todos_los_modelos.get(self.rol_activo, {})
        champs_rol = bloque.get('champs', [])
        print("Campeones del rol:", champs_rol[:10], "... total:", len(champs_rol))
        print("Vector de entrada (suma):", input_vector.sum())
        print("Probabilidades:", probabilidades)
        print("=====================")

        # 2. Obtener el mapeo exacto: índice en probabilidades -> nombre de campeón
        clases = self.modelo_actual.classes_  # list/array de strings o enteros
        bloque_rol = self.todos_los_modelos.get(self.rol_activo, {})
        champs_del_rol = bloque_rol.get('champs', [])

        if isinstance(clases[0], str):
            # Caso ideal: las clases ya son nombres
            idx_to_name = list(clases)  # idx -> nombre
        else:
            # Clases numéricas: asumimos que corresponden al orden alfabético de champs del rol
            if not champs_del_rol:
                return []
            # La codificación típica de LabelEncoder: el entero i corresponde
            # al i-ésimo nombre en la lista ordenada alfabéticamente.
            nombres_ordenados = sorted(champs_del_rol)
            # Creamos un mapeo idx (entero) -> nombre SOLO para los índices presentes en el modelo
            idx_to_name = [nombres_ordenados[i] for i in clases]  # clases son enteros 0,1,2...

        # 3. Filtrar solo campeones que están en champs_del_rol (seguridad extra)
        #    y que existan en el modelo (todos los de idx_to_name lo están).
        resultados = []
        set_champs_rol = set(champs_del_rol)
        for i, nombre in enumerate(idx_to_name):
            if nombre in set_champs_rol:
                winrate = probabilidades[i] * 100  # porcentaje real
                resultados.append((nombre, winrate))

        # 4. Top 3 por probabilidad
        resultados.sort(key=lambda x: x[1], reverse=True)
        top3 = resultados[:3]
        return [{"campeon": nombre, "winrate": prob} for nombre, prob in top3]