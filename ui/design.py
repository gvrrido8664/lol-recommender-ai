"""Constantes de diseno (paleta NEXUS) — namespace efectivo unico.

Reproduce exactamente el namespace que tenia app.py: primero el bloque local
de diseno y despues el override desde src.theme (que pisa BG_DARK, TEXT_MUTED,
etc. con los valores reales). Asi app.py y los modulos de ui/ comparten una
unica fuente, sin duplicacion ni shadowing.
"""

BG_PANEL = "#16131c"
BG_CARD = "#1b1620"
BORDER_ACCENT = "#e63946"
BORDER_SUBTLE = "{BG_CARD_HOVER}"
TEXT_WHITE = "{TEXT_PRIMARY}"
TEXT_GOLD = "{TEXT_SURFACE}"
ACCENT_RED = "#e63946"
ACCENT_TEAL = "#f0b232"
RED_WR = "{RED_DANGER}"
GREEN_WR = "{GREEN_SUCCESS}"
YELLOW_WR = "{YELLOW_WARNING}"
ALLY_BG = "{BG_DARK}"
ENEMY_BG = "#1a0a0f"
HOVER_GLOW = "#f43f5e"
FONT_FAMILY = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

# Override con los valores reales de la paleta semantica (igual que antes en app.py:309).
from src.theme import (
    ACCENT_GOLD,
    AMBER_ACCENT,
    BG_BORDER,
    BG_CARD_ELEVATED,
    BG_CARD_HOVER,
    BG_DARK,
    BG_DARK_BROWN,
    BG_DARK_GREEN,
    BG_DARK_PURPLE,
    BG_DARK_RED,
    BG_DARK_RED2,
    BG_DARK_TEAL,
    BG_DARK_YELLOW,
    BG_TABLE_HEADER,
    BORDER_TABLE_ITEM,
    CARD_DARK_BLUE,
    CARD_DARKER_BLUE,
    CARD_MID_BLUE2,
    GOLD_DARK,
    GREEN_SUCCESS,
    RED_DANGER,
    RED_DARK,
    RED_DARK_CARD,
    TEXT_LIGHT,
    TEXT_MUTED,
    TEXT_MUTED_ALT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_SUBTLE,
    TEXT_SURFACE,
    YELLOW_WARNING,
)

# Completar la migracion de tema: estas constantes quedaron como placeholders
# rotos ("{BG_CARD_HOVER}", etc.) que Qt ignoraba en los stylesheets. Sus nombres
# indican el valor pretendido; aqui se enlazan a los valores reales de la paleta.
BORDER_SUBTLE = BG_CARD_HOVER
TEXT_WHITE = TEXT_PRIMARY
TEXT_GOLD = TEXT_SURFACE
RED_WR = RED_DANGER
GREEN_WR = GREEN_SUCCESS
YELLOW_WR = YELLOW_WARNING
ALLY_BG = BG_DARK

# Aliases semanticos (nombres claros para los colores dorados)
ACCENT_GOLD = ACCENT_GOLD
GOLD_DARK = GOLD_DARK
AMBER_ACCENT = AMBER_ACCENT

__all__ = [
    "BG_DARK",
    "BG_PANEL",
    "BG_CARD",
    "BORDER_ACCENT",
    "BORDER_SUBTLE",
    "TEXT_WHITE",
    "TEXT_MUTED",
    "TEXT_MUTED_ALT",
    "TEXT_GOLD",
    "ACCENT_RED",
    "ACCENT_TEAL",
    "ACCENT_GOLD",
    "GOLD_DARK",
    "AMBER_ACCENT",
    "RED_WR",
    "GREEN_WR",
    "YELLOW_WARNING",
    "YELLOW_WR",
    "ALLY_BG",
    "ENEMY_BG",
    "HOVER_GLOW",
    "FONT_FAMILY",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TEXT_SUBTLE",
    "TEXT_LIGHT",
    "TEXT_SURFACE",
    "GREEN_SUCCESS",
    "RED_DANGER",
    "BG_CARD_HOVER",
    "BG_CARD_ELEVATED",
    "BG_BORDER",
    "BG_DARK_RED",
    "BG_DARK_RED2",
    "BG_DARK_YELLOW",
    "BG_DARK_BROWN",
    "BG_DARK_GREEN",
    "BG_DARK_PURPLE",
    "BG_DARK_TEAL",
    "BG_TABLE_HEADER",
    "BORDER_TABLE_ITEM",
    "CARD_DARK_BLUE",
    "CARD_DARKER_BLUE",
    "CARD_MID_BLUE2",
    "RED_DARK",
    "RED_DARK_CARD",
]
