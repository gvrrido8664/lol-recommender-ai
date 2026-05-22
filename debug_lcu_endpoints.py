import requests
from src.lcu_api import LCUConnector

conn = LCUConnector()
print('lockfile', conn.lockfile_path)
ok = conn.conectar()
print('conectar', ok)
print('port', conn.port, 'protocol', conn.protocol)
perfil = conn.obtener_perfil()
print('perfil', perfil)
if not ok or not perfil:
    raise SystemExit('No se pudo conectar o no hay perfil')

summoner_id = perfil.get('summonerId')
endpoints = [
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-ranked/v1/current-ranks',
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets/{summoner_id}',
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets/{summoner_id}/sets',
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets',
]
for url in endpoints:
    try:
        r = requests.get(url, headers=conn.headers, verify=False, timeout=3)
        print('GET', url, r.status_code, r.text[:500])
    except Exception as e:
        print('GET', url, 'ERROR', repr(e))
