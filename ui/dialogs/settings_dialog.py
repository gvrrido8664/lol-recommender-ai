"""Dialogo de configuracion de usuario. Extraido de app.py sin cambios."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
                               QRadioButton, QCheckBox, QComboBox, QGroupBox,
                               QButtonGroup, QSlider, QScrollArea, QDialogButtonBox)
from PySide6.QtCore import Qt

from ui.design import *


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("NEXUS — Configuración")
        self.resize(470, 540)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QLabel {{ color: {TEXT_WHITE}; font-size: 12px; background: transparent; }}
            QRadioButton {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 6px; padding: 6px 4px; }}
            QRadioButton::indicator {{ width: 18px; height: 18px; }}
            QRadioButton::indicator:checked {{ background-color: {BORDER_ACCENT}; border-radius: 9px; }}
            QRadioButton:hover {{ background-color: #211a28; border-radius: 4px; }}
            QCheckBox {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 8px; padding: 2px 0; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QCheckBox:hover {{ color: {BORDER_ACCENT}; }}
            QComboBox {{ background-color: #251d2b; color: {TEXT_WHITE}; border: 1px solid #2f2535; border-radius: 4px; padding: 4px 8px; min-width: 50px; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QGroupBox {{ color: {BORDER_ACCENT}; font-weight: bold; font-size: 12px; border: 1px solid #2a2030; border-radius: 6px; margin-top: 8px; padding-top: 14px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
            QPushButton {{ color: white; }}
        """)
        layout = QVBoxLayout(self); layout.setSpacing(4)

        title = QLabel("⚙️ CONFIGURACIÓN")
        title.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 18px; padding: 6px 0 2px 0;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_w = QWidget()
        scroll_w.setStyleSheet("background: transparent;")
        form = QVBoxLayout(scroll_w)
        form.setSpacing(2)
        form.setContentsMargins(0, 0, 0, 0)

        def _seccion(texto):
            gb = QGroupBox(texto)
            gl = QVBoxLayout(gb)
            gl.setSpacing(3)
            form.addWidget(gb)
            return gl

        def _desc(texto):
            lbl = QLabel(texto)
            lbl.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 11px; padding-left: 2px;")
            lbl.setWordWrap(True)
            return lbl

        # ── 1. ¿CUÁNTA AYUDA QUIERES? ──
        g_modo = _seccion("🎯 MODO DE AYUDA")
        self.rb_basico = QRadioButton("🟢 Básico — Todo explicado, guiado paso a paso")
        self.rb_normal = QRadioButton("🟡 Normal — Datos útiles sin vueltas, ideal para la mayoría")
        self.rb_avanzado = QRadioButton("🔴 Avanzado — Análisis táctico completo, tú decides")

        self.grupo_modo = QButtonGroup(self)
        self.grupo_modo.addButton(self.rb_basico, 1)
        self.grupo_modo.addButton(self.rb_normal, 2)
        self.grupo_modo.addButton(self.rb_avanzado, 3)

        modo_actual = "normal"
        if self.settings.get("modo_principiante", False): modo_actual = "basico"
        elif self.settings.get("modo_profesional", False): modo_actual = "avanzado"

        if modo_actual == "basico":
            self.rb_basico.setChecked(True)
        elif modo_actual == "avanzado":
            self.rb_avanzado.setChecked(True)
        else:
            self.rb_normal.setChecked(True)

        self.grupo_modo.buttonClicked.connect(lambda btn: setattr(self, '_modo',
            'basico' if btn == self.rb_basico else 'avanzado' if btn == self.rb_avanzado else 'normal'))
        self._modo = modo_actual

        g_modo.addWidget(self.rb_basico)
        g_modo.addWidget(self.rb_normal)
        g_modo.addWidget(self.rb_avanzado)
        self._lbl_modo_desc = _desc(
            "Básico: explicaciones amplias y tooltips grandes. "
            "Normal: información compacta pero completa. "
            "Avanzado: solo datos crudos, máximo rendimiento visual."
        )
        g_modo.addWidget(self._lbl_modo_desc)

        # ── 2. TECLA DE FLASH ──
        g_flash = _seccion("⌨️ TECLA DE FLASH")
        fl = QHBoxLayout()
        fl.addWidget(QLabel("¿En qué tecla tienes Flash?"))
        self.cb_flash_tecla = QComboBox()
        self.cb_flash_tecla.addItems(["D", "F"])
        self.cb_flash_tecla.setCurrentText("D" if self.settings.get("flash_en_d", True) else "F")
        fl.addWidget(self.cb_flash_tecla)
        fl.addStretch()
        g_flash.addLayout(fl)

        # ── 3. IMPORTACIÓN AUTOMÁTICA ──
        g_auto = _seccion("🤖 IMPORTACIÓN AUTOMÁTICA")
        g_auto.addWidget(_desc(
            "Al elegir un campeón en Champ Select, NEXUS puede importar "
            "automáticamente estas configuraciones al cliente de LoL."
        ))
        self.cb_auto_runas = QCheckBox("📜 Importar runas automáticamente")
        self.cb_auto_runas.setChecked(self.settings.get("auto_runas", False))
        self.cb_auto_runas.setToolTip("Crea una página de runas con la configuración recomendada para tu campeón.")
        g_auto.addWidget(self.cb_auto_runas)

        self.cb_auto_hechizos = QCheckBox("✨ Importar hechizos automáticamente")
        self.cb_auto_hechizos.setChecked(self.settings.get("auto_hechizos", False))
        self.cb_auto_hechizos.setToolTip("Selecciona los hechizos recomendados (respeta tu tecla de Flash).")
        g_auto.addWidget(self.cb_auto_hechizos)

        self.cb_auto_habilidades = QCheckBox("⚡ Importar orden de habilidades automáticamente")
        self.cb_auto_habilidades.setChecked(self.settings.get("auto_habilidades", False))
        self.cb_auto_habilidades.setToolTip("Configura el orden de skills Q>E>W según la recomendación.")
        g_auto.addWidget(self.cb_auto_habilidades)

        self.cb_auto_items = QCheckBox("🛡️ Crear set de objetos automáticamente")
        self.cb_auto_items.setChecked(self.settings.get("auto_items", False))
        self.cb_auto_items.setToolTip("Crea un set de objetos con el core build y early game recomendados.")
        g_auto.addWidget(self.cb_auto_items)

        # ── 5. COMPORTAMIENTO ──
        g_comp = _seccion("🎮 COMPORTAMIENTO")
        self.cb_auto_switch = QCheckBox("🔄 Cambiar automáticamente a la pestaña Radar en Champ Select")
        self.cb_auto_switch.setChecked(self.settings.get("auto_switch_radar", True))
        self.cb_auto_switch.setToolTip("NEXUS cambiará a Radar en Vivo cuando detecte una sesión de draft.")
        g_comp.addWidget(self.cb_auto_switch)

        self.cb_auto_aceptar = QCheckBox("✅ Auto-aceptar partida (ReadyCheck)")
        self.cb_auto_aceptar.setChecked(self.settings.get("auto_aceptar", False))
        self.cb_auto_aceptar.setToolTip("Acepta automáticamente cuando salta la cola. ¡No te pierdas partidas!")
        g_comp.addWidget(self.cb_auto_aceptar)

        # Frecuencia del radar
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Frecuencia del radar:"))
        self.slider_freq = QSlider(Qt.Horizontal)
        self.slider_freq.setRange(500, 3000)
        self.slider_freq.setSingleStep(250)
        self.slider_freq.setValue(self.settings.get("frecuencia_radar", 1500))
        self.slider_freq.setToolTip("Cada cuántos ms se actualiza el Radar en Vivo.")
        freq_layout.addWidget(self.slider_freq)
        self.lbl_freq_val = QLabel(f"{self.slider_freq.value()}ms")
        self.lbl_freq_val.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; min-width: 50px;")
        self.slider_freq.valueChanged.connect(lambda v: self.lbl_freq_val.setText(f"{v}ms"))
        freq_layout.addWidget(self.lbl_freq_val)
        g_comp.addLayout(freq_layout)

        # ── 6. NOTIFICACIONES ──
        g_notif = _seccion("🔔 NOTIFICACIONES")
        self.cb_sonido = QCheckBox("🔔 Sonidos al conectar, encontrar partida o terminar")
        self.cb_sonido.setChecked(self.settings.get("sonidos", False))
        self.cb_sonido.setToolTip("Avisos sonoros para que sepas qué pasa sin mirar la app.")
        g_notif.addWidget(self.cb_sonido)

        self.cb_notificaciones = QCheckBox("💬 Notificaciones de escritorio (cola, draft, fin de partida)")
        self.cb_notificaciones.setChecked(self.settings.get("notificaciones_escritorio", True))
        self.cb_notificaciones.setToolTip("Muestra avisos emergentes de Windows en eventos clave.")
        g_notif.addWidget(self.cb_notificaciones)

        # ── 7. EXTRAS ──
        g_extra = _seccion("🎨 EXTRAS")
        self.cb_dificultad = QCheckBox("⭐ Estrellas de dificultad en campeones (Garen ⭐, Zed ⭐⭐⭐)")
        self.cb_dificultad.setChecked(self.settings.get("mostrar_dificultad", True))
        self.cb_dificultad.setToolTip("Identifica de un vistazo qué tan difícil es un campeón.")
        g_extra.addWidget(self.cb_dificultad)
        self.cb_recordatorios = QCheckBox("💬 Recordatorios en partida (wardear, objetivos, etc.)")
        self.cb_recordatorios.setChecked(self.settings.get("recordatorios_partida", True))
        self.cb_recordatorios.setToolTip("Consejos que aparecen durante la partida para no perder el foco.")
        g_extra.addWidget(self.cb_recordatorios)

        form.addStretch()
        scroll.setWidget(scroll_w)
        layout.addWidget(scroll, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_settings(self):
        return {"auto_deteccion": True,
                "mostrar_power_spikes": self._modo != "avanzado",
                "mostrar_explicaciones": self._modo == "basico",
                "sonidos": self.cb_sonido.isChecked(),
                "frecuencia_radar": self.slider_freq.value(),
                "modo_principiante": self._modo == "basico",
                "modo_profesional": self._modo == "avanzado",
                "recordatorios_partida": self.cb_recordatorios.isChecked(),
                "mostrar_dificultad": self.cb_dificultad.isChecked(),
                "tooltips_grandes": self._modo == "basico",
                "flash_en_d": self.cb_flash_tecla.currentText() == "D",
                "auto_runas": self.cb_auto_runas.isChecked(),
                "auto_hechizos": self.cb_auto_hechizos.isChecked(),
                "auto_habilidades": self.cb_auto_habilidades.isChecked(),
                "auto_items": self.cb_auto_items.isChecked(),
                "auto_switch_radar": self.cb_auto_switch.isChecked(),
                "auto_aceptar": self.cb_auto_aceptar.isChecked(),
                "notificaciones_escritorio": self.cb_notificaciones.isChecked(),
                }
