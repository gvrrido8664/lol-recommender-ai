import requests
from src.lcu_api import LCUConnector
import urllib3
urllib3.disable_warnings()
conn = LCUConnector()
if not conn.conectar():
    raise SystemExit('No connect')
urls = [
    '/lol-ranked/v1/current-ranks',
    '/lol-ranked/v1/current-rank',
    '/lol-ranked/v1/queues',
    '/lol-ranked/v1/queue',
    '/lol-ranked/v1/entries',
    '/lol-ranked/v1/entries/420',
    '/lol-ranked/v1/entries/430',
    '/lol-ranked/v1/queue/entries',
    '/lol-ranked/v1/ranked-stats',
    '/lol-ranked/v1/current-ranked',
    '/lol-ranked/v1/queueMap',
    '/lol-ranking/v1/current-rank',
    '/lol-ranking/v1/current-ranks',
    '/lol-ranked/v1/',
    '/lol-ranked/v1/status',
    '/lol-ranked/v1/summary'
]
for path in urls:
    url = f'{conn.protocol}://127.0.0.1:{conn.port}{path}'
    try:
        r = requests.get(url, headers=conn.headers, verify=False, timeout=3)
        print('GET', path, r.status_code, r.text[:400])
    except Exception as e:
        print('GET', path, 'ERROR', type(e).__name__, e)
