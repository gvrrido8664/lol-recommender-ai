"""Dialogo de configuracion simplificado para gamers."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.design import *


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self._applied = False
        self.setWindowTitle("NEXUS — Configuracion")
        self.resize(420, 360)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QLabel {{ color: {TEXT_WHITE}; font-size: 12px; background: transparent; }}
            QCheckBox {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 8px; padding: 4px 0; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QCheckBox:hover {{ color: {BORDER_ACCENT}; }}
            QComboBox {{ background-color: {BG_CARD_HOVER}; color: {TEXT_WHITE}; border: 1px solid {BG_CARD_ELEVATED}; border-radius: 4px; padding: 4px 8px; min-width: 50px; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QGroupBox {{ color: {BORDER_ACCENT}; font-weight: bold; font-size: 12px; border: 1px solid {CARD_DARKER_BLUE}; border-radius: 6px; margin-top: 6px; padding-top: 12px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
            QTabWidget::pane {{ border: 1px solid {CARD_DARKER_BLUE}; background: transparent; }}
            QTabBar::tab {{ color: {TEXT_SUBTLE}; background: {BG_DARK}; border: none; padding: 8px 20px; }}
            QTabBar::tab:selected {{ color: {BORDER_ACCENT}; background: {BG_DARK}; border-bottom: 2px solid {BORDER_ACCENT}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Configuracion")
        title.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 18px; padding: 4px 0;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._tab_general(), "General")
        tabs.addTab(self._tab_auto(), "Auto-Importar")
        layout.addWidget(tabs, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _tab_general(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(6)

        gb = QGroupBox("Notificaciones")
        gl = QVBoxLayout(gb)
        gl.setSpacing(4)

        self.cb_sonido = QCheckBox("Sonidos (cola, partida encontrada, fin de juego)")
        self.cb_sonido.setChecked(self.settings.get("sonidos", False))
        gl.addWidget(self.cb_sonido)

        self.cb_notif = QCheckBox("Notificaciones de escritorio")
        self.cb_notif.setChecked(self.settings.get("notificaciones_escritorio", True))
        gl.addWidget(self.cb_notif)

        l.addWidget(gb)

        gb2 = QGroupBox("Interfaz")
        gl2 = QVBoxLayout(gb2)
        gl2.setSpacing(4)

        self.cb_dificultad = QCheckBox("Mostrar dificultad en campeones (Garen *, Zed ***)")
        self.cb_dificultad.setChecked(self.settings.get("mostrar_dificultad", True))
        gl2.addWidget(self.cb_dificultad)

        l.addWidget(gb2)

        gb3 = QGroupBox("Partida")
        gl3 = QVBoxLayout(gb3)
        gl3.setSpacing(4)

        self.cb_auto_switch = QCheckBox("Cambiar a Radar al entrar en Champ Select")
        self.cb_auto_switch.setChecked(self.settings.get("auto_switch_radar", True))
        gl3.addWidget(self.cb_auto_switch)

        self.cb_auto_aceptar = QCheckBox("Aceptar partida automaticamente")
        self.cb_auto_aceptar.setChecked(self.settings.get("auto_aceptar", False))
        gl3.addWidget(self.cb_auto_aceptar)

        l.addWidget(gb3)
        l.addStretch()
        return w

    def _tab_auto(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(6)

        desc = QLabel(
            "Al elegir un campeon en Champ Select, NEXUS puede\n"
            "importar automaticamente estas opciones al cliente de LoL."
        )
        desc.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 11px; padding: 2px 0 8px 0;")
        desc.setWordWrap(True)
        l.addWidget(desc)

        self.cb_auto_runas = QCheckBox("Pagina de runas recomendada")
        self.cb_auto_runas.setChecked(self.settings.get("auto_runas", False))
        l.addWidget(self.cb_auto_runas)

        self.cb_auto_hechizos = QCheckBox("Hechizos de invocador")
        self.cb_auto_hechizos.setChecked(self.settings.get("auto_hechizos", False))
        l.addWidget(self.cb_auto_hechizos)

        self.cb_auto_habilidades = QCheckBox("Orden de habilidades")
        self.cb_auto_habilidades.setChecked(self.settings.get("auto_habilidades", False))
        l.addWidget(self.cb_auto_habilidades)

        gb = QGroupBox("Tecla de Flash")
        fl = QHBoxLayout(gb)
        fl.addWidget(QLabel("Tu Flash esta en:"))
        self.cb_flash = QComboBox()
        self.cb_flash.addItems(["D", "F"])
        self.cb_flash.setCurrentText("D" if self.settings.get("flash_en_d", True) else "F")
        fl.addWidget(self.cb_flash)
        fl.addStretch()
        l.addWidget(gb)

        l.addStretch()
        return w

    def accept(self):
        s = self._collect()
        self.settings = s
        self._applied = True
        from ui.helpers import guardar_settings
        guardar_settings(s)
        if self.parent() and hasattr(self.parent(), "_aplicar_settings"):
            self.parent().user_settings = s
            self.parent()._aplicar_settings()
        super().accept()

    def _collect(self):
        return {
            "auto_deteccion": True,
            "sonidos": self.cb_sonido.isChecked(),
            "frecuencia_radar": 1500,
            "frecuencia_partida": 4000,
            "mostrar_dificultad": self.cb_dificultad.isChecked(),
            "flash_en_d": self.cb_flash.currentText() == "D",
            "auto_runas": self.cb_auto_runas.isChecked(),
            "auto_hechizos": self.cb_auto_hechizos.isChecked(),
            "auto_habilidades": self.cb_auto_habilidades.isChecked(),
            "auto_switch_radar": self.cb_auto_switch.isChecked(),
            "auto_aceptar": self.cb_auto_aceptar.isChecked(),
            "notificaciones_escritorio": self.cb_notif.isChecked(),
        }

    def get_settings(self):
        return self._collect()
