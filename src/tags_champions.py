"""
Sistema de Tags Hiper-Específico para Campeones (Pilar 5).

Cada campeón se define por:
- damage_type:      AD | AP | HYBRID
- champion_class:   Tank | Fighter | Assassin | Mage | Marksman | Support
- sub_class:        Juggernaut | Diver | BurstMage | BattleMage | Artillery |
                    Enchanter | Catcher | Warden | Vanguard | Skirmisher
- cc_level:         0 (nada) a 5 (CC masivo/diversos tipos)
- support_subrole:  peel | engage | poke | sustain | roam | warden  (solo soportes)
- damage_profile:   burst | dps | poke | mixed
- early_power:      strong | weak | neutral
- scaling:          early | mid | late | hyper
- mobility:         0 (inmóvil) a 5 (hiper-móvil)
- boots_policy:     static | adaptive   ← CLAVE para itemización dinámica
- static_boots:     ID de la bota fija (si boots_policy=static)
- difficulty:       1 (fácil) a 3 (difícil)
"""
import json
import os
import sys

_TAGS_CACHE = None

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(_get_base_dir(), "data")
TAGS_PATH = os.path.join(DATA_DIR, "tags_campeones.json")

# ─── PLANTILLA POR DEFECTO ───────────────────────────────────────────
_DEFAULT_TAG = {
    "damage_type": "AD",
    "champion_class": "Fighter",
    "sub_class": "Diver",
    "cc_level": 1,
    "support_subrole": None,
    "damage_profile": "dps",
    "early_power": "neutral",
    "scaling": "mid",
    "mobility": 2,
    "boots_policy": "adaptive",
    "static_boots": None,
    "difficulty": 2
}

# ─── TAGS MANUALES HIPER-ESPECÍFICOS ─────────────────────────────────
# Solo los campeones que necesitan overrides. El resto usa _DEFAULT_TAG
# enriquecido con los tags de Riot.

