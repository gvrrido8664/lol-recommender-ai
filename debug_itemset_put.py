import requests
from src.lcu_api import LCUConnector
import urllib3
urllib3.disable_warnings()
conn=LCUConnector()
if not conn.conectar():
    raise SystemExit('No connect')
per=conn.obtener_perfil()
id=per.get('summonerId')
url=f'{conn.protocol}://127.0.0.1:{conn.port}/lol-item-sets/v1/item-sets/{id}/sets'
r=requests.get(url, headers=conn.headers, verify=False, timeout=3)
print('GET', r.status_code, r.text[:1000])
obj=r.json()
print('PUT->trying')
r2=requests.put(url, headers=conn.headers, json=obj, verify=False, timeout=10)
print('PUT', r2.status_code, r2.text[:1000])
