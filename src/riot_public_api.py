"""Cliente minimo de la API publica de Riot (Account-v1, League-v4, Mastery-v4).

Se usa para enriquecer la vista in-game (estilo Porofessor) con datos de los
OTROS jugadores de la partida — rango/liga, campeon principal (maestria) y WR de
soloq — que la LCU solo expone para el invocador local.

Diseno barato en rate-limit: 3 requests por jugador (puuid + liga + maestria),
sin el bucle caro de detalles de match-v5. Degrada con elegancia: ante errores,
key invalida o 429 devuelve None / activa un cooldown, y la UI muestra "—".
"""
import time
import threading
import requests

from src.config import cargar_config
from src.logger import get_logger

log = get_logger(__name__)

# Codigo de region de la LCU -> (plataforma para league/mastery, routing regional para account)
_REGION_MAP = {
    "NA": ("na1", "americas"), "NA1": ("na1", "americas"),
    "BR": ("br1", "americas"), "BR1": ("br1", "americas"),
    "LAN": ("la1", "americas"), "LA1": ("la1", "americas"),
    "LAS": ("la2", "americas"), "LA2": ("la2", "americas"),
    "OCE": ("oc1", "sea"), "OC1": ("oc1", "sea"),
    "EUW": ("euw1", "europe"), "EUW1": ("euw1", "europe"),
    "EUNE": ("eun1", "europe"), "EUN1": ("eun1", "europe"),
    "TR": ("tr1", "europe"), "TR1": ("tr1", "europe"), "RU": ("ru", "europe"),
    "KR": ("kr", "asia"), "JP": ("jp1", "asia"), "JP1": ("jp1", "asia"),
    "PH": ("ph2", "sea"), "SG": ("sg2", "sea"), "TH": ("th2", "sea"),
    "TW": ("tw2", "sea"), "VN": ("vn2", "sea"),
}


def _api_key():
    return (cargar_config() or {}).get("API_KEY", "") or ""


class RiotPublicAPI:
    def __init__(self, region_code=None):
        self.api_key = _api_key()
        plat, routing = _REGION_MAP.get((region_code or "").upper(), ("la2", "americas"))
        self.platform = plat
        self.routing = routing
        self._cache = {}          # puuid -> perfil dict
        self._puuid_cache = {}    # "name#tag" -> puuid
        self._lock = threading.Lock()
        self._cooldown_until = 0  # si la API nos limita (429/403), pausamos hasta aqui

    @property
    def disponible(self):
        return bool(self.api_key) and not self.api_key.startswith("RGAPI-xxx")

    def _get(self, url):
        if not self.disponible or time.time() < self._cooldown_until:
            return None
        try:
            r = requests.get(url, headers={"X-Riot-Token": self.api_key}, timeout=6)
        except Exception:
            return None
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return None
        if r.status_code == 429:
            try:
                retry = int(r.headers.get("Retry-After", "10"))
            except Exception:
                retry = 10
            self._cooldown_until = time.time() + retry
            log.warning("Riot API 429: cooldown %ss", retry)
        elif r.status_code in (401, 403):
            self._cooldown_until = time.time() + 600  # key invalida: no insistir
            log.warning("Riot API %s: API_KEY invalida o expirada", r.status_code)
        return None

    def resolver_puuid(self, game_name, tag_line):
        if not game_name or not tag_line:
            return None
        key = f"{game_name}#{tag_line}".lower()
        with self._lock:
            if key in self._puuid_cache:
                return self._puuid_cache[key]
        url = (f"https://{self.routing}.api.riotgames.com/riot/account/v1/accounts/"
               f"by-riot-id/{requests.utils.quote(game_name)}/{requests.utils.quote(tag_line)}")
        data = self._get(url)
        puuid = data.get("puuid") if data else None
        with self._lock:
            self._puuid_cache[key] = puuid
        return puuid

    def obtener_liga(self, puuid):
        """Dict {tier, rank, lp, wins, losses, wr, soloq} o None."""
        url = f"https://{self.platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        data = self._get(url)
        if not data:
            return None
        solo = next((e for e in data if e.get("queueType") == "RANKED_SOLO_5x5"), None)
        entry = solo or (data[0] if data else None)
        if not entry:
            return None
        wins, losses = entry.get("wins", 0), entry.get("losses", 0)
        total = wins + losses
        return {
            "tier": (entry.get("tier") or "").capitalize(),
            "rank": entry.get("rank", ""),
            "lp": entry.get("leaguePoints", 0),
            "wins": wins, "losses": losses,
            "wr": round(wins * 100.0 / total) if total else None,
            "soloq": entry.get("queueType") == "RANKED_SOLO_5x5",
        }

    def obtener_maestria(self, puuid):
        """Campeon de mayor maestria (main): {champion_id, puntos, nivel} o None."""
        url = (f"https://{self.platform}.api.riotgames.com/lol/champion-mastery/v4/"
               f"champion-masteries/by-puuid/{puuid}/top?count=1")
        data = self._get(url)
        if not data:
            return None
        top = data[0]
        return {
            "champion_id": top.get("championId"),
            "puntos": top.get("championPoints", 0),
            "nivel": top.get("championLevel", 0),
        }

    def obtener_match(self, match_id):
        url = f"https://{self.routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        return self._get(url)

    def series_por_minuto(self, match_id, puuid):
        """Series por minuto del jugador (oro/CS/dano a campeones) del timeline
        de match-v5. Devuelve {'oro':[...], 'cs':[...], 'dano':[...]} o None."""
        url = f"https://{self.routing}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        tl = self._get(url)
        if not tl:
            return None
        info = tl.get("info", {})
        pid = None
        for p in info.get("participants", []):
            if p.get("puuid") == puuid:
                pid = p.get("participantId")
                break
        if not pid:
            return None
        oro, cs, dano = [], [], []
        for frame in info.get("frames", []):
            pf = (frame.get("participantFrames") or {}).get(str(pid)) or {}
            oro.append(pf.get("totalGold", 0))
            cs.append(pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0))
            dano.append((pf.get("damageStats") or {}).get("totalDamageDoneToChampions", 0))
        if len(oro) < 2:
            return None
        return {"oro": oro, "cs": cs, "dano": dano}

    def perfil_completo(self, game_name, tag_line):
        """Resuelve liga + maestria de un jugador, cacheado por puuid.
        Pesado (3 requests) -> llamar SIEMPRE en hilo de fondo."""
        puuid = self.resolver_puuid(game_name, tag_line)
        if not puuid:
            return None
        with self._lock:
            if puuid in self._cache:
                return self._cache[puuid]
        perfil = {
            "puuid": puuid,
            "liga": self.obtener_liga(puuid),
            "maestria": self.obtener_maestria(puuid),
        }
        with self._lock:
            self._cache[puuid] = perfil
        return perfil
