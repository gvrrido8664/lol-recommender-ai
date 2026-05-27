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

DESCANSO_MIN = 30  # minutos entre partidas para considerar "descanso"


def analizar_fatiga(historial_games):
    """
    Analiza el historial de partidas y devuelve un dict con métricas de fatiga.
    
    Args:
        historial_games: lista de partidas de LCU, cada una con:
            - gameCreation: timestamp de inicio
            - gameDuration: duración en segundos
            - participants[0].stats.win: bool
    
    Returns:
        dict con: sesiones, partidas_hoy, racha_actual, rendimiento_primera_vs_resto,
                 estado (fresh/tired/tilted), recomendacion
    """
    if not historial_games:
        return {"estado": "sin_datos", "mensaje": "Sin datos de partidas recientes", "recomendacion": "Jugá una partida para que el sistema aprenda tus patrones."}

    # Ordenar partidas por fecha (más reciente primero)
    partidas = []
    for g in historial_games:
        try:
            # LCU usa gameCreationDate (string) no gameCreation (timestamp)
            fecha_str = g.get("gameCreationDate", "")
            if fecha_str:
                # Formato LCU: "May 27, 2026 12:34:56 PM" o ISO
                try:
                    dt = datetime.strptime(fecha_str, "%b %d, %Y %I:%M:%S %p")
                except ValueError:
                    try:
                        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                    except:
                        continue
            else:
                # Fallback: probar gameCreation como timestamp
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

    partidas.sort(key=lambda p: p["fecha"], reverse=True)

    if not partidas:
        return {"estado": "sin_datos", "mensaje": "No se pudieron procesar las partidas", "recomendacion": "Verificá que el cliente de LoL esté funcionando correctamente."}

    # ── Detectar sesiones (grupos de partidas sin descanso >30 min) ──
    sesiones = []
    sesion_actual = []
    for i, p in enumerate(partidas):
        if not sesion_actual:
            sesion_actual.append(p)
        else:
            ultima = sesion_actual[-1]
            # Tiempo entre fin de la anterior e inicio de esta
            fin_anterior = ultima["fecha"] + timedelta(seconds=ultima["duracion"])
            pausa = (p["fecha"] - fin_anterior).total_seconds() / 60
            if pausa > DESCANSO_MIN:
                sesiones.append(sesion_actual)
                sesion_actual = [p]
            else:
                sesion_actual.append(p)
    if sesion_actual:
        sesiones.append(sesion_actual)

    # ── Partidas hoy ──
    hoy = datetime.now().date()
    partidas_hoy = [p for p in partidas if p["fecha"].date() == hoy]

    # ── Racha actual (sesión más reciente) ──
    sesion_actual = sesiones[0] if sesiones else []
    wins_sesion = sum(1 for p in sesion_actual if p["win"])
    total_sesion = len(sesion_actual)

    # ── Rendimiento: primera partida del día vs resto ──
    if len(sesion_actual) >= 2:
        primera = sesion_actual[-1]  # la más antigua de la sesión
        resto = sesion_actual[:-1]
        wr_resto = round(sum(1 for p in resto if p["win"]) / len(resto) * 100) if resto else 0
    else:
        wr_resto = 0

    # ── Determinar estado ──
    if total_sesion >= 5:
        if wins_sesion <= total_sesion * 0.3:
            estado = "tilted"
            mensaje = "😤 Estás en pérdida. 5+ partidas seguidas y bajo rendimiento. Descansa."
            recomendacion = "Toma un descanso de 30+ minutos. Tu WR cae con la fatiga."
        else:
            estado = "tired"
            mensaje = "😴 Llevas {} partidas seguidas. Tu rendimiento puede bajar.".format(total_sesion)
            recomendacion = "Considera una pausa de 15 min antes de la siguiente."
    elif total_sesion >= 3:
        wr_sesion = round(wins_sesion / total_sesion * 100) if total_sesion > 0 else 0
        if wr_sesion < 40:
            estado = "tilted"
            mensaje = "⚠️ 3+ partidas con bajo WR ({}%). Posible tilt.".format(wr_sesion)
            recomendacion = "Levántate, toma agua, vuelve en 20 min."
        else:
            estado = "tired"
            mensaje = "🎯 {} partidas en esta sesión. Rendimiento estable.".format(total_sesion)
            recomendacion = "Si te sentís bien, seguí. Si no, una pausa nunca sobra."
    elif total_sesion == 1:
        estado = "fresh"
        mensaje = "🌟 Primera partida de la sesión. Estás fresco."
        recomendacion = "Buen momento para jugar tu mejor campeón."
    else:
        estado = "neutral"
        mensaje = "👌 Sesión corta. Todo bien por ahora."
        recomendacion = "Mantené el ritmo."

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
