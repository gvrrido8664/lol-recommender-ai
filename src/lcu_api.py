import os
import requests
import urllib3
from base64 import b64encode

# Desactivamos las advertencias de seguridad porque los certificados locales de Riot son autofirmados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
                
                self.headers = {
                    "Authorization": f"Basic {auth_base64}",
                    "Accept": "application/json"
                }
                return True
        except Exception:
            return False

    def obtener_sesion_draft(self):
        """Obtiene los datos en vivo de la fase de selección de campeones."""
        if not self.port: return None
            
        url = f"{self.protocol}://127.0.0.1:{self.port}/lol-champ-select/v1/session"
        try:
            response = requests.get(url, headers=self.headers, verify=False, timeout=2)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def obtener_mi_rol(self, draft_data):
        """Identifica el rol asignado leyendo los datos del draft."""
        if not draft_data: return "MIDDLE"
            
        mi_celda = draft_data.get('localPlayerCellId')
        for jugador in draft_data.get('myTeam', []):
            if jugador.get('cellId') == mi_celda:
                rol_lcu = jugador.get('assignedPosition', 'MIDDLE').upper()
                mapeo = {
                    'UTILITY': 'UTILITY',
                    'BOTTOM': 'BOTTOM',
                    'JUNGLE': 'JUNGLE',
                    'TOP': 'TOP',
                    'MIDDLE': 'MIDDLE'
                }
                return mapeo.get(rol_lcu, 'MIDDLE')
        return "MIDDLE"


# BLOQUE DE PRUEBA
if __name__ == "__main__":
    cliente = LCUConnector()
    if cliente.conectar():
        datos_jugador = cliente.obtener_summoner_actual()
        if datos_jugador:
            riot_id = f"{datos_jugador.get('gameName')}#{datos_jugador.get('tagLine')}"
            print(f"\n👤 Sesión iniciada como: {riot_id} (Nivel {datos_jugador.get('summonerLevel')})")
        
        print("\n🔍 Buscando partida en curso...")
        draft_data = cliente.obtener_sesion_draft()
        
        if draft_data:
            print("✅ ¡Estás en la selección de campeones!")
            
            enemigos = draft_data.get('theirTeam', [])
            print("\n🔴 EQUIPO ENEMIGO:")
            for enemigo in enemigos:
                campeon_id = enemigo.get('championId')
                if campeon_id != 0: 
                    print(f" - Enemigo pickeó el campeón con ID: {campeon_id}")
                else:
                    print(" - Enemigo pensando...")
        else:
            print("❌ No estás en la selección de campeones actualmente.")
            print("💡 TIP: Crea una partida personalizada con bots y vuelve a ejecutar el script.")