"""
Analizador de Fatiga y Rendimiento (Pilar 6)
═══════════════════════════════════════════════
Evalúa el contexto físico/mental del jugador analizando:
- Partidas consecutivas sin descanso (>30 min entre partidas = reset)
- Rendimiento de la primera partida del día vs partidas acumuladas
- Tasa de victorias según hora del día y tamaño de sesión
"""
from datetime import datetime, timedelta
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FATIGA_PATH = os.path.join(DATA_DIR, "fatiga_sesiones.json")

RESET_SEGUNDOS = 3 * 3600  # 3 horas entre el fin de una partida y el inicio de la siguiente = nueva sesión


def analizar_fatiga(historial_games):
    """
    Analiza el historial de partidas y devuelve un dict con métricas de fatiga.
    
    Args:
        historial_games: lista de partidas de LCU, cada una con:
            - gameCreationDate: string de fecha
            - gameDuration: duración en segundos
            - participants[0].stats.win: bool
    
    Returns:
        dict con: sesiones, partidas_hoy, racha_actual, rendimiento_primera_vs_resto,
                 estado (fresh/tired/tilted), recomendacion
    """
    if not historial_games:
        return {"estado": "sin_datos", "mensaje": "Sin datos de partidas recientes", "recomendacion": "Juega una partida para que el sistema aprenda tus patrones."}

    partidas = []
    for g in historial_games:
        try:
            # LCU usa gameCreationDate (string) no gameCreation (timestamp)
            fecha_str = g.get("gameCreationDate", "")
            if fecha_str:
                try:
                    dt = datetime.strptime(fecha_str, "%b %d, %Y %I:%M:%S %p")
                except ValueError:
                    try:
                        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                    except:
                        continue
            else:
                ts = g.get("gameCreation", 0)
                if ts < 1000000000:
                    ts = ts / 1000
                if ts == 0:
                    continue
                dt = datetime.fromtimestamp(ts)
            dur = g.get("gameDuration", 0)
            win = g.get("participants", [{}])[0].get("stats", {}).get("win", False)
            partidas.append({"fecha": dt, "duracion": dur, "win": win})
        except Exception as e:
            continue

    # Ordenar por fecha ascendente (más antigua primero) para detectar sesiones correctamente
    partidas.sort(key=lambda p: p["fecha"])

    if not partidas:
        return {"estado": "sin_datos", "mensaje": "No se pudieron procesar las partidas", "recomendacion": "Verificá que el cliente de LoL esté funcionando correctamente."}

    # ── Detectar sesiones: 3h entre fin de partida e inicio de la siguiente = nueva sesión ──
    sesiones = []
    sesion_actual = []
    for p in partidas:
        if not sesion_actual:
            sesion_actual.append(p)
        else:
            ultima = sesion_actual[-1]
            fin_anterior = ultima["fecha"] + timedelta(seconds=ultima["duracion"])
            pausa = (p["fecha"] - fin_anterior).total_seconds()
            if pausa > RESET_SEGUNDOS:
                sesiones.append(sesion_actual)
                sesion_actual = [p]
            else:
                sesion_actual.append(p)
    if sesion_actual:
        sesiones.append(sesion_actual)

    # ── Partidas hoy ──
    hoy = datetime.now().date()
    partidas_hoy = [p for p in partidas if p["fecha"].date() == hoy]

    # ── Sesión más reciente (última en el array ordenado oldest-first) ──
    sesion_actual = sesiones[-1] if sesiones else []
    wins_sesion = sum(1 for p in sesion_actual if p["win"])
    total_sesion = len(sesion_actual)

    # ── Rendimiento: primera partida del día vs resto ──
    if len(sesion_actual) >= 2:
        resto = sesion_actual[:-1]
        wr_resto = round(sum(1 for p in resto if p["win"]) / len(resto) * 100) if resto else 0
    else:
        wr_resto = 0

    # ── ¿Primera partida del día? ──
    es_primera_del_dia = len(partidas_hoy) <= 1

    # ── Determinar estado ──
    if total_sesion >= 5:
        if wins_sesion <= total_sesion * 0.3:
            estado = "tilted"
            mensaje = f"😤 {total_sesion} partidas seguidas y bajo WR. Estás tilted."
            recomendacion = "Cierra LoL, descansa al menos 1 hora. Tu WR cae en picada con la fatiga."
        else:
            estado = "tired"
            mensaje = f"😴 Llevas {total_sesion} partidas seguidas. Tu rendimiento puede bajar."
            recomendacion = "Considera una pausa de 30 min antes de la siguiente."
    elif total_sesion >= 3:
        wr_sesion = round(wins_sesion / total_sesion * 100) if total_sesion > 0 else 0
        if wr_sesion < 40:
            estado = "tilted"
            mensaje = f"⚠️ {total_sesion} partidas con bajo WR ({wr_sesion}%). Posible tilt."
            recomendacion = "Levántate, toma agua, vuelve en 20 min."
        else:
            estado = "tired"
            mensaje = f"🎯 {total_sesion} partidas en esta sesión. Rendimiento estable."
            recomendacion = "Si te sientes bien, sigue. Si no, una pausa nunca sobra."
    elif total_sesion == 1:
        if es_primera_del_dia:
            estado = "fresh"
            mensaje = "🌅 ¡Es tu primera partida del día! Estás en tu mejor momento."
            recomendacion = "Juega tu mejor campeón. Calienta en práctica de herramientas si quieres antes de jugar ranked."
        else:
            estado = "fresh"
            mensaje = "🌟 Primera partida de la sesión. Estás fresco."
            recomendacion = "Buen momento para jugar tu mejor campeón."
    else:
        estado = "neutral"
        mensaje = "👌 Sesión corta. Todo bien por ahora."
        recomendacion = "Mantén el ritmo."

    return {
        "estado": estado,
        "mensaje": mensaje,
        "recomendacion": recomendacion,
        "sesion_actual": total_sesion,
        "wins_sesion": wins_sesion,
        "partidas_hoy": len(partidas_hoy),
        "total_sesiones": len(sesiones),
        "wr_sesion": round(wins_sesion / total_sesion * 100) if total_sesion > 0 else 0,
        "wr_resto_sesion": wr_resto,
    }


def guardar_fatiga(data):
    """Guarda datos de fatiga para tracking histórico."""
    try:
        historial = []
        if os.path.exists(FATIGA_PATH):
            with open(FATIGA_PATH, "r", encoding="utf-8") as f:
                historial = json.load(f)
        historial.append({**data, "fecha": datetime.now().isoformat()})
        if len(historial) > 50:
            historial = historial[-50:]
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(FATIGA_PATH, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except:
        pass
