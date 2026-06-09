import os
import json
import requests

class DataDragonAPI:
    def __init__(self):
        self.versiones_url = "https://ddragon.leagueoflegends.com/api/versions.json"
        self.cache_dir = "assets"
        self.cache_file = os.path.join(self.cache_dir, "campeones.json")
        
        # Crear la carpeta assets si no existe
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def obtener_version_actual(self):
        """Obtiene la versión más reciente del parche de LoL."""
        try:
            response = requests.get(self.versiones_url)
            response.raise_for_status()
            return response.json()[0] # El primer elemento siempre es el parche actual
        except Exception as e:
            print(f"❌ Error al consultar la versión de Riot: {e}")
            return "14.4.1" # Fallback de seguridad
            
    def actualizar_cache(self):
        """Descarga los datos oficiales y crea un diccionario {ID: Nombre}"""
        version = self.obtener_version_actual()
        print(f"🌐 Contactando a Data Dragon (Parche {version})...")
        
        # Pedimos los datos en español de España (es_ES) — consistente con riot_api.py
        url_campeones = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/champion.json"
        
        try:
            response = requests.get(url_campeones)
            response.raise_for_status()
            datos_brutos = response.json()['data']
            
            # Armamos un diccionario limpio y ultra ligero
            diccionario_campeones = {}
            for nombre_interno, datos in datos_brutos.items():
                id_numerico = str(datos['key'])
                nombre_real = datos['name']
                diccionario_campeones[id_numerico] = nombre_real
                
            # Lo guardamos en el disco duro
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(diccionario_campeones, f, ensure_ascii=False, indent=4)
                
            print("✅ Base de datos de campeones actualizada y guardada en caché.")
            return diccionario_campeones
            
        except Exception as e:
            print(f"❌ Error al descargar campeones: {e}")
            return {}

    def cargar_diccionario(self):
        """Carga el diccionario desde el disco. Si no existe, lo descarga."""
        if os.path.exists(self.cache_file):
            print("📂 Cargando base de datos de campeones desde el almacenamiento local...")
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return self.actualizar_cache()

# BLOQUE DE PRUEBA
if __name__ == "__main__":
    print("="*40)
    print("Iniciando Motor de Traducción...")
    print("="*40)
    
    ddragon = DataDragonAPI()
    diccionario = ddragon.cargar_diccionario()
    
    if diccionario:
        print("\n🧪 Prueba de traducción con los IDs de tu partida:")
        ids_enemigos_de_tu_partida = ['38', '14', '267', '143', '81']
        
        for id_champ in ids_enemigos_de_tu_partida:
            nombre = diccionario.get(id_champ, "Desconocido")
            print(f" - El ID {id_champ} corresponde a: {nombre}")