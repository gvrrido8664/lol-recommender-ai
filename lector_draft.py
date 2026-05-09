import time
import sys
import os
from src.lcu_api import LCUConnector
from src.data_dragon import DataDragonAPI
from src.motor_ia import MotorIA

def iniciar_monitoreo():
    print("="*60)
    print("🚀 SISTEMA DE RECOMENDACIÓN INTELIGENTE (AUTO-ROL)")
    print("="*60)
    
    ddragon = DataDragonAPI()
    diccionario_campeones = ddragon.cargar_diccionario()
    
    ia = MotorIA(ruta_modelo=os.path.join("data", "modelo_ia.pkl"))
    
    cliente = LCUConnector()
    if not cliente.conectar():
        print("\n❌ Error: Asegúrate de tener el LoL abierto.")
        return
        
    print("\n⏳ Radar activo. Esperando entrada a Draft...")
    en_draft = False
    rol_configurado = False
    
    try:
        while True:
            draft_data = cliente.obtener_sesion_draft()
            
            if draft_data:
                if not en_draft:
                    print("\n" + "!"*30)
                    print("🚨 SELECCIÓN DE CAMPEONES DETECTADA")
                    print("!"*30 + "\n")
                    en_draft = True
                    rol_configurado = False # Reiniciar para la nueva partida

                # --- AUTO-DETECCIÓN DE ROL ---
                if not rol_configurado:
                    # Buscamos nuestra posición en la sesión
                    mi_celda = draft_data.get('localPlayerCellId')
                    mi_rol = "MIDDLE" # Default
                    
                    for jugador in draft_data.get('myTeam', []):
                        if jugador.get('cellId') == mi_celda:
                            pos = jugador.get('assignedPosition', '').upper()
                            # Mapeamos a las llaves de tu .pkl
                            if pos == 'UTILITY': mi_rol = 'UTILITY'
                            elif pos == 'BOTTOM': mi_rol = 'BOTTOM'
                            elif pos == 'JUNGLE': mi_rol = 'JUNGLE'
                            elif pos == 'TOP': mi_rol = 'TOP'
                            else: mi_rol = 'MIDDLE'
                    
                    ia.cambiar_rol_activo(mi_rol)
                    print(f"📍 Posición detectada: {mi_rol} - Ajustando IA...")
                    rol_configurado = True

                # --- PROCESAMIENTO DE ENEMIGOS ---
                enemigos_raw = draft_data.get('theirTeam', [])
                nombres_enemigos = []
                for e in enemigos_raw:
                    cid = str(e.get('championId', 0))
                    if cid != '0':
                        nombres_enemigos.append(diccionario_campeones.get(cid, "Desconocido"))
                
                if nombres_enemigos:
                    sugerencias = ia.predecir_counters(nombres_enemigos)
                    if sugerencias:
                        texto = " | ".join([f"✨ {s['campeon']} ({s['winrate']}%)" for s in sugerencias])
                        sys.stdout.write(f"\r[ROL: {ia.rol_activo}] Enemigos: {', '.join(nombres_enemigos)} >>> {texto}      ")
                    else:
                        sys.stdout.write(f"\r[ROL: {ia.rol_activo}] Analizando picks enemigos...                  ")
                else:
                    sys.stdout.write(f"\r[ROL: {ia.rol_activo}] Esperando el primer pick enemigo...            ")
                
                sys.stdout.flush()
                    
            else:
                if en_draft:
                    print("\n\n🚪 Partida iniciada o Draft cancelado. Radar en espera...")
                    en_draft = False
                    rol_configurado = False
                    
            time.sleep(1.2)

    except KeyboardInterrupt:
        print("\n\n🛑 Apagando sistema...")

if __name__ == "__main__":
    iniciar_monitoreo()