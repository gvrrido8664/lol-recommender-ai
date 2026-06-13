"""Pestania META & BUILDS (counters/builds). Extraida de app.py sin cambios."""

from ui.contexto import *


class CountersTabMixin:
    # ================= META & BUILDS =================
    def armar_tab_counters(self):
        layout = QVBoxLayout(self.tab_counters)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)
        ctrl_layout.addWidget(QLabel("LÃ­nea:"))
        
        self.cb_rol_counter = QComboBox()
        self.cb_enemigo = QComboBox()
        ctrl_layout.addWidget(self.cb_rol_counter)
        ctrl_layout.addWidget(QLabel("Vs:"))
        ctrl_layout.addWidget(self.cb_enemigo)
        self.cb_rol_counter.addItems(UI_ROLES)
        self.cb_rol_counter.currentTextChanged.connect(self.actualizar_listas_counter)
        
        btn_analizar = QPushButton("ANALIZAR")
        btn_analizar.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_RED}; color: white; border: none; border-radius: 6px;
                           font-weight: bold; font-size: 11px; padding: 8px 18px; }}
            QPushButton:hover {{ background-color: {HOVER_GLOW}; }}
        """)
        btn_analizar.clicked.connect(self.buscar_counters)
        ctrl_layout.addWidget(btn_analizar)
        ctrl_layout.addStretch()
        
        layout.addLayout(ctrl_layout)
        
        # Split horizontal: tabla en izquierda, build visual en derecha
        split_layout = QHBoxLayout()
        split_layout.setSpacing(8)
        
        self.tree_counters = QTableWidget()
        self.tree_counters.setColumnCount(3)
        self.tree_counters.setHorizontalHeaderLabels(["CampeÃ³n Aliado", "Winrate %", "Partidas"])
        self.tree_counters.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tree_counters.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_counters.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_counters.itemSelectionChanged.connect(self.mostrar_build_visual)
        self.tree_counters.verticalHeader().setDefaultSectionSize(40)
        self.tree_counters.setIconSize(QSize(28, 28))
        self.tree_counters.verticalHeader().setVisible(False)
        self.tree_counters.setStyleSheet("""
            QTableWidget { border: 1px solid {BG_CARD_HOVER}; border-radius: 4px; background-color: transparent; }
            QTableWidget::item { padding: 2px 6px; }
            QHeaderView::section { background-color: #152040; border: none; border-bottom: 1px solid #e63946; color: #e63946; font-weight: bold; padding: 6px; }
            QTableWidget::item:selected { background-color: {BG_CARD_HOVER}; }
        """)
        split_layout.addWidget(self.tree_counters, 1)
        
        self.panel_visual, self.l_visual = self.crear_panel("SETUP & BUILD Ã“PTIMAS")
        self.frame_setup_visual = QVBoxLayout()
        self.frame_setup_visual.setAlignment(Qt.AlignTop)
        self.l_visual.addLayout(self.frame_setup_visual)
        split_layout.addWidget(self.panel_visual, 1)
        
        layout.addLayout(split_layout, 1)
        
        self.actualizar_listas_counter(UI_ROLES[0])

    def buscar_counters(self):
        """Lanza la bÃºsqueda en hilo secundario para no congelar la UI."""
        if self._cargando_meta:
            return
        self._cargando_meta = True
        rol_api = ROL_TO_API[self.cb_rol_counter.currentText()]
        enemigo = self.cb_enemigo.currentText()
        threading.Thread(target=self._fetch_meta_builds, args=(rol_api, enemigo), daemon=True).start()

    def _fetch_meta_builds(self, rol_api, enemigo):
        """Hilo secundario: ejecuta todas las queries de Meta Builds."""
        try:
            resultados = obtener_counters(rol_api, enemigo, min_partidas=20)
            builds_data = {}
            conn = obtener_conexion()
            for champ, winrate, partidas in resultados:
                if winrate <= 50:
                    continue
                ids_start, ids_fin = obtener_top_items(champ, rol_api, enemigos=[enemigo], conn=conn)
                builds_data[champ] = {
                    "starters": ids_start,
                    "finales": ids_fin,
                    "runas": obtener_top_runas(champ, rol_api, conn=conn),
                    "spells": obtener_top_hechizos(champ, rol_api, conn=conn)
                }
            conn.close()
            self.meta_builds_listo.emit(resultados, builds_data, rol_api, enemigo)
        except Exception as e:
            print(f"[MetaBuilds] Error: {e}")
            self.meta_builds_listo.emit([], {}, rol_api, enemigo)

    def _on_meta_builds_listo(self, resultados, builds_data, rol_api, enemigo):
        """Hilo principal: pinta la tabla con los resultados ya calculados."""
        self._cargando_meta = False
        self.builds_actuales.clear()
        self.tree_counters.setRowCount(0)
        clear_layout(self.frame_setup_visual)

        if not resultados:
            QMessageBox.information(self, "Aviso", "Datos insuficientes. Ajusta tus filtros.")
            return

        self.builds_actuales = builds_data

        self.tree_counters.blockSignals(True)
        for champ, winrate, partidas in resultados:
            if winrate <= 50:
                continue
            row = self.tree_counters.rowCount()
            self.tree_counters.insertRow(row)
            item_champ = QTableWidgetItem(f"  {champ}")
            icon_path = self.descargar_imagen(champ, "champ")
            if icon_path:
                item_champ.setIcon(QIcon(icon_path))
            item_wr = QTableWidgetItem(f"{winrate}%")
            if winrate >= 52:
                item_wr.setForeground(QColor(GREEN_WR))
            elif winrate <= 48:
                item_wr.setForeground(QColor(RED_WR))
            self.tree_counters.setItem(row, 0, item_champ)
            self.tree_counters.setItem(row, 1, item_wr)
            self.tree_counters.setItem(row, 2, QTableWidgetItem(str(partidas)))
        self.tree_counters.blockSignals(False)

    def mostrar_build_visual(self):
        filas = self.tree_counters.selectedItems()
        if not filas: return
        champ = self.tree_counters.item(filas[0].row(), 0).text().strip()
        data = self.builds_actuales.get(champ, {})
        
        if data.get("runas"): 
            self.renderizar_setup_completo(champ, data["runas"], data.get("spells", []), data.get("starters", []), data.get("finales", []), self.frame_setup_visual, mostrar_botones=False)

