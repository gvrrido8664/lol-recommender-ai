from fastapi import APIRouter, Depends, HTTPException

from backend.auth import verificar_token
from backend.config import API_KEY
from backend.riot import riot_get

router = APIRouter(prefix="/riot", tags=["riot"])

_cache: dict = {}


@router.get("/account/by-riot-id/{game_name}/{tag_line}")
async def account_by_riot_id(game_name: str, tag_line: str, routing: str = "americas", _token: str = Depends(verificar_token)):
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return await _proxy(url, cache_ttl=3600)


@router.get("/account/by-puuid/{puuid}")
async def account_by_puuid(puuid: str, routing: str = "americas", _token: str = Depends(verificar_token)):
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    return await _proxy(url, cache_ttl=3600)


@router.get("/summoner/by-puuid/{puuid}")
async def summoner_by_puuid(puuid: str, region: str = "la2", _token: str = Depends(verificar_token)):
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return await _proxy(url, cache_ttl=300)


@router.get("/league/by-puuid/{puuid}")
async def league_by_puuid(puuid: str, platform: str = "la2", _token: str = Depends(verificar_token)):
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    return await _proxy(url, cache_ttl=120)


@router.get("/league/by-summoner/{encrypted_id}")
async def league_by_summoner(encrypted_id: str, region: str = "la2", _token: str = Depends(verificar_token)):
    url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{encrypted_id}"
    return await _proxy(url, cache_ttl=120)


@router.get("/mastery/top/{puuid}")
async def mastery_top(puuid: str, platform: str = "la2", _token: str = Depends(verificar_token)):
    url = f"https://{platform}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count=1"
    return await _proxy(url, cache_ttl=600)


@router.get("/match/by-puuid/{puuid}/ids")
async def match_ids(
    puuid: str,
    routing: str = "americas",
    start: int = 0,
    count: int = 100,
    start_time: int | None = None,
    _token: str = Depends(verificar_token),
):
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
    if start_time:
        url += f"&startTime={start_time}"
    return await _proxy(url, cache_ttl=60)


@router.get("/match/{match_id}")
async def match_detail(match_id: str, routing: str = "americas", _token: str = Depends(verificar_token)):
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return await _proxy(url, cache_ttl=3600)


@router.get("/match/{match_id}/timeline")
async def match_timeline(match_id: str, routing: str = "americas", _token: str = Depends(verificar_token)):
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
    return await _proxy(url, cache_ttl=3600)


async def _proxy(url: str, cache_ttl: int = 300) -> dict:
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Riot API key no configurada en el backend")
    data = await riot_get(url, cache=_cache, cache_ttl=cache_ttl)
    if data is None:
        raise HTTPException(status_code=502, detail="Error al consultar la API de Riot")
    return data
