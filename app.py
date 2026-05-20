import json
import tkinter as tk
from tkinter import ttk, messagebox
import os
import requests
from io import BytesIO
from PIL import Image
import numpy as np
import joblib

# IMPORTACIÓN DE LA NUEVA LIBRERÍA MODERNA
import customtkinter as ctk

from src.db_manager import DATA_DIR
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, cargar_hechizos, obtener_version_actual
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol, 
                              obtener_top_runas, obtener_top_hechizos, obtenermejoresbaneos, obtener_peores_matchups, 
                              recomendar_picks_vivo, calcular_winrate_5v5, analizar_composicion)
from src.lcu_api import LCUConnector

# Configuraciones de rutas
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

# --- TEMA HEXTECH DARK (Adaptado a CustomTkinter) ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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
    """Clase para mostrar tooltips flotantes al pasar el ratón."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tw or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        
        lbl = tk.Label(
            self.tw, 
            text=self.text, 
            justify='left', 
            bg=BG_PANEL, 
            fg=TEXT_WHITE, 
            relief='solid', 
            borderwidth=1, 
            highlightbackground=BORDER_GOLD,
            wraplength=250, 
            font=("Helvetica", 9), 
            padx=8, 
            pady=8
        )
        lbl.pack()

    def hide(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

class LoLRecommenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LoL Esports Analytics Pro - V6.0 (CustomTkinter UI)")
        self.root.geometry("1450x950")
        self.root.configure(fg_color=BG_DARK)
        
        # Configurar estilo estricto para el único widget que Tkinter no reemplaza bien (Treeview)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=BG_PANEL, foreground=TEXT_WHITE, fieldbackground=BG_PANEL, borderwidth=0, rowheight=30)
        style.configure("Treeview.Heading", background=BORDER_GOLD, foreground=BG_DARK, font=("Helvetica", 11, "bold"))
        style.map('Treeview', background=[('selected', BORDER_GOLD)], foreground=[('selected', BG_DARK)])

        self.champs_dict = cargar_campeones()
        self.nombres_campeones_global = sorted(list(set([data["nombre"] for data in self.champs_dict.values()])))
        
        self.nombre_a_id_img = {v.get("nombre"): k for k, v in self.champs_dict.items()}
        self.nombre_a_id_img["Wukong"] = "MonkeyKing"
        self.nombre_a_id_img["MaestroYi"] = "MasterYi"
        self.nombre_a_id_img["KhaZix"] = "Khazix"

        self.version_juego = obtener_version_actual()
        self.roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        self.builds_actuales = {}
        self.imagenes_cacheadas = []
        
        self.lcu = LCUConnector()
        self.radar_activo = False
        
        self.last_aliados = None
        self.last_enemigos = None
        self.last_my_champ = "FORZAR_INICIO"

        self.crear_interfaz()
        
        # Lanzar el bucle silencioso de auto-detección
        self.root.after(1000, self.auto_detectar_lcu)

    def crear_panel(self, parent, text="", pad=10):
        """Crea un contenedor CustomTkinter con bordes redondeados."""
        fr = ctk.CTkFrame(parent, fg_color=BG_PANEL, border_width=1, border_color=BORDER_GOLD, corner_radius=8)
        if text:
            lbl = ctk.CTkLabel(
                fr, 
                text=text.upper(), 
                text_color=ACCENT_BLUE, 
                font=ctk.CTkFont(family="Helvetica", size=11, weight="bold")
            )
            lbl.pack(anchor="w", padx=pad, pady=(pad, 0))
            fr.label_title = lbl
        return fr

    def crear_interfaz(self):
        # Header
        header = ctk.CTkFrame(self.root, fg_color=BG_DARK)
        header.pack(fill="x", pady=10)
        ctk.CTkLabel(
            header, 
            text="LOL ESPORTS ANALYTICS", 
            font=ctk.CTkFont(family="Impact", size=32), 
            text_color=BORDER_GOLD
        ).pack()

        # CustomTkinter Tabview
        self.tabview = ctk.CTkTabview(
            self.root, 
            fg_color=BG_DARK,
            segmented_button_selected_color=BORDER_GOLD,
            segmented_button_selected_hover_color="#a67c2e",
            segmented_button_unselected_color=BG_PANEL,
            text_color=TEXT_WHITE,
            corner_radius=10
        )
        self.tabview.pack(fill='both', expand=True, padx=15, pady=10)

        # Creación de pestañas
        self.tab_vivo = self.tabview.add("📡 RADAR EN VIVO")
        self.tab_counters = self.tabview.add("📊 META & BUILDS")
        self.tab_ia = self.tabview.add("🤖 ANÁLISIS 1v1")
        self.tab_bans = self.tabview.add(" BANS RECOMENDADOS ")

        # Llenar cada pestaña
        self.armar_tab_vivo(self.tab_vivo)
        self.armar_tab_counters(self.tab_counters)
        self.armar_tab_ia(self.tab_ia)
        self.armar_tab_bans(self.tab_bans)

    def descargar_imagen(self, id_elemento, tipo):
        carpetas = {"runa": RUNAS_DIR, "champ": CHAMPS_DIR, "item": ITEMS_DIR, "spell": SPELLS_DIR}
        ruta_local = os.path.join(carpetas.get(tipo), f"{id_elemento}.png")
        
        if os.path.exists(ruta_local):
            return ruta_local
            
        try:
            if tipo == "runa": 
                url = f"https://ddragon.leagueoflegends.com/cdn/img/{RUNAS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "spell": 
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/spell/{SPELLS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "champ": 
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/champion/{self.nombre_a_id_img.get(id_elemento, id_elemento)}.png"
            else: 
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/item/{id_elemento}.png"
                
            resp = requests.get(url)
            resp.raise_for_status()
            
            with open(ruta_local, "wb") as f:
                f.write(resp.content)
                
            return ruta_local
        except Exception as e:
            return None

    def renderizar_icono(self, id_elemento, tipo, frame_padre, fila, columna, info_extra="", size=40):
        ruta = self.descargar_imagen(id_elemento, tipo)
        if not ruta:
            return
            
        # En CustomTkinter usamos CTkImage para que el escalado sea perfecto
        img_pil = Image.open(ruta)
        foto = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(size, size))
        self.imagenes_cacheadas.append(foto)
        
        info_texto = info_extra
        if tipo == "runa": 
            info_texto = f"{RUNAS_DICT.get(str(id_elemento), {}).get('nombre', 'Runa')}\n{RUNAS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"
        elif tipo == "item": 
            info_texto = f"{ITEMS_DICT.get(str(id_elemento), {}).get('nombre', 'Objeto')}\n{ITEMS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"
        elif tipo == "spell": 
            info_texto = f"{SPELLS_DICT.get(str(id_elemento), {}).get('nombre', 'Hechizo')}\n{SPELLS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"

        # Creamos un label sin texto, solo con la imagen
        lbl_img = ctk.CTkLabel(frame_padre, text="", image=foto)
        lbl_img.grid(row=fila, column=columna, padx=4, pady=4)
        
        if info_texto:
            ToolTip(lbl_img, info_texto)

    def inicializar_panel_setup(self):
        for w in self.fr_runas_icons_vivo.winfo_children():
            w.destroy()
            
        ctk.CTkLabel(
            self.fr_runas_icons_vivo, 
            text="Selecciona o haz pre-pick de un campeón en el\ncliente de LoL para generar su Setup Óptimo.", 
            text_color="gray", 
            font=ctk.CTkFont(family="Helvetica", size=14, slant="italic")
        ).pack(expand=True)

    def _animar_boton(self, btn, text_original):
        btn.configure(text="¡IMPORTADO! ✔", fg_color=GREEN_WR, text_color=BG_DARK)
        self.root.after(2000, lambda: btn.configure(text=text_original, fg_color="#1a2b4c", text_color=TEXT_WHITE))

    def accion_importar_runas(self, ids_runas, campeon, btn):
        if self.lcu.importar_runas(ids_runas, nombre=f"LEA {campeon}"):
            self._animar_boton(btn, "Exportar a LoL")
        else:
            messagebox.showerror("Error", "No se pudo importar las runas al cliente.")

    def accion_importar_spells(self, ids_spells, btn):
        if len(ids_spells) >= 2 and self.lcu.importar_hechizos(ids_spells[0], ids_spells[1]):
            self._animar_boton(btn, "Exportar a LoL")
        else:
            messagebox.showerror("Error", "No se pudo importar hechizos.")

    def accion_importar_items(self, campeon, ids_start, ids_core, btn):
        if self.lcu.importar_item_set(campeon, ids_start, ids_core):
            self._animar_boton(btn, "Crear Item Set")
        else:
            messagebox.showerror("Error", "No se pudo crear el Item Set.")

    # =========================================================================
    # RENDERIZADO VISUAL COMPLETO DE BUILDS (CORRECCIÓN DE LA CUADRÍCULA GRID)
    # =========================================================================
    def renderizar_setup_completo(self, campeon, ids_runas, ids_spells, ids_start, ids_core, frame_padre, is_centered=False):
        for w in frame_padre.winfo_children():
            w.destroy()

        # El contenedor principal del Setup debe expandirse y usar una cuadricula
        main_wrap = ctk.CTkFrame(frame_padre, fg_color="transparent")
        if is_centered:
            main_wrap.pack(expand=True, fill="both", padx=5, pady=5)
        else:
            main_wrap.pack(fill="both", expand=True, padx=5, pady=5)

        # Configuramos la cuadrícula 2x2. ¡ESTO GARANTIZA QUE LOS ITEMS TENGAN ESPACIO FÍSICO!
        main_wrap.columnconfigure(0, weight=1, uniform="col")
        main_wrap.columnconfigure(1, weight=1, uniform="col")
        main_wrap.rowconfigure(0, weight=6, uniform="row") # Runas y Spells son más altos
        main_wrap.rowconfigure(1, weight=4, uniform="row") # Start y Core son más bajos

        # Cuadrantes
        panel_runas = self.crear_panel(main_wrap, "Runas")
        panel_runas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        panel_spells = self.crear_panel(main_wrap, "Hechizos")
        panel_spells.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        panel_start = self.crear_panel(main_wrap, "Start / Early Game")
        panel_start.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        panel_core = self.crear_panel(main_wrap, "Core Build")
        panel_core.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # ====== 1. DIBUJAR RUNAS ======
        contenido_runas = ctk.CTkFrame(panel_runas, fg_color="transparent")
        contenido_runas.pack(padx=5, pady=5, expand=True)

        col_main = ctk.CTkFrame(contenido_runas, fg_color="transparent")
        col_main.pack(side="left", padx=10, anchor="n")

        col_sec = ctk.CTkFrame(contenido_runas, fg_color="transparent")
        col_sec.pack(side="left", padx=10, anchor="n")

        ctk.CTkLabel(col_main, text="PRIMARIA", text_color=BORDER_GOLD, font=ctk.CTkFont(family="Helvetica", size=10, weight="bold")).pack(pady=(0, 5))
        fr_m = ctk.CTkFrame(col_main, fg_color="transparent"); fr_m.pack()
        
        if len(ids_runas) > 4:
            self.renderizar_icono(ids_runas[0], "runa", fr_m, 0, 0, size=35)
            self.renderizar_icono(ids_runas[1], "runa", fr_m, 1, 0, size=55)
            self.renderizar_icono(ids_runas[2], "runa", fr_m, 2, 0, size=35)
            self.renderizar_icono(ids_runas[3], "runa", fr_m, 3, 0, size=35)
            self.renderizar_icono(ids_runas[4], "runa", fr_m, 4, 0, size=35)

        ctk.CTkLabel(col_sec, text="SECUNDARIA", text_color=BORDER_GOLD, font=ctk.CTkFont(family="Helvetica", size=10, weight="bold")).pack(pady=(0, 5))
        fr_s = ctk.CTkFrame(col_sec, fg_color="transparent"); fr_s.pack()
        
        if len(ids_runas) > 7:
            self.renderizar_icono(ids_runas[5], "runa", fr_s, 0, 0, size=30)
            self.renderizar_icono(ids_runas[6], "runa", fr_s, 1, 0, size=35)
            self.renderizar_icono(ids_runas[7], "runa", fr_s, 2, 0, size=35)

        ctk.CTkLabel(panel_runas, text="SHARDS", text_color=ACCENT_BLUE, font=ctk.CTkFont(family="Helvetica", size=10, weight="bold")).pack(pady=(5, 0))
        fr_shards = ctk.CTkFrame(panel_runas, fg_color="transparent")
        fr_shards.pack(pady=(0, 5))

        for stat_id in ([str(i) for i in ids_runas[8:11]] if len(ids_runas) >= 11 else ["5008", "5008", "5011"]):
            texto, color = STAT_SHARDS.get(stat_id, (f"Shard {stat_id}", "#ffffff"))
            # Simulamos el borde de color usando un Frame de fondo
            border_frame = ctk.CTkFrame(fr_shards, fg_color=color, corner_radius=4)
            border_frame.pack(side="left", padx=3)
            lbl = ctk.CTkLabel(border_frame, text=texto, text_color=TEXT_WHITE, fg_color=BG_DARK, font=ctk.CTkFont(size=9, weight="bold"), width=70, corner_radius=3)
            lbl.pack(padx=1, pady=1) # El padding de 1px simula el borde

        btn_imp_runas = ctk.CTkButton(panel_runas, text="Exportar a LoL", fg_color="#1a2b4c", hover_color=ACCENT_BLUE, height=25)
        btn_imp_runas.configure(command=lambda: self.accion_importar_runas(ids_runas, campeon, btn_imp_runas))
        btn_imp_runas.pack(pady=5)

        # ====== 2. DIBUJAR HECHIZOS ======
        cont_spells = ctk.CTkFrame(panel_spells, fg_color="transparent")
        cont_spells.pack(expand=True, pady=10)
        
        fr_spells = ctk.CTkFrame(cont_spells, fg_color="transparent")
        fr_spells.pack()
        
        for idx, sp in enumerate(ids_spells):
            self.renderizar_icono(str(sp), "spell", fr_spells, idx, 0, size=50)
            
        btn_imp_spells = ctk.CTkButton(panel_spells, text="Exportar a LoL", fg_color="#1a2b4c", hover_color=ACCENT_BLUE, height=25)
        btn_imp_spells.configure(command=lambda: self.accion_importar_spells(ids_spells, btn_imp_spells))
        btn_imp_spells.pack(side="bottom", pady=10)

        # ====== 3. DIBUJAR ITEMS START ======
        fr_s_i = ctk.CTkFrame(panel_start, fg_color="transparent")
        fr_s_i.pack(expand=True)
        
        if ids_start:
            for idx, i_id in enumerate(ids_start): 
                self.renderizar_icono(i_id, "item", fr_s_i, 0, idx, size=40)
        else:
            ctk.CTkLabel(fr_s_i, text="Sin datos.", text_color=TEXT_WHITE).grid(row=0, column=0)

        # ====== 4. DIBUJAR CORE BUILD ======
        fr_c_i = ctk.CTkFrame(panel_core, fg_color="transparent")
        fr_c_i.pack(expand=True)
        
        if ids_core:
            # Dividimos los 6 ítems en 2 filas de 3 para que no se amontonen horizontalmente
            for idx, i_id in enumerate(ids_core):
                row_idx = 0 if idx < 3 else 1
                col_idx = idx % 3
                self.renderizar_icono(i_id, "item", fr_c_i, row_idx, col_idx, size=40)
        else:
            ctk.CTkLabel(fr_c_i, text="Selecciona un campeón...", text_color=TEXT_WHITE).grid(row=0, column=0)

        btn_imp_items = ctk.CTkButton(panel_core, text="Crear Item Set en LoL", fg_color="#1a2b4c", hover_color=ACCENT_BLUE, height=25)
        btn_imp_items.configure(command=lambda: self.accion_importar_items(campeon, ids_start, ids_core, btn_imp_items))
        btn_imp_items.pack(side="bottom", pady=5)


    def mostrar_equipo_vivo(self, frame_padre, picks, is_ally=True):
        for w in frame_padre.winfo_children():
            w.destroy()
            
        if not picks:
            ctk.CTkLabel(frame_padre, text="Esperando equipo...", text_color=TEXT_WHITE, font=ctk.CTkFont(slant="italic")).pack(pady=20)
            return
            
        bg_card = ALLY_BG if is_ally else ENEMY_BG
        for champ in picks:
            card = ctk.CTkFrame(frame_padre, fg_color=bg_card, border_width=1, border_color=BORDER_GOLD, corner_radius=5)
            card.pack(fill="x", pady=4, padx=10, ipadx=5, ipady=5)
            
            self.renderizar_icono(champ, "champ", card, 0, 0, size=35)
            ctk.CTkLabel(card, text=champ, text_color=TEXT_WHITE, font=ctk.CTkFont(family="Helvetica", size=14, weight="bold")).grid(row=0, column=1, padx=10, sticky="w")

    # ================= RADAR EN VIVO =================
    def armar_tab_vivo(self, frame):
        top_bar = ctk.CTkFrame(frame, fg_color=BG_DARK)
        top_bar.pack(fill="x", pady=(0, 10))
        
        self.lbl_estado_lcu = ctk.CTkLabel(top_bar, text="Buscando Cliente de LoL...", font=ctk.CTkFont(family="Helvetica", size=12, weight="bold"), text_color=YELLOW_WR)
        self.lbl_estado_lcu.pack(side="left", padx=10)
        
        self.fr_wr_widget = ctk.CTkFrame(top_bar, fg_color=BG_DARK)
        self.fr_wr_widget.pack(side="right", padx=20)
        
        self.lbl_wr_numero = ctk.CTkLabel(self.fr_wr_widget, text="--%", font=ctk.CTkFont(family="Impact", size=42), text_color="gray")
        self.lbl_wr_numero.pack(side="left")
        
        self.lbl_wr_razon = ctk.CTkLabel(self.fr_wr_widget, text="Esperando equipos...", font=ctk.CTkFont(family="Helvetica", size=12, slant="italic"), text_color="gray")
        self.lbl_wr_razon.pack(side="left", padx=10, anchor="s", pady=10)

        draft_flow = ctk.CTkFrame(frame, fg_color=BG_DARK)
        draft_flow.pack(fill="both", expand=True)

        # Columna 1: Enemigos
        col_enemy = self.crear_panel(draft_flow, "Enemigos")
        col_enemy.pack(side="left", fill="both", expand=True, padx=5)
        
        self.lbl_enemy_stats = ctk.CTkLabel(col_enemy, text="AD: --% | AP: --% | Tanks: 0", font=ctk.CTkFont(weight="bold"), text_color=RED_WR)
        self.lbl_enemy_stats.pack(pady=5)
        
        self.fr_enemigos_picks = ctk.CTkFrame(col_enemy, fg_color="transparent")
        self.fr_enemigos_picks.pack(fill="both", expand=True, pady=5)
        
        self.panel_bans_vivo = self.crear_panel(col_enemy, "Bans Sugeridos (Tu Línea)")
        self.panel_bans_vivo.pack(fill="x", side="bottom", pady=5)
        
        self.fr_bans_icons_vivo = ctk.CTkFrame(self.panel_bans_vivo, fg_color="transparent")
        self.fr_bans_icons_vivo.pack(pady=5)

        # Columna 2: Central (Sugerencias y Build)
        col_center = ctk.CTkFrame(draft_flow, fg_color=BG_DARK)
        col_center.pack(side="left", fill="both", expand=True, padx=5)
        
        self.lbl_rol_vivo = ctk.CTkLabel(col_center, text="ASIGNACIÓN PENDIENTE", font=ctk.CTkFont(family="Helvetica", size=18, weight="bold"), text_color=BORDER_GOLD)
        self.lbl_rol_vivo.pack(pady=5)
        
        self.panel_sugerencias = self.crear_panel(col_center, "Recomendaciones de Pick")
        self.panel_sugerencias.pack(fill="x", pady=5)
        
        self.fr_picks_icons = ctk.CTkFrame(self.panel_sugerencias, fg_color="transparent")
        self.fr_picks_icons.pack(pady=10)

        self.panel_runas_vivo = self.crear_panel(col_center, "Setup Recomendado Integral")
        self.panel_runas_vivo.pack(fill="both", expand=True, pady=5)
        
        self.fr_runas_icons_vivo = ctk.CTkFrame(self.panel_runas_vivo, fg_color="transparent")
        self.fr_runas_icons_vivo.pack(fill="both", expand=True, pady=5)
        
        self.inicializar_panel_setup() 

        # Columna 3: Aliados
        col_ally = self.crear_panel(draft_flow, "Aliados")
        col_ally.pack(side="left", fill="both", expand=True, padx=5)
        
        self.lbl_ally_stats = ctk.CTkLabel(col_ally, text="AD: --% | AP: --% | Tanks: 0", font=ctk.CTkFont(weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_ally_stats.pack(pady=5)
        
        self.fr_aliados_picks = ctk.CTkFrame(col_ally, fg_color="transparent")
        self.fr_aliados_picks.pack(fill="both", expand=True, pady=5)

    def auto_detectar_lcu(self):
        """Bucle silencioso para auto-conectar con el cliente."""
        if not self.radar_activo:
            if self.lcu.conectar():
                self.radar_activo = True
                self.lbl_estado_lcu.configure(text="✓ ENLAZADO AL CLIENTE DE LOL", text_color=GREEN_WR)
                self.actualizar_radar_loop()
            else:
                self.lbl_estado_lcu.configure(text="Buscando Cliente de LoL... (Abre el juego)", text_color=YELLOW_WR)
                self.root.after(3000, self.auto_detectar_lcu)

    def procesar_nombre_champ(self, cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0": 
            return "Wukong" if MAPEO_IDS_CAMPEONES.get(final_id) == "MonkeyKing" else MAPEO_IDS_CAMPEONES.get(final_id, "Desconocido")
        return None

    def actualizar_radar_loop(self):
        if not self.radar_activo: return
        try:
            draft = self.lcu.obtener_sesion_draft()
            if draft:
                rol_actual = self.lcu.obtener_mi_rol(draft)
                self.lbl_rol_vivo.configure(text=f"LÍNEA ASIGNADA: {rol_actual}")

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
                    
                if picks_al != self.last_aliados or picks_en != self.last_enemigos or mi_campeon != self.last_my_champ:
                    self.last_aliados, self.last_enemigos = picks_al.copy(), picks_en.copy()
                    
                    self.mostrar_equipo_vivo(self.fr_aliados_picks, picks_al, is_ally=True)
                    self.mostrar_equipo_vivo(self.fr_enemigos_picks, picks_en, is_ally=False)
                    
                    ad_al, ap_al, tanks_al, _ = analizar_composicion(picks_al)
                    self.lbl_ally_stats.configure(text=f"Daño AD: {ad_al}% | Daño AP: {ap_al}% | Frontlane: {tanks_al}")
                    
                    ad_en, ap_en, tanks_en, _ = analizar_composicion(picks_en)
                    self.lbl_enemy_stats.configure(text=f"Daño AD: {ad_en}% | Daño AP: {ap_en}% | Frontlane: {tanks_en}")
                    
                    self.mostrar_picks_vivo(rol_actual, picks_al, picks_en)
                    
                    for w in self.fr_bans_icons_vivo.winfo_children(): w.destroy()
                    
                    if mi_campeon: 
                        self.panel_bans_vivo.label_title.configure(text=f"BANS SUGERIDOS (VS {mi_campeon.upper()})")
                        bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_actual, min_partidas=5)
                    else: 
                        self.panel_bans_vivo.label_title.configure(text=f"BANS SUGERIDOS (META {rol_actual})")
                        bans_sugeridos = obtenermejoresbaneos(rol_actual, min_partidas=5)

                    bans_filtrados = [b for b, wr, p in bans_sugeridos if b not in picks_al and b not in picks_en][:4]
                    if bans_filtrados:
                        for i, ban in enumerate(bans_filtrados): 
                            self.renderizar_icono(ban, "champ", self.fr_bans_icons_vivo, 0, i, f"Prioridad Ban: {ban}", size=35)
                    else: 
                        ctk.CTkLabel(self.fr_bans_icons_vivo, text="Sin recomendaciones claras", text_color="gray").grid(row=0, column=0, pady=10)

                    if len(picks_al) == 5 and len(picks_en) == 5:
                        wr = calcular_winrate_5v5(picks_al, picks_en)
                        color = GREEN_WR if wr > 52 else RED_WR if wr < 48 else YELLOW_WR
                        tendencia = "↑ Ventaja de Sinergia" if wr > 52 else "↓ Desventaja de Draft" if wr < 48 else "≈ Matchup Equilibrado"
                        self.lbl_wr_numero.configure(text=f"{wr}%", text_color=color)
                        self.lbl_wr_razon.configure(text=tendencia, text_color=color)

                if mi_campeon != self.last_my_champ:
                    self.last_my_champ = mi_campeon
                    if mi_campeon:
                        ids_runas = obtener_top_runas(mi_campeon, rol_actual)
                        ids_spells = obtener_top_hechizos(mi_campeon, rol_actual)
                        ids_start, ids_core = obtener_top_items(mi_campeon, rol_actual)
                        self.renderizar_setup_completo(mi_campeon, ids_runas, ids_spells, ids_start, ids_core, self.fr_runas_icons_vivo, is_centered=True)
                    else: 
                        self.inicializar_panel_setup()
            else:
                if self.last_my_champ != "FORZAR_INICIO":
                    self.radar_activo = False
                    self.last_aliados = None
                    self.last_enemigos = None
                    self.last_my_champ = "FORZAR_INICIO"
                    self.auto_detectar_lcu()
                    return

        except Exception as e: 
            pass
            
        self.root.after(1500, self.actualizar_radar_loop)

    def mostrar_picks_vivo(self, rol, aliados, enemigos):
        for w in self.fr_picks_icons.winfo_children(): 
            w.destroy()
            
        sugerencias = recomendar_picks_vivo(rol, aliados, enemigos)
        col_idx = 0
        
        for categoria, champs in sugerencias.items():
            if not champs: continue
            
            fr_cat = ctk.CTkFrame(self.fr_picks_icons, fg_color="transparent")
            fr_cat.grid(row=0, column=col_idx, padx=15, sticky="n")
            
            ctk.CTkLabel(fr_cat, text=categoria, text_color=BORDER_GOLD, font=ctk.CTkFont(size=10, weight="bold")).pack()
            
            fr_icons = ctk.CTkFrame(fr_cat, fg_color="transparent")
            fr_icons.pack()
            
            for i, (champ, wr, razon) in enumerate(champs): 
                self.renderizar_icono(champ, "champ", fr_icons, i // 2, i % 2, f"{champ}\nWR Esperado: {wr}%\nPor qué: {razon}", size=35)
                
            col_idx += 1

    # ================= META & BUILDS =================
    def armar_tab_counters(self, frame):
        ctrls = ctk.CTkFrame(frame, fg_color=BG_DARK)
        ctrls.pack(fill='x', pady=10)
        
        ctk.CTkLabel(ctrls, text="Línea:", text_color=TEXT_WHITE).pack(side="left", padx=5)
        
        self.cb_rol_counter = ctk.CTkComboBox(ctrls, values=self.roles, command=self.actualizar_listas_counter, width=150)
        self.cb_rol_counter.set(self.roles[0])
        self.cb_rol_counter.pack(side="left", padx=5)
        
        ctk.CTkLabel(ctrls, text="Vs:", text_color=TEXT_WHITE).pack(side="left", padx=5)
        
        self.cb_enemigo = ctk.CTkComboBox(ctrls, values=[], width=150)
        self.cb_enemigo.pack(side="left", padx=5)
        
        ctk.CTkButton(ctrls, text="ANALIZAR", fg_color=BORDER_GOLD, text_color=BG_DARK, hover_color="#a67c2e", font=ctk.CTkFont(weight="bold"), command=self.buscar_counters).pack(side="left", padx=15)
        
        content = ctk.CTkFrame(frame, fg_color=BG_DARK)
        content.pack(fill="both", expand=True)
        
        # El Treeview sigue usando ttk porque CustomTkinter no tiene tablas nativas, pero aplicamos el estilo oscuro.
        self.tree_counters = ttk.Treeview(content, columns=("Campeón Aliado", "Winrate %", "Partidas"), show="headings", height=5)
        self.tree_counters.heading("Campeón Aliado", text="Mejores Respuestas")
        self.tree_counters.heading("Winrate %", text="Winrate %")
        self.tree_counters.heading("Partidas", text="Partidas Analizadas")
        self.tree_counters.pack(fill='x', pady=10)
        self.tree_counters.bind("<<TreeviewSelect>>", self.mostrar_build_visual)
        
        self.panel_visual = self.crear_panel(content, "Setup & Build Óptimas")
        self.panel_visual.pack(fill='both', expand=True, pady=5)
        
        self.fr_contenido_visual = ctk.CTkFrame(self.panel_visual, fg_color="transparent")
        self.fr_contenido_visual.pack(fill="both", expand=True)
        
        self.frame_setup_visual = ctk.CTkFrame(self.fr_contenido_visual, fg_color="transparent")
        self.frame_setup_visual.pack(side="top", fill="both", expand=True, pady=10)

        self.actualizar_listas_counter(self.roles[0])

    def buscar_counters(self):
        rol = self.cb_rol_counter.get()
        enemigo = self.cb_enemigo.get()
        self.builds_actuales.clear() 
        
        for item in self.tree_counters.get_children(): 
            self.tree_counters.delete(item)
            
        for w in self.frame_setup_visual.winfo_children(): 
            w.destroy()

        resultados = obtener_counters(rol, enemigo, min_partidas=5)
        if not resultados: 
            return messagebox.showinfo("Aviso", "Datos insuficientes.")

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
        
        if data.get("runas"): 
            self.renderizar_setup_completo(champ, data["runas"], data.get("spells", []), data.get("starters", []), data.get("finales", []), self.frame_setup_visual, is_centered=False)

    # ================= ANÁLISIS 1v1 =================
    def armar_tab_ia(self, frame):
        panel_ia = self.crear_panel(frame, "Simulador de Línea")
        panel_ia.pack(fill="x", pady=20)
        
        ctrls = ctk.CTkFrame(panel_ia, fg_color="transparent")
        ctrls.pack(pady=10)
        
        ctk.CTkLabel(ctrls, text="Línea:", text_color=TEXT_WHITE).grid(row=0, column=0, padx=10, pady=10)
        self.cb_ia_rol = ctk.CTkComboBox(ctrls, values=self.roles, command=self.actualizar_listas_ia)
        self.cb_ia_rol.set(self.roles[0])
        self.cb_ia_rol.grid(row=0, column=1)
        
        ctk.CTkLabel(ctrls, text="Tu Pick:", text_color=TEXT_WHITE).grid(row=0, column=2, padx=10)
        self.cb_ia_aliado = ctk.CTkComboBox(ctrls, values=[])
        self.cb_ia_aliado.grid(row=0, column=3)
        
        ctk.CTkLabel(ctrls, text="VS", text_color=RED_WR, font=ctk.CTkFont(weight="bold")).grid(row=0, column=4, padx=15)
        
        self.cb_ia_enemigo = ctk.CTkComboBox(ctrls, values=[])
        self.cb_ia_enemigo.grid(row=0, column=5)
        
        ctk.CTkButton(ctrls, text="SIMULAR", fg_color=BORDER_GOLD, text_color=BG_DARK, hover_color="#a67c2e", font=ctk.CTkFont(weight="bold"), command=self.predecir_ia).grid(row=0, column=6, padx=20)
        
        res_panel = ctk.CTkFrame(frame, fg_color="transparent")
        res_panel.pack(pady=20)
        
        self.lbl_resultado_ia = ctk.CTkLabel(res_panel, text="", font=ctk.CTkFont(family="Impact", size=40), text_color=TEXT_WHITE)
        self.lbl_resultado_ia.pack()
        
        self.lbl_analisis_ia = ctk.CTkLabel(res_panel, text="", font=ctk.CTkFont(slant="italic", size=14), text_color=ACCENT_BLUE, wraplength=600)
        self.lbl_analisis_ia.pack(pady=10)

        self.actualizar_listas_ia(self.roles[0])

    def actualizar_listas_counter(self, value):
        champs = obtener_campeones_por_rol(value)
        self.cb_enemigo.configure(values=champs)
        if champs: 
            self.cb_enemigo.set(champs[0])

    def actualizar_listas_ia(self, value):
        champs = obtener_campeones_por_rol(value)
        self.cb_ia_aliado.configure(values=champs)
        self.cb_ia_enemigo.configure(values=champs)
        if len(champs) >= 2: 
            self.cb_ia_aliado.set(champs[0])
            self.cb_ia_enemigo.set(champs[1])

    def predecir_ia(self):
        rol = self.cb_ia_rol.get()
        aliado = self.cb_ia_aliado.get()
        enemigo = self.cb_ia_enemigo.get()
        
        if not aliado or not enemigo or not modelo_1v1.get(rol): 
            return
        
        n = len(self.nombres_campeones_global)
        X = np.zeros(n * 2)
        if aliado in self.nombres_campeones_global: 
            X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global: 
            X[n + self.nombres_campeones_global.index(enemigo)] = 1
            
        prob = modelo_1v1[rol].predict_proba(X.reshape(1, -1))[0][1] * 100
        
        self.lbl_resultado_ia.configure(text=f"{prob:.1f}% Winrate", text_color=GREEN_WR if prob > 50 else RED_WR)
        
        tags_al = self.champs_dict.get(aliado, {}).get("tags", [])
        tags_en = self.champs_dict.get(enemigo, {}).get("tags", [])
        
        if prob > 55: 
            text = f"✅ MATCHUP FAVORABLE: El kit de {aliado} neutraliza naturalmente a {enemigo}." + (" Especialmente fuerte como Asesino vs Mago." if "Assassin" in tags_al and "Mage" in tags_en else "")
        elif prob < 45: 
            text = f"⚠️ MATCHUP PELIGROSO: {enemigo} tiene ventaja estadística pura en fase de líneas. Juega al escalado."
        else: 
            text = f"⚔️ MATCHUP DE HABILIDAD: La estadística es {prob:.1f}%. El ganador se decide por control de oleadas y ganks."
            
        self.lbl_analisis_ia.configure(text=text)

    # ================= BANS RECOMENDADOS =================
    def armar_tab_bans(self, frame):
        ctrls = ctk.CTkFrame(frame, fg_color="transparent")
        ctrls.pack(fill="x", pady=10)
        
        ctk.CTkLabel(ctrls, text="Línea", text_color=TEXT_WHITE).pack(side="left", padx=5)
        
        self.cbbanrol = ctk.CTkComboBox(ctrls, values=self.roles, width=150)
        self.cbbanrol.set(self.roles[0])
        self.cbbanrol.pack(side="left", padx=5)
        
        ctk.CTkButton(ctrls, text="ANALIZAR BANS", fg_color=BORDER_GOLD, text_color=BG_DARK, hover_color="#a67c2e", font=ctk.CTkFont(weight="bold"), command=self.buscar_baneos).pack(side="left", padx=15)

        self.treebans = ttk.Treeview(frame, columns=("Campeón", "Banrate %", "Partidas"), show="headings", height=12)
        self.treebans.heading("Campeón", text="Mejores Bans")
        self.treebans.heading("Banrate %", text="Banrate")
        self.treebans.heading("Partidas", text="Partidas Analizadas")
        self.treebans.pack(fill="both", expand=True, pady=10)

    def buscar_baneos(self):
        for item in self.treebans.get_children(): 
            self.treebans.delete(item)
            
        resultados = obtenermejoresbaneos(self.cbbanrol.get(), min_partidas=5)
        if not resultados: 
            return messagebox.showinfo("Aviso", "No hay datos suficientes para ese rol.")
            
        for champ, banrate, partidas in resultados[:10]: 
            self.treebans.insert("", "end", values=(champ, f"{banrate}%", partidas))


if __name__ == "__main__":
    root = ctk.CTk()
    app = LoLRecommenderApp(root)
    root.mainloop()