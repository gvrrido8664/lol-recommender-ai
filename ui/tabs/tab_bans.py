"""Pestania TIER LIST DE BANS — mejorada con ELO, min partidas y refresco."""

from ui.contexto import *


class BansTabMixin:
    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        layout.setContentsMargins(10, 10, 10, 10)

        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Línea:"))

        self.cbbanrol = QComboBox()
        self.cbbanrol.addItems(UI_ROLES)
        ctrls.addWidget(self.cbbanrol)

        ctrls.addWidget(QLabel("  ELO:"))

        self.cbbanelo = QComboBox()
        self.cbbanelo.addItems([
            "Todos", "Iron", "Bronze", "Silver", "Gold",
            "Platinum", "Emerald", "Diamond", "Master+",
        ])
        ctrls.addWidget(self.cbbanelo)

        ctrls.addWidget(QLabel("  Mín. partidas:"))

        self.spb_min = QSpinBox()
        self.spb_min.setRange(5, 200)
        self.spb_min.setValue(20)
        self.spb_min.setSingleStep(10)
        self.spb_min.setFixedWidth(60)
        ctrls.addWidget(self.spb_min)

        btn_analizar = QPushButton("ANALIZAR BANS")
        btn_analizar.clicked.connect(self.buscar_baneos)
        ctrls.addWidget(btn_analizar)

        self.btn_refresh = QPushButton("⟳ Refrescar")
        self.btn_refresh.clicked.connect(self.buscar_baneos)
        ctrls.addWidget(self.btn_refresh)

        ctrls.addStretch()
        layout.addLayout(ctrls)

        self.lbl_ban_info = QLabel("")
        self.lbl_ban_info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(self.lbl_ban_info)

        self.treebans = QTableWidget()
        self.treebans.setColumnCount(4)
        self.treebans.setHorizontalHeaderLabels(["Campeón", "Banrate", "Partidas", "Prioridad"])
        self.treebans.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.treebans.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.treebans.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.treebans.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.treebans.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.treebans.setSelectionMode(QAbstractItemView.NoSelection)
        self.treebans.verticalHeader().setDefaultSectionSize(45)
        self.treebans.setIconSize(QSize(35, 35))
        self.treebans.verticalHeader().setVisible(False)
        layout.addWidget(self.treebans, 1)

    def buscar_baneos(self):
        self.treebans.setRowCount(0)
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⟳ Cargando...")

        rol = self.cbbanrol.currentText()
        elo = self.cbbanelo.currentText()
        min_partidas = self.spb_min.value()

        results = obtenermejoresbaneos(ROL_TO_API.get(rol, rol), min_partidas=min_partidas)

        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("⟳ Refrescar")

        if not results:
            self.lbl_ban_info.setText(f"Sin datos para {rol} con ≥{min_partidas} partidas.")
            QMessageBox.information(self, "Aviso", f"No hay datos suficientes para {rol}.\nPrueba con un mínimo de partidas más bajo.")
            return

        elo_texto = f" · ELO: {elo}" if elo != "Todos" else ""
        self.lbl_ban_info.setText(f"{len(results[:15])} campeones sugeridos para banear en {rol}{elo_texto} (≥{min_partidas} partidas)")

        for _idx, (champ, banrate, partidas) in enumerate(results[:15]):
            row = self.treebans.rowCount()
            self.treebans.insertRow(row)

            item_champ = QTableWidgetItem(f"  {champ}")
            icon_path = self.descargar_imagen(champ, "champ")
            if icon_path:
                item_champ.setIcon(QIcon(icon_path))

            color_ban = RED_WR if banrate > 60 else YELLOW_WR if banrate > 40 else GREEN_WR
            item_ban = QTableWidgetItem(f"{banrate}%")
            item_ban.setForeground(QColor(color_ban))

            item_part = QTableWidgetItem(str(partidas))

            prioridad = "🔴 Alta" if banrate > 60 else "🟡 Media" if banrate > 40 else "🟢 Baja"
            item_prio = QTableWidgetItem(prioridad)

            self.treebans.setItem(row, 0, item_champ)
            self.treebans.setItem(row, 1, item_ban)
            self.treebans.setItem(row, 2, item_part)
            self.treebans.setItem(row, 3, item_prio)

    def _cargar_logros(self):
        try:
            if not hasattr(self, "historial_games") or not self.historial_games:
                return

            while self.fr_logros.count():
                item = self.fr_logros.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        child = item.layout().takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()

            insights = generar_insights_jugador(self.historial_games)

            if not insights:
                self.lbl_logros_text = QLabel("Sigue jugando para desbloquear insights...")
                self.lbl_logros_text.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 11px;")
                self.lbl_logros_text.setWordWrap(True)
                self.fr_logros.addWidget(self.lbl_logros_text, 0, 0, 1, 2)
                return

            for idx, ins in enumerate(insights[:5]):
                row = idx // 2
                col = idx % 2
                lbl = QLabel(f"{ins['icono']}  {ins['texto']}")
                lbl.setWordWrap(True)
                lbl.setMinimumHeight(28)
                lbl.setStyleSheet(
                    f"color: {TEXT_LIGHT}; font-size: 9px; padding: 3px 7px; "
                    f"background: {ins['fondo']}; "
                    f"border-left: 2px solid {ins['color']}; "
                    f"border-radius: 3px;"
                )
                self.fr_logros.addWidget(lbl, row, col)

        except Exception as e:
            print(f"[Logros] Error: {e}")
