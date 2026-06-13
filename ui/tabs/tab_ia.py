"""Pestania SIMULADOR 1v1 (IA) con items, runas, hechizos y barras expandidas."""

from ui.contexto import *


class IATabMixin:
    def armar_tab_ia(self):
        layout = QVBoxLayout(self.tab_ia)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        panel_ia, l_ia = self.crear_panel("CONFIGURACION DEL MATCHUP")
        ctrls = QHBoxLayout()
        ctrls.setSpacing(6)
        self.cb_ia_rol = QComboBox()
        self.cb_ia_aliado = QComboBox()
        self.cb_ia_enemigo = QComboBox()
        ctrls.addWidget(QLabel("Linea:"))
        ctrls.addWidget(self.cb_ia_rol)
        ctrls.addWidget(QLabel("Tu Pick:"))
        ctrls.addWidget(self.cb_ia_aliado)

        sw_frame = QFrame()
        sw_frame.setFixedSize(48, 34)
        sw_frame.setStyleSheet(f"background-color: transparent; border: none;")
        sw_lay = QHBoxLayout(sw_frame)
        sw_lay.setContentsMargins(0, 0, 0, 0)
        sw_lay.setSpacing(0)
        for arrow, clr in [("←", GREEN_WR), ("→", RED_WR)]:
            btn = QPushButton(arrow)
            btn.setFixedSize(24, 34)
            btn.setToolTip("Intercambiar aliado / enemigo")
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {BG_CARD_HOVER}; color: {clr}; border: 1px solid {BORDER_SUBTLE};
                               border-radius: 2px; font-size: 14px; font-weight: bold; }}
                QPushButton:hover {{ background-color: {ACCENT_RED}; color: white; }}
            """)
            btn.clicked.connect(self._swap_matchup)
            sw_lay.addWidget(btn)
        ctrls.addWidget(sw_frame)

        lbl_vs = QLabel("VS")
        lbl_vs.setStyleSheet(f"color: {RED_WR}; font-weight: bold; font-size: 13px; margin: 0 2px;")
        ctrls.addWidget(lbl_vs)
        ctrls.addWidget(self.cb_ia_enemigo)
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
        ctrls.addStretch()

        l_ia.addLayout(ctrls)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        preset_row.addWidget(QLabel("Populares:"))
        for label, rol, a, e in self._presets():
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {BG_CARD}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE};
                               border-radius: 4px; padding: 4px 10px; font-size: 10px; }}
                QPushButton:hover {{ background-color: {BG_CARD_HOVER}; color: {TEXT_WHITE}; }}
            """)
            btn.clicked.connect(lambda checked, r=rol, al=a, en=e: self._preset_matchup(r, al, en))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        l_ia.addLayout(preset_row)

        layout.addWidget(panel_ia)

        # ===== HUD DE RESULTADO =====
        hud_panel, l_hud = self.crear_panel("RESULTADO PREDICTIVO (IA)")
        l_hud.setAlignment(Qt.AlignTop)
        l_hud.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }}")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setAlignment(Qt.AlignTop)
        scroll_lay.setSpacing(8)
        scroll_lay.setContentsMargins(0, 6, 0, 0)
        scroll.setWidget(scroll_content)
        l_hud.addWidget(scroll)

        batalla_layout = QHBoxLayout()
        batalla_layout.setSpacing(16)

        # Columna 1: Aliado
        col_aliado = QVBoxLayout()
        col_aliado.setAlignment(Qt.AlignCenter)
        col_aliado.setSpacing(4)
        fr_al = QFrame()
        fr_al.setObjectName("BuildCard")
        fr_al.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {GREEN_WR}; border-radius: 10px; padding: 8px; background-color: #0a1a0f; }}")
        l_al = QVBoxLayout(fr_al)
        l_al.setAlignment(Qt.AlignCenter)
        self.img_aliado_1v1 = QLabel()
        self.img_aliado_1v1.setAlignment(Qt.AlignCenter)
        self.img_aliado_1v1.setScaledContents(True)
        self.img_aliado_1v1.setMaximumSize(120, 120)
        self.img_aliado_1v1.setMinimumSize(60, 60)
        l_al.addWidget(self.img_aliado_1v1, alignment=Qt.AlignCenter)
        self.lbl_nombre_aliado_1v1 = QLabel("--")
        self.lbl_nombre_aliado_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nombre_aliado_1v1.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 11px;")
        l_al.addWidget(self.lbl_nombre_aliado_1v1)
        col_aliado.addWidget(fr_al)
        batalla_layout.addLayout(col_aliado, 1)

        # Columna 2: Centro
        col_centro = QVBoxLayout()
        col_centro.setSpacing(4)
        col_centro.setAlignment(Qt.AlignCenter)

        self.lbl_wr_1v1 = QLabel("50.0%")
        self.lbl_wr_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 38px; color: {YELLOW_WR};")
        col_centro.addWidget(self.lbl_wr_1v1)

        self.lbl_nivel_1v1 = QLabel("Selecciona campeones")
        self.lbl_nivel_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nivel_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        col_centro.addWidget(self.lbl_nivel_1v1)

        self.lbl_wr_real_1v1 = QLabel("")
        self.lbl_wr_real_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
        col_centro.addWidget(self.lbl_wr_real_1v1)

        self.lbl_confianza_1v1 = QLabel("")
        self.lbl_confianza_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_confianza_1v1.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 9px;")
        col_centro.addWidget(self.lbl_confianza_1v1)

        barras_frame = QFrame()
        barras_frame.setStyleSheet(f"background-color: {BG_CARD}; border-radius: 6px; padding: 8px;")
        barras_layout = QVBoxLayout(barras_frame)
        barras_layout.setSpacing(3)
        barras_layout.setContentsMargins(8, 6, 8, 6)

        self._barras_1v1 = {}
        for lbl_txt, bar_attr in [
            ("CC", "barra_cc"),
            ("Movilidad", "barra_movilidad"),
            ("Early Game", "barra_early"),
            ("Escalado", "barra_escalado"),
            ("Danio", "barra_dano"),
            ("Dificultad", "barra_dificultad"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-weight: bold;")
            lbl.setFixedWidth(72)
            row.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(50)
            bar.setTextVisible(False); bar.setFixedHeight(12)
            bar.setStyleSheet(self._estilo_barra_comparativa(50))
            setattr(self, bar_attr, bar)
            self._barras_1v1[bar_attr] = bar
            row.addWidget(bar, 1)
            barras_layout.addLayout(row)

        col_centro.addWidget(barras_frame)

        self.info_1v1_frame = QFrame()
        self.info_1v1_frame.setStyleSheet(f"background-color: transparent; padding: 2px 0;")
        self.info_1v1_layout = QHBoxLayout(self.info_1v1_frame)
        self.info_1v1_layout.setContentsMargins(0, 0, 0, 0)
        self.info_1v1_layout.setSpacing(0)
        col_centro.addWidget(self.info_1v1_frame)

        batalla_layout.addLayout(col_centro, 2)

        # Columna 3: Enemigo
        col_enemigo = QVBoxLayout()
        col_enemigo.setAlignment(Qt.AlignCenter)
        col_enemigo.setSpacing(4)
        fr_en = QFrame()
        fr_en.setObjectName("BuildCard")
        fr_en.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {RED_WR}; border-radius: 10px; padding: 8px; background-color: #1a0a0f; }}")
        l_en = QVBoxLayout(fr_en)
        l_en.setAlignment(Qt.AlignCenter)
        self.img_enemigo_1v1 = QLabel()
        self.img_enemigo_1v1.setAlignment(Qt.AlignCenter)
        self.img_enemigo_1v1.setScaledContents(True)
        self.img_enemigo_1v1.setMaximumSize(120, 120)
        self.img_enemigo_1v1.setMinimumSize(60, 60)
        l_en.addWidget(self.img_enemigo_1v1, alignment=Qt.AlignCenter)
        self.lbl_nombre_enemigo_1v1 = QLabel("--")
        self.lbl_nombre_enemigo_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nombre_enemigo_1v1.setStyleSheet(f"color: {RED_WR}; font-weight: bold; font-size: 11px;")
        l_en.addWidget(self.lbl_nombre_enemigo_1v1)
        col_enemigo.addWidget(fr_en)
        batalla_layout.addLayout(col_enemigo, 1)

        scroll_lay.addLayout(batalla_layout)

        # ===== CARDS DE RECOMENDACIONES =====
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self.fr_items_1v1 = QFrame()
        self.fr_items_1v1.setStyleSheet(f"background-color: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 8px;")
        self.ly_items_1v1 = QVBoxLayout(self.fr_items_1v1)
        self.ly_items_1v1.setSpacing(2)
        self.ly_items_1v1.setContentsMargins(6, 4, 6, 4)
        cards_row.addWidget(self.fr_items_1v1, 1)

        self.fr_runas_1v1 = QFrame()
        self.fr_runas_1v1.setStyleSheet(f"background-color: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 8px;")
        self.ly_runas_1v1 = QVBoxLayout(self.fr_runas_1v1)
        self.ly_runas_1v1.setSpacing(2)
        self.ly_runas_1v1.setContentsMargins(6, 4, 6, 4)
        cards_row.addWidget(self.fr_runas_1v1, 1)

        self.fr_spells_1v1 = QFrame()
        self.fr_spells_1v1.setStyleSheet(f"background-color: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 8px;")
        self.ly_spells_1v1 = QVBoxLayout(self.fr_spells_1v1)
        self.ly_spells_1v1.setSpacing(2)
        self.ly_spells_1v1.setContentsMargins(6, 4, 6, 4)
        cards_row.addWidget(self.fr_spells_1v1, 1)

        scroll_lay.addLayout(cards_row)

        # Analisis de la IA
        self.lbl_analisis_ia = QLabel("Selecciona los campeones y presiona Simular.")
        self.lbl_analisis_ia.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; padding: 12px; background-color: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px;")
        self.lbl_analisis_ia.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_analisis_ia.setWordWrap(True)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)
        self.lbl_analisis_ia.setMinimumHeight(80)
        scroll_lay.addWidget(self.lbl_analisis_ia)
        layout.addWidget(hud_panel, 1)

        self.actualizar_listas_ia(UI_ROLES[0])

    @staticmethod
    def _presets():
        return [
            ("Yasuo vs Zed", "MIDDLE", "Yasuo", "Zed"),
            ("Darius vs Garen", "TOP", "Darius", "Garen"),
            ("Ahri vs Yasuo", "MIDDLE", "Ahri", "Yasuo"),
            ("Caitlyn vs Jhin", "BOTTOM", "Caitlyn", "Jhin"),
            ("Lee Sin vs Viego", "JUNGLE", "Lee Sin", "Viego"),
        ]

    @staticmethod
    def _difficulty(val):
        return {1: "Facil", 2: "Media", 3: "Dificil"}.get(val, "?")

    def _preset_matchup(self, rol_api, aliado, enemigo):
        rol_ui = API_TO_ROL.get(rol_api, rol_api)
        idx = self.cb_ia_rol.findText(rol_ui)
        if idx >= 0:
            self.cb_ia_rol.setCurrentIndex(idx)
        QTimer.singleShot(50, lambda: self._set_champs(aliado, enemigo))

    def _set_champs(self, aliado, enemigo):
        idx_a = self.cb_ia_aliado.findText(aliado)
        idx_e = self.cb_ia_enemigo.findText(enemigo)
        if idx_a >= 0: self.cb_ia_aliado.setCurrentIndex(idx_a)
        if idx_e >= 0: self.cb_ia_enemigo.setCurrentIndex(idx_e)

    def _swap_matchup(self):
        a = self.cb_ia_aliado.currentText()
        e = self.cb_ia_enemigo.currentText()
        if a and e:
            self.cb_ia_aliado.setCurrentText(e)
            self.cb_ia_enemigo.setCurrentText(a)

    def _estilo_barra_comparativa(self, valor):
        if valor >= 50:
            return f"""
                QProgressBar {{ background-color: #3b1018; border: 1px solid #5a1a28; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {GREEN_WR}; border-radius: 2px; }}
            """
        else:
            return f"""
                QProgressBar {{ background-color: {BG_DARK}; border: 1px solid #211a28; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {RED_WR}; border-radius: 2px; }}
            """

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

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            elif item.layout(): self._clear_layout(item.layout())

    def predecir_ia(self):
        rol_api = ROL_TO_API[self.cb_ia_rol.currentText()]
        aliado = self.cb_ia_aliado.currentText()
        enemigo = self.cb_ia_enemigo.currentText()

        if not aliado or not enemigo or not modelo_1v1.get(rol_api): return

        # ─── Imagenes y nombres ───
        ruta_al = self.descargar_imagen(aliado, "champ")
        ruta_en = self.descargar_imagen(enemigo, "champ")
        if ruta_al: self.img_aliado_1v1.setPixmap(QPixmap(ruta_al).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if ruta_en: self.img_enemigo_1v1.setPixmap(QPixmap(ruta_en).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.lbl_nombre_aliado_1v1.setText(self._nombre_display(aliado))
        self.lbl_nombre_enemigo_1v1.setText(self._nombre_display(enemigo))

        # === FEATURE ENGINEERING ===
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

        prob = modelo_1v1[rol_api].predict_proba(X.reshape(1, -1))[0][1] * 100

        # === DATOS REALES DE LA DB ===
        counters = obtener_counters(rol_api, enemigo, min_partidas=10)
        wr_real = None
        partidas_real = 0
        for c_name, wr_val, p in counters:
            if c_name == aliado:
                wr_real = wr_val
                partidas_real = p
                break

        # === FUSION ===
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

        # === UI CENTRAL ===
        self.lbl_wr_1v1.setText(f"{prob_final:.1f}%")
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 38px; color: {nivel_color};")
        self.lbl_nivel_1v1.setText(f"{nivel_icono} {nivel_texto}")
        self.lbl_nivel_1v1.setStyleSheet(f"color: {nivel_color}; font-size: 11px; font-weight: bold;")

        if wr_real is not None:
            real_color = GREEN_WR if wr_real >= 50 else RED_WR
            self.lbl_wr_real_1v1.setText(f"WR Real: {wr_real:.0f}% ({partidas_real} partidas)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {real_color}; font-size: 9px;")
        else:
            self.lbl_wr_real_1v1.setText("(sin datos reales en BD)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")

        if partidas_real >= 50:
            self.lbl_confianza_1v1.setText("⬤⬤⬤ Confianza Alta")
            self.lbl_confianza_1v1.setStyleSheet(f"color: {GREEN_WR}; font-size: 9px;")
        elif partidas_real >= 10:
            self.lbl_confianza_1v1.setText("⬤⬤◯ Confianza Media")
            self.lbl_confianza_1v1.setStyleSheet(f"color: {YELLOW_WR}; font-size: 9px;")
        else:
            self.lbl_confianza_1v1.setText("⬤◯◯ Confianza Baja (estimacion IA)")
            self.lbl_confianza_1v1.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 9px;")

        # === BARRAS COMPARATIVAS (6 barras) ===
        t_a = obtener_tag(aliado)
        t_e = obtener_tag(enemigo)
        try:
            _EM = {"weak": 1, "neutral": 2, "strong": 3}
            _SM = {"early": 1, "mid": 2, "late": 3, "hyper": 4}

            def _set_bar(bar_attr, val_a, val_e, max_v):
                val = round((val_a / max(0.1, val_a + val_e)) * 100)
                bar = getattr(self, bar_attr, None)
                if bar:
                    bar.setValue(val)
                    bar.setStyleSheet(self._estilo_barra_comparativa(val))

            cc_a = t_a.get("cc_level", 1)
            cc_e = t_e.get("cc_level", 1)
            _set_bar("barra_cc", cc_a, cc_e, 5)

            mob_a = t_a.get("mobility", 2)
            mob_e = t_e.get("mobility", 2)
            _set_bar("barra_movilidad", mob_a, mob_e, 5)

            early_a = _EM.get(t_a.get("early_power", "neutral"), 2)
            early_e = _EM.get(t_e.get("early_power", "neutral"), 2)
            _set_bar("barra_early", early_a, early_e, 3)

            scale_a = _SM.get(t_a.get("scaling", "mid"), 2)
            scale_e = _SM.get(t_e.get("scaling", "mid"), 2)
            _set_bar("barra_escalado", scale_a, scale_e, 4)

            dmg_a_val = 5 if t_a.get("damage_type") == "HYBRID" else 4
            dmg_e_val = 5 if t_e.get("damage_type") == "HYBRID" else 4
            _set_bar("barra_dano", dmg_a_val, dmg_e_val, 5)

            diff_a = 4 - t_a.get("difficulty", 2)
            diff_e = 4 - t_e.get("difficulty", 2)
            _set_bar("barra_dificultad", diff_a, diff_e, 4)
        except Exception as e:
            print(f"[predecir_ia] Error en barras: {e}")
            for attr in self._barras_1v1:
                bar = getattr(self, attr, None)
                if bar:
                    bar.setValue(50)
                    bar.setStyleSheet(self._estilo_barra_comparativa(50))

        # === ITEMS ===
        self._clear_layout(self.ly_items_1v1)
        tit = QLabel(f"🛡️ Items vs {self._nombre_display(enemigo)}")
        tit.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 11px; background: transparent;")
        self.ly_items_1v1.addWidget(tit)
        try:
            items = obtener_items_situacionales(aliado, rol_api, [enemigo])
            if not items:
                _, fallback = obtener_top_items(aliado, rol_api)
                items = [{"id": iid, "nombre": ITEMS_DICT.get(str(iid), {}).get("nombre", iid), "prioridad": 3, "razon": "Build recomendado", "categoria": "core"}
                         for iid in fallback[:4] if ITEMS_DICT.get(str(iid))]
            for it in items[:4]:
                row = QHBoxLayout()
                row.setSpacing(4)
                iid = str(it.get("id", ""))
                icon_path = os.path.join(ITEMS_DIR, f"{iid}.png") if iid else None
                if icon_path and os.path.exists(icon_path):
                    ic = QLabel()
                    ic.setPixmap(QPixmap(icon_path).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    ic.setFixedSize(22, 22)
                    row.addWidget(ic)
                lbl = QLabel(it.get("nombre", "?")[:22])
                lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent;")
                if it.get("prioridad") == 1:
                    lbl.setStyleSheet(f"color: {RED_WR}; font-size: 10px; font-weight: bold; background: transparent;")
                lbl.setToolTip(f"{it.get('razon', '')} ({it.get('categoria', '')})")
                row.addWidget(lbl)
                row.addStretch()
                self.ly_items_1v1.addLayout(row)
        except Exception as e:
            err = QLabel("No disponible")
            err.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 10px;")
            self.ly_items_1v1.addWidget(err)
        self.ly_items_1v1.addStretch()

        # === RUNAS OPTIMAS ===
        self._clear_layout(self.ly_runas_1v1)
        tit_r = QLabel("📜 Runas optimas")
        tit_r.setStyleSheet(f"color: {ACCENT_TEAL}; font-weight: bold; font-size: 11px; background: transparent;")
        self.ly_runas_1v1.addWidget(tit_r)
        try:
            runas = obtener_top_runas(aliado, rol_api)
            for rid in runas[:5]:
                rname = RUNAS_DICT.get(str(rid), {}).get("nombre", f"Runa {rid}")
                row = QHBoxLayout()
                row.setSpacing(4)
                icon_path = os.path.join(RUNAS_DIR, f"{rid}.png")
                if os.path.exists(icon_path):
                    ic = QLabel()
                    ic.setPixmap(QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    ic.setFixedSize(20, 20)
                    row.addWidget(ic)
                lbl = QLabel(rname[:24])
                lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent;")
                row.addWidget(lbl)
                row.addStretch()
                self.ly_runas_1v1.addLayout(row)
        except Exception:
            err = QLabel("No disponible")
            err.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 10px;")
            self.ly_runas_1v1.addWidget(err)
        self.ly_runas_1v1.addStretch()

        # === HECHIZOS ===
        self._clear_layout(self.ly_spells_1v1)
        tit_s = QLabel("⚡ Hechizos")
        tit_s.setStyleSheet(f"color: #818cf8; font-weight: bold; font-size: 11px; background: transparent;")
        self.ly_spells_1v1.addWidget(tit_s)
        try:
            spells = obtener_top_hechizos(aliado, rol_api)
            for sid in spells[:2]:
                sname = SPELLS_DICT.get(int(sid), {}).get("nombre", f"Hechizo {sid}")
                row = QHBoxLayout()
                row.setSpacing(4)
                icon_path = os.path.join(SPELLS_DIR, f"{sid}.png")
                if os.path.exists(icon_path):
                    ic = QLabel()
                    ic.setPixmap(QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    ic.setFixedSize(20, 20)
                    row.addWidget(ic)
                lbl = QLabel(sname[:22])
                lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent;")
                row.addWidget(lbl)
                row.addStretch()
                self.ly_spells_1v1.addLayout(row)
        except Exception:
            err = QLabel("No disponible")
            err.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 10px;")
            self.ly_spells_1v1.addWidget(err)
        self.ly_spells_1v1.addStretch()

        # === CHAMPION INFO ROW (native) ===
        def _tag_lbl(text, color=TEXT_MUTED):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: 600; background: transparent;")
            return lbl

        self._clear_layout(self.info_1v1_layout)
        info_a = QHBoxLayout()
        info_a.setSpacing(2)
        info_a.addWidget(_tag_lbl(t_a.get('damage_type', '?'), ACCENT_TEAL))
        info_a.addWidget(_tag_lbl("|", TEXT_SUBTLE))
        info_a.addWidget(_tag_lbl(t_a.get('champion_class', '?'), GREEN_WR))
        info_a.addWidget(_tag_lbl("|", TEXT_SUBTLE))
        info_a.addWidget(_tag_lbl(self._difficulty(t_a.get('difficulty', 2)), TEXT_SECONDARY))
        self.info_1v1_layout.addLayout(info_a, 1)

        vs_lbl = QLabel("  VS  ")
        vs_lbl.setAlignment(Qt.AlignCenter)
        vs_lbl.setStyleSheet(f"color: {RED_WR}; font-size: 10px; font-weight: 800; background: transparent;")
        self.info_1v1_layout.addWidget(vs_lbl)

        info_e = QHBoxLayout()
        info_e.setSpacing(2)
        info_e.addWidget(_tag_lbl(t_e.get('damage_type', '?'), YELLOW_WR))
        info_e.addWidget(_tag_lbl("|", TEXT_SUBTLE))
        info_e.addWidget(_tag_lbl(t_e.get('champion_class', '?'), RED_WR))
        info_e.addWidget(_tag_lbl("|", TEXT_SUBTLE))
        info_e.addWidget(_tag_lbl(self._difficulty(t_e.get('difficulty', 2)), TEXT_SECONDARY))
        self.info_1v1_layout.addLayout(info_e, 1)

        # === ANALISIS IA ===
        try:
            insights = interpretar_features(aliado, enemigo)
            ventajas = []; desventajas = []; neutral = []
            for ins in insights:
                if "Desventaja" in ins or "Deficit" in ins or "contra" in ins:
                    desventajas.append(ins)
                elif "Ventaja" in ins or "Dominio" in ins or "Enfrentamiento equilibrado" in ins:
                    ventajas.append(ins) if "equilibrado" not in ins else neutral.append(ins)
                else:
                    neutral.append(ins)

            parts = []
            for label, items, bg, border in [
                ("VENTAJAS", ventajas, "#0a2a0f", GREEN_WR),
                ("DESVENTAJAS", desventajas, "#2a0a0f", RED_WR),
                ("INFO", neutral, "#1a1a2e", BORDER_SUBTLE),
            ]:
                if items:
                    parts.append(
                        f'<div style="background:{bg};border-left:3px solid {border};border-radius:4px;'
                        f'padding:6px 10px;margin:3px 0;">'
                        f'<p style="color:{border};font-size:10px;font-weight:700;margin:0 0 3px 0;">{label}</p>'
                        + ''.join(f'<p style="color:{TEXT_SECONDARY};font-size:10px;margin:1px 0 1px 6px;">• {i}</p>' for i in items)
                        + '</div>')

            feats = extraer_features_comparativas(aliado, enemigo)
            badges = []
            badge_names = ["CC", "Movilidad", "Early", "Escalado", "Tanque(A)", "Tanque(E)",
                           "CC+", "CC+(E)", "Burst", "TankCtr", "DmgIgual", "Early+", "Early+(E)", "Hiper", "Hiper(E)"]
            for i, (v, name) in enumerate(zip(feats[:10], badge_names)):
                if i in (0, 1, 2, 3) and v != 0:
                    sign = "+" if v > 0 else ""
                    color = GREEN_WR if v > 0 else RED_WR
                    badges.append(f'<span style="display:inline-block;background:{BG_CARD};color:{color};'
                                  f'border-radius:3px;padding:1px 6px;margin:1px;font-size:9px;">{name} {sign}{int(v)}</span>')

            resumen = f'<p style="color:{TEXT_MUTED};font-size:10px;margin:0 0 4px 0;">{aliado} vs {enemigo}: '
            resumen += f'<b style="color:{GREEN_WR};">{len(ventajas)} ventajas</b>, '
            resumen += f'<b style="color:{RED_WR};">{len(desventajas)} desventajas</b></p>'

            html = f"""
            <div style="font-family:{FONT_FAMILY};font-size:11px;">
            <hr style="border:none;border-top:1px solid {BORDER_ACCENT};margin:6px 0;">
            <p style="color:{ACCENT_RED};font-weight:700;font-size:12px;margin:2px 0 4px 0;">ANALISIS DEL MATCHUP</p>
            {resumen}
            {''.join(parts)}
            {f'<p style="margin:6px 0 2px 0;">{chr(32).join(badges)}</p>' if badges else ''}
            </div>"""
        except Exception:
            html = f"""<div style="font-family:{FONT_FAMILY};font-size:11px;">
            <hr style="border:none;border-top:1px solid {BORDER_ACCENT};margin:6px 0;">
            <p style="color:{ACCENT_RED};font-weight:700;font-size:12px;margin:2px 0;">ANALISIS DEL MATCHUP</p>
            <p style="color:{TEXT_MUTED};font-size:10px;">Analisis no disponible para este matchup.</p>
            </div>"""

        self.lbl_analisis_ia.setText(html)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)
