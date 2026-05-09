from .db_manager import obtener_conexion
import datetime

def generar_reporte_completo():
    conn = obtener_conexion()
    cur = conn.cursor()

    print("\n" + "="*50)
    print("       📊 REPORTE ANALÍTICO DE LA BASE DE DATOS")
    print("="*50)

    # 1. ESTADÍSTICAS GENERALES
    cur.execute("SELECT COUNT(*) FROM matches")
    total_partidas = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM participantes")
    total_registros = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT champion) FROM participantes")
    total_champs = cur.fetchone()[0]

    print(f"🏟️  Partidas totales:      {total_partidas}")
    print(f"👥  Registros de jugadores: {total_registros}")
    print(f"⚔️  Campeones únicos:      {total_champs}/168")

    # 2. DISTRIBUCIÓN POR LÍNEA (Calidad del entrenamiento)
    print("\n📍 COBERTURA POR POSICIÓN:")
    cur.execute("""
        SELECT team_position, COUNT(*) 
        FROM participantes 
        WHERE team_position != '' 
        GROUP BY team_position
    """)
    posiciones = cur.fetchall()
    for pos, cant in posiciones:
        # Cada partida tiene 2 jugadores por posición (aliado y enemigo)
        progreso = min(100, (cant / 200) * 100) # 200 registros es buena base para una línea
        barra = "█" * int(progreso / 10) + "░" * (10 - int(progreso / 10))
        print(f"  {pos:8}: {cant:5} registros |{barra}| {progreso:.1f}%")

    # 3. TOP 5 CAMPEONES CON MÁS "INTELIGENCIA"
    print("\n🏆 CAMPEONES CON MEJOR DATA (BUILD + IA):")
    cur.execute("""
        SELECT champion, COUNT(*) as cant, 
               ROUND(AVG(win) * 100, 1) as wr
        FROM participantes 
        GROUP BY champion 
        ORDER BY cant DESC 
        LIMIT 5
    """)
    for i, fila in enumerate(cur.fetchall(), 1):
        print(f"  {i}. {fila['champion']:12} | {fila['cant']:4} partidas | WR: {fila['wr']}%")

    # 4. SALUD DE LAS BUILDS (Partidas de larga duración)
    # Buscamos partidas de más de 25 min donde es probable ver 6 ítems
    cur.execute("SELECT COUNT(*) FROM matches WHERE game_duration > 1500")
    partidas_largas = cur.fetchone()[0]
    pct_largas = (partidas_largas / total_partidas * 100) if total_partidas > 0 else 0
    
    print(f"\n🧪 SALUD DE BUILDS COMPLETAS:")
    print(f"  Partidas >25 min: {partidas_largas} ({pct_largas:.1f}%)")
    if pct_largas < 20:
        print("  ⚠️ Nota: Tienes pocas partidas largas. Las builds de 6 ítems podrían ser escasas.")
    else:
        print("  ✅ Tienes suficiente data para mostrar builds finales sólidas.")

    print("="*50 + "\n")
    conn.close()

if __name__ == "__main__":
    generar_reporte_completo()