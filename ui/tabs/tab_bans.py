"""Pestania TIER LIST DE BANS. Extraida de app.py sin cambios."""

from ui.contexto import *


class BansTabMixin:
    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        layout.setContentsMargins(10, 10, 10, 10)
        
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Selecciona la LÃ­nea a Proteger:"))
        
        self.cbbanrol = QComboBox()
        self.cbbanrol.addItems(UI_ROLES)
        ctrls.addWidget(self.cbbanrol)

        self.rb_ban_global = QRadioButton("Global")
        self.rb_ban_personal = QRadioButton("Personal")
        self.rb_ban_global.setChecked(True)
        self.rb_ban_global.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px;")
        self.rb_ban_personal.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px;")
        ctrls.addWidget(self.rb_ban_global)
        ctrls.addWidget(self.rb_ban_personal)
        
        btn_analizar = QPushButton("ANALIZAR BANS DEL META")
        btn_analizar.clicked.connect(self.buscar_baneos)
        ctrls.addWidget(btn_analizar)
        ctrls.addStretch()
        layout.addLayout(ctrls)

        self.treebans = QTableWidget()
        self.treebans.setColumnCount(3)
        self.treebans.setHorizontalHeaderLabels(["CampeÃ³n", "Banrate Sugerido %", "Partidas Analizadas"])
        self.treebans.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.treebans.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.treebans.setSelectionMode(QAbstractItemView.NoSelection)
        self.treebans.verticalHeader().setDefaultSectionSize(45)
        self.treebans.setIconSize(QSize(35, 35))
        self.treebans.verticalHeader().setVisible(False)
        layout.addWidget(self.treebans, 1)  # Stretch para llenar espacio

    def buscar_baneos(self):
        self.treebans.setRowCount(0)
        modo_personal = self.rb_ban_personal.isChecked()

        if modo_personal and hasattr(self, 'historial_games') and self.historial_games:
            results = self._tierlist_personal(ROL_TO_API[self.cbbanrol.currentText()])
        else:
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

    def _tierlist_personal(self, rol_api):
        from collections import Counter
        champ_vs = Counter()
        for g in getattr(self, 'historial_games', []) or []:
            role = (g.get("role") or g.get("lane") or "").upper()
            api_role = role
            if role in ("SUPPORT",): api_role = "UTILITY"
            elif role in ("BOT", "ADC"): api_role = "BOTTOM"
            elif role in ("JUNGLA",): api_role = "JUNGLE"
            elif role in ("MID",): api_role = "MIDDLE"
            if api_role != rol_api:
                continue
            champ_list = g.get("enemyTeam", [])
            if not champ_list:
                continue
            for c in champ_list:
                name = c.get("championName") or c.get("championId", "")
                if name:
                    champ_vs[name] += 1
        total = sum(champ_vs.values())
        if total < 5:
            return []
        results = []
        for champ, count in champ_vs.most_common(15):
            rate = round(count / total * 100, 1)
            results.append((champ, rate, count))
        return results

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
                self.lbl_logros_text.setStyleSheet("color: {TEXT_SUBTLE}; font-size: 11px;")
                self.lbl_logros_text.setWordWrap(True)
                self.fr_logros.addWidget(self.lbl_logros_text)
            else:
                for lg in conseguidos:
                    lbl = QLabel(f"{lg['emoji']} {lg['nombre']}")
                    lbl.setStyleSheet("color: {TEXT_LIGHT}; font-size: 11px; background: #1a2744; border-radius: 4px; padding: 2px 6px;")
                    lbl.setToolTip(lg['desc'])
                    self.fr_logros.addWidget(lbl)
            self.fr_logros.addStretch()
        except Exception as e:
            print(f"[Logros] Error: {e}")

if __name__ == "__main__":
    import signal
    app = QApplication(sys.argv)
    app.setApplicationName("NEXUS")
    app.setFont(QFont("Segoe UI", 10))

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    from setup import verificar_datos_iniciales
    if not verificar_datos_iniciales():
        from src.setup_wizard import SetupWizard
        wizard = SetupWizard()
        wizard.exec()
        if not wizard.success:
            sys.exit(1)
        from src.db_manager import inicializar_db, ConexionDBError
        try:
            inicializar_db()
        except ConexionDBError:
            pass

    window = LoLRecommenderApp()
    window.show()
    sys.exit(app.exec())

