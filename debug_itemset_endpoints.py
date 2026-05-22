import json
import requests
import urllib3
from src.lcu_api import LCUConnector

urllib3.disable_warnings()
conn = LCUConnector()
if not conn.conectar():
    raise SystemExit('No lockfile')
perfil = conn.obtener_perfil()
sid = perfil.get('summonerId')
urls = [
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets',
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets/{sid}',
    f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets/{sid}/sets',
]
for url in urls:
    try:
        r = requests.get(url, headers=conn.headers, verify=False, timeout=5)
        print('GET', url, r.status_code)
        print(r.text[:1000])
    except Exception as e:
        print('ERR', url, e)
    print('-'*80)
