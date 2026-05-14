import requests
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

CACHE_CHAMPS = os.path.join(DATA_DIR, "champion_data.json")
CACHE_ITEMS = os.path.join(DATA_DIR, "item_data.json")
CACHE_RUNAS = os.path.join(DATA_DIR, "rune_data.json")
CACHE_IDS = os.path.join(DATA_DIR, "champ_ids.json") # NUEVO: Mapeo de IDs reales

def limpiar_html(texto):
    texto = re.sub(r'<br\s*/?>', '\n', texto)
    texto = re.sub(r'<[^>]+>', '', texto)
    return texto.strip()

def obtener_version_actual():
    try:
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()[0]
    except Exception as e:
        return "14.10.1"

def actualizar_datos_riot():
    version = obtener_version_actual()
    print(f"🔄 Descargando datos del parche {version}...")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 1. Campeones y Mapeo de IDs
    try:
        url_champs = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/champion.json"
        resp_champs = requests.get(url_champs, timeout=10)
        data_champs = resp_champs.json()["data"]
        
        diccionario_campeones = {}
        diccionario_ids = {}
        
        for champ_id, details in data_champs.items():
            nombre_real = details.get("name", "").replace(" ", "").replace("'", "")
            key_num = str(details.get("key")) # EL ID REAL DE RIOT
            
            diccionario_campeones[champ_id] = {"nombre": nombre_real, "tags": details.get("tags", [])}
            if nombre_real and nombre_real != champ_id:
                diccionario_campeones[nombre_real] = {"nombre": nombre_real, "tags": details.get("tags", [])}
            
            # Guardar el ID numérico oficial -> Nombre
            diccionario_ids[key_num] = nombre_real

        with open(CACHE_CHAMPS, "w", encoding="utf-8") as f:
            json.dump(diccionario_campeones, f, ensure_ascii=False, indent=2)
            
        with open(CACHE_IDS, "w", encoding="utf-8") as f:
            json.dump(diccionario_ids, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"❌ Error descargando campeones: {e}")

    # 2. Objetos
    try:
        url_items = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/item.json"
        resp_items = requests.get(url_items, timeout=10)
        data_items = resp_items.json()["data"]
        diccionario_objetos = {}
        
        for item_id, details in data_items.items():
            if details.get("gold", {}).get("purchasable", False) or item_id in ["1101", "1102", "1103"]:
                diccionario_objetos[item_id] = {
                    "nombre": details.get("name", f"Item {item_id}"),
                    "oro": details.get("gold", {}).get("total", 0),
                    "avanza_a": details.get("into", []),
                    "tags": details.get("tags", []),
                    "descripcion": limpiar_html(details.get("description", ""))
                }
        with open(CACHE_ITEMS, "w", encoding="utf-8") as f:
            json.dump(diccionario_objetos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error descargando objetos: {e}")

    # 3. Runas
    try:
        url_runas = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/runesReforged.json"
        resp_runas = requests.get(url_runas, timeout=10)
        data_runas = resp_runas.json()
        diccionario_runas = {}
        
        for arbol in data_runas:
            diccionario_runas[str(arbol["id"])] = {
                "nombre": arbol["name"],
                "icono": arbol["icon"],
                "descripcion": f"Rama principal de {arbol['name']}"
            }
            for slot in arbol["slots"]:
                for runa in slot["runes"]:
                    diccionario_runas[str(runa["id"])] = {
                        "nombre": runa["name"],
                        "icono": runa["icon"],
                        "descripcion": limpiar_html(runa.get("shortDesc", ""))
                    }
        with open(CACHE_RUNAS, "w", encoding="utf-8") as f:
            json.dump(diccionario_runas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error descargando runas: {e}")

def cargar_campeones():
    if not os.path.exists(CACHE_CHAMPS): actualizar_datos_riot()
    with open(CACHE_CHAMPS, "r", encoding="utf-8") as f: return json.load(f)

def cargar_objetos():
    if not os.path.exists(CACHE_ITEMS): actualizar_datos_riot()
    with open(CACHE_ITEMS, "r", encoding="utf-8") as f: return json.load(f)

def cargar_runas():
    if not os.path.exists(CACHE_RUNAS): actualizar_datos_riot()
    with open(CACHE_RUNAS, "r", encoding="utf-8") as f: return json.load(f)

def cargar_mapeo_ids():
    if not os.path.exists(CACHE_IDS): actualizar_datos_riot()
    with open(CACHE_IDS, "r", encoding="utf-8") as f: return json.load(f)

if __name__ == "__main__":
    actualizar_datos_riot()