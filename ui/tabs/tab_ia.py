"""Pestania SIMULADOR 1v1 (IA). Interfaz nativa Qt (sin HTML) con stats de ambos
campeones, barras comparativas, datos reales de BD, swap de matchup y consejos pro."""

from ui.contexto import *


# Mapas de texto -> valor numerico (compartidos por barras y tarjetas)
_EARLY_VAL = {"weak": 1, "neutral": 2, "strong": 3}
_SCALE_VAL = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
_PROFILE_VAL = {"poke": 1, "dps": 2, "mixed": 2, "burst": 3}

# Texto legible (capitalizado) para mostrar en las tarjetas de stats
_PERFIL_DISPLAY = {"burst": "Burst", "dps": "DPS", "poke": "Poke", "mixed": "Mixto"}
_ESCALADO_DISPLAY = {"early": "Temprano", "mid": "Medio", "late": "Tardío", "hyper": "Hyper"}

# Color por sentimiento de los insights de "QUÉ VE LA IA"
_SENT_COLOR = {"good": GREEN_WR, "bad": RED_WR, "scale": YELLOW_WR, "neutral": TEXT_WHITE}

# Filas de la tarjeta de stats de cada campeon: (clave interna, etiqueta visible)
_FILAS_STATS = [
    ("clase", "Clase"),
    ("subclase", "Subclase"),
    ("dano", "Daño"),
    ("perfil", "Perfil"),
    ("escalado", "Escalado"),
    ("dificultad", "Dificultad"),
    ("wr", "WR Global"),
]

# Barras comparativas (tira y afloja): (atributo, etiqueta)
_SPEC_BARRAS = [
    ("barra_cc", "CC"),
    ("barra_movilidad", "Movilidad"),
    ("barra_early", "Early"),
    ("barra_escalado", "Escalado"),
    ("barra_dano", "Daño"),
]


