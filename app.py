import json
import tkinter as tk
from tkinter import ttk, messagebox
import pickle
import os
import requests
from io import BytesIO
from PIL import Image, ImageTk
import numpy as np
import joblib

from src.db_manager import DATA_DIR
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, cargar_hechizos, obtener_version_actual
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol, 
                              obtener_top_runas, obtener_top_hechizos, obtener_mejores_baneos, recomendar_picks_vivo, 
                              calcular_winrate_5v5, analizar_composicion)
from src.lcu_api import LCUConnector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ITEMS_DIR = os.path.join(ASSETS_DIR, "items")
RUNAS_DIR = os.path.join(ASSETS_DIR, "runas")
CHAMPS_DIR = os.path.join(ASSETS_DIR, "champs")
SPELLS_DIR = os.path.join(ASSETS_DIR, "spells")
os.makedirs(ITEMS_DIR, exist_ok=True)
os.makedirs(RUNAS_DIR, exist_ok=True)
os.makedirs(CHAMPS_DIR, exist_ok=True)
os.makedirs(SPELLS_DIR, exist_ok=True)

modelo_1v1 = joblib.load("data/modelo_1v1.pkl") if os.path.exists("data/modelo_1v1.pkl") else {}
ITEMS_DICT = cargar_objetos()
RUNAS_DICT = cargar_runas()
SPELLS_DICT = cargar_hechizos()
MAPEO_IDS_CAMPEONES = cargar_mapeo_ids()

# --- TEMA HEXTECH DARK (Alto Contraste) ---
BG_DARK = "#010a13"      
BG_PANEL = "#0a1428"     
BORDER_GOLD = "#c89b3c"  
TEXT_WHITE = "#ffffff"   
TEXT_GOLD = "#f0e6d2"    
ACCENT_BLUE = "#0ac8b9"  
RED_WR = "#ff4e50"
GREEN_WR = "#00e676"
YELLOW_WR = "#f9a826"
ALLY_BG = "#0b1b3d"      
ENEMY_BG = "#3d0b13"     

STAT_SHARDS = {
    "5008": ("Fuerza Adapt.", "#e74c3c"),
    "5005": ("Vel. Ataque", "#f1c40f"),
    "5007": ("Acel. Hab.", "#9b59b6"),
    "5009": ("Vel. Mov.", "#1abc9c"),
    "5001": ("Prog. Vida", "#2ecc71"),
    "5010": ("Vida Plana", "#27ae60"),
    "5011": ("Vida", "#16a085"),
    "5013": ("Tenacidad", "#34495e"),
    "5002": ("Armadura", "#e67e22"),
    "5003": ("Res. Mágica", "#3498db"),
}

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tw or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tw = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=self.text, justify='left', bg=BG_PANEL, fg=TEXT_WHITE, 
                       relief='solid', borderwidth=1, highlightbackground=BORDER_GOLD,
                       wraplength=250, font=("Helvetica", 9), padx=8, pady=8)
        lbl.pack()

    def hide(self, event=None):
        if self.tw: self.tw.destroy(); self.tw = None

class LoLRecommenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LoL Esports Analytics Pro - V5.1 (Bugfixes Completos)")
        self.root.geometry("1200x900")
        self.root.configure(bg=BG_DARK)
        
        self.root.option_add('*TCombobox*Listbox.background', BG_PANEL)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT_WHITE)
        self.root.option_add('*TCombobox*Listbox.selectBackground', BORDER_GOLD)
        self.root.option_add('*TCombobox*Listbox.selectForeground', BG_DARK)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=TEXT_GOLD, font=("Helvetica", 10, "bold"), padding=[15, 5])
        style.map("TNotebook.Tab", background=[("selected", BORDER_GOLD)], foreground=[("selected", BG_DARK)])
        style.configure("Treeview", background=BG_PANEL, foreground=TEXT_WHITE, fieldbackground=BG_PANEL, borderwidth=0)
        style.configure("Treeview.Heading", background=BORDER_GOLD, foreground=BG_DARK, font=("Helvetica", 10, "bold"))
        style.configure("TCombobox", fieldbackground=BG_PANEL, background=BG_PANEL, foreground=TEXT_WHITE, arrowcolor=TEXT_GOLD)
        style.map('TCombobox', fieldbackground=[('readonly', BG_PANEL)], selectbackground=[('readonly', BORDER_GOLD)], selectforeground=[('readonly', BG_DARK)])

        self.champs_dict = cargar_campeones()
        self.nombres_campeones_global = sorted(list(set([data["nombre"] for data in self.champs_dict.values()])))
        self.version_juego = obtener_version_actual()
        self.roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        self.builds_actuales = {}
        self.imagenes_cacheadas = []
        
        self.lcu = LCUConnector()
        self.radar_activo = False
        self.ultimo_rol_detectado = None
        self.last_aliados = []
        self.last_enemigos = []
        self.last_my_champ = None

        self.crear_interfaz()

    def crear_panel(self, parent, text="", pad=10):
        fr = tk.Frame(parent, bg=BG_PANEL, highlightbackground=BORDER_GOLD, highlightthickness=1)
        if text:
            tk.Label(fr, text=text.upper(), bg=BG_PANEL, fg=ACCENT_BLUE, font=("Helvetica", 9, "bold")).pack(anchor="w", padx=pad, pady=(pad, 0))
        return fr

    def crear_interfaz(self):
        header = tk.Frame(self.root, bg=BG_DARK)
        header.pack(fill="x", pady=10)
        tk.Label(header, text="LOL ESPORTS ANALYTICS", font=("Impact", 24), bg=BG_DARK, fg=BORDER_GOLD).pack()

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        tab_vivo = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab_vivo, text="📡 RADAR EN VIVO")
        self.armar_tab_vivo(tab_vivo)

        tab_counters = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab_counters, text="📊 META & BUILDS")
        self.armar_tab_counters(tab_counters)

        tab_ia = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(tab_ia, text="🤖 ANÁLISIS 1v1")
        self.armar_tab_ia(tab_ia)

    def descargar_imagen(self, id_elemento, tipo):
        carpetas = {"runa": RUNAS_DIR, "champ": CHAMPS_DIR, "item": ITEMS_DIR, "spell": SPELLS_DIR}
        carpeta = carpetas.get(tipo)
        ruta_local = os.path.join(carpeta, f"{id_elemento}.png")
        if os.path.exists(ruta_local): return ruta_local
        try:
            if tipo == "runa": url = f"https://ddragon.leagueoflegends.com/cdn/img/{RUNAS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "spell": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/spell/{SPELLS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "champ": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/champion/{id_elemento}.png"
            else: url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/item/{id_elemento}.png"
            
            resp = requests.get(url)
            resp.raise_for_status()
            Image.open(BytesIO(resp.content)).save(ruta_local)
            return ruta_local
        except: return None

    def renderizar_icono(self, id_elemento, tipo, frame_padre, fila, columna, info_extra="", size=40):
        if tipo == "champ" and id_elemento == "Wukong": id_elemento = "MonkeyKing"
        ruta = self.descargar_imagen(id_elemento, tipo)
        if not ruta: return
        
        imagen = Image.open(ruta).resize((size, size), Image.Resampling.LANCZOS)
        foto = ImageTk.PhotoImage(imagen)
        self.imagenes_cacheadas.append(foto)
        
        info_texto = info_extra
        if tipo == "runa": info_texto = f"{RUNAS_DICT.get(str(id_elemento), {}).get('nombre', 'Runa')}\n{RUNAS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"
        elif tipo == "item": info_texto = f"{ITEMS_DICT.get(str(id_elemento), {}).get('nombre', 'Objeto')}\n{ITEMS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"
        elif tipo == "spell": info_texto = f"{SPELLS_DICT.get(str(id_elemento), {}).get('nombre', 'Hechizo')}\n{SPELLS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"

        border = 0 if tipo == "runa" else 1
        lbl_img = tk.Label(frame_padre, image=foto, bg=frame_padre.cget("bg"), bd=border, relief="solid", highlightbackground=BORDER_GOLD)
        lbl_img.grid(row=fila, column=columna, padx=4, pady=4)
        if info_texto: ToolTip(lbl_img, info_texto)

    def renderizar_setup_completo(self, ids_runas, ids_spells, frame_padre, is_centered=False):
        for w in frame_padre.winfo_children():
            w.destroy()

        root = tk.Frame(frame_padre, bg=BG_PANEL)
        if is_centered:
            root.pack(expand=True, fill="both", padx=10, pady=10)
        else:
            root.pack(fill="both", expand=True, padx=10, pady=10)

        main_wrap = tk.Frame(root, bg=BG_PANEL)
        main_wrap.pack(anchor="center")

        # ================= FILA 1 =================
        fila_1 = tk.Frame(main_wrap, bg=BG_PANEL)
        fila_1.pack(fill="x", pady=(0, 15))

        panel_runas = self.crear_panel(fila_1, "Runas")
        panel_runas.pack(side="left", fill="both", expand=True, padx=10, ipadx=10, ipady=10)

        panel_spells = self.crear_panel(fila_1, "Hechizos")
        panel_spells.pack(side="left", fill="both", expand=True, padx=10, ipadx=10, ipady=10)

        # ================= FILA 2 =================
        fila_2 = tk.Frame(main_wrap, bg=BG_PANEL)
        fila_2.pack(fill="x")

        panel_start = self.crear_panel(fila_2, "Start / Early Game")
        panel_start.pack(side="left", fill="both", expand=True, padx=10, ipadx=10, ipady=10)

        panel_core = self.crear_panel(fila_2, "Core Build")
        panel_core.pack(side="left", fill="both", expand=True, padx=10, ipadx=10, ipady=10)

        # =========================================================
        # ====================== RUNAS ============================
        # =========================================================
        contenido_runas = tk.Frame(panel_runas, bg=BG_PANEL)
        contenido_runas.pack(padx=10, pady=10)

        col_main = tk.Frame(contenido_runas, bg=BG_PANEL)
        col_main.pack(side="left", padx=15, anchor="n")

        col_sec = tk.Frame(contenido_runas, bg=BG_PANEL)
        col_sec.pack(side="left", padx=15, anchor="n")

        # Rama primaria
        tk.Label(
            col_main,
            text="PRIMARIA",
            bg=BG_PANEL,
            fg=BORDER_GOLD,
            font=("Helvetica", 9, "bold")
        ).pack(pady=(0, 8))

        fr_main_icons = tk.Frame(col_main, bg=BG_PANEL)
        fr_main_icons.pack()

        if len(ids_runas) > 0:
            self.renderizar_icono(ids_runas[0], "runa", fr_main_icons, 0, 0, size=35)
        if len(ids_runas) > 1:
            self.renderizar_icono(ids_runas[1], "runa", fr_main_icons, 1, 0, size=55)
        if len(ids_runas) > 2:
            self.renderizar_icono(ids_runas[2], "runa", fr_main_icons, 2, 0, size=35)
        if len(ids_runas) > 3:
            self.renderizar_icono(ids_runas[3], "runa", fr_main_icons, 3, 0, size=35)
        if len(ids_runas) > 4:
            self.renderizar_icono(ids_runas[4], "runa", fr_main_icons, 4, 0, size=35)

        # Rama secundaria
        tk.Label(
            col_sec,
            text="SECUNDARIA",
            bg=BG_PANEL,
            fg=BORDER_GOLD,
            font=("Helvetica", 9, "bold")
        ).pack(pady=(0, 8))

        fr_sec_icons = tk.Frame(col_sec, bg=BG_PANEL)
        fr_sec_icons.pack()

        if len(ids_runas) > 5:
            self.renderizar_icono(ids_runas[5], "runa", fr_sec_icons, 0, 0, size=30)
        if len(ids_runas) > 6:
            self.renderizar_icono(ids_runas[6], "runa", fr_sec_icons, 1, 0, size=35)
        if len(ids_runas) > 7:
            self.renderizar_icono(ids_runas[7], "runa", fr_sec_icons, 2, 0, size=35)

        # Shards: YA vienen en orden correcto desde obtener_top_runas:
        # [ofensivo, flex, defensivo]
        tk.Label(
            panel_runas,
            text="SHARDS / MINI STATS",
            bg=BG_PANEL,
            fg=ACCENT_BLUE,
            font=("Helvetica", 9, "bold")
        ).pack(pady=(5, 5))

        fr_shards = tk.Frame(panel_runas, bg=BG_PANEL)
        fr_shards.pack(pady=(0, 10))

        shards_recibidos = [str(i) for i in ids_runas[8:11]] if len(ids_runas) >= 11 else ["5008", "5008", "5011"]

        for stat_id in shards_recibidos:
            texto, color = STAT_SHARDS.get(stat_id, (f"Shard {stat_id}", "#ffffff"))
            lbl = tk.Label(
                fr_shards,
                text=texto,
                bg=BG_DARK,
                fg=TEXT_WHITE,
                font=("Helvetica", 8, "bold"),
                width=16,
                pady=4,
                highlightbackground=color,
                highlightthickness=1
            )
            lbl.pack(side="left", padx=6)

        # =========================================================
        # ===================== HECHIZOS ==========================
        # =========================================================
        cont_spells = tk.Frame(panel_spells, bg=BG_PANEL)
        cont_spells.pack(expand=True, pady=20)

        tk.Label(
            cont_spells,
            text="SUMMONER SPELLS",
            bg=BG_PANEL,
            fg=BORDER_GOLD,
            font=("Helvetica", 9, "bold")
        ).pack(pady=(0, 10))

        fr_spells = tk.Frame(cont_spells, bg=BG_PANEL)
        fr_spells.pack()

        for idx, sp in enumerate(ids_spells):
            self.renderizar_icono(str(sp), "spell", fr_spells, idx, 0, size=48)

        # =========================================================
        # ======================= START ===========================
        # =========================================================
        cont_start = tk.Frame(panel_start, bg=BG_PANEL)
        cont_start.pack(expand=True, pady=20)

        tk.Label(
            cont_start,
            text="OBJETOS INICIALES",
            bg=BG_PANEL,
            fg=BORDER_GOLD,
            font=("Helvetica", 9, "bold")
        ).pack(pady=(0, 10))

        tk.Label(
            cont_start,
            text="Los items iniciales se muestran en el panel superior de build.",
            bg=BG_PANEL,
            fg=TEXT_WHITE,
            font=("Helvetica", 9, "italic"),
            wraplength=220,
            justify="center"
        ).pack(pady=10)

        # =========================================================
        # ===================== CORE BUILD ========================
        # =========================================================
        cont_core = tk.Frame(panel_core, bg=BG_PANEL)
        cont_core.pack(expand=True, pady=20)

        tk.Label(
            cont_core,
            text="BUILD PRINCIPAL",
            bg=BG_PANEL,
            fg=BORDER_GOLD,
            font=("Helvetica", 9, "bold")
        ).pack(pady=(0, 10))

        tk.Label(
            cont_core,
            text="La build final se muestra en la sección superior de objetos.",
            bg=BG_PANEL,
            fg=TEXT_WHITE,
            font=("Helvetica", 9, "italic"),
            wraplength=220,
            justify="center"
        ).pack(pady=10)

    def mostrar_equipo_vivo(self, frame_padre, picks, is_ally=True):
        for w in frame_padre.winfo_children(): w.destroy()
        if not picks:
            tk.Label(frame_padre, text="Esperando...", bg=BG_PANEL, fg=TEXT_WHITE, font=("Helvetica", 10, "italic")).pack(pady=20)
            return
        bg_card = ALLY_BG if is_ally else ENEMY_BG
        for champ in picks:
            card = tk.Frame(frame_padre, bg=bg_card, bd=1, relief="solid", highlightbackground=BORDER_GOLD)
            card.pack(fill="x", pady=4, padx=10)
            self.renderizar_icono(champ, "champ", card, 0, 0, size=35)
            tk.Label(card, text=champ, bg=bg_card, fg=TEXT_WHITE, font=("Helvetica", 11, "bold")).grid(row=0, column=1, padx=10, sticky="w")

    # ================= RADAR EN VIVO =================
    def armar_tab_vivo(self, frame):
        top_bar = tk.Frame(frame, bg=BG_DARK)
        top_bar.pack(fill="x", pady=(0,10))
        self.btn_radar = tk.Button(top_bar, text="INICIAR RADAR LCU", bg=BG_PANEL, fg=TEXT_WHITE, font=("Helvetica", 10, "bold"), 
                                   relief="solid", bd=1, highlightbackground=BORDER_GOLD, command=self.toggle_radar)
        self.btn_radar.pack(side="left", padx=5)
        
        self.fr_wr_widget = tk.Frame(top_bar, bg=BG_DARK)
        self.fr_wr_widget.pack(side="right", padx=20)
        self.lbl_wr_numero = tk.Label(self.fr_wr_widget, text="--%", font=("Impact", 36), bg=BG_DARK, fg="gray")
        self.lbl_wr_numero.pack(side="left")
        self.lbl_wr_razon = tk.Label(self.fr_wr_widget, text="Esperando equipos...", font=("Helvetica", 10, "italic"), bg=BG_DARK, fg="gray")
        self.lbl_wr_razon.pack(side="left", padx=10, anchor="s", pady=10)

        draft_flow = tk.Frame(frame, bg=BG_DARK)
        draft_flow.pack(fill="both", expand=True)

        col_enemy = self.crear_panel(draft_flow, "Enemigos")
        col_enemy.pack(side="left", fill="both", expand=True, padx=5)
        self.lbl_enemy_stats = tk.Label(col_enemy, text="AD: --% | AP: --% | Tanks: 0", font=("Helvetica", 9, "bold"), bg=BG_PANEL, fg=RED_WR)
        self.lbl_enemy_stats.pack(pady=5)
        self.fr_enemigos_picks = tk.Frame(col_enemy, bg=BG_PANEL)
        self.fr_enemigos_picks.pack(fill="both", expand=True, pady=5)

        col_center = tk.Frame(draft_flow, bg=BG_DARK)
        col_center.pack(side="left", fill="both", expand=True, padx=5)
        self.lbl_rol_vivo = tk.Label(col_center, text="ASIGNACIÓN PENDIENTE", font=("Helvetica", 14, "bold"), bg=BG_DARK, fg=BORDER_GOLD)
        self.lbl_rol_vivo.pack(pady=5)
        
        self.panel_sugerencias = self.crear_panel(col_center, "Recomendaciones de Pick")
        self.panel_sugerencias.pack(fill="x", pady=5)
        self.fr_picks_icons = tk.Frame(self.panel_sugerencias, bg=BG_PANEL)
        self.fr_picks_icons.pack(pady=10)

        self.panel_runas_vivo = self.crear_panel(col_center, "Setup Recomendado (Runas & Hechizos)")
        self.panel_runas_vivo.pack(fill="both", expand=True, pady=5)
        self.fr_runas_icons_vivo = tk.Frame(self.panel_runas_vivo, bg=BG_PANEL)
        self.fr_runas_icons_vivo.pack(fill="both", expand=True, pady=5)

        col_ally = self.crear_panel(draft_flow, "Aliados")
        col_ally.pack(side="left", fill="both", expand=True, padx=5)
        self.lbl_ally_stats = tk.Label(col_ally, text="AD: --% | AP: --% | Tanks: 0", font=("Helvetica", 9, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE)
        self.lbl_ally_stats.pack(pady=5)
        self.fr_aliados_picks = tk.Frame(col_ally, bg=BG_PANEL)
        self.fr_aliados_picks.pack(fill="both", expand=True, pady=5)

    def toggle_radar(self):
        if not self.radar_activo:
            if self.lcu.conectar():
                self.radar_activo = True
                self.btn_radar.config(text="ENLAZADO AL CLIENTE", fg=GREEN_WR)
                self.actualizar_radar_loop()
            else: messagebox.showerror("Error", "Abre League of Legends primero.")
        else:
            self.radar_activo = False
            self.btn_radar.config(text="INICIAR RADAR LCU", fg=TEXT_WHITE)

    def procesar_nombre_champ(self, cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0": return "Wukong" if MAPEO_IDS_CAMPEONES.get(final_id) == "MonkeyKing" else MAPEO_IDS_CAMPEONES.get(final_id, "Desconocido")
        return None

    def actualizar_radar_loop(self):
        if not self.radar_activo: return
        draft = self.lcu.obtener_sesion_draft()
        if draft:
            rol_actual = self.lcu.obtener_mi_rol(draft)
            self.lbl_rol_vivo.config(text=f"LÍNEA ASIGNADA: {rol_actual}")

            picks_al, picks_en = [], []
            mi_campeon = None
            mi_celda = draft.get("localPlayerCellId")

            for j in draft.get("myTeam", []):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ: picks_al.append(champ)
                if j.get("cellId") == mi_celda: mi_campeon = champ
            
            for j in draft.get("theirTeam", []):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ: picks_en.append(champ)
                
            if picks_al != self.last_aliados or picks_en != self.last_enemigos:
                self.last_aliados, self.last_enemigos = picks_al.copy(), picks_en.copy()
                
                self.mostrar_equipo_vivo(self.fr_aliados_picks, picks_al, is_ally=True)
                self.mostrar_equipo_vivo(self.fr_enemigos_picks, picks_en, is_ally=False)
                
                ad_al, ap_al, tanks_al, _ = analizar_composicion(picks_al)
                self.lbl_ally_stats.config(text=f"Daño AD: {ad_al}% | Daño AP: {ap_al}% | Frontlane: {tanks_al}")
                
                ad_en, ap_en, tanks_en, _ = analizar_composicion(picks_en)
                self.lbl_enemy_stats.config(text=f"Daño AD: {ad_en}% | Daño AP: {ap_en}% | Frontlane: {tanks_en}")
                
                self.mostrar_picks_vivo(rol_actual, picks_al, picks_en)
                
                if len(picks_al) == 5 and len(picks_en) == 5:
                    wr = calcular_winrate_5v5(picks_al, picks_en)
                    color = GREEN_WR if wr > 52 else RED_WR if wr < 48 else YELLOW_WR
                    tendencia = "↑ Ventaja de Sinergia" if wr > 52 else "↓ Desventaja de Draft" if wr < 48 else "≈ Matchup Equilibrado"
                    self.lbl_wr_numero.config(text=f"{wr}%", fg=color)
                    self.lbl_wr_razon.config(text=tendencia, fg=color)

            if mi_campeon != self.last_my_champ:
                self.last_my_champ = mi_campeon
                if mi_campeon:
                    ids_runas = obtener_top_runas(mi_campeon, rol_actual)
                    ids_spells = obtener_top_hechizos(mi_campeon, rol_actual)
                    self.renderizar_setup_completo(ids_runas, ids_spells, self.fr_runas_icons_vivo, is_centered=True)
                
        self.root.after(1500, self.actualizar_radar_loop)

    def mostrar_picks_vivo(self, rol, aliados, enemigos):
        for w in self.fr_picks_icons.winfo_children(): w.destroy()
        sugerencias = recomendar_picks_vivo(rol, aliados, enemigos)
        
        col_idx = 0
        for categoria, champs in sugerencias.items():
            if not champs: continue
            fr_cat = tk.Frame(self.fr_picks_icons, bg=BG_PANEL)
            fr_cat.grid(row=0, column=col_idx, padx=10, sticky="n")
            tk.Label(fr_cat, text=categoria, bg=BG_PANEL, fg=BORDER_GOLD, font=("Helvetica", 8, "bold")).pack()
            
            fr_icons = tk.Frame(fr_cat, bg=BG_PANEL)
            fr_icons.pack()
            for i, (champ, wr, razon) in enumerate(champs):
                self.renderizar_icono(champ, "champ", fr_icons, 0, i, f"{champ}\nWR Esperado: {wr}%\nPor qué: {razon}")
            col_idx += 1

    # ================= META & BUILDS =================
    def armar_tab_counters(self, frame):
        ctrls = tk.Frame(frame, bg=BG_DARK)
        ctrls.pack(fill='x', pady=10)
        
        tk.Label(ctrls, text="Línea:", bg=BG_DARK, fg=TEXT_WHITE).pack(side="left", padx=5)
        self.cb_rol_counter = ttk.Combobox(ctrls, values=self.roles, state="readonly", width=15)
        self.cb_rol_counter.current(0)
        self.cb_rol_counter.pack(side="left", padx=5)
        self.cb_rol_counter.bind("<<ComboboxSelected>>", self.actualizar_listas_counter)
        
        tk.Label(ctrls, text="Vs:", bg=BG_DARK, fg=TEXT_WHITE).pack(side="left", padx=5)
        self.cb_enemigo = ttk.Combobox(ctrls, state="readonly", width=15)
        self.cb_enemigo.pack(side="left", padx=5)
        
        tk.Button(ctrls, text="ANALIZAR", bg=BORDER_GOLD, fg=BG_DARK, font=("Helvetica", 9, "bold"), command=self.buscar_counters).pack(side="left", padx=15)
        
        content = tk.Frame(frame, bg=BG_DARK)
        content.pack(fill="both", expand=True)
        
        self.tree_counters = ttk.Treeview(content, columns=("Campeón Aliado", "Winrate %", "Partidas"), show="headings", height=5)
        self.tree_counters.heading("Campeón Aliado", text="Mejores Respuestas")
        self.tree_counters.heading("Winrate %", text="Winrate %")
        self.tree_counters.heading("Partidas", text="Partidas Analizadas")
        self.tree_counters.pack(fill='x', pady=10)
        self.tree_counters.bind("<<TreeviewSelect>>", self.mostrar_build_visual)
        
        self.panel_visual = self.crear_panel(content, "Setup & Build Óptimas")
        self.panel_visual.pack(fill='both', expand=True, pady=5)
        self.fr_contenido_visual = tk.Frame(self.panel_visual, bg=BG_PANEL)
        self.fr_contenido_visual.pack(fill="both", expand=True)
        self.frame_iconos_items = tk.Frame(self.fr_contenido_visual, bg=BG_PANEL)
        self.frame_iconos_items.pack(side="top", pady=10)
        self.frame_iconos_runas = tk.Frame(self.fr_contenido_visual, bg=BG_PANEL)
        self.frame_iconos_runas.pack(side="top", pady=10)

        # SOLUCIÓN BUG META & BUILDS: Cargar campeones al iniciar la pestaña
        self.actualizar_listas_counter()

    def buscar_counters(self):
        rol = self.cb_rol_counter.get()
        enemigo = self.cb_enemigo.get()
        self.builds_actuales.clear() 
        for item in self.tree_counters.get_children(): self.tree_counters.delete(item)
        for w in self.frame_iconos_items.winfo_children(): w.destroy()
        for w in self.frame_iconos_runas.winfo_children(): w.destroy()

        resultados = obtener_counters(rol, enemigo, min_partidas=5)
        if not resultados: return messagebox.showinfo("Aviso", "Datos insuficientes.")

        for champ, winrate, partidas in resultados[:5]:
            ids_start, ids_fin = obtener_top_items(champ, rol)
            self.builds_actuales[champ] = {
                "starters": ids_start, 
                "finales": ids_fin, 
                "runas": obtener_top_runas(champ, rol),
                "spells": obtener_top_hechizos(champ, rol)
            }
            self.tree_counters.insert("", "end", values=(champ, f"{winrate}%", partidas))

    def mostrar_build_visual(self, event):
        seleccion = self.tree_counters.selection()
        if not seleccion: return
        champ = self.tree_counters.item(seleccion[0])['values'][0]
        data = self.builds_actuales.get(champ, {})
        
        for w in self.frame_iconos_items.winfo_children(): w.destroy()
        
        fr_start = tk.Frame(self.frame_iconos_items, bg=BG_PANEL)
        fr_start.pack(side="left", padx=20)
        tk.Label(fr_start, text="Start", bg=BG_PANEL, fg=TEXT_WHITE).pack()
        fr_s_i = tk.Frame(fr_start, bg=BG_PANEL); fr_s_i.pack()
        for idx, i_id in enumerate(data.get("starters", [])): self.renderizar_icono(i_id, "item", fr_s_i, 0, idx)

        fr_fin = tk.Frame(self.frame_iconos_items, bg=BG_PANEL)
        fr_fin.pack(side="left", padx=20)
        tk.Label(fr_fin, text="Core Build", bg=BG_PANEL, fg=TEXT_WHITE).pack()
        fr_f_i = tk.Frame(fr_fin, bg=BG_PANEL); fr_f_i.pack()
        for idx, i_id in enumerate(data.get("finales", [])): self.renderizar_icono(i_id, "item", fr_f_i, 0, idx)

        if data.get("runas"): 
            self.renderizar_setup_completo(data["runas"], data.get("spells", []), self.frame_iconos_runas, is_centered=False)

    # ================= ANÁLISIS 1v1 =================
    def armar_tab_ia(self, frame):
        panel_ia = self.crear_panel(frame, "Simulador de Línea")
        panel_ia.pack(fill="x", pady=20)
        
        ctrls = tk.Frame(panel_ia, bg=BG_PANEL)
        ctrls.pack(pady=10)
        
        tk.Label(ctrls, text="Línea:", bg=BG_PANEL, fg=TEXT_WHITE).grid(row=0, column=0, padx=10, pady=10)
        self.cb_ia_rol = ttk.Combobox(ctrls, values=self.roles, state="readonly"); self.cb_ia_rol.current(0)
        self.cb_ia_rol.bind("<<ComboboxSelected>>", self.actualizar_listas_ia)
        self.cb_ia_rol.grid(row=0, column=1)
        
        tk.Label(ctrls, text="Tu Pick:", bg=BG_PANEL, fg=TEXT_WHITE).grid(row=0, column=2, padx=10)
        self.cb_ia_aliado = ttk.Combobox(ctrls, state="readonly"); self.cb_ia_aliado.grid(row=0, column=3)
        
        tk.Label(ctrls, text="VS", bg=BG_PANEL, fg=RED_WR, font=("Helvetica", 10, "bold")).grid(row=0, column=4, padx=15)
        self.cb_ia_enemigo = ttk.Combobox(ctrls, state="readonly"); self.cb_ia_enemigo.grid(row=0, column=5)
        
        tk.Button(ctrls, text="SIMULAR", bg=BORDER_GOLD, fg=BG_DARK, font=("Helvetica", 9, "bold"), command=self.predecir_ia).grid(row=0, column=6, padx=20)
        
        res_panel = tk.Frame(frame, bg=BG_DARK)
        res_panel.pack(pady=20)
        self.lbl_resultado_ia = tk.Label(res_panel, text="", font=("Impact", 30), bg=BG_DARK, fg=TEXT_WHITE)
        self.lbl_resultado_ia.pack()
        self.lbl_analisis_ia = tk.Label(res_panel, text="", font=("Helvetica", 12, "italic"), bg=BG_DARK, fg=ACCENT_BLUE, wraplength=600)
        self.lbl_analisis_ia.pack(pady=10)

        # SOLUCIÓN BUG: Se inicializan los Combobox de esta pestaña inmediatamente al arrancar.
        self.actualizar_listas_ia()

    def actualizar_listas_counter(self, event=None):
        self.cb_enemigo['values'] = obtener_campeones_por_rol(self.cb_rol_counter.get())
        if self.cb_enemigo['values']: self.cb_enemigo.current(0)

    def actualizar_listas_ia(self, event=None):
        champs = obtener_campeones_por_rol(self.cb_ia_rol.get())
        self.cb_ia_aliado['values'] = self.cb_ia_enemigo['values'] = champs
        if len(champs) >= 2: self.cb_ia_aliado.current(0); self.cb_ia_enemigo.current(1)

    def predecir_ia(self):
        rol, aliado, enemigo = self.cb_ia_rol.get(), self.cb_ia_aliado.get(), self.cb_ia_enemigo.get()
        if not aliado or not enemigo or not modelo_1v1.get(rol): return
        
        n = len(self.nombres_campeones_global)
        X = np.zeros(n * 2)
        if aliado in self.nombres_campeones_global: X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global: X[n + self.nombres_campeones_global.index(enemigo)] = 1
        
        prob = modelo_1v1[rol].predict_proba(X.reshape(1, -1))[0][1] * 100
        self.lbl_resultado_ia.config(text=f"{prob:.1f}% Winrate", fg=GREEN_WR if prob > 50 else RED_WR)
        
        tags_al = self.champs_dict.get(aliado, {}).get("tags", [])
        tags_en = self.champs_dict.get(enemigo, {}).get("tags", [])
        
        if prob > 55: text = f"✅ MATCHUP FAVORABLE: El kit de {aliado} neutraliza naturalmente a {enemigo}." + (" Especialmente fuerte como Asesino vs Mago." if "Assassin" in tags_al and "Mage" in tags_en else "")
        elif prob < 45: text = f"⚠️ MATCHUP PELIGROSO: {enemigo} tiene ventaja estadística pura en fase de líneas. Juega al escalado."
        else: text = f"⚔️ MATCHUP DE HABILIDAD: La estadística es {prob:.1f}%. El ganador se decide por control de oleadas y ganks."
        self.lbl_analisis_ia.config(text=text)

if __name__ == "__main__":
    root = tk.Tk()
    app = LoLRecommenderApp(root)
    root.mainloop()