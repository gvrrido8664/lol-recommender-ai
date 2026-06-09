import ctypes
try:
    import win32gui  # type: ignore
    import win32con  # type: ignore
    import win32api  # type: ignore
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    win32gui = None  # type: ignore
    win32con = None  # type: ignore
    win32api = None  # type: ignore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap, QIcon, QColor, QPainter, QBrush, QPen
import os
import sys
import time

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312
HOTKEY_SHOW_HIDE = 1
HOTKEY_CLOSE = 2

BG_DARK = "#0a0e17"
BG_PANEL = "#0f172a"
BG_CARD = "#1a2332"
TEXT_WHITE = "#f1f5f9"
ACCENT_RED = "#e63946"
ACCENT_TEAL = "#2dd4bf"
GREEN_WR = "#22c55e"
RED_WR = "#ef4444"
YELLOW_WR = "#f59e0b"

class OverlayWindow(QWidget):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LoL Overlay")
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._show_on_game_start = True
        self._visible = False
        self._closing = False
        self._game_active = False

        self.setup_ui()
        self.resize(420, 320)
        self._center_bottom_right()

        self._hotkeys_ok = False
        self._timer_update = QTimer(self)
        self._timer_update.timeout.connect(self._update_data)
        self._timer_update.start(3000)

    def setup_ui(self):
        self.setStyleSheet(f"""
            QWidget#overlayContainer {{
                background-color: {BG_DARK};
                border: 1px solid {ACCENT_RED};
                border-left: 3px solid {ACCENT_RED};
                border-radius: 6px;
            }}
            QLabel {{
                color: {TEXT_WHITE};
                font-size: 11px;
                background: transparent;
            }}
            QPushButton {{
                background: transparent;
                border: 1px solid #2a3050;
                border-radius: 4px;
                color: {TEXT_WHITE};
                font-size: 10px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                border-color: {ACCENT_RED};
                color: {ACCENT_RED};
            }}
        """)

        container = QWidget(self)
        container.setObjectName("overlayContainer")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(3)

        # Header compacto
        header = QHBoxLayout()
        self.lbl_title = QLabel("LIVE")
        self.lbl_title.setStyleSheet(f"color: {ACCENT_RED}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        header.addWidget(self.lbl_title)
        self.lbl_phase = QLabel("")
        self.lbl_phase.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px;")
        header.addWidget(self.lbl_phase)
        header.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.clicked.connect(self.hide_overlay)
        self.btn_close.setFixedSize(18, 18)
        header.addWidget(self.btn_close)
        main_layout.addLayout(header)

        # ─── KDA GRANDE + TIEMPO + CS ───
        kda_row = QHBoxLayout()
        kda_row.setSpacing(6)

        self.lbl_kda_k = QLabel("-")
        self.lbl_kda_k.setStyleSheet(f"color: {GREEN_WR}; font-size: 28px; font-weight: bold;")
        self.lbl_kda_k.setFixedWidth(32)
        kda_row.addWidget(self.lbl_kda_k)

        lbl_s = QLabel("/")
        lbl_s.setStyleSheet(f"color: #475569; font-size: 22px;")
        lbl_s.setFixedWidth(12)
        kda_row.addWidget(lbl_s)

        self.lbl_kda_d = QLabel("-")
        self.lbl_kda_d.setStyleSheet(f"color: {RED_WR}; font-size: 28px; font-weight: bold;")
        self.lbl_kda_d.setFixedWidth(32)
        kda_row.addWidget(self.lbl_kda_d)

        lbl_s2 = QLabel("/")
        lbl_s2.setStyleSheet(f"color: #475569; font-size: 22px;")
        lbl_s2.setFixedWidth(12)
        kda_row.addWidget(lbl_s2)

        self.lbl_kda_a = QLabel("-")
        self.lbl_kda_a.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 28px; font-weight: bold;")
        self.lbl_kda_a.setFixedWidth(32)
        kda_row.addWidget(self.lbl_kda_a)

        kda_row.addSpacing(8)

        self.lbl_cs = QLabel("CS: --")
        self.lbl_cs.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 12px;")
        kda_row.addWidget(self.lbl_cs)

        kda_row.addStretch()

        self.lbl_timer = QLabel("00:00")
        self.lbl_timer.setStyleSheet(f"color: #94a3b8; font-size: 14px; font-weight: bold; font-family: 'Consolas', monospace;")
        kda_row.addWidget(self.lbl_timer)

        main_layout.addLayout(kda_row)

        # ─── ALERTAS ───
        self.lbl_alerta = QLabel("")
        self.lbl_alerta.setAlignment(Qt.AlignCenter)
        self.lbl_alerta.setWordWrap(True)
        self.lbl_alerta.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; font-weight: bold; padding: 2px 0;")
        self.lbl_alerta.setVisible(False)
        main_layout.addWidget(self.lbl_alerta)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1e293b;")
        main_layout.addWidget(sep)

        # ─── PANEL DE JUGADORES COMPACTO ───
        players_header = QHBoxLayout()
        allies_h = QLabel("🔵 ALIADOS")
        allies_h.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 10px; font-weight: bold;")
        players_header.addWidget(allies_h)
        players_header.addStretch()
        enemies_h = QLabel("🔴 ENEMIGOS")
        enemies_h.setStyleSheet(f"color: {RED_WR}; font-size: 10px; font-weight: bold;")
        players_header.addWidget(enemies_h)
        main_layout.addLayout(players_header)

        self.lbl_players = QLabel("Esperando datos...")
        self.lbl_players.setWordWrap(True)
        self.lbl_players.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 10px; line-height: 1.5;")
        main_layout.addWidget(self.lbl_players)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

    def _center_bottom_right(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.width() - 40
            y = geo.bottom() - self.height() - 100
            self.move(x, y)

    def _register_hotkeys(self):
        if not HAS_WIN32:
            return
        try:
            hwnd = int(self.winId())
            win32gui.RegisterHotKey(hwnd, HOTKEY_SHOW_HIDE, MOD_CONTROL | MOD_SHIFT, ord('I'))
            win32gui.RegisterHotKey(hwnd, HOTKEY_CLOSE, MOD_CONTROL | MOD_SHIFT, ord('X'))
        except Exception as e:
            print(f"[Overlay] Error registrando hotkeys: {e}")

    def winEvent(self, msg, wparam, lparam):
        if not HAS_WIN32:
            return False
        if msg == WM_HOTKEY:
            if wparam == HOTKEY_SHOW_HIDE:
                self.toggle_visibility()
                return True
            elif wparam == HOTKEY_CLOSE:
                self.close_overlay()
                return True
        return False

    def show_overlay(self):
        self._visible = True
        self.show()
        self.raise_()
        self._center_bottom_right()
        if not self._hotkeys_ok:
            self._register_hotkeys()
            self._hotkeys_ok = True

    def hide_overlay(self):
        self._visible = False
        self.hide()

    def toggle_visibility(self):
        if self._visible:
            self.hide_overlay()
        else:
            self.show_overlay()

    def close_overlay(self):
        self._closing = True
        self._timer_update.stop()
        if HAS_WIN32:
            try:
                hwnd = int(self.winId())
                win32gui.UnregisterHotKey(hwnd, HOTKEY_SHOW_HIDE)
                win32gui.UnregisterHotKey(hwnd, HOTKEY_CLOSE)
            except:
                pass
        self.hide()
        self.closed.emit()

    def update_game_state(self, is_active, lcu_connector=None):
        self._game_active = is_active
        if is_active and self._show_on_game_start and not self._visible:
            self.show_overlay()
        elif not is_active and self._visible:
            self.hide_overlay()

    def _update_data(self):
        if not self._visible or not self._game_active:
            return
        try:
            from .lcu_api import LCUConnector
            lcu = LCUConnector()
            if not lcu.conectar():
                return
            live_data = lcu.obtener_liveclient_data()
            if not live_data or not live_data[0]:
                self.lbl_phase.setText("Cargando...")
                return
            players, game_data = live_data
            if not players:
                return

            mi_nombre = lcu.obtener_nombre_invocador()
            yo = None
            aliados = []
            enemigos = []
            for p in players:
                if p.get("summonerName") == mi_nombre:
                    yo = p
                elif p.get("team") == "ORDER":
                    aliados.append(p)
                else:
                    enemigos.append(p)

            # Game timer
            game_time = game_data.get("gameTime", 0) if isinstance(game_data, dict) else 0
            mins = int(game_time // 60)
            secs = int(game_time % 60)
            self.lbl_timer.setText(f"{mins:02d}:{secs:02d}")

            if yo:
                k = yo.get("kills", 0) or 0
                d = yo.get("deaths", 0) or 0
                a = yo.get("assists", 0) or 0
                cs = yo.get("creepScore", 0) or 0

                self.lbl_kda_k.setText(str(k))
                self.lbl_kda_d.setText(str(d))
                self.lbl_kda_a.setText(str(a))
                self.lbl_cs.setText(f"CS: {cs}")

                # Colorear muertes: verde si <=2, rojo si >=6
                self.lbl_kda_d.setStyleSheet(
                    f"color: {'#22c55e' if d <= 2 else '#ef4444' if d >= 6 else '#f59e0b'}; font-size: 28px; font-weight: bold;"
                )

                # Alertas relevantes
                alertas = []
                if yo.get("isDead", False):
                    alertas.append("💀 MUERTO — Espera respawn, analiza tu jugada")
                if d >= 6:
                    alertas.append(f"⚠️ {d} MUERTES — Juega seguro, no obligues jugadas")
                if d >= 3 and k < 2:
                    alertas.append("⚠️ Vas perdiendo — Farmea y espera tu oportunidad")

                if alertas:
                    self.lbl_alerta.setText(" | ".join(alertas[:2]))
                    self.lbl_alerta.setVisible(True)
                else:
                    self.lbl_alerta.setVisible(False)
            else:
                self.lbl_kda_k.setText("-"); self.lbl_kda_d.setText("-"); self.lbl_kda_a.setText("-")
                self.lbl_cs.setText("CS: --")
                self.lbl_alerta.setVisible(False)

            # Panel de jugadores compacto: aliados verdes, enemigos rojos con amenaza
            lines = []
            if not aliados and not enemigos:
                lines.append("Esperando datos de jugadores...")
            else:
                for label, team, icon, color in [("ALIADOS", aliados, "🔵", ACCENT_TEAL), ("ENEMIGOS", enemigos, "🔴", RED_WR)]:
                    if team:
                        parts = []
                        for p in team:
                            pk = p.get("kills", 0) or 0
                            pd = p.get("deaths", 0) or 0
                            pa = p.get("assists", 0) or 0
                            pname = p.get("summonerName", "?")[:10]
                            pchamp = p.get("championName", "?")[:8]
                            # Nivel de amenaza
                            kda_rat = (pk + pa) / max(1, pd)
                            threat = "🔥" if kda_rat >= 4 or pk >= 7 else ("⚠️" if kda_rat >= 2.5 else "")
                            parts.append(f"{threat}{pchamp} {pk}/{pd}/{pa}")
                        lines.append(f"<span style='color:{color};font-weight:bold;'>{icon}{label}</span> {' · '.join(parts)}")

            self.lbl_players.setText("<br>".join(lines))

        except Exception as e:
            print(f"[Overlay] Error update: {e}")

    def cleanup(self):
        self._closing = True
        self._timer_update.stop()
        try:
            hwnd = int(self.winId())
            win32gui.UnregisterHotKey(hwnd, HOTKEY_SHOW_HIDE)
            win32gui.UnregisterHotKey(hwnd, HOTKEY_CLOSE)
        except:
            pass
        self.close()
