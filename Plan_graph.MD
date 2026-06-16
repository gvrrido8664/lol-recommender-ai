Eres un asistente que genera código en Python para una app de escritorio escrita con PySide6.

La interfaz ya existe. En la vista de "Mi Perfil" hay un panel llamado "Insights" que contiene un QLabel
donde quiero mostrar un gráfico de la evolución de LP (League Points) de un jugador de League of Legends.

Cualquier paso que ya tengas realizado anteriormente puedes saltarlo

Necesito que generes SOLO código Python que:

1) IMPORTS Y CONSTANTES
- Importe:
  - import os
  - import json
  - from datetime import datetime
  - import requests
  - import matplotlib.pyplot as plt
  - from PySide6.QtWidgets import QLabel
  - from PySide6.QtGui import QPixmap
  - from PySide6.QtCore import Qt
- Defina constantes:
  - API_KEY = "{API_KEY}"              # API key de Riot
  - PLATFORM_REGION = "{PLATFORM_REGION}"   # ej: "la2", "lan", "euw1" (plataforma)
  - ROUTING_REGION = "{ROUTING_REGION}"     # ej: "americas", "europe", "asia"
  - GAME_NAME = "{GAME_NAME}"          # Riot ID name, ej: "LuckyAD"
  - TAG_LINE = "{TAG_LINE}"            # Riot ID tag, ej: "LAS"
  - QUEUE_TYPE = "RANKED_SOLO_5x5"
- Defina:
  - LP_HISTORY_FILE = f"lp_history_{GAME_NAME}_{TAG_LINE}_{QUEUE_TYPE}.json"

2) OBTENER PUUID A PARTIR DE RIOT ID (account-v1)
- Función get_puuid(game_name: str, tag_line: str) -> str:
  - Construye la URL:
    f"https://{ROUTING_REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
  - Hace GET con headers = {"X-Riot-Token": API_KEY}.
  - Si status_code != 200 lanza una excepción con el mensaje del servidor.
  - Devuelve el campo "puuid" del JSON.

3) OBTENER encryptedSummonerId A PARTIR DE PUUID (summoner-v4)
- Función get_summoner_id(puuid: str) -> str:
  - URL:
    f"https://{PLATFORM_REGION}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
  - GET con el mismo header.
  - Devuelve el campo "id" (encryptedSummonerId).

4) OBTENER LP ACTUAL (league-v4)
- Función get_current_lp(encrypted_summoner_id: str, queue_type: str) -> dict:
  - URL:
    f"https://{PLATFORM_REGION}.api.riotgames.com/lol/league/v4/entries/by-summoner/{encrypted_summoner_id}"
  - GET con header.
  - Recorre la lista devuelta y busca la entrada donde entry["queueType"] == queue_type.
  - Devuelve un dict con:
    {
      "lp": entry["leaguePoints"],
      "tier": entry["tier"],
      "rank": entry["rank"],
      "wins": entry["wins"],
      "losses": entry["losses"]
    }

5) PERSISTENCIA DEL HISTORIAL LOCAL DE LP
- Función load_lp_history() -> list[dict]:
  - Si LP_HISTORY_FILE existe y es válido, lo lee como JSON y devuelve la lista.
  - Si no existe, devuelve [].
- Función save_lp_history(history: list[dict]) -> None:
  - Guarda la lista en LP_HISTORY_FILE con json.dump(..., ensure_ascii=False, indent=2).
- Función update_lp_history() -> list[dict]:
  - Llama a get_puuid(GAME_NAME, TAG_LINE).
  - Llama a get_summoner_id(puuid).
  - Llama a get_current_lp(encrypted_summoner_id, QUEUE_TYPE).
  - Obtiene ahora = datetime.now().isoformat(timespec="seconds").
  - Carga history = load_lp_history().
  - Si history está vacío o history[-1]["lp"] es distinto de lp actual:
    - Añade:
      {
        "timestamp": ahora,
        "lp": lp_actual,
        "tier": tier,
        "rank": rank,
        "wins": wins,
        "losses": losses
      }
    - Llama a save_lp_history(history).
  - Devuelve history.

6) GENERAR GRÁFICO CON MATPLOTLIB
- Función generate_lp_chart_png(history: list[dict]) -> str | None:
  - Si history está vacío, devuelve None.
  - Define:
    - x = list(range(1, len(history) + 1))
    - y = [point["lp"] for point in history]
  - Crea figura: plt.figure(figsize=(10, 4))
  - Dibuja la línea con marcadores: plt.plot(x, y, marker="o", color="#00ff99")
  - Título: f"Historial de LP – {GAME_NAME}#{TAG_LINE}"
  - Etiquetas de ejes: "Snapshot / Partida" y "LP totales".
  - Activa cuadrícula.
  - Usa plt.tight_layout().
  - Asegura que exista un subdirectorio "charts" (os.makedirs("charts", exist_ok=True)).
  - file_path = os.path.join("charts", f"lp_history_{GAME_NAME}_{TAG_LINE}_{QUEUE_TYPE}.png")
  - Guarda la figura con plt.savefig(file_path, dpi=120) y hace plt.close().
  - Devuelve file_path.

7) MOSTRAR EL PNG EN UN QLabel DE PYSIDE6
- Función display_chart_in_label(label: QLabel, image_path: str) -> None:
  - Si image_path es None o el archivo no existe, limpia el label: label.clear(); return.
  - Crea pixmap = QPixmap(image_path).
  - Si pixmap.isNull(): label.clear(); return.
  - Escala el pixmap a label.size() manteniendo relación de aspecto:
    - scaled = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
  - Asigna al label: label.setPixmap(scaled)
  - Centra el contenido: label.setAlignment(Qt.AlignCenter)

8) FUNCIÓN PÚBLICA PARA USAR EN LA VISTA (INSIGHTS)
- Función update_insights_lp_chart(insight_label: QLabel) -> None:
  - Llama a history = update_lp_history().
  - Llama a image_path = generate_lp_chart_png(history).
  - Llama a display_chart_in_label(insight_label, image_path).

9) RESTRICCIONES
- NO generes código de creación de la ventana principal ni del resto de la UI.
- Asume que la clase de la ventana principal ya tiene un QLabel en el panel de "Insights"
  y que el código de esa clase llamará a update_insights_lp_chart(self.{NOMBRE_DEL_LABEL}).
- No generes datos de ejemplo ni llamadas de prueba fuera de funciones.
- No imprimas texto salvo en mensajes de error mínimos cuando una petición HTTP falle.
- Devuélveme únicamente el código Python, sin explicaciones de texto fuera del código.

