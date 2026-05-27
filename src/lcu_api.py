import os
import json
import requests
import urllib3
import sys
from base64 import b64encode

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
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champ-select/v1/session"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200: return res.json()
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

    # ================= JUEGO EN VIVO =================

    def obtener_fase_juego(self):
        """Devuelve la fase actual: None, Lobby, Matchmaking, ReadyCheck, ChampSelect, GameStart, InProgress, WaitingForStats, PreEndOfGame, EndOfGame"""
        if not self.port: return None
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-gameflow/v1/session"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200:
                data = res.json()
                return data.get("phase")
        except: pass
        return None

    def obtener_summoners_partida(self):
        """Obtiene la lista de summoners en la partida activa con championId, spellIds y summonerName."""
        if not self.port: return []
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-gameflow/v1/session"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200:
                data = res.json()
                game_data = data.get("gameData", {})
                players = []
                selections = game_data.get("playerChampionSelections", [])
                queue_info = game_data.get("queue", {})
                for sel in selections:
                    players.append({
                        "summonerId": sel.get("summonerInternalName", ""),
                        "championId": sel.get("championId", 0),
                        "spell1Id": sel.get("spell1Id", 0),
                        "spell2Id": sel.get("spell2Id", 0),
                        "team": sel.get("team", ""),
                        "skinIndex": sel.get("skinIndex", 0),
                        "summonerName": sel.get("summonerName", sel.get("summonerInternalName", "")),
                    })
                return players
        except: pass
        return []

    def obtener_maestria_champ(self, champion_id):
        """Obtiene la maestria del jugador actual con un campeon especifico."""
        if not self.port: return 0
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champions/v1/inventories/CHAMPION/champions-minimal"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200:
                for champ in res.json():
                    if champ.get("id") == champion_id:
                        return champ.get("masteryLevel", 0)
        except: pass
        return 0

    def obtener_nombre_invocador(self):
        """Obtiene el nombre del invocador actual."""
        if not self.port: return ""
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-summoner/v1/current-summoner"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200:
                data = res.json()
                return data.get("displayName", data.get("gameName", ""))
        except: pass
        return ""

    # ================= FUNCIONES DE PERFIL Y LIGAS =================
    
    def obtener_perfil(self):
        if not self.port: return None
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-summoner/v1/current-summoner"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200: return res.json()
        except: pass
        return None

    def obtener_region_local(self):
        config_path = os.path.join(self.lol_path, "Config", "LeagueClientSettings.yaml")
        if not os.path.exists(config_path):
            return None
        try:
            with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith("region:"):
                        return line.split(":", 1)[1].strip().strip('"').strip("'")
        except: pass
        return None

    def obtener_api_key_local(self):
        if getattr(sys, 'frozen', False):
            root_path = sys._MEIPASS
        else:
            root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(root_path, "config.json")
        if not os.path.exists(config_path):
            return None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("API_KEY")
        except: pass
        return None

    def obtener_encrypted_summoner_id(self, puuid, region):
        api_key = self.obtener_api_key_local()
        if not api_key or not region or not puuid:
            return None
        try:
            url = f"https://{region.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
            res = requests.get(url, headers={"X-Riot-Token": api_key}, timeout=5)
            if res.status_code == 200:
                return res.json().get("id")
        except: pass
        return None

    def obtener_ligas(self):
        """Obtiene datos de ranked desde LCU, con fallback a Riot API.
        Normaliza la respuesta a: {"queues": [{"tier":..., "division":..., "leaguePoints":..., "wins":..., "losses":..., "queueType":...}]}
        """
        if self.port:
            for endpoint in [
                "/lol-ranked/v1/current-ranked-stats",
                "/lol-ranked/v1/current-ranks",
            ]:
                try:
                    url = f"{self.protocol}://127.0.0.1:{self.port}{endpoint}"
                    res = requests.get(url, headers=self.headers, verify=False, timeout=3)
                    if res.status_code != 200:
                        continue
                    data = res.json()

                    queues = []

                    if isinstance(data, list):
                        # Riot-style: lista de entries [{tier, rank, leaguePoints, ...}, ...]
                        for entry in data:
                            entry["division"] = entry.get("division") or entry.get("rank") or ""
                            queues.append(entry)

                    elif isinstance(data, dict):
                        # --- queueMap ---
                        qmap = data.get("queueMap", {})
                        if isinstance(qmap, dict):
                            for qtype, qdata in qmap.items():
                                if isinstance(qdata, dict) and qdata.get("tier"):
                                    qdata["division"] = qdata.get("division") or qdata.get("rank") or ""
                                    queues.append({**qdata, "queueType": qtype})

                        # --- queues (dentro del dict, si queueMap no encontró nada) ---
                        if not queues:
                            qlist = data.get("queues", [])
                            if isinstance(qlist, list):
                                for entry in qlist:
                                    if isinstance(entry, dict):
                                        entry["division"] = entry.get("division") or entry.get("rank") or ""
                                        queues.append(entry)

                        # --- La raíz misma tiene tier (raro pero posible) ---
                        if not queues and data.get("tier"):
                            data["division"] = data.get("division") or data.get("rank") or ""
                            queues.append(data)

                    if queues:
                        print(f"[LCU] Ligas encontradas ({endpoint}): {[(q.get('queueType','?'), q.get('tier','?')) for q in queues]}")
                        return {"queues": queues}
                except Exception as e:
                    print(f"[LCU] Error en {endpoint}: {e}")
                    continue

        # ===== FALLBACK: Riot API =====
        region = self.obtener_region_local()
        api_key = self.obtener_api_key_local()
        if region and api_key:
            perfil = self.obtener_perfil()
            if perfil:
                encrypted_id = perfil.get("summonerId") or perfil.get("accountId")
                if not encrypted_id:
                    puuid = perfil.get("puuid")
                    encrypted_id = self.obtener_encrypted_summoner_id(puuid, region)
                if encrypted_id:
                    try:
                        league_url = f"https://{region.lower()}.api.riotgames.com/lol/league/v4/entries/by-summoner/{encrypted_id}"
                        res = requests.get(league_url, headers={"X-Riot-Token": api_key}, timeout=5)
                        if res.status_code == 200:
                            entries = res.json()
                            # Riot API usa "rank" en vez de "division", normalizar
                            for e in entries:
                                e["division"] = e.get("rank", "")
                            print(f"[RiotAPI] Ligas encontradas: {[(e.get('queueType','?'), e.get('tier','?')) for e in entries]}")
                            return {"queues": entries}
                    except Exception as e:
                        print(f"[RiotAPI] Error: {e}")
        return None

    def obtener_maestrias(self, count=3):
        # FIX: Este endpoint de Local-Player NUNCA falla si estás logueado en LoL
        if not self.port: return []
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champion-mastery/v1/local-player/champion-mastery"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if res.status_code == 200: return res.json()[:count]
        except: pass
        return []

    def obtener_historial(self, puuid, count=20):
        if not self.port: return None
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex={count}"
            res = requests.get(url, headers=self.headers, verify=False, timeout=3)
            if res.status_code == 200: return res.json()
        except: pass
        return None

    def obtener_ranked_stats(self):
        """Obtiene estadisticas completas de ranked (season actual) desde LCU."""
        if not self.port: return None
        try:
            url = f"{self.protocol}://127.0.0.1:{self.port}/lol-ranked/v1/current-ranked-stats"
            res = requests.get(url, headers=self.headers, verify=False, timeout=3)
            if res.status_code == 200:
                data = res.json()
                result = {"queues": {}, "seasons": data.get("seasons", {})}
                qmap = data.get("queueMap", {})
                for qtype, qdata in qmap.items():
                    if isinstance(qdata, dict) and qdata.get("tier"):
                        result["queues"][qtype] = qdata
                return result
        except: pass
        return None

    def obtener_historial_extendido(self, puuid: str = None, inicio: int = 0, cantidad: int = 100):
        """Obtiene historial de partidas via LCU (hasta 100)."""
        if not self.port: return []
        try:
            if not puuid:
                perfil = self.obtener_perfil()
                if perfil: puuid = perfil.get("puuid", "")
            if not puuid: return []
            url = (f"{self.protocol}://127.0.0.1:{self.port}"
                   f"/lol-match-history/v1/products/lol/{puuid}/matches"
                   f"?begIndex={inicio}&endIndex={inicio + cantidad}")
            res = requests.get(url, headers=self.headers, verify=False, timeout=5)
            if res.status_code == 200:
                data = res.json()
                return data.get("games", {}).get("games", [])
        except: pass
        return []

    # ================= FUNCIONES DE AUTO-IMPORTACIÓN =================
    def importar_hechizos(self, spell1, spell2):
        if not self.port: return False
        url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champ-select/v1/session/my-selection"
        try:
            res = requests.patch(url, headers=self.headers, json={"spell1Id": int(spell1), "spell2Id": int(spell2)}, verify=False, timeout=3)
            return res.status_code in [200, 204]
        except: return False

    def importar_runas(self, ids_runas, nombre="Analytics Build"):
        if not self.port or len(ids_runas) < 11: return False
        try:
            url_pages = f"{self.protocol}://127.0.0.1:{self.port}/lol-perks/v1/pages"
            res = requests.get(url_pages, headers=self.headers, verify=False, timeout=3)
            if res.status_code == 200:
                editables = [p for p in res.json() if p.get('isEditable', True)]
                if editables:
                    requests.delete(f"{url_pages}/{editables[0]['id']}", headers=self.headers, verify=False, timeout=3)
            
            data = {
                "name": nombre, "primaryStyleId": int(ids_runas[0]), "subStyleId": int(ids_runas[5]),
                "selectedPerkIds": [int(x) for x in ids_runas[1:5] + ids_runas[6:8] + ids_runas[8:11]], "current": True
            }
            res_post = requests.post(url_pages, headers=self.headers, json=data, verify=False, timeout=3)
            return res_post.status_code == 200
        except: return False

    def importar_item_set(self, campeon, champ_id_int, ids_start, ids_core):
        """Fix definitivo: Requiere champ_id_int (el id numérico) para asociarlo correctamente en la tienda de LoL"""
        if not self.port: 
            if not self.conectar(): return "Cliente de LoL no encontrado"
            
        try:
            url_sum = f"{self.protocol}://127.0.0.1:{self.port}/lol-summoner/v1/current-summoner"
            sum_res = requests.get(url_sum, headers=self.headers, verify=False, timeout=3)
            if sum_res.status_code != 200: return False
            summoner_id = sum_res.json().get('summonerId')
            if not summoner_id: return False

            url_sets_base = f"{self.protocol}://127.0.0.1:{self.port}/lol-item-sets/v1/item-sets"
            url_sets_with_id = f"{url_sets_base}/{summoner_id}/sets"

            item_sets_data = {"accountId": summoner_id, "itemSets": []}
            try:
                items_res = requests.get(url_sets_base, headers=self.headers, verify=False, timeout=3)
                if items_res.status_code == 200:
                    item_sets_data = items_res.json()
                else:
                    items_res = requests.get(url_sets_with_id, headers=self.headers, verify=False, timeout=3)
                    if items_res.status_code == 200:
                        item_sets_data = items_res.json()
            except (ValueError, requests.exceptions.RequestException):
                item_sets_data = {"accountId": summoner_id, "itemSets": []}

            clean_start = [{"id": str(i).strip(), "count": 1} for i in ids_start if str(i).strip() and str(i).strip() != "0"]
            clean_core = [{"id": str(i).strip(), "count": 1} for i in ids_core if str(i).strip() and str(i).strip() != "0"]

            nuevo_set = {
                "associatedChampions": [champ_id_int] if champ_id_int > 0 else [], # CLAVE PARA QUE FUNCIONE EN PARTIDA
                "associatedMaps": [11],
                "blocks": [
                    {"type": "Start & Early Game", "items": clean_start},
                    {"type": "Core Build", "items": clean_core}
                ],
                "title": f"LEA - {campeon}",
                "uid": f"lea_custom_build_{campeon.lower()}",
                "type": "custom",
                "map": "any",
                "mode": "any",
                "preferredItemSlots": [],
                "sortrank": 0,
                "startedFrom": "blank"
            }

            lista_sets = item_sets_data.get("itemSets", [])
            reemplazado = False
            for i, s in enumerate(lista_sets):
                if s.get("uid") == nuevo_set["uid"]:
                    lista_sets[i] = nuevo_set
                    reemplazado = True
                    break
            if not reemplazado: lista_sets.append(nuevo_set)
            
            item_sets_data = {"accountId": summoner_id, "itemSets": lista_sets}
            try:
                put_res = requests.put(url_sets_base, headers=self.headers, json=item_sets_data, verify=False, timeout=30)
                if put_res.status_code in [200, 201, 204]:
                    return True

                put_res2 = requests.put(url_sets_with_id, headers=self.headers, json={"itemSets": lista_sets}, verify=False, timeout=30)
                if put_res2.status_code in [200, 201, 204]:
                    return True

                if put_res.status_code == 404 or put_res2.status_code == 404:
                    return "Endpoint inválido. No se pudo guardar el item set en el cliente de LoL."
                return f"Error al guardar item set: {put_res.status_code} / {put_res2.status_code}"
            except requests.exceptions.ReadTimeout:
                return "Tiempo de espera agotado al guardar el item set. El set puede haberse creado; verifica en el cliente."
            except requests.exceptions.RequestException as exc:
                return f"Error de conexión al guardar item set: {exc}"
        except Exception as e:
            return f"Excepción fatal: {str(e)}"