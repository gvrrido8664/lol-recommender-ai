"""Constantes de diseno (paleta NEXUS) — namespace efectivo unico.

Reproduce exactamente el namespace que tenia app.py: primero el bloque local
de diseno y despues el override desde src.theme (que pisa BG_DARK, TEXT_MUTED,
etc. con los valores reales). Asi app.py y los modulos de ui/ comparten una
unica fuente, sin duplicacion ni shadowing.

NOTA: varios valores locales ("{BG_CARD_HOVER}", etc.) son placeholders rotos
de una migracion previa; se conservan tal cual para no cambiar el comportamiento.
Se corrigen en la fase de tema.
"""

BG_DARK = "#05080f"
BG_PANEL = "#0c101a"
BG_CARD = "#111827"
BORDER_ACCENT = "#e63946"
BORDER_SUBTLE = "{BG_CARD_HOVER}"
TEXT_WHITE = "{TEXT_PRIMARY}"
TEXT_MUTED = "{TEXT_SUBTLE}"
TEXT_GOLD = "{TEXT_SURFACE}"
ACCENT_RED = "#e63946"
ACCENT_TEAL = "#2dd4bf"
RED_WR = "{RED_DANGER}"
GREEN_WR = "{GREEN_SUCCESS}"
YELLOW_WR = "{YELLOW_WARNING}"
ALLY_BG = "{BG_DARK}"
ENEMY_BG = "#1a0a0f"
HOVER_GLOW = "#f43f5e"
FONT_FAMILY = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

# Override con los valores reales de la paleta semantica (igual que antes en app.py:309).
from src.theme import (TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_SUBTLE,
                       TEXT_LIGHT, TEXT_SURFACE, GREEN_SUCCESS, RED_DANGER,
                       YELLOW_WARNING, BG_DARK, BG_CARD_HOVER, BG_BORDER)

__all__ = [
    "BG_DARK", "BG_PANEL", "BG_CARD", "BORDER_ACCENT", "BORDER_SUBTLE",
    "TEXT_WHITE", "TEXT_MUTED", "TEXT_GOLD", "ACCENT_RED", "ACCENT_TEAL",
    "RED_WR", "GREEN_WR", "YELLOW_WR", "ALLY_BG", "ENEMY_BG", "HOVER_GLOW",
    "FONT_FAMILY", "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_SUBTLE",
    "TEXT_LIGHT", "TEXT_SURFACE", "GREEN_SUCCESS", "RED_DANGER",
    "YELLOW_WARNING", "BG_CARD_HOVER", "BG_BORDER",
]
