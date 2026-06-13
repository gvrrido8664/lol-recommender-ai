"""Pestania SIMULADOR 1v1 (IA). Extraida de app.py sin cambios."""

from ui.contexto import *


class IATabMixin:
    def armar_tab_ia(self):
        layout = QVBoxLayout(self.tab_ia)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        panel_ia, l_ia = self.crear_panel("CONFIGURACIÓN DEL MATCHUP")
        ctrls = QHBoxLayout()
        ctrls.setSpacing(8)
        self.cb_ia_rol = QComboBox()
        self.cb_ia_aliado = QComboBox()
        self.cb_ia_enemigo = QComboBox()
        ctrls.addWidget(QLabel("Línea:"))
        ctrls.addWidget(self.cb_ia_rol)
        ctrls.addWidget(QLabel("Tu Pick:"))
        ctrls.addWidget(self.cb_ia_aliado)
        lbl_vs = QLabel("VS")
        lbl_vs.setStyleSheet(f"color: {RED_WR}; font-weight: bold; font-size: 13px; margin: 0 4px;")
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
        
        l_ia.addLayout(ctrls)
        layout.addWidget(panel_ia)
        
        # ===== HUD DE RESULTADO =====
        hud_panel, l_hud = self.crear_panel("RESULTADO PREDICTIVO (IA)")
        l_hud.setAlignment(Qt.AlignTop)
        l_hud.setSpacing(8)
        
        batalla_layout = QHBoxLayout()
        batalla_layout.setSpacing(20)
        
        # Columna 1: Aliado
        col_aliado = QVBoxLayout()
        col_aliado.setAlignment(Qt.AlignCenter)
        col_aliado.setSpacing(6)
        fr_al = QFrame()
        fr_al.setObjectName("BuildCard")
        fr_al.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {GREEN_WR}; border-radius: 10px; padding: 10px; background-color: #0a1a0f; }}")
        l_al = QVBoxLayout(fr_al)
        l_al.setAlignment(Qt.AlignCenter)
        self.img_aliado_1v1 = QLabel()
        self.img_aliado_1v1.setAlignment(Qt.AlignCenter)
        self.img_aliado_1v1.setFixedSize(100, 100)
        l_al.addWidget(self.img_aliado_1v1, alignment=Qt.AlignCenter)
        self.lbl_nombre_aliado_1v1 = QLabel("--")
        self.lbl_nombre_aliado_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nombre_aliado_1v1.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 12px;")
        l_al.addWidget(self.lbl_nombre_aliado_1v1)
        col_aliado.addWidget(fr_al)
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
        
        # Barras comparativas compactas
        barras_frame = QFrame()
        barras_frame.setStyleSheet(f"background-color: {BG_CARD}; border-radius: 6px; padding: 8px;")
        barras_layout = QVBoxLayout(barras_frame)
        barras_layout.setSpacing(3)
        barras_layout.setContentsMargins(8, 6, 8, 6)
        
        for lbl_txt, bar_attr in [
            ("CC (Control)", "barra_cc"),
            ("Movilidad", "barra_movilidad"),
            ("Early Game", "barra_early"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-weight: bold;")
            lbl.setFixedWidth(80)
            row.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(50)
            bar.setTextVisible(False); bar.setFixedHeight(10)
            bar.setStyleSheet(self._estilo_barra_comparativa(50))
            setattr(self, bar_attr, bar)
            row.addWidget(bar, 1)
            barras_layout.addLayout(row)
        
        col_centro.addWidget(barras_frame)
        batalla_layout.addLayout(col_centro, 2)
        
        # Columna 3: Enemigo
        col_enemigo = QVBoxLayout()
        col_enemigo.setAlignment(Qt.AlignCenter)
        col_enemigo.setSpacing(6)
        fr_en = QFrame()
        fr_en.setObjectName("BuildCard")
        fr_en.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {RED_WR}; border-radius: 10px; padding: 10px; background-color: #1a0a0f; }}")
        l_en = QVBoxLayout(fr_en)
        l_en.setAlignment(Qt.AlignCenter)
        self.img_enemigo_1v1 = QLabel()
        self.img_enemigo_1v1.setAlignment(Qt.AlignCenter)
        self.img_enemigo_1v1.setFixedSize(100, 100)
        l_en.addWidget(self.img_enemigo_1v1, alignment=Qt.AlignCenter)
        self.lbl_nombre_enemigo_1v1 = QLabel("--")
        self.lbl_nombre_enemigo_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nombre_enemigo_1v1.setStyleSheet(f"color: {RED_WR}; font-weight: bold; font-size: 12px;")
        l_en.addWidget(self.lbl_nombre_enemigo_1v1)
        col_enemigo.addWidget(fr_en)
        batalla_layout.addLayout(col_enemigo, 1)
        
        l_hud.addLayout(batalla_layout)
        
        # Análisis de la IA
        self.lbl_analisis_ia = QLabel("Selecciona los campeones y presiona Simular.")
        self.lbl_analisis_ia.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 12px; padding: 14px; background-color: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px;")
        self.lbl_analisis_ia.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_analisis_ia.setWordWrap(True)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)
        self.lbl_analisis_ia.setMinimumHeight(200)
        l_hud.addWidget(self.lbl_analisis_ia)
        layout.addWidget(hud_panel, 1)
        
        self.actualizar_listas_ia(UI_ROLES[0])

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

    def predecir_ia(self):
        rol_api = ROL_TO_API[self.cb_ia_rol.currentText()]
        aliado = self.cb_ia_aliado.currentText()
        enemigo = self.cb_ia_enemigo.currentText()
        
        if not aliado or not enemigo or not modelo_1v1.get(rol_api): return
        
        # ─── Imagenes y nombres ───
        ruta_al = self.descargar_imagen(aliado, "champ")
        ruta_en = self.descargar_imagen(enemigo, "champ")
        if ruta_al: self.img_aliado_1v1.setPixmap(QPixmap(ruta_al).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if ruta_en: self.img_enemigo_1v1.setPixmap(QPixmap(ruta_en).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.lbl_nombre_aliado_1v1.setText(self._nombre_display(aliado))
        self.lbl_nombre_enemigo_1v1.setText(self._nombre_display(enemigo))
        
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
        counters = obtener_counters(rol_api, enemigo, min_partidas=10)
        wr_real = None
        partidas_real = 0
        for c_name, wr, p in counters:
            if c_name == aliado:
                wr_real = wr
                partidas_real = p
                break
        
        # === FASE 2: FUSION Y AMPLIFICACION MATEMATICA ===
        if wr_real is not None:
            # Promedio ponderado: 40% IA + 60% datos reales
            prob_base = (prob * 0.4) + (wr_real * 0.6)
        else:
            prob_base = prob
        
        # Amplificar varianza para UI: alejar del 50%
        prob_final = 50 + ((prob_base - 50) * 1.8)
        prob_final = max(0, min(100, prob_final))
        
        # === NIVEL DE MATCHUP (umbrales calibrados) ===
        if prob_final > 54:
            nivel_color = GREEN_WR
            nivel_icono = "🔥"
            nivel_texto = "HARD COUNTER (Ventaja Absoluta)"
        elif prob_final >= 51.5:
            nivel_color = GREEN_WR
            nivel_icono = "✅"
            nivel_texto = "VENTAJA LIGERA"
        elif prob_final >= 48.5:
            nivel_color = YELLOW_WR
            nivel_icono = "⚔️"
            nivel_texto = "MATCHUP DE HABILIDAD (50/50)"
        else:
            nivel_color = RED_WR
            nivel_icono = "⚠️"
            nivel_texto = "MATCHUP DESFAVORABLE"
        
        # === ACTUALIZAR UI CENTRAL ===
        self.lbl_wr_1v1.setText(f"{prob_final:.1f}%")
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 38px; color: {nivel_color};")
        self.lbl_nivel_1v1.setText(f"{nivel_icono} {nivel_texto}")
        self.lbl_nivel_1v1.setStyleSheet(f"color: {nivel_color}; font-size: 12px; font-weight: bold;")
        
        if wr_real is not None:
            real_color = GREEN_WR if wr_real >= 50 else RED_WR
            self.lbl_wr_real_1v1.setText(f"WR Real: {wr_real}% ({partidas_real} partidas)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {real_color}; font-size: 10px;")
        else:
            self.lbl_wr_real_1v1.setText("(sin datos reales en BD)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        
        # === FASE 3: BARRAS COMPARATIVAS (TIRA Y AFLOJA) ===
        # NOTA: obtener_tag, obtener_nivel_cc ya importados a nivel modulo (linea 23)
        # NO usar import local dentro de la funcion (causa NameError en runtime)
        try:
            t_a = obtener_tag(aliado)
            t_e = obtener_tag(enemigo)
            
            # CC
            cc_a = obtener_nivel_cc(aliado)
            cc_e = obtener_nivel_cc(enemigo)
            val_cc = round((cc_a / max(0.1, cc_a + cc_e)) * 100)
            self.barra_cc.setValue(val_cc)
            self.barra_cc.setStyleSheet(self._estilo_barra_comparativa(val_cc))
            self.barra_cc.setToolTip(f"{aliado}: CC {cc_a}/5  |  {enemigo}: CC {cc_e}/5")
            
            # Movilidad
            mob_a = t_a.get("mobility", 2)
            mob_e = t_e.get("mobility", 2)
            val_mob = round((mob_a / max(0.1, mob_a + mob_e)) * 100)
            self.barra_movilidad.setValue(val_mob)
            self.barra_movilidad.setStyleSheet(self._estilo_barra_comparativa(val_mob))
            self.barra_movilidad.setToolTip(f"{aliado}: Movilidad {mob_a}/5  |  {enemigo}: Movilidad {mob_e}/5")
            
            # Early
            _EM = {"weak": 1, "neutral": 2, "strong": 3}
            early_a = _EM.get(t_a.get("early_power", "neutral"), 2)
            early_e = _EM.get(t_e.get("early_power", "neutral"), 2)
            val_early = round((early_a / max(0.1, early_a + early_e)) * 100)
            self.barra_early.setValue(val_early)
            self.barra_early.setStyleSheet(self._estilo_barra_comparativa(val_early))
            self.barra_early.setToolTip(f"{aliado}: Early {t_a.get('early_power','?')}  |  {enemigo}: Early {t_e.get('early_power','?')}")
            
        except Exception as e:
            print(f"[predecir_ia] Error en barras comparativas: {e}")
            # Fallback: barras a 50 (neutral) para no crashear
            for bar in [self.barra_cc, self.barra_movilidad, self.barra_early]:
                bar.setValue(50)
                bar.setStyleSheet(self._estilo_barra_comparativa(50))
        
        # === ANALISIS HTML (mantener el detalle abajo) ===
        _SM = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
        scale_a = _SM.get(t_a.get("scaling", "mid"), 2)
        scale_e = _SM.get(t_e.get("scaling", "mid"), 2)
        
        def _barra_html(val_a, val_e, max_v, label):
            pct_a = min(100, int(val_a / max_v * 100))
            pct_e = min(100, int(val_e / max_v * 100))
            delta = val_a - val_e
            if delta > 0:
                delta_str = f'<span style="color:{GREEN_WR};">(+{delta})</span>'
            elif delta < 0:
                delta_str = f'<span style="color:{RED_WR};">({delta})</span>'
            else:
                delta_str = '<span style="color:#7a6f68;">(=)</span>'
            return (
                f'<tr>'
                f'<td width="140" style="color:{TEXT_MUTED};font-size:11px;padding:2px 6px;">{label}</td>'
                f'<td width="160"><div style="background:{BG_CARD_HOVER};border-radius:3px;height:14px;width:100%;">'
                f'<div style="background:{GREEN_WR};height:14px;width:{pct_a}%;border-radius:3px 0 0 3px;"></div></div></td>'
                f'<td width="30" style="color:{TEXT_WHITE};font-size:11px;text-align:center;font-weight:700;">{val_a}</td>'
                f'<td width="20" style="text-align:center;">{delta_str}</td>'
                f'<td width="30" style="color:{TEXT_WHITE};font-size:11px;text-align:center;font-weight:700;">{val_e}</td>'
                f'<td width="160"><div style="background:{BG_CARD_HOVER};border-radius:3px;height:14px;width:100%;">'
                f'<div style="background:{RED_WR};height:14px;width:{pct_e}%;border-radius:0 3px 3px 0;float:right;"></div></div></td>'
                f'</tr>'
            )
        
        html = f"""
        <div style="font-family:{FONT_FAMILY};font-size:12px;">
        <hr style="border:none;border-top:1px solid {BORDER_ACCENT};margin:10px 0;">
        <p style="color:{ACCENT_RED};font-weight:700;font-size:13px;letter-spacing:1px;margin:6px 0;">
            &#9889; STATS COMPARATIVAS
        </p>
        <p style="color:{TEXT_MUTED};font-size:10px;margin:2px 0;">
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{aliado[:10]:<10} <span style="color:{GREEN_WR};">verde</span> &nbsp;&#8594;&nbsp; DELTA &nbsp;&#8592;&nbsp; <span style="color:{RED_WR};">rojo</span> {enemigo[:10]:<10}
        </p>
        <table cellspacing="2" style="margin:8px 0;">
            {_barra_html(mob_a, mob_e, 5, "Movilidad")}
            {_barra_html(cc_a, cc_e, 5, "Control (CC)")}
            {_barra_html(early_a, early_e, 3, "Early Game")}
            {_barra_html(scale_a, scale_e, 4, "Escalado")}
        </table>
        <p style="color:{TEXT_MUTED};font-size:11px;margin:4px 0;">
            Daño: <b style="color:{ACCENT_TEAL};">{aliado} {t_a.get('damage_type','?')}</b>
            &nbsp;vs&nbsp;
            <b style="color:{YELLOW_WR};">{enemigo} {t_e.get('damage_type','?')}</b>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            Clase: <b style="color:{ACCENT_TEAL};">{t_a.get('champion_class','?')}</b>
            &nbsp;vs&nbsp;
            <b style="color:{YELLOW_WR};">{t_e.get('champion_class','?')}</b>
        </p>
        <hr style="border:none;border-top:1px solid {BORDER_ACCENT};margin:10px 0;">
        <p style="color:{ACCENT_RED};font-weight:700;font-size:13px;letter-spacing:1px;margin:6px 0;">
            &#129504; QUE VE LA IA
        </p>
        <ul style="margin:4px 0;padding-left:18px;line-height:1.6;">"""
        
        try:
            insights = interpretar_features(aliado, enemigo)
            for ins in insights:
                if "Desventaja" in ins or "Déficit" in ins or "contra" in ins:
                    color = RED_WR
                elif "Ventaja" in ins or "Dominio" in ins or "mejor" in ins or "dicta" in ins:
                    color = GREEN_WR
                elif "hyper-carry" in ins:
                    color = YELLOW_WR
                else:
                    color = TEXT_MUTED
                html += f'<li style="color:{color};font-size:11px;">{ins}</li>'
        except Exception:
            html += f'<li style="color:{TEXT_MUTED};font-size:11px;">Análisis no disponible para este matchup.</li>'
        
        html += "</ul></div>"
        
        self.lbl_analisis_ia.setText(html)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)

