import os
import requests
import urllib3
from base64 import b64encode

# Desactivamos advertencias de certificados autofirmados locales
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LCUConnector:
    def __init__(self, lol_path=r"C:\Riot Games\League of Legends"):
        self.lol_path = lol_path
        self.lockfile_path = os.path.join(self.lol_path, "lockfile")
        self.port = None
        self.password = None
        self.protocol = None
        self.headers = {}
        
    def conectar(self):
        """Busca el lockfile de LoL y extrae las credenciales para la sesión."""
        if not os.path.exists(self.lockfile_path): return False
        try:
            with open(self.lockfile_path, 'r') as file:
                data = file.read().split(':')
                self.port = data[2]
                self.password = data[3]
                self.protocol = data[4]
                auth_string = f"riot:{self.password}"
                auth_base64 = b64encode(auth_string.encode('ascii')).decode('ascii')
                self.headers = {"Authorization": f"Basic {auth_base64}", "Accept": "application/json"}
                return True
        except Exception: return False

    def obtener_sesion_draft(self):
        if not self.port: return None
        url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champ-select/v1/session"
        try:
            response = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if response.status_code == 200: return response.json()
        except: pass
        return None

    def obtener_mi_rol(self, draft_data):
        if not draft_data: return "MIDDLE"
        mi_celda = draft_data.get('localPlayerCellId')
        for jugador in draft_data.get('myTeam', []):
            if jugador.get('cellId') == mi_celda:
                rol_lcu = jugador.get('assignedPosition', 'MIDDLE').upper()
                return {'UTILITY': 'UTILITY', 'BOTTOM': 'BOTTOM', 'JUNGLE': 'JUNGLE', 'TOP': 'TOP'}.get(rol_lcu, 'MIDDLE')
        return "MIDDLE"

    # ================= FUNCIONES DE AUTO-IMPORTACIÓN =================

    def importar_hechizos(self, spell1, spell2):
        if not self.port: return False
        url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champ-select/v1/session/my-selection"
        data = {"spell1Id": int(spell1), "spell2Id": int(spell2)}
        try:
            res = requests.patch(url, headers=self.headers, json=data, verify=False)
            return res.status_code in [200, 204]
        except: return False

    def importar_runas(self, ids_runas, nombre="Analytics Build"):
        """Elimina la página actual y crea una nueva con el setup recomendado."""
        if not self.port or len(ids_runas) < 11: return False
        try:
            url_pages = f"{self.protocol}://127.0.0.1:{self.port}/lol-perks/v1/pages"
            res = requests.get(url_pages, headers=self.headers, verify=False)
            if res.status_code == 200:
                pages = res.json()
                editables = [p for p in pages if p.get('isEditable', True)]
                if editables: # Borramos la primera editable que encontremos para hacer hueco
                    requests.delete(f"{url_pages}/{editables[0]['id']}", headers=self.headers, verify=False)
            
            data = {
                "name": nombre,
                "primaryStyleId": int(ids_runas[0]),
                "subStyleId": int(ids_runas[5]),
                "selectedPerkIds": [int(x) for x in ids_runas[1:5] + ids_runas[6:8] + ids_runas[8:11]],
                "current": True
            }
            res_post = requests.post(url_pages, headers=self.headers, json=data, verify=False)
            return res_post.status_code == 200
        except Exception as e:
            print("Error al importar runas:", e)
            return False

    def importar_item_set(self, campeon, ids_start, ids_core):
        """Genera un Item Set en la pestaña de Colección del jugador."""
        if not self.port: return False
        try:
            # Obtener Summoner ID
            url_sum = f"{self.protocol}://127.0.0.1:{self.port}/lol-summoner/v1/current-summoner"
            sum_res = requests.get(url_sum, headers=self.headers, verify=False)
            if sum_res.status_code != 200: return False
            summoner_id = sum_res.json()['summonerId']

            # Obtener sets existentes para no borrar todo
            url_sets = f"{self.protocol}://127.0.0.1:{self.port}/lol-item-sets/v1/item-sets/{summoner_id}/sets"
            items_res = requests.get(url_sets, headers=self.headers, verify=False)
            item_sets_data = items_res.json() if items_res.status_code == 200 else {"accountId": summoner_id, "itemSets": []}

            nuevo_set = {
                "associatedChampions": [],
                "associatedMaps": [11], # 11 es la Grieta del Invocador
                "blocks": [
                    {"type": "Start & Early Game", "items": [{"id": str(i), "count": 1} for i in ids_start]},
                    {"type": "Core Build", "items": [{"id": str(i), "count": 1} for i in ids_core]}
                ],
                "title": f"LEA - {campeon}",
                "uid": "lea_custom_build_uid_999" # UID fijo para que siempre sobrescriba la build anterior
            }

            lista_sets = item_sets_data.get("itemSets", [])
            reemplazado = False
            for i, s in enumerate(lista_sets):
                if s.get("uid") == nuevo_set["uid"]:
                    lista_sets[i] = nuevo_set
                    reemplazado = True
                    break
            if not reemplazado: lista_sets.append(nuevo_set)
            
            item_sets_data["itemSets"] = lista_sets
            put_res = requests.put(url_sets, headers=self.headers, json=item_sets_data, verify=False)
            return put_res.status_code in [200, 204]
        except Exception as e:
            print("Error al importar items:", e)
            return False