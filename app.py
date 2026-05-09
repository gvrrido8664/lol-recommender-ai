import tkinter as tk
from tkinter import ttk, messagebox
import pickle
import os
import requests
from io import BytesIO
from PIL import Image, ImageTk
import numpy as np

from src.db_manager import DATA_DIR
from src.riot_api import cargar_campeones, obtener_version_actual
from src.recomendador import obtener_counters, obtener_top_items, obtener_campeones_por_rol

# Rutas para guardar las imágenes y no descargarlas cada vez
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "items")
os.makedirs(ASSETS_DIR, exist_ok=True)

class LoLRecommenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LoL Recommender V2 - Inteligencia Artificial")
        self.root.geometry("850x650") # Ventana más alta para el panel visual
        self.root.configure(padx=20, pady=20)

        print("Cargando base de datos de campeones...")
        self.champs_dict = cargar_campeones()
        nombres_sucios = [data["nombre"] for data in self.champs_dict.values()]
        self.nombres_campeones_global = sorted(list(set(nombres_sucios)))
        self.version_juego = obtener_version_actual()
        self.roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

        self.modelo_ia = None
        modelo_path = os.path.join(DATA_DIR, "modelo_ia.pkl")
        if os.path.exists(modelo_path):
            with open(modelo_path, "rb") as f:
                self.modelo_ia = pickle.load(f)
            print("Cerebro IA cargado.")
            
        # Diccionario temporal para guardar las builds de la búsqueda actual
        self.builds_actuales = {}
        # Para evitar que Python borre las imágenes de la memoria
        self.imagenes_cacheadas = []

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

    # ==========================================
    # PESTAÑA 1: COUNTERS Y BUILD VISUAL
    # ==========================================
    def renderizar_icono(self, item_id, frame_padre, fila, columna):
        """Función auxiliar para descargar y dibujar un solo ícono."""
        ruta_local = os.path.join(ASSETS_DIR, f"{item_id}.png")
        if not os.path.exists(ruta_local):
            try:
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/item/{item_id}.png"
                resp = requests.get(url)
                resp.raise_for_status()
                imagen = Image.open(BytesIO(resp.content))
                imagen.save(ruta_local)
            except:
                return # Si falla internet, ignoramos la imagen
        else:
            imagen = Image.open(ruta_local)

        # 48x48 es un tamaño ideal para que quepan 8 imágenes sin desbordar
        imagen = imagen.resize((48, 48), Image.Resampling.LANCZOS)
        foto = ImageTk.PhotoImage(imagen)
        self.imagenes_cacheadas.append(foto)
        
        lbl_img = tk.Label(frame_padre, image=foto, bg="#eef2f3", bd=2, relief="solid")
        lbl_img.grid(row=fila, column=columna, padx=4)
    
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

        # Tabla (Ahora sin la enorme columna de texto de items)
        columnas = ("Campeón Aliado", "Winrate %", "Partidas")
        self.tree_counters = ttk.Treeview(frame, columns=columnas, show="headings", height=5)
        self.tree_counters.heading("Campeón Aliado", text="Campeón Aliado")
        self.tree_counters.column("Campeón Aliado", width=150, anchor="center")
        self.tree_counters.heading("Winrate %", text="Winrate %")
        self.tree_counters.column("Winrate %", width=100, anchor="center")
        self.tree_counters.heading("Partidas", text="Partidas Analizadas")
        self.tree_counters.column("Partidas", width=150, anchor="center")
        self.tree_counters.pack(fill='x', pady=10)

        # 🚀 EVENTO: Detectar cuando haces clic en la tabla
        self.tree_counters.bind("<<TreeviewSelect>>", self.mostrar_build_visual)

        # Panel Inferior para los Íconos
        self.panel_visual = tk.Frame(frame, bg="#eef2f3", bd=2, relief="groove")
        self.panel_visual.pack(fill='both', expand=True, pady=10, padx=5)
        
        self.lbl_visual_titulo = tk.Label(self.panel_visual, text="Haz clic en un campeón para ver su Build de 6 objetos", bg="#eef2f3", font=("Helvetica", 11, "italic"))
        self.lbl_visual_titulo.pack(pady=10)
        
        self.frame_iconos = tk.Frame(self.panel_visual, bg="#eef2f3")
        self.frame_iconos.pack(pady=10)

    def buscar_counters(self):
        rol = self.cb_rol_counter.get()
        enemigo = self.cb_enemigo.get()
        self.builds_actuales.clear() 

        for item in self.tree_counters.get_children():
            self.tree_counters.delete(item)
            
        self.lbl_visual_titulo.config(text="Haz clic en un campeón para ver su Build detallada")
        for widget in self.frame_iconos.winfo_children():
            widget.destroy()

        resultados = obtener_counters(rol, enemigo, min_partidas=15)
        if not resultados:
            messagebox.showinfo("Sin datos", f"No hay datos contra {enemigo} en {rol}.")
            return

        for champ, winrate, partidas in resultados[:5]:
            # Ahora recibimos las dos listas limpias
            ids_starters, ids_finales = obtener_top_items(champ, rol)
            
            # Guardamos ambas listas en el diccionario
            self.builds_actuales[champ] = {
                "starters": ids_starters,
                "finales": ids_finales
            }
            self.tree_counters.insert("", "end", values=(champ, f"{winrate}%", partidas))

    def mostrar_build_visual(self, event):
        seleccion = self.tree_counters.selection()
        if not seleccion: return
        
        item_tabla = self.tree_counters.item(seleccion[0])
        campeon = item_tabla['values'][0]
        data_build = self.builds_actuales.get(campeon, {})
        
        ids_starters = data_build.get("starters", [])
        ids_finales = data_build.get("finales", [])
        
        self.lbl_visual_titulo.config(text=f"Build Analítica para {campeon}", font=("Helvetica", 12, "bold"))
        
        for widget in self.frame_iconos.winfo_children():
            widget.destroy()
        self.imagenes_cacheadas.clear()

        # --- SECCIÓN 1: Items Iniciales ---
        if ids_starters:
            fr_start = tk.Frame(self.frame_iconos, bg="#eef2f3")
            fr_start.pack(side="left", padx=10)
            tk.Label(fr_start, text="Iniciales", bg="#eef2f3", font=("Helvetica", 9, "bold")).pack()
            fr_img_start = tk.Frame(fr_start, bg="#eef2f3")
            fr_img_start.pack(pady=5)
            for idx, item_id in enumerate(ids_starters):
                self.renderizar_icono(item_id, fr_img_start, 0, idx)

        # --- Separador Visual ---
        if ids_starters and ids_finales:
            tk.Label(self.frame_iconos, text="➕", bg="#eef2f3", font=("Helvetica", 14)).pack(side="left", padx=5)

        # --- SECCIÓN 2: Build Completa ---
        if ids_finales:
            fr_final = tk.Frame(self.frame_iconos, bg="#eef2f3")
            fr_final.pack(side="left", padx=10)
            tk.Label(fr_final, text="Build Completa (Final)", bg="#eef2f3", font=("Helvetica", 9, "bold")).pack()
            fr_img_final = tk.Frame(fr_final, bg="#eef2f3")
            fr_img_final.pack(pady=5)
            for idx, item_id in enumerate(ids_finales):
                self.renderizar_icono(item_id, fr_img_final, 0, idx)
                
    # ==========================================
    # PESTAÑA 2: IA (Sin cambios)
    # ==========================================
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
        if not self.modelo_ia:
            messagebox.showerror("Error", "El modelo de IA no está cargado.")
            return

        rol = self.cb_ia_rol.get()
        aliado = self.cb_ia_aliado.get()
        enemigo = self.cb_ia_enemigo.get()

        if rol not in self.modelo_ia:
            self.lbl_resultado_ia.config(text="⚠️ Sin entrenamiento para esta línea.", fg="orange")
            return

        datos_modelo = self.modelo_ia[rol]
        modelo = datos_modelo["model"]
        champs_conocidos = datos_modelo["champs"]

        if aliado not in champs_conocidos or enemigo not in champs_conocidos:
            self.lbl_resultado_ia.config(text="⚠️ Datos insuficientes para estos campeones.", fg="orange")
            return

        n = len(champs_conocidos)
        X_input = np.zeros((1, n * 2))
        X_input[0, champs_conocidos.index(aliado)] = 1
        X_input[0, n + champs_conocidos.index(enemigo)] = 1

        prob_victoria = modelo.predict_proba(X_input)[0][1] * 100 
        color = "green" if prob_victoria >= 50 else "red"
        self.lbl_resultado_ia.config(text=f"Probabilidad de victoria para {aliado}: {prob_victoria:.1f}%", fg=color)

if __name__ == "__main__":
    root = tk.Tk()
    app = LoLRecommenderApp(root)
    root.mainloop()