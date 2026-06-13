"""Pestania TIER LIST DE BANS. Extraida de app.py sin cambios."""

from ui.contexto import *


class BansTabMixin:
    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        layout.setContentsMargins(10, 10, 10, 10)
        
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Selecciona la Línea a Proteger:"))
        
        self.cbbanrol = QComboBox()
        self.cbbanrol.addItems(UI_ROLES)
        ctrls.addWidget(self.cbbanrol)

        btn_analizar = QPushButton("ANALIZAR BANS DEL META")
        btn_analizar.clicked.connect(self.buscar_baneos)
        ctrls.addWidget(btn_analizar)
        ctrls.addStretch()
        layout.addLayout(ctrls)

        self.treebans = QTableWidget()
        self.treebans.setColumnCount(3)
        self.treebans.setHorizontalHeaderLabels(["Campeón", "Banrate Sugerido %", "Partidas Analizadas"])
        self.treebans.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.treebans.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.treebans.setSelectionMode(QAbstractItemView.NoSelection)
        self.treebans.verticalHeader().setDefaultSectionSize(45)
        self.treebans.setIconSize(QSize(35, 35))
        self.treebans.verticalHeader().setVisible(False)
        layout.addWidget(self.treebans, 1)  # Stretch para llenar espacio

    def buscar_baneos(self):
        self.treebans.setRowCount(0)
        results = obtenermejoresbaneos(ROL_TO_API[self.cbbanrol.currentText()], min_partidas=20)

        if not results:
            QMessageBox.information(self, "Aviso", "No hay datos suficientes para ese rol.")
            return
            
        for champ, banrate, partidas in results[:15]: 
            row = self.treebans.rowCount()
            self.treebans.insertRow(row)
            
            item_champ = QTableWidgetItem(f"  {champ}")
            icon_path = self.descargar_imagen(champ, "champ")
            if icon_path: item_champ.setIcon(QIcon(icon_path))
            item_champ.setToolTip(f"{champ}\nFrecuencia de pick: {banrate}%\n{partidas} partidas analizadas")
            
            item_ban = QTableWidgetItem(f"{banrate}%")
            item_ban.setForeground(QColor(RED_WR))
            
            self.treebans.setItem(row, 0, item_champ)
            self.treebans.setItem(row, 1, item_ban)
            self.treebans.setItem(row, 2, QTableWidgetItem(str(partidas)))

    def _cargar_logros(self):
        try:
            if not hasattr(self, 'historial_games') or not self.historial_games:
                return
            logros_dict = evaluar_logros(self.historial_games)
            conseguidos = obtener_logros_conseguidos(logros_dict)

            # Clear previous logros
            while self.fr_logros.count():
                item = self.fr_logros.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not conseguidos:
                self.lbl_logros_text = QLabel("Sigue jugando para desbloquear logros...")
                self.lbl_logros_text.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 11px;")
                self.lbl_logros_text.setWordWrap(True)
                self.fr_logros.addWidget(self.lbl_logros_text)
            else:
                for lg in conseguidos:
                    lbl = QLabel(f"{lg['emoji']} {lg['nombre']}")
                    lbl.setStyleSheet(f"color: {TEXT_LIGHT}; font-size: 11px; background: #211a28; border-radius: 4px; padding: 2px 6px;")
                    lbl.setToolTip(lg['desc'])
                    self.fr_logros.addWidget(lbl)
            self.fr_logros.addStretch()
        except Exception as e:
            print(f"[Logros] Error: {e}")