MANUAL_TAGS = {
    # ── TOP LANERS ───────────────────────────────────────────────
    "Aatrox":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":3,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":3},
    "Camille":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"late",
                   "mobility":4,"boots_policy":"adaptive","difficulty":3},
    "Chogath":    {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"mixed","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"adaptive","difficulty":2},
    "Darius":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":1,"boots_policy":"adaptive","difficulty":1},
    "DrMundo":    {"damage_type":"AD","champion_class":"Tank","sub_class":"Juggernaut",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"adaptive","difficulty":1},
    "Fiora":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"neutral","scaling":"hyper",
                   "mobility":4,"boots_policy":"adaptive","difficulty":3},
    "Gangplank":  {"damage_type":"AD","champion_class":"Fighter","sub_class":"Specialist",
                   "cc_level":2,"damage_profile":"burst","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"static","static_boots":"3009","difficulty":3},
    "Garen":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":1,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3009","difficulty":1},
    "Gnar":       {"damage_type":"AD","champion_class":"Fighter","sub_class":"Vanguard",
                   "cc_level":3,"damage_profile":"mixed","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":3},
    "Gwen":       {"damage_type":"AP","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"adaptive","difficulty":2},
    "Illaoi":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":1,"boots_policy":"adaptive","difficulty":2},
    "Irelia":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"adaptive","difficulty":3},
    "Jax":        {"damage_type":"HYBRID","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"adaptive","difficulty":2},
    "Jayce":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Artillery",
                   "cc_level":1,"damage_profile":"poke","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Kayle":      {"damage_type":"AP","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Kennen":     {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Kled":       {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":2},
    "KSante":     {"damage_type":"AD","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":4,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":3,"boots_policy":"adaptive","difficulty":3},
    "Malphite":   {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":1},
    "Mordekaiser":{"damage_type":"AP","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Nasus":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"adaptive","difficulty":1},
    "Olaf":       {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"early",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Ornn":       {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":5,"damage_profile":"mixed","early_power":"neutral","scaling":"late",
                   "mobility":2,"boots_policy":"adaptive","difficulty":2},
    "Pantheon":   {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Quinn":      {"damage_type":"AD","champion_class":"Marksman","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Renekton":   {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Riven":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"adaptive","difficulty":3},
    "Rumble":     {"damage_type":"AP","champion_class":"Fighter","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Sett":       {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":1},
    "Shen":       {"damage_type":"AP","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":3,"damage_profile":"mixed","early_power":"neutral","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":2},
    "Singed":     {"damage_type":"AP","champion_class":"Tank","sub_class":"Specialist",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"late",
                   "mobility":4,"boots_policy":"static","static_boots":"3009","difficulty":2},
    "Sion":       {"damage_type":"AD","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"mixed","early_power":"neutral","scaling":"hyper",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Teemo":      {"damage_type":"AP","champion_class":"Mage","sub_class":"Specialist",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Trundle":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Tryndamere": {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"hyper",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Urgot":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"adaptive","difficulty":2},
    "Volibear":   {"damage_type":"AP","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":3,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":1},
    "Warwick":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Wukong":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Yasuo":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":3,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":5,"boots_policy":"static","static_boots":"3006","difficulty":3},
    "Yone":       {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":3,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Yorick":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"adaptive","difficulty":2},

    # ── JUNGLE ────────────────────────────────────────────────────
    "Amumu":      {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":5,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":1},
    "Belveth":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"neutral","scaling":"hyper",
                   "mobility":5,"boots_policy":"adaptive","difficulty":2},
    "Briar":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":1},
    "Diana":      {"damage_type":"AP","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Ekko":       {"damage_type":"AP","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":2,"damage_profile":"burst","early_power":"neutral","scaling":"late",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Elise":      {"damage_type":"AP","champion_class":"Mage","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Evelynn":    {"damage_type":"AP","champion_class":"Assassin","sub_class":"BurstMage",
                   "cc_level":2,"damage_profile":"burst","early_power":"weak","scaling":"late",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Fiddlesticks":{"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Graves":     {"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":2},
    "Hecarim":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":5,"boots_policy":"adaptive","difficulty":1},
    "Ivern":      {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"peel","damage_profile":"poke",
                   "early_power":"neutral","scaling":"mid","mobility":2,
                   "boots_policy":"static","static_boots":"3158","difficulty":2},
    "JarvanIV":   {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":4,"boots_policy":"adaptive","difficulty":1},
    "Karthus":    {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Kayn":       {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"weak","scaling":"late",
                   "mobility":5,"boots_policy":"adaptive","difficulty":2},
    "Khazix":     {"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":2},
    "Kindred":    {"damage_type":"AD","champion_class":"Marksman","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"hyper",
                   "mobility":3,"boots_policy":"adaptive","difficulty":2},
    "LeeSin":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":5,"boots_policy":"adaptive","difficulty":3},
    "Lillia":     {"damage_type":"AP","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":3,"damage_profile":"dps","early_power":"weak","scaling":"late",
                   "mobility":5,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "MasterYi":   {"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":0,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Nidalee":    {"damage_type":"AP","champion_class":"Assassin","sub_class":"Artillery",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":5,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Nocturne":   {"damage_type":"AD","champion_class":"Assassin","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":1},
    "Nunu":       {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":1},
    "Rammus":     {"damage_type":"AP","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":3,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":5,"boots_policy":"adaptive","difficulty":1},
    "RekSai":     {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":3,"boots_policy":"adaptive","difficulty":2},
    "Rengar":     {"damage_type":"AD","champion_class":"Assassin","sub_class":"Diver",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":3},
    "Sejuani":    {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Shaco":      {"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":3},
    "Shyvana":    {"damage_type":"HYBRID","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"late",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Skarner":    {"damage_type":"AD","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":1},
    "Taliyah":    {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Talon":      {"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"adaptive","difficulty":1},
    "Udyr":       {"damage_type":"AP","champion_class":"Fighter","sub_class":"Juggernaut",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3009","difficulty":1},
    "Vi":         {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Viego":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":2},
    "XinZhao":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"early",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Zac":        {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3047","difficulty":2},

    # ── MID LANERS ────────────────────────────────────────────────
    "Ahri":       {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Akali":      {"damage_type":"AP","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Akshan":     {"damage_type":"AD","champion_class":"Marksman","sub_class":"Assassin",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":3},
    "Anivia":     {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":4,"damage_profile":"dps","early_power":"weak","scaling":"late",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Annie":      {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":4,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "AurelionSol":{"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Azir":       {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":3,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Cassiopeia": {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"hyper",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Corki":      {"damage_type":"AD","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":1,"damage_profile":"poke","early_power":"weak","scaling":"late",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Fizz":       {"damage_type":"AP","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"burst","early_power":"weak","scaling":"mid",
                   "mobility":5,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Galio":      {"damage_type":"AP","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":4,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Hwei":       {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":3,"damage_profile":"poke","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Kassadin":   {"damage_type":"AP","champion_class":"Assassin","sub_class":"BattleMage",
                   "cc_level":1,"damage_profile":"burst","early_power":"weak","scaling":"hyper",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Katarina":   {"damage_type":"AP","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":0,"damage_profile":"burst","early_power":"weak","scaling":"mid",
                   "mobility":5,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Leblanc":    {"damage_type":"AP","champion_class":"Assassin","sub_class":"BurstMage",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Lissandra":  {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":4,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Lux":        {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Malzahar":   {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":4,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Naafiri":    {"damage_type":"AD","champion_class":"Assassin","sub_class":"Diver",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":1},
    "Neeko":      {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":4,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Orianna":    {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":3,"damage_profile":"mixed","early_power":"neutral","scaling":"late",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Qiyana":     {"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":3},
    "Ryze":       {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":3},
    "Swain":      {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":3,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Sylas":      {"damage_type":"AP","champion_class":"Mage","sub_class":"Skirmisher",
                   "cc_level":2,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Syndra":     {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":3,"damage_profile":"burst","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Tristana":   {"damage_type":"AD","champion_class":"Marksman","sub_class":"Assassin",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "TwistedFate":{"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"burst","early_power":"weak","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Veigar":     {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":3,"damage_profile":"burst","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Vex":        {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":2,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Viktor":     {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Vladimir":   {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":1,"damage_profile":"burst","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Xerath":     {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"poke","early_power":"strong","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Zed":        {"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":3},
    "Ziggs":      {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"poke","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":1},
    "Zoe":        {"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":2},

    # ── ADC (BOTTOM) ──────────────────────────────────────────────
    "Aphelios":   {"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"static","static_boots":"3006","difficulty":3},
    "Ashe":       {"damage_type":"AD","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":3,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":1,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Caitlyn":    {"damage_type":"AD","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":2,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Draven":     {"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist",
                   "cc_level":1,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":3},
    "Ezreal":     {"damage_type":"HYBRID","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":1,"damage_profile":"poke","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Jhin":       {"damage_type":"AD","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3009","difficulty":2},
    "Jinx":       {"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist",
                   "cc_level":2,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Kaisa":      {"damage_type":"HYBRID","champion_class":"Marksman","sub_class":"Assassin",
                   "cc_level":1,"damage_profile":"mixed","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Kalista":    {"damage_type":"AD","champion_class":"Marksman","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"mid",
                   "mobility":5,"boots_policy":"static","static_boots":"3006","difficulty":3},
    "KogMaw":     {"damage_type":"HYBRID","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":1,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Lucian":     {"damage_type":"AD","champion_class":"Marksman","sub_class":"Skirmisher",
                   "cc_level":0,"damage_profile":"burst","early_power":"strong","scaling":"early",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "MissFortune":{"damage_type":"AD","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Nilah":      {"damage_type":"AD","champion_class":"Fighter","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Samira":     {"damage_type":"AD","champion_class":"Marksman","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"strong","scaling":"late",
                   "mobility":4,"boots_policy":"static","static_boots":"3047","difficulty":2},
    "Senna":      {"damage_type":"AD","champion_class":"Marksman","sub_class":"Enchanter",
                   "cc_level":2,"damage_profile":"mixed","early_power":"weak","scaling":"hyper",
                   "mobility":2,"boots_policy":"static","static_boots":"3009","difficulty":2},
    "Sivir":      {"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist",
                   "cc_level":0,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Smolder":    {"damage_type":"AD","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Twitch":     {"damage_type":"AD","champion_class":"Marksman","sub_class":"Assassin",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":3,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Varus":      {"damage_type":"HYBRID","champion_class":"Marksman","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"poke","early_power":"strong","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3006","difficulty":1},
    "Vayne":      {"damage_type":"AD","champion_class":"Marksman","sub_class":"Assassin",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":4,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Xayah":      {"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"late",
                   "mobility":2,"boots_policy":"static","static_boots":"3006","difficulty":2},
    "Zeri":       {"damage_type":"AD","champion_class":"Marksman","sub_class":"Skirmisher",
                   "cc_level":1,"damage_profile":"dps","early_power":"weak","scaling":"hyper",
                   "mobility":5,"boots_policy":"static","static_boots":"3006","difficulty":3},

    # ── SUPPORT (UTILITY) ─────────────────────────────────────────
    "Alistar":    {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"support_subrole":"engage","damage_profile":"burst",
                   "early_power":"neutral","scaling":"mid","mobility":3,
                   "boots_policy":"adaptive","difficulty":1},
    "Bard":       {"damage_type":"AP","champion_class":"Support","sub_class":"Catcher",
                   "cc_level":3,"support_subrole":"roam","damage_profile":"poke",
                   "early_power":"strong","scaling":"hyper","mobility":5,
                   "boots_policy":"static","static_boots":"3009","difficulty":3},
    "Blitzcrank": {"damage_type":"AP","champion_class":"Tank","sub_class":"Catcher",
                   "cc_level":3,"support_subrole":"engage","damage_profile":"burst",
                   "early_power":"strong","scaling":"mid","mobility":3,
                   "boots_policy":"adaptive","difficulty":1},
    "Brand":      {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"support_subrole":"poke","damage_profile":"dps",
                   "early_power":"strong","scaling":"mid","mobility":1,
                   "boots_policy":"static","static_boots":"3020","difficulty":1},
    "Braum":      {"damage_type":"AP","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":4,"support_subrole":"peel","damage_profile":"mixed",
                   "early_power":"neutral","scaling":"mid","mobility":2,
                   "boots_policy":"adaptive","difficulty":1},
    "Janna":      {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":4,"support_subrole":"peel","damage_profile":"poke",
                   "early_power":"neutral","scaling":"late","mobility":4,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Karma":      {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":2,"support_subrole":"poke","damage_profile":"poke",
                   "early_power":"strong","scaling":"mid","mobility":3,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Leona":      {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":5,"support_subrole":"engage","damage_profile":"burst",
                   "early_power":"strong","scaling":"mid","mobility":3,
                   "boots_policy":"adaptive","difficulty":1},
    "Lulu":       {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"peel","damage_profile":"poke",
                   "early_power":"strong","scaling":"late","mobility":2,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Milio":      {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"peel","damage_profile":"poke",
                   "early_power":"neutral","scaling":"late","mobility":2,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Morgana":    {"damage_type":"AP","champion_class":"Mage","sub_class":"Catcher",
                   "cc_level":4,"support_subrole":"peel","damage_profile":"burst",
                   "early_power":"neutral","scaling":"mid","mobility":1,
                   "boots_policy":"static","static_boots":"3020","difficulty":1},
    "Nami":       {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"sustain","damage_profile":"poke",
                   "early_power":"strong","scaling":"mid","mobility":2,
                   "boots_policy":"static","static_boots":"3158","difficulty":2},
    "Nautilus":   {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":5,"support_subrole":"engage","damage_profile":"burst",
                   "early_power":"strong","scaling":"mid","mobility":3,
                   "boots_policy":"adaptive","difficulty":1},
    "Pyke":       {"damage_type":"AD","champion_class":"Assassin","sub_class":"Catcher",
                   "cc_level":3,"support_subrole":"engage","damage_profile":"burst",
                   "early_power":"strong","scaling":"early","mobility":5,
                   "boots_policy":"static","static_boots":"3158","difficulty":2},
    "Rakan":      {"damage_type":"AP","champion_class":"Support","sub_class":"Catcher",
                   "cc_level":4,"support_subrole":"engage","damage_profile":"mixed",
                   "early_power":"neutral","scaling":"mid","mobility":5,
                   "boots_policy":"static","static_boots":"3158","difficulty":2},
    "Renata":     {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"peel","damage_profile":"poke",
                   "early_power":"neutral","scaling":"late","mobility":1,
                   "boots_policy":"static","static_boots":"3158","difficulty":2},
    "Rell":       {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":5,"support_subrole":"engage","damage_profile":"burst",
                   "early_power":"strong","scaling":"mid","mobility":3,
                   "boots_policy":"adaptive","difficulty":2},
    "Seraphine":  {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"sustain","damage_profile":"poke",
                   "early_power":"neutral","scaling":"late","mobility":2,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Sona":       {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":2,"support_subrole":"sustain","damage_profile":"poke",
                   "early_power":"weak","scaling":"hyper","mobility":3,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Soraka":     {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":2,"support_subrole":"sustain","damage_profile":"poke",
                   "early_power":"strong","scaling":"mid","mobility":1,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "TahmKench":  {"damage_type":"AP","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":3,"support_subrole":"peel","damage_profile":"dps",
                   "early_power":"neutral","scaling":"late","mobility":3,
                   "boots_policy":"adaptive","difficulty":1},
    "Taric":      {"damage_type":"AP","champion_class":"Support","sub_class":"Warden",
                   "cc_level":2,"support_subrole":"peel","damage_profile":"mixed",
                   "early_power":"weak","scaling":"late","mobility":1,
                   "boots_policy":"static","static_boots":"3047","difficulty":2},
    "Thresh":     {"damage_type":"AP","champion_class":"Support","sub_class":"Catcher",
                   "cc_level":5,"support_subrole":"engage","damage_profile":"mixed",
                   "early_power":"strong","scaling":"late","mobility":2,
                   "boots_policy":"adaptive","difficulty":3},
    "Velkoz":     {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"support_subrole":"poke","damage_profile":"poke",
                   "early_power":"strong","scaling":"mid","mobility":1,
                   "boots_policy":"static","static_boots":"3020","difficulty":2},
    "Yuumi":      {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":1,"support_subrole":"sustain","damage_profile":"poke",
                   "early_power":"weak","scaling":"late","mobility":1,
                   "boots_policy":"static","static_boots":"3158","difficulty":1},
    "Zilean":     {"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter",
                   "cc_level":3,"support_subrole":"peel","damage_profile":"poke",
                   "early_power":"neutral","scaling":"late","mobility":3,
                   "boots_policy":"static","static_boots":"3158","difficulty":2},
    "Zyra":       {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"support_subrole":"poke","damage_profile":"dps",
                   "early_power":"strong","scaling":"mid","mobility":1,
                   "boots_policy":"static","static_boots":"3020","difficulty":1},

    # ── CAMPEONES NUEVOS / OMITIDOS ───────────────────────────────
    "Ambessa":    {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":4,"boots_policy":"adaptive","difficulty":2},
    "Aurora":     {"damage_type":"AP","champion_class":"Mage","sub_class":"BattleMage",
                   "cc_level":2,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":4,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Gragas":     {"damage_type":"AP","champion_class":"Fighter","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"burst","early_power":"neutral","scaling":"mid",
                   "mobility":3,"boots_policy":"static","static_boots":"3158","difficulty":2},
    "Heimerdinger":{"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"poke","early_power":"strong","scaling":"mid",
                   "mobility":1,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "Maokai":     {"damage_type":"AP","champion_class":"Tank","sub_class":"Vanguard",
                   "cc_level":4,"damage_profile":"dps","early_power":"neutral","scaling":"mid",
                   "mobility":2,"boots_policy":"adaptive","difficulty":1},
    "Mel":        {"damage_type":"AP","champion_class":"Mage","sub_class":"Artillery",
                   "cc_level":2,"damage_profile":"burst","early_power":"strong","scaling":"late",
                   "mobility":2,"boots_policy":"static","static_boots":"3020","difficulty":2},
    "MonkeyKing": {"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver",
                   "cc_level":3,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
    "Poppy":      {"damage_type":"AD","champion_class":"Tank","sub_class":"Warden",
                   "cc_level":4,"damage_profile":"burst","early_power":"strong","scaling":"mid",
                   "mobility":3,"boots_policy":"adaptive","difficulty":1},
}


def cargar_tags():
    """Carga los tags desde el JSON. Si no existe, lo genera desde los datos de Riot."""
    global _TAGS_CACHE
    if _TAGS_CACHE is not None:
        return _TAGS_CACHE
    if os.path.exists(TAGS_PATH):
        with open(TAGS_PATH, "r", encoding="utf-8") as f:
            _TAGS_CACHE = json.load(f)
        return _TAGS_CACHE
    _TAGS_CACHE = _generar_tags()
    return _TAGS_CACHE


def _generar_tags():
    """Genera el diccionario de tags combinando datos de Riot con overrides manuales."""
    # Intentar cargar datos base de Riot
    ruta_champs = os.path.join(DATA_DIR, "champion_data.json")
    riot_data = {}
    if os.path.exists(ruta_champs):
        with open(ruta_champs, "r", encoding="utf-8") as f:
            riot_data = json.load(f)

    tags_final = {}

    for nombre, data_riot in riot_data.items():
        riot_tags = data_riot.get("tags", [])

        # Empezar con la plantilla default
        tag = dict(_DEFAULT_TAG)

        # Inferir tipo de daño desde tags de Riot
        if "Mage" in riot_tags or "Support" in riot_tags:
            tag["damage_type"] = "AP"
        elif "Marksman" in riot_tags:
            tag["damage_type"] = "AD"
        elif "Assassin" in riot_tags:
            tag["damage_type"] = "AD"
        elif "Fighter" in riot_tags:
            tag["damage_type"] = "AD"
        elif "Tank" in riot_tags:
            tag["damage_type"] = "AD"

        # Inferir clase
        if "Mage" in riot_tags:
            tag["champion_class"] = "Mage"
        elif "Support" in riot_tags:
            tag["champion_class"] = "Support"
        elif "Marksman" in riot_tags:
            tag["champion_class"] = "Marksman"
        elif "Assassin" in riot_tags:
            tag["champion_class"] = "Assassin"
        elif "Tank" in riot_tags:
            tag["champion_class"] = "Tank"
        elif "Fighter" in riot_tags:
            tag["champion_class"] = "Fighter"

        # Inferir subclase desde tags de Riot
        if "Mage" in riot_tags:
            tag["sub_class"] = "BurstMage"
        elif "Support" in riot_tags:
            tag["sub_class"] = "Enchanter"
        elif "Marksman" in riot_tags:
            tag["sub_class"] = "Specialist"
        elif "Assassin" in riot_tags:
            tag["sub_class"] = "Skirmisher"
        elif "Tank" in riot_tags:
            tag["sub_class"] = "Vanguard"
        elif "Fighter" in riot_tags:
            tag["sub_class"] = "Diver"

        # Inferir política de botas
        if "Mage" in riot_tags:
            tag["boots_policy"] = "static"
            tag["static_boots"] = "3020"  # Sorcerer
        elif "Marksman" in riot_tags:
            tag["boots_policy"] = "static"
            tag["static_boots"] = "3006"  # Berserker
        else:
            tag["boots_policy"] = "adaptive"

        # Aplicar overrides manuales (prioridad máxima)
        if nombre in MANUAL_TAGS:
            override = MANUAL_TAGS[nombre]
            if override:  # si es diccionario vacío, saltar
                tag.update(override)

        tags_final[nombre] = tag

    # ── Añadir aliases de campeones.json para cubrir variantes de nombre ──
    ruta_campeones = os.path.join(_get_base_dir(), "assets", "campeones.json")
    if os.path.exists(ruta_campeones):
        with open(ruta_campeones, "r", encoding="utf-8") as f:
            campeones = json.load(f)
        for cid, cname in campeones.items():
            if cname not in tags_final:
                # Buscar en riot_data por nombre similar
                for riot_name, riot_info in riot_data.items():
                    if riot_name.lower() == cname.lower():
                        tag = dict(_DEFAULT_TAG)
                        riot_tags = riot_info.get("tags", [])
                        # Aplicar misma inferencia que arriba (simplificada)
                        if "Mage" in riot_tags: tag.update({"damage_type":"AP","champion_class":"Mage","sub_class":"BurstMage","boots_policy":"static","static_boots":"3020"})
                        elif "Support" in riot_tags: tag.update({"damage_type":"AP","champion_class":"Support","sub_class":"Enchanter","boots_policy":"static","static_boots":"3158"})
                        elif "Marksman" in riot_tags: tag.update({"damage_type":"AD","champion_class":"Marksman","sub_class":"Specialist","boots_policy":"static","static_boots":"3006"})
                        elif "Assassin" in riot_tags: tag.update({"damage_type":"AD","champion_class":"Assassin","sub_class":"Skirmisher"})
                        elif "Tank" in riot_tags: tag.update({"damage_type":"AD","champion_class":"Tank","sub_class":"Vanguard"})
                        elif "Fighter" in riot_tags: tag.update({"damage_type":"AD","champion_class":"Fighter","sub_class":"Diver"})
                        if cname in MANUAL_TAGS and MANUAL_TAGS[cname]:
                            tag.update(MANUAL_TAGS[cname])
                        tags_final[cname] = tag
                        break

    # Guardar para futuras ejecuciones
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(tags_final, f, ensure_ascii=False, indent=2)

    return tags_final


def obtener_tag(campeon: str) -> dict:
    """Devuelve el diccionario de tags para un campeón. Si no existe, usa default."""
    tags = cargar_tags()
    # Normalizar nombres
    nombre = campeon.replace(" ", "").replace("'", "")
    if nombre in tags:
        return tags[nombre]
    return dict(_DEFAULT_TAG)


def obtener_dano(campeon: str) -> str:
    """AD, AP o HYBRID"""
    return obtener_tag(campeon).get("damage_type", "AD")


def es_tanque(campeon: str) -> bool:
    return obtener_tag(campeon).get("champion_class") == "Tank"


def es_mago(campeon: str) -> bool:
    return obtener_tag(campeon).get("champion_class") == "Mage"


def es_soporte(campeon: str) -> bool:
    return obtener_tag(campeon).get("champion_class") == "Support"


def es_tirador(campeon: str) -> bool:
    return obtener_tag(campeon).get("champion_class") == "Marksman"


def es_asesino(campeon: str) -> bool:
    return obtener_tag(campeon).get("champion_class") == "Assassin"


def es_luchador(campeon: str) -> bool:
    return obtener_tag(campeon).get("champion_class") == "Fighter"


def obtener_nivel_cc(campeon: str) -> int:
    return obtener_tag(campeon).get("cc_level", 0)


def obtener_subrol_soporte(campeon: str) -> str | None:
    return obtener_tag(campeon).get("support_subrole")


def es_botas_estaticas(campeon: str) -> bool:
    """True si el campeón SIEMPRE usa las mismas botas (core fijo)."""
    return obtener_tag(campeon).get("boots_policy") == "static"


def obtener_bota_estatica(campeon: str) -> str | None:
    """Devuelve el ID de la bota fija, o None si es adaptativo."""
    t = obtener_tag(campeon)
    if t.get("boots_policy") == "static":
        return t.get("static_boots")
    return None


def obtener_escalado(campeon: str) -> str:
    """early, mid, late, hyper"""
    return obtener_tag(campeon).get("scaling", "mid")


def obtener_poder_temprano(campeon: str) -> str:
    """strong, weak, neutral"""
    return obtener_tag(campeon).get("early_power", "neutral")


def get_rol_tags(campeon: str) -> dict:
    """Alias corto para obtener_tag()."""
    return obtener_tag(campeon)
