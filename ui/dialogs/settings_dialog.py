"""Dialogo de configuracion de usuario — 3 pestañas + boton Aplicar."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
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
        self.resize(440, 420)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QLabel {{ color: {TEXT_WHITE}; font-size: 12px; background: transparent; }}
            QCheckBox {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 8px; padding: 2px 0; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QCheckBox:hover {{ color: {BORDER_ACCENT}; }}
            QComboBox {{ background-color: #251d2b; color: {TEXT_WHITE}; border: 1px solid #2f2535; border-radius: 4px; padding: 4px 8px; min-width: 50px; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QGroupBox {{ color: {BORDER_ACCENT}; font-weight: bold; font-size: 12px; border: 1px solid #2a2030; border-radius: 6px; margin-top: 8px; padding-top: 14px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
            QPushButton {{ color: white; }}
            QSlider::groove:horizontal {{ height: 6px; background: #2a2030; border-radius: 3px; }}
            QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -5px 0; background: {BORDER_ACCENT}; border-radius: 8px; }}
            QTabWidget::pane {{ border: 1px solid #2a2030; background: transparent; }}
            QTabBar::tab {{ color: {TEXT_SUBTLE}; background: #16121c; border: none; padding: 6px 16px; }}
            QTabBar::tab:selected {{ color: {BORDER_ACCENT}; background: {BG_DARK}; border-bottom: 2px solid {BORDER_ACCENT}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel("Configuracion")
        title.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 18px; padding: 4px 0;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._tab_general(), "General")
        tabs.addTab(self._tab_auto(), "Auto-Importar")
        tabs.addTab(self._tab_partida(), "En Partida")
        layout.addWidget(tabs, 1)

        # ── Botones: Aplicar + OK/Cancel ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.setFixedWidth(90)
        self.btn_apply.setStyleSheet(f"""
            QPushButton {{ background-color: #2a2030; color: {BORDER_ACCENT}; border: 1px solid {BORDER_ACCENT}; border-radius: 4px; padding: 6px 12px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {BORDER_ACCENT}; color: #000; }}
        """)
        self.btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(self.btn_apply)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btn_row.addWidget(btns)

        layout.addLayout(btn_row)

    # ═══════════════════════════════════════════
    # TAB 1: General
    # ═══════════════════════════════════════════
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
        l.addStretch()
        return w

    # ═══════════════════════════════════════════
    # TAB 2: Auto-Importar
    # ═══════════════════════════════════════════
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

    # ═══════════════════════════════════════════
    # TAB 3: En Partida
    # ═══════════════════════════════════════════
    def _tab_partida(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(6)

        gb = QGroupBox("Automatizaciones")
        gl = QVBoxLayout(gb)
        gl.setSpacing(4)

        self.cb_auto_switch = QCheckBox("Cambiar a la pestana Radar al entrar en Champ Select")
        self.cb_auto_switch.setChecked(self.settings.get("auto_switch_radar", True))
        gl.addWidget(self.cb_auto_switch)

        self.cb_auto_aceptar = QCheckBox("Aceptar partida automaticamente")
        self.cb_auto_aceptar.setChecked(self.settings.get("auto_aceptar", False))
        gl.addWidget(self.cb_auto_aceptar)

        l.addWidget(gb)

        # ── Actualizacion del radar ──
        gb2 = QGroupBox("Frecuencia de actualizacion")
        gl2 = QVBoxLayout(gb2)
        gl2.setSpacing(2)

        gl2.addWidget(QLabel("Durante el draft (Radar):"))
        self._slider_row(
            gl2,
            "radar",
            "frecuencia_radar",
            1500,
            [(1000, "Rapida (1s)"), (1500, "Normal (1.5s)"), (3000, "Lenta (3s)")],
        )

        gl2.addWidget(QLabel("Durante la partida:"))
        self._slider_row(
            gl2,
            "partida",
            "frecuencia_partida",
            4000,
            [(2000, "Rapida (2s)"), (4000, "Normal (4s)"), (6000, "Lenta (6s)")],
        )

        l.addWidget(gb2)
        l.addStretch()
        return w

    def _slider_row(self, layout, attr_name, setting_key, default, steps):
        """Crea un slider con labels descriptivas."""
        row = QHBoxLayout()
        row.setSpacing(6)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(steps[0][0], steps[-1][0])
        step_values = [s[0] for s in steps]
        # snap to steps
        slider.setSingleStep(min(b - a for a, b in zip(step_values, step_values[1:])))
        slider.setPageStep(step_values[1] - step_values[0])

        lbl = QLabel()
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; min-width: 80px;")

        current = self.settings.get(setting_key, default)

        def _on_change(v):
            # snap to nearest step
            nearest = min(steps, key=lambda s: abs(s[0] - v))
            slider.setValue(nearest[0])
            lbl.setText(nearest[1])

        _on_change(current)
        slider.setValue(current)
        slider.valueChanged.connect(_on_change)
        row.addWidget(slider)
        row.addWidget(lbl)

        setattr(self, f"_slider_{attr_name}", slider)
        setattr(self, f"_lbl_{attr_name}", lbl)
        layout.addLayout(row)

    # ═══════════════════════════════════════════
    # Apply / OK handlers
    # ═══════════════════════════════════════════
    def _on_apply(self):
        s = self._collect()
        self.settings = s
        self._applied = True
        # Notificar al parent para que aplique inmediatamente
        if self.parent() and hasattr(self.parent(), "_aplicar_settings"):
            self.parent().user_settings = s
            from ui.helpers import guardar_settings

            guardar_settings(s)
            self.parent()._aplicar_settings()

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
            "frecuencia_radar": self._slider_radar.value(),
            "frecuencia_partida": self._slider_partida.value(),
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