class IATabMixin:
    def armar_tab_ia(self):
        layout = QVBoxLayout(self.tab_ia)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ===== CONFIGURACION DEL MATCHUP =====
        panel_ia, l_ia = self.crear_panel("CONFIGURACIÓN DEL MATCHUP")
        ctrls = QHBoxLayout()
        ctrls.setSpacing(8)
        self.cb_ia_rol = QComboBox()
        self.cb_ia_aliado = QComboBox()
        self.cb_ia_enemigo = QComboBox()
        ctrls.addWidget(QLabel("Línea:"))
        ctrls.addWidget(self.cb_ia_rol)
        ctrls.addWidget(QLabel("Tu Pick:"))
        ctrls.addWidget(self.cb_ia_aliado, 1)

        # Boton swap (dar vuelta el matchup)
        btn_swap = QPushButton("⇄")
        btn_swap.setToolTip("Intercambiar campeones y recalcular")
        btn_swap.setFixedWidth(38)
        btn_swap.setStyleSheet(f"""
            QPushButton {{ background-color: {BG_CARD}; color: {ACCENT_RED}; border: 1px solid {ACCENT_RED};
                           border-radius: 6px; font-weight: bold; font-size: 15px; padding: 6px; }}
            QPushButton:hover {{ background-color: {ACCENT_RED}; color: white; }}
        """)
        btn_swap.clicked.connect(self.intercambiar_picks_1v1)
        ctrls.addWidget(btn_swap)

        ctrls.addWidget(self.cb_ia_enemigo, 1)
        self.cb_ia_rol.addItems(UI_ROLES)
        self.cb_ia_rol.currentTextChanged.connect(self.actualizar_listas_ia)

        btn_simular = QPushButton("SIMULAR ENFRENTAMIENTO")
        btn_simular.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_RED}; color: white; border: none; border-radius: 6px;
                           font-weight: bold; font-size: 11px; padding: 8px 16px; }}
            QPushButton:hover {{ background-color: {HOVER_GLOW}; }}
        """)
        btn_simular.clicked.connect(self.predecir_ia)
        ctrls.addWidget(btn_simular)

        l_ia.addLayout(ctrls)
        layout.addWidget(panel_ia)

        # Caches de sesion para evitar relag de BD al re-simular / hacer swap
        self._cache_wr_global = {}
        self._cache_counters = {}

        # ===== AREA DE RESULTADOS (scrollable para no clipear nunca) =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        cont = QWidget()
        cont.setStyleSheet("background: transparent;")
        l_cont = QVBoxLayout(cont)
        l_cont.setContentsMargins(0, 0, 0, 0)
        l_cont.setSpacing(8)

        # ----- HUD: 3 columnas (aliado | centro | enemigo) -----
        hud_panel, l_hud = self.crear_panel("RESULTADO PREDICTIVO (IA)")
        l_hud.setAlignment(Qt.AlignTop)

        batalla_layout = QHBoxLayout()
        batalla_layout.setSpacing(16)

        # Columna 1: Aliado
        col_aliado, self.img_aliado_1v1, self.lbl_nombre_aliado_1v1, self.stats_aliado = \
            self._crear_columna_campeon(GREEN_WR, "#0a1a0f")
        batalla_layout.addLayout(col_aliado, 1)

        # Columna 2: Centro
        col_centro = QVBoxLayout()
        col_centro.setSpacing(6)
        col_centro.setAlignment(Qt.AlignCenter)

        self.lbl_wr_1v1 = QLabel("50.0%")
        self.lbl_wr_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 42px; color: {YELLOW_WR};")
        col_centro.addWidget(self.lbl_wr_1v1)

        self.lbl_nivel_1v1 = QLabel("Selecciona campeones")
        self.lbl_nivel_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nivel_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: bold;")
        col_centro.addWidget(self.lbl_nivel_1v1)

        self.lbl_wr_real_1v1 = QLabel("")
        self.lbl_wr_real_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        col_centro.addWidget(self.lbl_wr_real_1v1)

        # Barras comparativas (tira y afloja)
        barras_frame = QFrame()
        barras_frame.setStyleSheet(f"background-color: {BG_CARD}; border-radius: 6px;")
        barras_layout = QVBoxLayout(barras_frame)
        barras_layout.setSpacing(5)
        barras_layout.setContentsMargins(10, 8, 10, 8)

        leyenda = QLabel("◄ TÚ          RIVAL ►")
        leyenda.setAlignment(Qt.AlignCenter)
        leyenda.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8px;")
        barras_layout.addWidget(leyenda)

        self.barras_1v1 = {}  # attr -> (bar, lbl_val_a, lbl_val_e)
        for attr, etiqueta in _SPEC_BARRAS:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(etiqueta)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-weight: bold;")
            lbl.setFixedWidth(70)
            row.addWidget(lbl)
            lbl_a = QLabel("-")
            lbl_a.setStyleSheet(f"color: {GREEN_WR}; font-size: 10px; font-weight: bold;")
            lbl_a.setFixedWidth(20)
            lbl_a.setAlignment(Qt.AlignCenter)
            row.addWidget(lbl_a)
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(50)
            bar.setTextVisible(False); bar.setFixedHeight(12)
            bar.setStyleSheet(self._estilo_barra_comparativa(50))
            row.addWidget(bar, 1)
            lbl_e = QLabel("-")
            lbl_e.setStyleSheet(f"color: {RED_WR}; font-size: 10px; font-weight: bold;")
            lbl_e.setFixedWidth(20)
            lbl_e.setAlignment(Qt.AlignCenter)
            row.addWidget(lbl_e)
            setattr(self, attr, bar)
            self.barras_1v1[attr] = (bar, lbl_a, lbl_e)
            barras_layout.addLayout(row)

        col_centro.addWidget(barras_frame)
        batalla_layout.addLayout(col_centro, 2)

        # Columna 3: Enemigo
        col_enemigo, self.img_enemigo_1v1, self.lbl_nombre_enemigo_1v1, self.stats_enemigo = \
            self._crear_columna_campeon(RED_WR, "#1a0a0f")
        batalla_layout.addLayout(col_enemigo, 1)

        l_hud.addLayout(batalla_layout)
        l_cont.addWidget(hud_panel)

        # ----- QUE VE LA IA -----
        panel_ins, l_ins = self.crear_panel("QUÉ VE LA IA")
        self.layout_insights = QVBoxLayout()
        self.layout_insights.setSpacing(4)
        self._lbl_insights_placeholder = QLabel("Selecciona los campeones y presiona Simular.")
        self._lbl_insights_placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self.layout_insights.addWidget(self._lbl_insights_placeholder)
        l_ins.addLayout(self.layout_insights)
        l_cont.addWidget(panel_ins)

        # ----- CONSEJOS PROFESIONALES -----
        panel_con, l_con = self.crear_panel("CONSEJOS PROFESIONALES")
        self.layout_consejos = QVBoxLayout()
        self.layout_consejos.setSpacing(4)
        l_con.addLayout(self.layout_consejos)
        l_cont.addWidget(panel_con)

        l_cont.addStretch(1)
        scroll.setWidget(cont)
        layout.addWidget(scroll, 1)

        self.actualizar_listas_ia(UI_ROLES[0])

    def _crear_columna_campeon(self, color_acento, bg_card):
        """Construye una columna de campeon: imagen + nombre + tarjeta de stats.

        Devuelve (layout, img_label, nombre_label, dict_de_labels_de_valor).
        """
        col = QVBoxLayout()
        col.setAlignment(Qt.AlignTop)
        col.setSpacing(6)

        fr = QFrame()
        fr.setObjectName("BuildCard")
        fr.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {color_acento}; border-radius: 10px; padding: 8px; background-color: {bg_card}; }}")
        fr.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        l_fr = QVBoxLayout(fr)
        l_fr.setAlignment(Qt.AlignTop)
        l_fr.setSpacing(4)

        img = QLabel()
        img.setAlignment(Qt.AlignCenter)
        img.setFixedSize(96, 96)
        l_fr.addWidget(img, alignment=Qt.AlignCenter)

        nombre = QLabel("--")
        nombre.setAlignment(Qt.AlignCenter)
        nombre.setStyleSheet(f"color: {color_acento}; font-weight: bold; font-size: 12px;")
        l_fr.addWidget(nombre)

        # Tarjeta de stats (grid)
        grid = QGridLayout()
        grid.setVerticalSpacing(3)
        grid.setHorizontalSpacing(8)
        grid.setContentsMargins(2, 6, 2, 2)
        labels = {}
        for fila, (clave, etiqueta) in enumerate(_FILAS_STATS):
            lbl_k = QLabel(etiqueta)
            lbl_k.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
            lbl_v = QLabel("--")
            lbl_v.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 10px; font-weight: bold;")
            lbl_v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl_v.setWordWrap(True)
            grid.addWidget(lbl_k, fila, 0, Qt.AlignLeft)
            grid.addWidget(lbl_v, fila, 1)
            labels[clave] = lbl_v
        grid.setColumnStretch(1, 1)
        l_fr.addLayout(grid)

        col.addWidget(fr)
        col.addStretch(1)
        return col, img, nombre, labels

    def _estilo_barra_comparativa(self, valor):
        """Estilo para barras de tira y afloja: >50 verde (aliado gana), <50 rojo (enemigo gana)."""
        if valor >= 50:
            return f"""
                QProgressBar {{ background-color: #3b1018; border: 1px solid #5a1a28; border-radius: 4px; }}
                QProgressBar::chunk {{ background-color: {GREEN_WR}; border-radius: 3px; }}
            """
        else:
            return f"""
                QProgressBar {{ background-color: {BG_DARK}; border: 1px solid #211a28; border-radius: 4px; }}
                QProgressBar::chunk {{ background-color: {RED_WR}; border-radius: 3px; }}
            """

    def _limpiar_layout(self, layout):
        """Elimina todos los widgets de un layout (para repoblar insights/consejos)."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def actualizar_listas_counter(self, value):
        if not value or value not in ROL_TO_API:
            return
        champs = obtener_campeones_por_rol(ROL_TO_API[value], min_partidas=20)
        self.cb_enemigo.clear()
        self.cb_enemigo.addItems(champs)

    def actualizar_listas_ia(self, value):
        if not value or value not in ROL_TO_API:
            return
        champs = obtener_campeones_por_rol(ROL_TO_API[value], min_partidas=20)
        self.cb_ia_aliado.clear()
        self.cb_ia_enemigo.clear()
        self.cb_ia_aliado.addItems(champs)
        self.cb_ia_enemigo.addItems(champs)
        if len(champs) >= 2: self.cb_ia_enemigo.setCurrentText(champs[1])

    def intercambiar_picks_1v1(self):
        """Da vuelta el matchup: intercambia aliado <-> enemigo y recalcula."""
        a = self.cb_ia_aliado.currentText()
        e = self.cb_ia_enemigo.currentText()
        if not a or not e:
            return
        self.cb_ia_aliado.setCurrentText(e)
        self.cb_ia_enemigo.setCurrentText(a)
        self.predecir_ia()

    def _wr_global_cacheado(self, campeon, rol_api):
        """obtener_winrate_global memoizado por sesion (evita relag en swap)."""
        key = (campeon, rol_api)
        if key not in self._cache_wr_global:
            try:
                self._cache_wr_global[key] = obtener_winrate_global(campeon, rol_api)
            except Exception:
                self._cache_wr_global[key] = (None, 0)
        return self._cache_wr_global[key]

    def _counters_cacheado(self, rol_api, enemigo):
        """obtener_counters memoizado por sesion (evita relag en swap)."""
        key = (rol_api, enemigo)
        if key not in self._cache_counters:
            try:
                self._cache_counters[key] = obtener_counters(rol_api, enemigo, min_partidas=10)
            except Exception:
                self._cache_counters[key] = []
        return self._cache_counters[key]

    def _rellenar_tarjeta_stats(self, labels, campeon, rol_api, color_acento):
        """Rellena la tarjeta de stats de un campeon a partir de sus tags + BD."""
        try:
            tag = obtener_tag(campeon)
        except Exception:
            tag = {}
        labels["clase"].setText(tag.get("champion_class", "?"))
        labels["subclase"].setText(tag.get("sub_class", "?") or "—")
        labels["dano"].setText(tag.get("damage_type", "?"))
        perfil = tag.get("damage_profile", "?")
        labels["perfil"].setText(_PERFIL_DISPLAY.get(perfil, perfil.capitalize()))
        escalado = tag.get("scaling", "?")
        labels["escalado"].setText(_ESCALADO_DISPLAY.get(escalado, escalado.capitalize()))
        dif = tag.get("difficulty", 2) or 2
        labels["dificultad"].setText("★" * int(dif) + "☆" * (3 - int(dif)))
        wr, partidas = self._wr_global_cacheado(campeon, rol_api)
        if wr is not None:
            wr_color = GREEN_WR if wr >= 50 else RED_WR
            labels["wr"].setText(f"{wr}% ({partidas})")
            labels["wr"].setStyleSheet(f"color: {wr_color}; font-size: 10px; font-weight: bold;")
        else:
            labels["wr"].setText("—")
            labels["wr"].setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: bold;")

    def predecir_ia(self):
        rol_api = ROL_TO_API[self.cb_ia_rol.currentText()]
        aliado = self.cb_ia_aliado.currentText()
        enemigo = self.cb_ia_enemigo.currentText()

        if not aliado or not enemigo or not modelo_1v1.get(rol_api): return

        # ─── Imagenes y nombres ───
        ruta_al = self.descargar_imagen(aliado, "champ")
        ruta_en = self.descargar_imagen(enemigo, "champ")
        if ruta_al: self.img_aliado_1v1.setPixmap(QPixmap(ruta_al).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if ruta_en: self.img_enemigo_1v1.setPixmap(QPixmap(ruta_en).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.lbl_nombre_aliado_1v1.setText(self._nombre_display(aliado))
        self.lbl_nombre_enemigo_1v1.setText(self._nombre_display(enemigo))

        # ─── Tarjetas de stats (ambos lados) ───
        self._rellenar_tarjeta_stats(self.stats_aliado, aliado, rol_api, GREEN_WR)
        self._rellenar_tarjeta_stats(self.stats_enemigo, enemigo, rol_api, RED_WR)

        # === FEATURE ENGINEERING: mismo vector que en entrenamiento ===
        n = len(self.nombres_campeones_global)
        N_COMP = 15
        X = np.zeros(n * 2 + N_COMP)
        if aliado in self.nombres_campeones_global:
            X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global:
            X[n + self.nombres_campeones_global.index(enemigo)] = 1
        try:
            feats = extraer_features_comparativas(aliado, enemigo)
            X[n * 2:] = feats
        except Exception: pass

        # Prediccion IA cruda
        prob = modelo_1v1[rol_api].predict_proba(X.reshape(1, -1))[0][1] * 100

        # === DATOS REALES DE LA DB ===
        counters = self._counters_cacheado(rol_api, enemigo)
        wr_real = None
        partidas_real = 0
        for c_name, wr, p in counters:
            if c_name == aliado:
                wr_real = wr
                partidas_real = p
                break

        # === FUSION Y AMPLIFICACION MATEMATICA ===
        if wr_real is not None:
            prob_base = (prob * 0.4) + (wr_real * 0.6)
        else:
            prob_base = prob
        prob_final = 50 + ((prob_base - 50) * 1.8)
        prob_final = max(0, min(100, prob_final))

        # === NIVEL DE MATCHUP ===
        if prob_final > 54:
            nivel_color, nivel_icono, nivel_texto = GREEN_WR, "🔥", "HARD COUNTER (Ventaja Absoluta)"
        elif prob_final >= 51.5:
            nivel_color, nivel_icono, nivel_texto = GREEN_WR, "✅", "VENTAJA LIGERA"
        elif prob_final >= 48.5:
            nivel_color, nivel_icono, nivel_texto = YELLOW_WR, "⚔️", "MATCHUP DE HABILIDAD (50/50)"
        else:
            nivel_color, nivel_icono, nivel_texto = RED_WR, "⚠️", "MATCHUP DESFAVORABLE"

        self.lbl_wr_1v1.setText(f"{prob_final:.1f}%")
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 42px; color: {nivel_color};")
        self.lbl_nivel_1v1.setText(f"{nivel_icono} {nivel_texto}")
        self.lbl_nivel_1v1.setStyleSheet(f"color: {nivel_color}; font-size: 12px; font-weight: bold;")

        if wr_real is not None:
            real_color = GREEN_WR if wr_real >= 50 else RED_WR
            self.lbl_wr_real_1v1.setText(f"WR Real: {wr_real}% ({partidas_real} partidas)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {real_color}; font-size: 10px;")
        else:
            self.lbl_wr_real_1v1.setText("(sin datos reales en BD)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")

        # === BARRAS COMPARATIVAS (TIRA Y AFLOJA) ===
        try:
            t_a = obtener_tag(aliado)
            t_e = obtener_tag(enemigo)
        except Exception:
            t_a, t_e = {}, {}

        # (atributo, valor_aliado, valor_enemigo, texto_tooltip)
        cc_a, cc_e = t_a.get("cc_level", 1), t_e.get("cc_level", 1)
        mob_a, mob_e = t_a.get("mobility", 2), t_e.get("mobility", 2)
        early_a = _EARLY_VAL.get(t_a.get("early_power", "neutral"), 2)
        early_e = _EARLY_VAL.get(t_e.get("early_power", "neutral"), 2)
        scale_a = _SCALE_VAL.get(t_a.get("scaling", "mid"), 2)
        scale_e = _SCALE_VAL.get(t_e.get("scaling", "mid"), 2)
        dano_a = _PROFILE_VAL.get(t_a.get("damage_profile", "dps"), 2)
        dano_e = _PROFILE_VAL.get(t_e.get("damage_profile", "dps"), 2)

        valores_barras = {
            "barra_cc": (cc_a, cc_e),
            "barra_movilidad": (mob_a, mob_e),
            "barra_early": (early_a, early_e),
            "barra_escalado": (scale_a, scale_e),
            "barra_dano": (dano_a, dano_e),
        }
        for attr, (va, ve) in valores_barras.items():
            try:
                bar, lbl_a, lbl_e = self.barras_1v1[attr]
                val = round((va / max(0.1, va + ve)) * 100)
                bar.setValue(val)
                bar.setStyleSheet(self._estilo_barra_comparativa(val))
                bar.setToolTip(f"{aliado}: {va}  |  {enemigo}: {ve}")
                lbl_a.setText(str(va))
                lbl_e.setText(str(ve))
            except Exception as ex:
                print(f"[predecir_ia] barra {attr}: {ex}")

        # === QUE VE LA IA (nativo) ===
        self._limpiar_layout(self.layout_insights)
        try:
            insights = interpretar_features(aliado, enemigo)
        except Exception:
            insights = [("Análisis no disponible para este matchup.", "neutral")]
        for texto, sent in insights:
            color = _SENT_COLOR.get(sent, TEXT_WHITE)
            lbl = QLabel(f"•  {texto}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 0;")
            self.layout_insights.addWidget(lbl)

        # === CONSEJOS PROFESIONALES (nativo) ===
        self._limpiar_layout(self.layout_consejos)
        try:
            consejos = consejos_matchup(aliado, enemigo, rol_api)
        except Exception as ex:
            print(f"[predecir_ia] consejos: {ex}")
            consejos = ["Consejos no disponibles para este matchup."]
        for tip in consejos:
            lbl = QLabel(f"▸  {tip}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; padding: 2px 0;")
            self.layout_consejos.addWidget(lbl)
