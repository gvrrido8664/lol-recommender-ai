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
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, obtener_version_actual
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol, 
                              obtener_top_runas, obtener_mejores_baneos, recomendar_picks_vivo, 
                              calcular_winrate_5v5)
from src.lcu_api import LCUConnector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ITEMS_DIR = os.path.join(ASSETS_DIR, "items")
RUNAS_DIR = os.path.join(ASSETS_DIR, "runas")
CHAMPS_DIR = os.path.join(ASSETS_DIR, "champs")
os.makedirs(ITEMS_DIR, exist_ok=True)
os.makedirs(RUNAS_DIR, exist_ok=True)
os.makedirs(CHAMPS_DIR, exist_ok=True)

modelo_1v1 = joblib.load("data/modelo_1v1.pkl") if os.path.exists("data/modelo_1v1.pkl") else {}
ITEMS_DICT = cargar_objetos()
RUNAS_DICT = cargar_runas()
MAPEO_IDS_CAMPEONES = cargar_mapeo_ids()
STAT_SHARDS = {
    "5001": ("+10-180 Vida Lvl", "#2ecc71"),
    "5002": ("+6 Armadura", "#e67e22"),
    "5003": ("+8 Res. Mágica", "#3498db"),
    "5005": ("+10% Vel. Ataque", "#f1c40f"),
    "5007": ("+8 Acel. Hab.", "#9b59b6"),
    "5008": ("+9 Fue. Adapt.", "#e74c3c"),
    "5009": ("+2% Vel. Mov.", "#1abc9c"),
    "5010": ("+65 Vida Fija", "#27ae60"),
    "5011": ("+10-180 Vida", "#2ecc71"),
    "5013": ("+10% Tenacidad", "#34495e"),
}

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 35
        y += self.widget.winfo_rooty() + 20
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left',
                         background="#2b2d42", foreground="white", relief='solid', borderwidth=1,
                         wraplength=250, font=("Helvetica", 9), padx=5, pady=5)
        label.pack(ipadx=1, ipady=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class LoLRecommenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LoL Recommender V2.5 - Radar e IA Predictiva")
        self.root.geometry("900x800")
        self.root.configure(padx=20, pady=20)

        self.champs_dict = cargar_campeones()
        self.nombres_campeones_global = sorted(list(set([data["nombre"] for data in self.champs_dict.values()])))
        self.version_juego = obtener_version_actual()
        self.roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        self.builds_actuales = {}
        self.imagenes_cacheadas = []
        
        # Variables LCU Live
        self.lcu = LCUConnector()
        self.radar_activo = False
        self.ultimo_rol_detectado = None
        self.last_aliados = []
        self.last_enemigos = []
        self.last_my_champ = None

        self.crear_interfaz()
        self.actualizar_listas_counter()
        self.actualizar_listas_ia()

    def crear_interfaz(self):
        lbl_titulo = tk.Label(self.root, text="Asistente de Draft & Análisis de Meta", font=("Helvetica", 16, "bold"))
        lbl_titulo.pack(pady=(0, 15))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True)

        tab_counters = ttk.Frame(notebook)
        notebook.add(tab_counters, text="📊 Counters y Builds")
        self.armar_tab_counters(tab_counters)

        tab_ia = ttk.Frame(notebook)
        notebook.add(tab_ia, text="🤖 Predicción IA (1v1)")
        self.armar_tab_ia(tab_ia)
        
        tab_vivo = ttk.Frame(notebook)
        notebook.add(tab_vivo, text="📡 Radar en Vivo")
        self.armar_tab_vivo(tab_vivo)

    def descargar_imagen(self, id_elemento, tipo):
        if tipo == "runa": carpeta, ext = RUNAS_DIR, ".png"
        elif tipo == "champ": carpeta, ext = CHAMPS_DIR, ".png"
        else: carpeta, ext = ITEMS_DIR, ".png"
        
        ruta_local = os.path.join(carpeta, f"{id_elemento}{ext}")
        if os.path.exists(ruta_local): return ruta_local

        try:
            if tipo == "runa":
                data_runa = RUNAS_DICT.get(str(id_elemento), {})
                icon_path = data_runa.get("icono", "")
                if not icon_path: return None
                url = f"https://ddragon.leagueoflegends.com/cdn/img/{icon_path}"
            elif tipo == "champ":
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/champion/{id_elemento}.png"
            else:
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/item/{id_elemento}.png"
                
            resp = requests.get(url)
            resp.raise_for_status()
            Image.open(BytesIO(resp.content)).save(ruta_local)
            return ruta_local
        except: return None

    def renderizar_icono(self, id_elemento, tipo, frame_padre, fila, columna, info_extra=""):
        if tipo == "champ" and id_elemento == "Wukong": id_elemento = "MonkeyKing"
        
        ruta = self.descargar_imagen(id_elemento, tipo)
        if not ruta: return
        
        imagen = Image.open(ruta)
        tamaño = (48, 48) if tipo != "runa" else (40, 40)
        imagen = imagen.resize(tamaño, Image.Resampling.LANCZOS)
        foto = ImageTk.PhotoImage(imagen)
        self.imagenes_cacheadas.append(foto)
        
        info_texto = info_extra
        if tipo == "runa":
            data = RUNAS_DICT.get(str(id_elemento), {})
            info_texto = f"{data.get('nombre', 'Runa')}\n{data.get('descripcion', '')}"
        elif tipo == "item":
            data = ITEMS_DICT.get(str(id_elemento), {})
            info_texto = f"{data.get('nombre', 'Objeto')} ({data.get('oro', 0)}g)\n{data.get('descripcion', '')}"

        relieve = "flat" if tipo == "runa" else "solid"
        bd = 0 if tipo == "runa" else 2
        
        lbl_img = tk.Label(frame_padre, image=foto, bg="#eef2f3", bd=bd, relief=relieve)
        lbl_img.grid(row=fila, column=columna, padx=4, pady=4)
        if info_texto: ToolTip(lbl_img, info_texto)

    def renderizar_runas_vertical(self, ids_runas, frame_padre):
        for w in frame_padre.winfo_children(): w.destroy()
        
        # Dos columnas: Rama Principal a la Izq, Secundaria+Stats a la Der
        col1 = tk.Frame(frame_padre, bg="#eef2f3")
        col1.pack(side="left", padx=15, anchor="n")
        
        col2 = tk.Frame(frame_padre, bg="#eef2f3")
        col2.pack(side="left", padx=15, anchor="n")
        
        # Rama Principal (Índices 0 al 4)
        if len(ids_runas) > 0: self.renderizar_icono(ids_runas[0], "runa", col1, 0, 0)
        if len(ids_runas) > 1: self.renderizar_icono(ids_runas[1], "runa", col1, 1, 0) # Runa Clave
        if len(ids_runas) > 2: self.renderizar_icono(ids_runas[2], "runa", col1, 2, 0)
        if len(ids_runas) > 3: self.renderizar_icono(ids_runas[3], "runa", col1, 3, 0)
        if len(ids_runas) > 4: self.renderizar_icono(ids_runas[4], "runa", col1, 4, 0)
        
        # Rama Secundaria (Índices 5 al 7)
        if len(ids_runas) > 5: self.renderizar_icono(ids_runas[5], "runa", col2, 0, 0)
        if len(ids_runas) > 6: self.renderizar_icono(ids_runas[6], "runa", col2, 1, 0)
        if len(ids_runas) > 7: self.renderizar_icono(ids_runas[7], "runa", col2, 2, 0)
        
        # Stat Shards (Índices 8, 9, 10) - Se dibujan como bonitas etiquetas de texto de colores
        fr_stats = tk.Frame(col2, bg="#eef2f3")
        fr_stats.grid(row=3, column=0, pady=10)
        
        for idx in range(8, 11):
            if len(ids_runas) > idx:
                stat_id = str(ids_runas[idx])
                if stat_id in STAT_SHARDS:
                    texto, color = STAT_SHARDS[stat_id]
                    lbl = tk.Label(fr_stats, text=texto, bg=color, fg="white", font=("Helvetica", 8, "bold"), width=15, pady=2, relief="flat")
                    lbl.pack(pady=2)

    # ================= PESTAÑA 3: RADAR EN VIVO MEJORADO =================
    def armar_tab_vivo(self, frame):
        frame.configure(padding=15)
        
        # Panel de Control
        panel_control = tk.Frame(frame)
        panel_control.pack(fill="x", pady=5)
        self.lbl_estado_lcu = tk.Label(panel_control, text="🔴 Desconectado", font=("Helvetica", 12, "bold"), fg="#d90429")
        self.lbl_estado_lcu.pack(side="left", padx=10)
        self.btn_radar = tk.Button(panel_control, text="Activar Radar LCU", bg="#2b2d42", fg="white", font=("Helvetica", 10, "bold"), command=self.toggle_radar)
        self.btn_radar.pack(side="right", padx=10)

        self.lbl_rol_vivo = tk.Label(frame, text="Esperando Partida...", font=("Helvetica", 14, "italic"), fg="gray")
        self.lbl_rol_vivo.pack(pady=5)

        # Frame de Recomendaciones (Bans & Picks)
        frame_sugs = tk.Frame(frame)
        frame_sugs.pack(fill="x", pady=5)
        
        self.frame_baneos_container = tk.LabelFrame(frame_sugs, text="🛡️ Baneos Sugeridos", font=("Helvetica", 10, "bold"), bg="#f8f9fa")
        self.frame_baneos_container.pack(side="left", fill="x", expand=True, padx=5, ipady=5)
        self.frame_baneos_icons = tk.Frame(self.frame_baneos_container, bg="#f8f9fa")
        self.frame_baneos_icons.pack()

        self.frame_picks_container = tk.LabelFrame(frame_sugs, text="💡 Mejores Picks (Por Composición)", font=("Helvetica", 10, "bold"), bg="#f8f9fa")
        self.frame_picks_container.pack(side="right", fill="x", expand=True, padx=5, ipady=5)
        self.frame_picks_icons = tk.Frame(self.frame_picks_container, bg="#f8f9fa")
        self.frame_picks_icons.pack()

        # Frame Composición
        self.frame_comps = tk.LabelFrame(frame, text="⚔️ Composición en Vivo", font=("Helvetica", 10, "bold"))
        self.frame_comps.pack(fill="x", pady=5, padx=5)
        
        self.frame_aliados = tk.Frame(self.frame_comps)
        self.frame_aliados.pack(side="left", expand=True, fill="both", padx=5, pady=5)
        tk.Label(self.frame_aliados, text="Aliados", fg="blue", font=("Helvetica", 10, "bold")).pack()
        self.lbl_aliados_picks = tk.Label(self.frame_aliados, text="[Esperando picks...]")
        self.lbl_aliados_picks.pack(pady=5)

        self.frame_enemigos = tk.Frame(self.frame_comps)
        self.frame_enemigos.pack(side="right", expand=True, fill="both", padx=5, pady=5)
        tk.Label(self.frame_enemigos, text="Enemigos", fg="red", font=("Helvetica", 10, "bold")).pack()
        self.lbl_enemigos_picks = tk.Label(self.frame_enemigos, text="[Esperando picks...]")
        self.lbl_enemigos_picks.pack(pady=5)

        # Winrate y Runas
        self.frame_wr_runes = tk.Frame(frame)
        self.frame_wr_runes.pack(fill="both", expand=True, pady=5)
        
        self.lbl_winrate_vivo = tk.Label(self.frame_wr_runes, text="", font=("Helvetica", 16, "bold"))
        self.lbl_winrate_vivo.pack(pady=5)
        
        self.frame_runas_vivo_container = tk.LabelFrame(self.frame_wr_runes, text="✨ Tus Runas Recomendadas", font=("Helvetica", 10, "bold"), bg="#f8f9fa")
        self.frame_runas_vivo_container.pack(fill="x", padx=5, pady=5)
        self.frame_runas_vivo_icons = tk.Frame(self.frame_runas_vivo_container, bg="#f8f9fa")
        self.frame_runas_vivo_icons.pack(pady=5)

    def toggle_radar(self):
        if not self.radar_activo:
            if self.lcu.conectar():
                self.radar_activo = True
                self.lbl_estado_lcu.config(text="🟢 Conectado al Cliente", fg="green")
                self.btn_radar.config(text="Desactivar Radar", bg="#d90429")
                self.actualizar_radar_loop()
            else:
                messagebox.showerror("Error", "No se encontró League of Legends abierto.")
        else:
            self.radar_activo = False
            self.lbl_estado_lcu.config(text="🔴 Desconectado", fg="#d90429")
            self.btn_radar.config(text="Activar Radar LCU", bg="#2b2d42")
            self.lbl_rol_vivo.config(text="Esperando Partida...", fg="gray")
            self.lbl_winrate_vivo.config(text="")
            for w in self.frame_baneos_icons.winfo_children(): w.destroy()
            for w in self.frame_picks_icons.winfo_children(): w.destroy()
            for w in self.frame_runas_vivo_icons.winfo_children(): w.destroy()

    def procesar_nombre_champ(self, cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0":
            nombre = MAPEO_IDS_CAMPEONES.get(final_id, "Desconocido")
            if nombre == "MonkeyKing": nombre = "Wukong"
            return nombre
        return None

    def actualizar_radar_loop(self):
        if not self.radar_activo: return
        
        draft = self.lcu.obtener_sesion_draft()
        if draft:
            rol_actual = self.lcu.obtener_mi_rol(draft)
            
            if rol_actual != self.ultimo_rol_detectado:
                self.ultimo_rol_detectado = rol_actual
                self.lbl_rol_vivo.config(text=f"📍 Línea Asignada: {rol_actual}", fg="black", font=("Helvetica", 16, "bold"))
                self.mostrar_baneos_vivo(rol_actual)

            picks_aliados = []
            picks_enemigos = []
            mi_campeon = None
            mi_celda = draft.get("localPlayerCellId")

            for j in draft.get("myTeam", []):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ: picks_aliados.append(champ)
                if j.get("cellId") == mi_celda: mi_campeon = champ
            
            for j in draft.get("theirTeam", []):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ: picks_enemigos.append(champ)
                
            # Solo actualizar la UI visual si hubo un cambio real (ahorra memoria)
            if picks_aliados != self.last_aliados or picks_enemigos != self.last_enemigos:
                self.last_aliados = picks_aliados.copy()
                self.last_enemigos = picks_enemigos.copy()
                
                self.lbl_aliados_picks.config(text="\n".join(picks_aliados) if picks_aliados else "...")
                self.lbl_enemigos_picks.config(text="\n".join(picks_enemigos) if picks_enemigos else "...")
                
                self.mostrar_picks_vivo(rol_actual, picks_aliados, picks_enemigos)
                
                # Calcular Winrate si están los 10
                if len(picks_aliados) == 5 and len(picks_enemigos) == 5:
                    wr = calcular_winrate_5v5(picks_aliados, picks_enemigos)
                    color = "green" if wr >= 50 else "red"
                    self.lbl_winrate_vivo.config(text=f"Probabilidad de Victoria 5v5: {wr}%", fg=color)
                else:
                    self.lbl_winrate_vivo.config(text="")

            # Mostrar las runas cuando el jugador seleccione a su campeón
            if mi_campeon != self.last_my_champ:
                self.last_my_champ = mi_campeon
                self.mostrar_runas_vivo(mi_campeon, rol_actual)
                
        else:
            if self.ultimo_rol_detectado is not None:
                self.ultimo_rol_detectado = None
                self.last_aliados = []
                self.last_enemigos = []
                self.last_my_champ = None
                self.lbl_rol_vivo.config(text="Buscando nueva partida...", fg="gray", font=("Helvetica", 14, "italic"))
                self.lbl_winrate_vivo.config(text="")
                self.lbl_aliados_picks.config(text="...")
                self.lbl_enemigos_picks.config(text="...")
                for w in self.frame_baneos_icons.winfo_children(): w.destroy()
                for w in self.frame_picks_icons.winfo_children(): w.destroy()
                for w in self.frame_runas_vivo_icons.winfo_children(): w.destroy()

        self.root.after(1500, self.actualizar_radar_loop)

    def mostrar_baneos_vivo(self, rol):
        for w in self.frame_baneos_icons.winfo_children(): w.destroy()
        baneos = obtener_mejores_baneos(rol, limite=6)
        if not baneos:
            tk.Label(self.frame_baneos_icons, text="Faltan datos para esta línea.", bg="#f8f9fa").pack()
            return
        for idx, champ in enumerate(baneos):
            self.renderizar_icono(champ, "champ", self.frame_baneos_icons, 0, idx, info_extra=f"Ban Sugerido: {champ}")

    def mostrar_picks_vivo(self, rol, aliados, enemigos):
        for w in self.frame_picks_icons.winfo_children(): w.destroy()
        sugerencias = recomendar_picks_vivo(rol, aliados, enemigos)
        if not sugerencias:
            tk.Label(self.frame_picks_icons, text="Calculando...", bg="#f8f9fa").pack()
            return
        for idx, champ in enumerate(sugerencias):
            self.renderizar_icono(champ, "champ", self.frame_picks_icons, 0, idx, info_extra=f"Sinergia de Composición: {champ}")

    def mostrar_runas_vivo(self, campeon, rol):
        for w in self.frame_runas_vivo_icons.winfo_children(): w.destroy()
        if not campeon: return
        
        ids_runas = obtener_top_runas(campeon, rol)
        if not ids_runas:
            tk.Label(self.frame_runas_vivo_icons, text=f"Sin datos de runas para {campeon}.", bg="#f8f9fa").pack()
            return
            
        self.renderizar_runas_vertical(ids_runas, self.frame_runas_vivo_icons) # Usando la nueva función

    # ================= PESTAÑAS 1 Y 2 =================
    def armar_tab_counters(self, frame):
        frame.configure(padding=10)
        controles_frame = tk.Frame(frame)
        controles_frame.pack(fill='x', pady=5)
        tk.Label(controles_frame, text="Línea:").grid(row=0, column=0, padx=5)
        self.cb_rol_counter = ttk.Combobox(controles_frame, values=self.roles, state="readonly", width=15)
        self.cb_rol_counter.current(0)
        self.cb_rol_counter.grid(row=0, column=1, padx=5)
        self.cb_rol_counter.bind("<<ComboboxSelected>>", self.actualizar_listas_counter)
        tk.Label(controles_frame, text="Enemigo:").grid(row=0, column=2, padx=5)
        self.cb_enemigo = ttk.Combobox(controles_frame, state="readonly", width=20)
        self.cb_enemigo.grid(row=0, column=3, padx=5)
        btn_buscar = tk.Button(controles_frame, text="Buscar Counters", bg="#2b2d42", fg="white", command=self.buscar_counters)
        btn_buscar.grid(row=0, column=4, padx=15)
        columnas = ("Campeón Aliado", "Winrate %", "Partidas")
        self.tree_counters = ttk.Treeview(frame, columns=columnas, show="headings", height=5)
        self.tree_counters.heading("Campeón Aliado", text="Campeón Aliado")
        self.tree_counters.column("Campeón Aliado", width=150, anchor="center")
        self.tree_counters.heading("Winrate %", text="Winrate %")
        self.tree_counters.column("Winrate %", width=100, anchor="center")
        self.tree_counters.heading("Partidas", text="Partidas Analizadas")
        self.tree_counters.column("Partidas", width=150, anchor="center")
        self.tree_counters.pack(fill='x', pady=10)
        self.tree_counters.bind("<<TreeviewSelect>>", self.mostrar_build_visual)
        self.panel_visual = tk.Frame(frame, bg="#eef2f3", bd=2, relief="groove")
        self.panel_visual.pack(fill='both', expand=True, pady=10, padx=5)
        self.lbl_visual_titulo = tk.Label(self.panel_visual, text="Haz clic en un campeón para ver su Build Analítica", bg="#eef2f3", font=("Helvetica", 11, "italic"))
        self.lbl_visual_titulo.pack(pady=10)
        self.frame_iconos_items = tk.Frame(self.panel_visual, bg="#eef2f3")
        self.frame_iconos_items.pack(pady=5)
        self.frame_iconos_runas = tk.Frame(self.panel_visual, bg="#eef2f3")
        self.frame_iconos_runas.pack(pady=5)

    def buscar_counters(self):
        rol = self.cb_rol_counter.get()
        enemigo = self.cb_enemigo.get()
        self.builds_actuales.clear() 
        for item in self.tree_counters.get_children(): self.tree_counters.delete(item)
        self.lbl_visual_titulo.config(text="Haz clic en un campeón para ver su Build Analítica")
        for widget in self.frame_iconos_items.winfo_children(): widget.destroy()
        for widget in self.frame_iconos_runas.winfo_children(): widget.destroy()

        resultados = obtener_counters(rol, enemigo, min_partidas=15)
        if not resultados:
            messagebox.showinfo("Sin datos", f"No hay suficientes datos válidos contra {enemigo} en {rol}.")
            return

        for champ, winrate, partidas in resultados[:5]:
            ids_starters, ids_finales = obtener_top_items(champ, rol)
            ids_runas = obtener_top_runas(champ, rol)
            self.builds_actuales[champ] = {"starters": ids_starters, "finales": ids_finales, "runas": ids_runas}
            self.tree_counters.insert("", "end", values=(champ, f"{winrate}%", partidas))

    def mostrar_build_visual(self, event):
        seleccion = self.tree_counters.selection()
        if not seleccion: return
        item_tabla = self.tree_counters.item(seleccion[0])
        campeon = item_tabla['values'][0]
        data_build = self.builds_actuales.get(campeon, {})
        ids_starters = data_build.get("starters", [])
        ids_finales = data_build.get("finales", [])
        ids_runas = data_build.get("runas", [])
        
        self.lbl_visual_titulo.config(text=f"Meta Build & Runas para {campeon}", font=("Helvetica", 12, "bold"))
        for widget in self.frame_iconos_items.winfo_children(): widget.destroy()
        for widget in self.frame_iconos_runas.winfo_children(): widget.destroy()
        self.imagenes_cacheadas.clear()

        if ids_starters:
            fr_start = tk.Frame(self.frame_iconos_items, bg="#eef2f3")
            fr_start.pack(side="left", padx=10)
            tk.Label(fr_start, text="Iniciales", bg="#eef2f3", font=("Helvetica", 9, "bold")).pack()
            fr_img_start = tk.Frame(fr_start, bg="#eef2f3")
            fr_img_start.pack(pady=5)
            for idx, item_id in enumerate(ids_starters): self.renderizar_icono(item_id, "item", fr_img_start, 0, idx)

        if ids_starters and ids_finales: tk.Label(self.frame_iconos_items, text="➕", bg="#eef2f3", font=("Helvetica", 14)).pack(side="left", padx=5)

        if ids_finales:
            fr_final = tk.Frame(self.frame_iconos_items, bg="#eef2f3")
            fr_final.pack(side="left", padx=10)
            tk.Label(fr_final, text="Build en Orden de Compra", bg="#eef2f3", font=("Helvetica", 9, "bold")).pack()
            fr_img_final = tk.Frame(fr_final, bg="#eef2f3")
            fr_img_final.pack(pady=5)
            for idx, item_id in enumerate(ids_finales): self.renderizar_icono(item_id, "item", fr_img_final, 0, idx)

        if ids_runas:
            fr_runas = tk.Frame(self.frame_iconos_runas, bg="#eef2f3")
            fr_runas.pack()
            tk.Label(fr_runas, text="Runas Recomendadas", bg="#eef2f3", font=("Helvetica", 9, "bold")).pack()
            fr_img_runas = tk.Frame(fr_runas, bg="#eef2f3")
            fr_img_runas.pack(pady=5)
            self.renderizar_runas_vertical(ids_runas, fr_img_runas) # Usando la nueva función

    def actualizar_listas_counter(self, event=None):
        rol = self.cb_rol_counter.get()
        campeones_del_rol = obtener_campeones_por_rol(rol)
        campeones_del_rol.sort()
        if not campeones_del_rol: campeones_del_rol = self.nombres_campeones_global
        self.cb_enemigo['values'] = campeones_del_rol
        if campeones_del_rol: self.cb_enemigo.current(0)

    def actualizar_listas_ia(self, event=None):
        rol = self.cb_ia_rol.get()
        campeones_del_rol = obtener_campeones_por_rol(rol)
        campeones_del_rol.sort()
        if not campeones_del_rol: campeones_del_rol = self.nombres_campeones_global
        self.cb_ia_aliado['values'] = campeones_del_rol
        self.cb_ia_enemigo['values'] = campeones_del_rol
        if len(campeones_del_rol) >= 2:
            self.cb_ia_aliado.current(0)
            self.cb_ia_enemigo.current(1)
        elif campeones_del_rol:
            self.cb_ia_aliado.current(0)
            self.cb_ia_enemigo.current(0)

    def armar_tab_ia(self, frame):
        frame.configure(padding=20)
        tk.Label(frame, text="Selecciona el enfrentamiento para predecir", font=("Helvetica", 10, "italic")).pack(pady=10)
        controles = tk.Frame(frame)
        controles.pack(pady=20)
        tk.Label(controles, text="Línea:").grid(row=0, column=2, pady=(0, 20))
        self.cb_ia_rol = ttk.Combobox(controles, values=self.roles, state="readonly")
        self.cb_ia_rol.current(0)
        self.cb_ia_rol.grid(row=1, column=2, pady=(0, 20))
        self.cb_ia_rol.bind("<<ComboboxSelected>>", self.actualizar_listas_ia)
        tk.Label(controles, text="Tu Campeón:").grid(row=2, column=0, padx=10)
        self.cb_ia_aliado = ttk.Combobox(controles, state="readonly")
        self.cb_ia_aliado.grid(row=2, column=1)
        tk.Label(controles, text="VS", font=("Helvetica", 12, "bold"), fg="red").grid(row=2, column=2, padx=20)
        tk.Label(controles, text="Enemigo:").grid(row=2, column=3, padx=10)
        self.cb_ia_enemigo = ttk.Combobox(controles, state="readonly")
        self.cb_ia_enemigo.grid(row=2, column=4)
        btn_predecir = tk.Button(frame, text="⚡ Ejecutar Predicción IA", bg="#d90429", fg="white", font=("Helvetica", 11, "bold"), command=self.predecir_ia)
        btn_predecir.pack(pady=20)
        self.lbl_resultado_ia = tk.Label(frame, text="", font=("Helvetica", 14))
        self.lbl_resultado_ia.pack(pady=10)

    def predecir_ia(self):
        rol = self.cb_ia_rol.get()
        aliado = self.cb_ia_aliado.get()
        enemigo = self.cb_ia_enemigo.get()
        if not aliado or not enemigo:
            self.lbl_resultado_ia.config(text="Selecciona ambos campeones.")
            return
        if rol not in modelo_1v1:
            self.lbl_resultado_ia.config(text="Modelo no disponible para este rol.")
            return
        modelo = modelo_1v1[rol]
        n = len(self.nombres_campeones_global)
        X = np.zeros(n * 2)
        if aliado in self.nombres_campeones_global: X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global: X[n + self.nombres_campeones_global.index(enemigo)] = 1
        prob = modelo.predict_proba(X.reshape(1, -1))[0][1] * 100
        self.lbl_resultado_ia.config(text=f"Victoria estimada: {prob:.1f}%")

if __name__ == "__main__":
    root = tk.Tk()
    app = LoLRecommenderApp(root)
    root.mainloop()