"""Componentes reutilizables de UI para NEXUS.

EmptyStateWidget, BadgeLabel, ErrorBanner, LoadingOverlay, StatCardWidget.
Todos usan constantes de ui.design para mantener consistencia de paleta.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.design import *


class EmptyStateWidget(QWidget):
    def __init__(self, icono, titulo, descripcion, cta_text=None, cta_callback=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)
        lay.setContentsMargins(24, 32, 24, 32)

        lbl_icon = QLabel(icono)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("font-size: 36px; background: transparent;")
        lay.addWidget(lbl_icon)

        lbl_title = QLabel(titulo)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet(
            f"color: {ACCENT_RED}; font-size: 14px; font-weight: bold; background: transparent;"
        )
        lay.addWidget(lbl_title)

        lbl_desc = QLabel(descripcion)
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;")
        lay.addWidget(lbl_desc)

        if cta_text and cta_callback:
            btn = QPushButton(cta_text)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {ACCENT_RED}; color: white; border: none;
                               border-radius: 6px; font-weight: bold; font-size: 11px; padding: 8px 18px; }}
                QPushButton:hover {{ background-color: {HOVER_GLOW}; }}
            """)
            btn.clicked.connect(cta_callback)
            lay.addWidget(btn, alignment=Qt.AlignCenter)


class BadgeLabel(QWidget):
    def __init__(self, texto, color=GREEN_WR, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        lbl = QLabel(texto)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"""
            color: {color}; background-color: {BG_DARK}; border: 1px solid {color};
            border-radius: 8px; padding: 2px 10px; font-weight: bold; font-size: 9px;
        """)
        lay.addWidget(lbl)


class ErrorBanner(QFrame):
    def __init__(self, mensaje, cta_text=None, cta_callback=None, auto_hide_ms=30000, parent=None):
        super().__init__(parent)
        self.setObjectName("ErrorBanner")
        self.setStyleSheet("""
            QFrame#ErrorBanner {
                background-color: #1a0a0a; border: 1px solid #3a1a1a;
                border-radius: 6px; padding: 8px 12px;
            }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        lbl_icon = QLabel("⚠️")
        lbl_icon.setStyleSheet("background: transparent; font-size: 14px;")
        lay.addWidget(lbl_icon)

        lbl_msg = QLabel(mensaje)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet(
            f"color: {RED_WR}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        lay.addWidget(lbl_msg, 1)

        if cta_text and cta_callback:
            btn = QPushButton(cta_text)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {ACCENT_RED}; border: 1px solid {ACCENT_RED};
                               border-radius: 4px; font-weight: bold; font-size: 10px; padding: 4px 10px; }}
                QPushButton:hover {{ background-color: {ACCENT_RED}; color: white; }}
            """)
            btn.clicked.connect(cta_callback)
            lay.addWidget(btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: none; font-size: 12px; }}
            QPushButton:hover {{ color: {TEXT_WHITE}; }}
        """)
        self._close_btn.clicked.connect(self.hide)
        lay.addWidget(self._close_btn)

        if auto_hide_ms and auto_hide_ms > 0:
            QTimer.singleShot(auto_hide_ms, self.hide)


class LoadingOverlay(QFrame):
    def __init__(self, parent=None, mensaje="Cargando..."):
        super().__init__(parent)
        self.setObjectName("LoadingOverlay")
        self.setStyleSheet(
            "QFrame#LoadingOverlay { background-color: rgba(7,7,10,200); border-radius: 10px; }"
        )
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)

        self._spinner = QLabel("⏳")
        self._spinner.setAlignment(Qt.AlignCenter)
        self._spinner.setStyleSheet("font-size: 32px; background: transparent;")
        lay.addWidget(self._spinner)

        self._msg = QLabel(mensaje)
        self._msg.setAlignment(Qt.AlignCenter)
        self._msg.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        lay.addWidget(self._msg)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate_spinner)
        self._spin_frames = ["⏳", "⌛", "⏳", "⌛"]
        self._spin_idx = 0

    def show(self):
        self._spin_idx = 0
        self._timer.start(500)
        super().show()
        self.raise_()

    def hide(self):
        self._timer.stop()
        super().hide()

    def set_message(self, msg):
        self._msg.setText(msg)

    def _rotate_spinner(self):
        self._spin_idx = (self._spin_idx + 1) % len(self._spin_frames)
        self._spinner.setText(self._spin_frames[self._spin_idx])
