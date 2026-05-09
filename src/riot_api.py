import requests
import json
import os

# Definimos la ruta base de la carpeta 'data' (subiendo un nivel desde 'src')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Archivos de caché locales
CACHE_CHAMPS = os.path.join(DATA_DIR, "champion_data.json")
CACHE_ITEMS = os.path.join(DATA_DIR, "item_data.json")

def obtener_version_actual():
    """Obtiene la versión más reciente del parche de LoL."""
    try:
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()[0]
    except Exception as e:
        print(f"⚠️ Error obteniendo la versión: {e}. Usando versión de respaldo.")
        return "14.10.1" # Versión de respaldo segura en caso de caída de internet

def actualizar_datos_riot():
    """Descarga y guarda los datos de campeones y objetos del parche actual."""
    version = obtener_version_actual()
    print(f"🔄 Descargando datos del parche {version}...")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 1. Descargar Campeones (Se mantiene igual)
    try:
        url_champs = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/champion.json"
        resp_champs = requests.get(url_champs, timeout=10)
        resp_champs.raise_for_status()
        data_champs = resp_champs.json()["data"]
        
        diccionario_campeones = {}
        for champ_id, details in data_champs.items():
            nombre_real = details.get("name", "").replace(" ", "").replace("'", "")
            diccionario_campeones[champ_id] = {"nombre": nombre_real, "tags": details.get("tags", [])}
            if nombre_real and nombre_real != champ_id:
                diccionario_campeones[nombre_real] = {"nombre": nombre_real, "tags": details.get("tags", [])}
                
        with open(CACHE_CHAMPS, "w", encoding="utf-8") as f:
            json.dump(diccionario_campeones, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error descargando campeones: {e}")

    # 2. Descargar Objetos (¡AQUÍ ESTÁ LA MAGIA!)
    try:
        url_items = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/item.json"
        resp_items = requests.get(url_items, timeout=10)
        resp_items.raise_for_status()
        data_items = resp_items.json()["data"]
        
        diccionario_objetos = {}
        
        for item_id, details in data_items.items():
            # Descargamos items comprables y las mascotas de jungla
            if details.get("gold", {}).get("purchasable", False) or item_id in ["1101", "1102", "1103"]:
                diccionario_objetos[item_id] = {
                    "nombre": details.get("name", f"Item {item_id}"),
                    "oro": details.get("gold", {}).get("total", 0),
                    "avanza_a": details.get("into", []), # Si está vacío, es un item final
                    "tags": details.get("tags", [])      # Para detectar Consumibles o Visión
                }
                
        with open(CACHE_ITEMS, "w", encoding="utf-8") as f:
            json.dump(diccionario_objetos, f, ensure_ascii=False, indent=2)
        print(f"✅ Datos de {len(diccionario_objetos)} objetos válidos actualizados con metadata.")
    except Exception as e:
        print(f"❌ Error descargando objetos: {e}")

def cargar_campeones():
    """Carga los campeones desde el caché. Si no existe, lo descarga."""
    if not os.path.exists(CACHE_CHAMPS):
        actualizar_datos_riot()
    try:
        with open(CACHE_CHAMPS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error leyendo caché de campeones: {e}")
        return {}

def cargar_objetos():
    """Carga los objetos desde el caché. Si no existe, lo descarga."""
    if not os.path.exists(CACHE_ITEMS):
        actualizar_datos_riot()
    try:
        with open(CACHE_ITEMS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error leyendo caché de objetos: {e}")
        return {}

# Si ejecutamos este archivo directamente (python src/riot_api.py), descargará los datos.
if __name__ == "__main__":
    actualizar_datos_riot()