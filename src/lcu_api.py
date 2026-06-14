import os
import json
import requests
import urllib3
import sys
import time
import winreg
from base64 import b64encode

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LCUConnector:
    def __init__(self, lol_path=None):
        if lol_path is None:
            lol_path = self._detectar_lol_path()
        self.lol_path = lol_path
        self.lockfile_path = os.path.join(self.lol_path, "lockfile") if lol_path else ""
        self.port = None
        self.password = None
        self.protocol = None
        self.headers = {}

    @staticmethod
    def _detectar_lol_path():
        """Detecta la instalación de League of Legends vía registro o rutas comunes."""
        rutas = [
            r"C:\Riot Games\League of Legends",
            r"C:\Program Files\Riot Games\League of Legends",
            r"D:\Riot Games\League of Legends",
            r"D:\Program Files\Riot Games\League of Legends",
        ]
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Riot Games\RADS") as key:
                path = winreg.QueryValueEx(key, "LocalRootFolder")[0]
                lol_client = os.path.join(path, "RADS", "solutions", "lol_game_client_sln")
                for f in os.listdir(lol_client):
                    if f.startswith("releases"):
                        rutas.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(lol_client))))
                        break
        except (FileNotFoundError, OSError):
            pass

        for r in rutas:
            if os.path.exists(os.path.join(r, "lockfile")):
                return r
        return rutas[0]

    def conectar(self):
        if not self.lol_path or not os.path.exists(self.lockfile_path):
            # Intentar redetectar si el lockfile no existe
            self.lol_path = self._detectar_lol_path()
            self.lockfile_path = os.path.join(self.lol_path, "lockfile")
            if not os.path.exists(self.lockfile_path):
                return False
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
        except (OSError, IndexError, ValueError):
            return False

    def reconnect(self):
        self.port = None
        self.password = None
        self.protocol = None
        self.headers = {}
        return self.conectar()

    def request(self, method, endpoint, **kwargs):
        _RETRIES = 3
        _BACKOFF = 0.5
        for intento in range(_RETRIES):
            if not self.port:
                if not self.conectar():
                    if intento < _RETRIES - 1:
                        time.sleep(_BACKOFF * (2 ** intento))
                    continue
            url = f"{self.protocol}://127.0.0.1:{self.port}{endpoint}"
            kwargs.setdefault("headers", self.headers)
            kwargs.setdefault("verify", False)
            kwargs.setdefault("timeout", 3)
            try:
                res = requests.request(method, url, **kwargs)
                return res
            except requests.ConnectionError:
                self.reconnect()
            except requests.Timeout:
                pass
            except requests.RequestException:
                return None
            if intento < _RETRIES - 1:
                time.sleep(_BACKOFF * (2 ** intento))
        return None

    def obtener_sesion_draft(self):
        res = self.request('GET', '/lol-champ-select/v1/session')
        if res and res.status_code == 200:
            return res.json()
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
        res = self.request('GET', '/lol-gameflow/v1/session')
        if res and res.status_code == 200:
            return res.json().get("phase")
        return None

    def obtener_summoners_partida(self):
        """Obtiene la lista de summoners en la partida activa con championId, spellIds y summonerName.
        Usa playerChampionSelections (champ select) o teamOne/teamTwo (in-game).
        Durante InProgress tambien busca en el objeto 'gameData' completo como fallback."""
        res = self.request('GET', '/lol-gameflow/v1/session')
        if not res or res.status_code != 200:
            return []
        data = res.json()
        game_data = data.get("gameData", {})
        players = []

        # Metodo 1: playerChampionSelections (funciona en champ select y a veces in-game)
        selections = game_data.get("playerChampionSelections", [])
        if selections:
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
            if players:
                print(f"[LCU] {len(players)} jugadores via playerChampionSelections")
                return players

        # Metodo 2: teamOne/teamTwo (funciona durante la partida en vivo)
        players = self._extraer_de_team(game_data, "teamOne", "ORDER")
        players += self._extraer_de_team(game_data, "teamTwo", "CHAOS")
        
        if len(players) >= 2:
            print(f"[LCU] {len(players)} jugadores via teamOne/teamTwo")
            return players

        # Metodo 3: Buscar en todo gameData recursivamente objetos con championId
        players_fallback = self._buscar_jugadores_en_dict(game_data)
        if players_fallback:
            print(f"[LCU] {len(players_fallback)} jugadores via busqueda profunda en gameData")
            return players_fallback

        print(f"[LCU] gameData keys: {list(game_data.keys()) if game_data else 'vacio'}")
        return players if players else []

    def _extraer_de_team(self, game_data, team_key, team_name):
        """Extrae jugadores de teamOne/teamTwo del gameData."""
        players = []
        team = game_data.get(team_key, {})
        if isinstance(team, dict):
            for summoner in team.get("summoners", team.get("players", [])):
                if isinstance(summoner, dict):
                    players.append({
                        "summonerId": summoner.get("summonerInternalName", summoner.get("summonerName", "")),
                        "championId": summoner.get("championId", 0),
                        "spell1Id": summoner.get("spell1Id", 0),
                        "spell2Id": summoner.get("spell2Id", 0),
                        "team": team_name,
                        "skinIndex": 0,
                        "summonerName": summoner.get("summonerName", summoner.get("summonerInternalName", "")),
                    })
        elif isinstance(team, list):
            for summoner in team:
                if isinstance(summoner, dict):
                    players.append({
                        "summonerId": summoner.get("summonerInternalName", summoner.get("summonerName", "")),
                        "championId": summoner.get("championId", 0),
                        "spell1Id": summoner.get("spell1Id", 0),
                        "spell2Id": summoner.get("spell2Id", 0),
                        "team": team_name,
                        "skinIndex": 0,
                        "summonerName": summoner.get("summonerName", summoner.get("summonerInternalName", "")),
                    })
        return players

    def _buscar_jugadores_en_dict(self, d, profundidad=0):
        """Busqueda recursiva en dict/list buscando objetos con championId > 0.
        Retorna lista de dicts con championId, summonerName y team inferido."""
        if profundidad > 4:
            return []
        resultados = []
        if isinstance(d, dict):
            # ¿Es un objeto jugador?
            if d.get("championId", 0) and d.get("championId") != 0:
                team_guess = "ORDER"  # No podemos saber el equipo, el caller debe inferirlo
                # Intentar inferir equipo
                for k in d:
                    if "team" in str(k).lower():
                        val = str(d[k]).upper()
                        if "CHAOS" in val or "RED" in val or "TWO" in val.upper():
                            team_guess = "CHAOS"
                        break
                resultados.append({
                    "summonerId": d.get("summonerInternalName", d.get("summonerName", "")),
                    "championId": d.get("championId", 0),
                    "spell1Id": d.get("spell1Id", 0),
                    "spell2Id": d.get("spell2Id", 0),
                    "team": team_guess,
                    "skinIndex": 0,
                    "summonerName": d.get("summonerName", d.get("summonerInternalName", "")),
                })
            # Buscar en hijos
            for v in d.values():
                resultados += self._buscar_jugadores_en_dict(v, profundidad + 1)
        elif isinstance(d, list):
            for item in d:
                resultados += self._buscar_jugadores_en_dict(item, profundidad + 1)
        return resultados

    def obtener_maestria_champ(self, champion_id):
        """Obtiene la maestria del jugador actual con un campeon especifico."""
        res = self.request('GET', '/lol-champions/v1/inventories/CHAMPION/champions-minimal')
        if res and res.status_code == 200:
            for champ in res.json():
                if champ.get("id") == champion_id:
                    return champ.get("masteryLevel", 0)
        return 0

    def obtener_nombre_invocador(self):
        """Obtiene el nombre del invocador actual."""
        res = self.request('GET', '/lol-summoner/v1/current-summoner')
        if res and res.status_code == 200:
            return res.json().get("displayName", res.json().get("gameName", ""))
        return ""

    # ================= FUNCIONES DE PERFIL Y LIGAS =================
    
    def obtener_perfil(self):
        # Endpoint clásico (funciona en clientes más viejos)
        res = self.request('GET', '/lol-summoner/v1/current-summoner')
        if res and res.status_code == 200:
            return res.json()

        # Estrategia moderna: combinar varios endpoints parciales
        perfil = {}

        # Paso 1: /lol-chat/v1/me — tiene gameName, gameTag, icon
        # (puuid puede estar vacío si el cliente no terminó de cargar)
        res = self.request('GET', '/lol-chat/v1/me')
        if res and res.status_code == 200:
            d = res.json()
            lol = d.get("lol") or {}
            perfil.update({
                "puuid":         d.get("puuid") or lol.get("puuid", ""),
                "displayName":   d.get("gameName", ""),
                "gameName":      d.get("gameName", ""),
                "tagLine":       d.get("gameTag", ""),
                "profileIconId": d.get("icon", 0),
                "summonerLevel": int(lol.get("summonerLevel") or lol.get("level") or 0),
                "summonerId":    str(lol.get("summonerId", "")),
                "summonerName":  lol.get("summonerName", d.get("gameName", "")),
            })

        # Paso 2: /lol-login/v1/session — tiene puuid y summonerId fiables
        res = self.request('GET', '/lol-login/v1/session')
        if res and res.status_code == 200:
            d = res.json()
            if d.get("state") == "SUCCEEDED":
                if not perfil.get("puuid"):
                    perfil["puuid"] = d.get("puuid", "")
                if not perfil.get("summonerId"):
                    perfil["summonerId"] = str(d.get("summonerId", ""))

        # Paso 3: /lol-summoner/v1/summoners/{id} — nivel + icono
        summ_id = perfil.get("summonerId")
        if summ_id and str(summ_id) not in ("0", ""):
            res = self.request('GET', f'/lol-summoner/v1/summoners/{summ_id}')
            if res and res.status_code == 200:
                d = res.json()
                if not perfil.get("puuid"):
                    perfil["puuid"] = d.get("puuid", "")
                if not perfil.get("profileIconId"):
                    perfil["profileIconId"] = d.get("profileIconId", 0)
                if not perfil.get("summonerLevel"):
                    perfil["summonerLevel"] = d.get("summonerLevel", 0)
                display = d.get("displayName") or d.get("gameName", "")
                if display and not perfil.get("gameName"):
                    perfil["displayName"]  = display
                    perfil["gameName"]     = display
                    perfil["summonerName"] = display

        # Paso 4: Riot API — gameName + tagLine + profileIconId + summonerLevel por puuid
        puuid = perfil.get("puuid")
        needs_name = not perfil.get("gameName")
        needs_icon = not perfil.get("profileIconId")
        needs_lvl  = not perfil.get("summonerLevel")
        if puuid and (needs_name or needs_icon or needs_lvl):
            try:
                api_key = self.obtener_api_key_local()
                region  = self.obtener_region_local() or "la2"
                routing = "americas" if region in ("la1","la2","na1","br1","oc1") else \
                          "europe"   if region in ("euw1","eun1","tr1","ru")      else "asia"
                hdrs = {"X-Riot-Token": api_key}

                # Summoner API — icono + nivel + summonerId
                if needs_icon or needs_lvl:
                    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
                    r = requests.get(url, headers=hdrs, timeout=5, verify=True)
                    if r.status_code == 200:
                        sd = r.json()
                        if needs_icon: perfil["profileIconId"] = sd.get("profileIconId", 0)
                        if needs_lvl:  perfil["summonerLevel"] = sd.get("summonerLevel", 0)
                        if not perfil.get("summonerId"):
                            perfil["summonerId"] = sd.get("id", "")
                        if needs_name and sd.get("name"):
                            perfil["gameName"]    = sd["name"]
                            perfil["displayName"] = sd["name"]
                            perfil["summonerName"]= sd["name"]
                            needs_name = False

                # Account API — gameName#tagLine (Riot ID)
                if needs_name:
                    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
                    r = requests.get(url, headers=hdrs, timeout=5, verify=True)
                    if r.status_code == 200:
                        ad = r.json()
                        perfil["gameName"]    = ad.get("gameName", "")
                        perfil["tagLine"]     = ad.get("tagLine", "")
                        perfil["displayName"] = ad.get("gameName", "")
                        perfil["summonerName"]= ad.get("gameName", "")
            except Exception:
                pass

        if perfil.get("puuid") or perfil.get("displayName") or perfil.get("gameName"):
            fuentes = []
            if perfil.get("gameName"):      fuentes.append("chat/riot")
            if perfil.get("puuid"):         fuentes.append("session")
            if perfil.get("summonerLevel"): fuentes.append("summoner")
            print(f"[LCU] obtener_perfil: combinado [{', '.join(fuentes)}]")
            return perfil

        print(f"[LCU] obtener_perfil: todos los endpoints fallaron")
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
        # Primero buscar en directorio escribible (donde el usuario guarda config)
        if getattr(sys, 'frozen', False):
            writable_root = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
        else:
            writable_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(writable_root, "config.json")
        if not os.path.exists(config_path):
            # Fallback: directorio del bundle
            if getattr(sys, 'frozen', False):
                config_path = os.path.join(sys._MEIPASS, "config.json")
            else:
                config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("API_KEY")
        except Exception:
            pass
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
        for endpoint in [
            "/lol-ranked/v1/current-ranked-stats",
            "/lol-ranked/v1/current-ranks",
        ]:
            try:
                res = self.request('GET', endpoint, timeout=3)
                if not res or res.status_code != 200:
                    continue
                data = res.json()

                queues = []

                if isinstance(data, list):
                    for entry in data:
                        entry["division"] = entry.get("division") or entry.get("rank") or ""
                        queues.append(entry)

                elif isinstance(data, dict):
                    qmap = data.get("queueMap", {})
                    if isinstance(qmap, dict):
                        for qtype, qdata in qmap.items():
                            if isinstance(qdata, dict) and qdata.get("tier"):
                                qdata["division"] = qdata.get("division") or qdata.get("rank") or ""
                                queues.append({**qdata, "queueType": qtype})

                    if not queues:
                        qlist = data.get("queues", [])
                        if isinstance(qlist, list):
                            for entry in qlist:
                                if isinstance(entry, dict):
                                    entry["division"] = entry.get("division") or entry.get("rank") or ""
                                    queues.append(entry)

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
        res = self.request('GET', '/lol-champion-mastery/v1/local-player/champion-mastery')
        if res and res.status_code == 200:
            return res.json()[:count]
        return []

    def obtener_historial(self, puuid, count=20):
        if not puuid:
            return None
        res = self.request('GET', f'/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex={count}')
        if res and res.status_code == 200:
            return res.json()
        return None

    def obtener_liveclient_data(self):
        """Obtiene datos en vivo de la partida via Live Client Data API (puerto 2999).
        Esta API se activa automáticamente al entrar a la Grieta — no requiere configuración.
        Retorna ([], {'status': 'loading'}) si todavía está en pantalla de carga."""
        try:
            url = "https://127.0.0.1:2999/liveclientdata/allgamedata"
            res = requests.get(url, verify=False, timeout=2)
            if res.status_code == 200:
                data = res.json()
                players = []
                for p in data.get("allPlayers", []):
                    if not isinstance(p, dict):
                        continue
                    team_raw = p.get("team", "")
                    if isinstance(team_raw, str):
                        team_norm = "ORDER" if team_raw.upper() in ("ORDER", "BLUE", "ALLY", "ALLIES") else "CHAOS"
                    else:
                        team_norm = "ORDER"
                    
                    # Sanitizar items: evitar IndexError si la lista es corta
                    items_raw = p.get("items", [])
                    safe_items = []
                    if isinstance(items_raw, list):
                        for i in range(min(7, len(items_raw))):
                            safe_items.append(items_raw[i] if isinstance(items_raw[i], dict) else {})
                    
                    # Sanitizar summoner spells
                    spells = p.get("summonerSpells", {})
                    spell_one = (spells.get("summonerSpellOne") or {}).get("rawDisplayName", "") if isinstance(spells, dict) else ""
                    spell_two = (spells.get("summonerSpellsTwo") or {}).get("rawDisplayName", "") if isinstance(spells, dict) else ""
                    
                    players.append({
                        "summonerName": p.get("summonerName", p.get("riotId", "")),
                        "riotId": p.get("riotId", ""),
                        "riotIdGameName": p.get("riotIdGameName", ""),
                        "riotIdTagLine": p.get("riotIdTagLine", ""),
                        "championName": p.get("championName", ""),
                        "team": team_norm,
                        "level": p.get("level", 1),
                        "kills": (p.get("scores") or {}).get("kills", 0),
                        "deaths": (p.get("scores") or {}).get("deaths", 0),
                        "assists": (p.get("scores") or {}).get("assists", 0),
                        "creepScore": (p.get("scores") or {}).get("creepScore", 0),
                        "items": safe_items,
                        "summonerSpells": [spell_one, spell_two],
                        "runes": p.get("runes", {}),
                        "isDead": p.get("isDead", False),
                        "championId": 0,
                    })
                return players, data.get("gameData", {})
            else:
                # Rate-limit logs
                now = time.time()
                if not hasattr(self, '_last_liveclient_warn') or now - self._last_liveclient_warn > 60:
                    print(f"[LiveClient] Puerto 2999 respondió con status={res.status_code}")
                    self._last_liveclient_warn = now
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Normal: el juego todavía está en pantalla de carga o acaba de empezar
            now = time.time()
            if not hasattr(self, '_last_liveclient_warn') or now - self._last_liveclient_warn > 60:
                print("[LiveClient] Puerto 2999 no disponible aún (pantalla de carga). Reintentando...")
                self._last_liveclient_warn = now
            return [], {"status": "loading"}
        except Exception as e:
            print(f"[LiveClient] Error inesperado: {e}")
        return [], {}

    def obtener_ranked_stats(self):
        """Obtiene estadisticas completas de ranked (season actual) desde LCU."""
        res = self.request('GET', '/lol-ranked/v1/current-ranked-stats')
        if res and res.status_code == 200:
            data = res.json()
            result = {"queues": {}, "seasons": data.get("seasons", {})}
            qmap = data.get("queueMap", {})
            for qtype, qdata in qmap.items():
                if isinstance(qdata, dict) and qdata.get("tier"):
                    result["queues"][qtype] = qdata
            return result
        return None

    def obtener_region(self):
        """Devuelve el codigo de region del cliente (p. ej. 'LA2', 'EUW'). None si falla."""
        res = self.request('GET', '/riotclient/region-locale')
        if res and res.status_code == 200:
            try:
                return (res.json() or {}).get("region")
            except Exception:
                return None
        return None

    def obtener_historial_extendido(self, puuid: str = None, inicio: int = 0, cantidad: int = 100):
        """Obtiene historial de partidas via LCU."""
        if not puuid:
            perfil = self.obtener_perfil()
            if perfil:
                puuid = perfil.get("puuid", "")
        if not puuid:
            return []

        # LCU rechaza endIndex > 200 en versiones modernas; hacer lotes de 20
        MAX_POR_LOTE = 20
        todos = []
        offset = inicio
        restante = min(cantidad, 200)
        while restante > 0:
            lote = min(MAX_POR_LOTE, restante)
            res = self.request('GET', f'/lol-match-history/v1/products/lol/{puuid}/matches?begIndex={offset}&endIndex={offset + lote}')
            if not res or res.status_code != 200:
                break
            data = res.json()
            games = data.get("games", {}).get("games", [])
            if not games:
                break
            todos.extend(games)
            restante -= lote
            offset += lote
            if len(games) < lote:
                break
        return todos

    # ================= FUNCIONES DE AUTO-IMPORTACIÓN =================
    def importar_hechizos(self, spell1, spell2):
        res = self.request('PATCH', '/lol-champ-select/v1/session/my-selection',
                          json={"spell1Id": int(spell1), "spell2Id": int(spell2)}, timeout=3)
        return res is not None and res.status_code in [200, 204]

    def importar_skill_order(self, skill_order_str):
        """Exporta la ruta de habilidades al cliente (formato 'Q>E>W').
        Intenta múltiples formatos y endpoints porque la API varía entre parches."""
        skills = [s.strip().upper() for s in skill_order_str.replace(">", ",").split(",") if s.strip()]
        if len(skills) < 3:
            return False

        # Formato 1: lista de strings ["Q","E","W",...]
        # Formato 2: lista de enteros [1,2,3,...]  (Q=1,W=2,E=3,R=4)
        map_skill_int = {"Q": 1, "W": 2, "E": 3, "R": 4}
        skills_int = [map_skill_int.get(s, 1) for s in skills]
        # Formato 3: string plano "QEQWQQ..."
        skills_str = "".join(skills)

        payloads = [
            {"skillOrder": skills, "championSkillOrder": skills, "abilityOrder": skills},
            {"skillOrder": skills_int, "championSkillOrder": skills_int, "abilityOrder": skills_int},
            {"skillOrder": skills_str, "championSkillOrder": skills_str, "abilityOrder": skills_str},
            {"championSkillOrder": skills},
            {"championSkillOrder": skills_str},
            {"championSkillOrder": skills_int},
        ]

        # Intento 1: PATCH my-selection con diversos formatos
        for payload in payloads:
            res = self.request('PATCH', '/lol-champ-select/v1/session/my-selection', json=payload, timeout=3)
            if res and res.status_code in [200, 204]:
                return True

        # Intento 2: PATCH a actions (algunas versiones del cliente lo requieren)
        session = self.obtener_sesion_draft()
        if session:
            actions = session.get("actions", [[]])
            local_cell = session.get("localPlayerCellId")
            for action_group in actions:
                for action in action_group:
                    if action.get("actorCellId") == local_cell and action.get("type") == "pick":
                        action_id = action.get("id")
                        if action_id:
                            for fmt in [skills, skills_str, skills_int]:
                                res2 = self.request('PATCH', f'/lol-champ-select/v1/session/actions/{action_id}',
                                                  json={"championSkillOrder": fmt}, timeout=3)
                                if res2 and res2.status_code in [200, 204]:
                                    return True
        return False

    def importar_runas(self, ids_runas, nombre="Analytics Build"):
        if not ids_runas or len(ids_runas) < 11:
            return False

        res = self.request('GET', '/lol-perks/v1/pages')
        if res and res.status_code == 200:
            editables = [p for p in res.json() if p.get('isEditable', True)]
            if editables:
                self.request('DELETE', f'/lol-perks/v1/pages/{editables[0]["id"]}')

        data = {
            "name": nombre, "primaryStyleId": int(ids_runas[0]), "subStyleId": int(ids_runas[5]),
            "selectedPerkIds": [int(x) for x in ids_runas[1:5] + ids_runas[6:8] + ids_runas[8:11]], "current": True
        }
        res_post = self.request('POST', '/lol-perks/v1/pages', json=data, timeout=3)
        return res_post is not None and res_post.status_code == 200

    def importar_item_set(self, campeon, champ_id_int, ids_start, ids_core, ids_sit=None):
        """Fix definitivo: Requiere champ_id_int (el id numérico) para asociarlo correctamente en la tienda de LoL.
        ids_sit: lista opcional de situacionales (ids o dicts con clave 'id') -> bloque extra "Situacionales"."""
        sum_res = self.request('GET', '/lol-summoner/v1/current-summoner')
        if not sum_res or sum_res.status_code != 200:
            return "No se pudo obtener el invocador"
        summoner_id = sum_res.json().get('summonerId')
        if not summoner_id:
            return False

        url_sets_base = f'/lol-item-sets/v1/item-sets'
        url_sets_with_id = f'{url_sets_base}/{summoner_id}/sets'

        item_sets_data = {"accountId": summoner_id, "itemSets": []}
        items_res = self.request('GET', url_sets_base)
        if items_res and items_res.status_code == 200:
            item_sets_data = items_res.json()
        else:
            items_res2 = self.request('GET', url_sets_with_id)
            if items_res2 and items_res2.status_code == 200:
                item_sets_data = items_res2.json()

        clean_start = [{"id": str(i).strip(), "count": 1} for i in ids_start if str(i).strip() and str(i).strip() != "0"]
        clean_core = [{"id": str(i).strip(), "count": 1} for i in ids_core if str(i).strip() and str(i).strip() != "0"]

        # Situacionales: aceptar lista de ids o de dicts {'id': ...}
        clean_sit = []
        for it in (ids_sit or []):
            iid = it.get("id") if isinstance(it, dict) else it
            iid = str(iid).strip()
            if iid and iid != "0":
                clean_sit.append({"id": iid, "count": 1})

        blocks = [
            {"type": "Start & Early Game", "items": clean_start},
            {"type": "Core Build (orden de compra)", "items": clean_core},
        ]
        if clean_sit:
            blocks.append({"type": "Situacionales", "items": clean_sit})

        nuevo_set = {
            "associatedChampions": [champ_id_int] if champ_id_int > 0 else [],
            "associatedMaps": [11],
            "blocks": blocks,
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
        if not reemplazado:
            lista_sets.append(nuevo_set)

        try:
            put_res = self.request('PUT', url_sets_base, json={"accountId": summoner_id, "itemSets": lista_sets}, timeout=30)
            if put_res and put_res.status_code in [200, 201, 204]:
                return True
            put_res2 = self.request('PUT', url_sets_with_id, json={"itemSets": lista_sets}, timeout=30)
            if put_res2 and put_res2.status_code in [200, 201, 204]:
                return True
            if (put_res and put_res.status_code == 404) or (put_res2 and put_res2.status_code == 404):
                return "Endpoint inválido. No se pudo guardar el item set en el cliente de LoL."
            return f"Error al guardar item set: {put_res.status_code if put_res else 'N/A'} / {put_res2.status_code if put_res2 else 'N/A'}"
        except requests.exceptions.ReadTimeout:
            return "Tiempo de espera agotado al guardar el item set. El set puede haberse creado; verifica en el cliente."
        except requests.exceptions.RequestException as exc:
            return f"Error de conexión al guardar item set: {exc}"