"""Revision post-partida tipo coach (solo tus stats de la partida):
comparativa vs benchmarks de rol, series por minuto (si hay timeline),
fortalezas/mejoras y veredicto con acciones concretas."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
                               QLabel, QPushButton, QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal

from ui.design import *
from ui.dialogs.postgame_charts import BarComparisonWidget, TimelineChartWidget


class PostGameDialog(QDialog):
    """Revision completa de TU partida: stats, comparativa, series y veredicto."""

    coaching_requested = Signal()

    def __init__(self, stats: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Revisión de Partida")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(500)
        self._build_ui(stats)
        if parent:
            pr = parent.frameGeometry()
            self.move(pr.center().x() - self.width() // 2, max(40, pr.top() + 40))

    # ── helpers ──
    def _seccion(self, lay, titulo, color=None):
        lbl = QLabel(titulo)
        lbl.setStyleSheet(f"color: {color or ACCENT_RED}; font-size: 11px; font-weight: bold; "
                          f"letter-spacing: 1px; margin-top: 6px;")
        lay.addWidget(lbl)
        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background: {BORDER_SUBTLE};")
        lay.addWidget(sep)

    def _metricas(self, s):
        gt = max(1, s.get("game_time", 1))
        mins = gt / 60.0
        k, d, a = s.get("kills", 0), s.get("deaths", 0), s.get("assists", 0)
        kda = (k + a) / max(1, d)
        cs_min = s.get("cs", 0) / mins
        vis_min = s.get("vision_score", 0) / mins
        dmg_min = s.get("damage_dealt", 0) / mins
        gold_min = s.get("gold", 0) / mins
        role = (s.get("role") or "").upper()
        lane = (s.get("lane") or "").upper()
        es_sup = "SUPPORT" in role or "SUPPORT" in lane
        es_jg = lane == "JUNGLE"
        b_cs = 1.5 if es_sup else (5.5 if es_jg else 7.0)
        b_gold = 250 if es_sup else 350
        b_dmg = 250 if es_sup else (400 if es_jg else 500)
        b_vis = 1.8 if es_sup else 0.9
        return [
            {"label": "KDA",        "valor": f"{kda:.1f}",       "ratio": kda / 3.0},
            {"label": "CS/min",     "valor": f"{cs_min:.1f}",    "ratio": cs_min / b_cs},
            {"label": "Oro/min",    "valor": f"{gold_min:.0f}",  "ratio": gold_min / b_gold},
            {"label": "Daño/min",   "valor": f"{dmg_min:.0f}",   "ratio": dmg_min / b_dmg},
            {"label": "Visión/min", "valor": f"{vis_min:.2f}",   "ratio": vis_min / b_vis},
        ]

    def _build_ui(self, s):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("pgCard")
        card.setStyleSheet(f"""
            QWidget#pgCard {{ background: {BG_PANEL}; border: 2px solid {BORDER_ACCENT}; border-radius: 10px; }}
            QLabel {{ color: {TEXT_WHITE}; background: transparent; }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 12, 16, 12)
        card_lay.setSpacing(8)

        # ── Cabecera (fija) ──
        hdr = QHBoxLayout()
        lbl_title = QLabel("🏁  REVISIÓN DE PARTIDA")
        lbl_title.setStyleSheet(f"color: {ACCENT_RED}; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        resultado = s.get("resultado", "")
        if resultado in ("Victoria", "Derrota"):
            lbl_res = QLabel(f"  {resultado.upper()}  ")
            col = GREEN_WR if resultado == "Victoria" else RED_WR
            lbl_res.setStyleSheet(f"background: {col}; color: #fff; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 2px 6px;")
            hdr.addWidget(lbl_res)
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet(f"background: transparent; border: none; color: {TEXT_MUTED}; font-size: 12px;")
        btn_close.clicked.connect(self.close)
        hdr.addWidget(btn_close)
        card_lay.addLayout(hdr)

        # ── Contenido scrollable ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setMaximumHeight(640)
        cont = QWidget(); cont.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(6)

        # Campeon + KDA
        champ = s.get("champion", "?")
        k, d, a = s.get("kills", 0), s.get("deaths", 0), s.get("assists", 0)
        gt = s.get("game_time", 0)
        cs = s.get("cs", 0)
        cs_min = cs / max(1, gt / 60) if gt else 0
        lbl_champ = QLabel(f"🎮  {champ}    "
                           f"<span style='color:{ACCENT_TEAL};font-weight:bold;'>{k}/{d}/{a}</span>"
                           f"   <span style='color:{TEXT_MUTED};font-size:10px;'>{cs} CS · {cs_min:.1f}/min · {gt//60}min</span>")
        lbl_champ.setTextFormat(Qt.RichText)
        lbl_champ.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {ACCENT_TEAL};")
        lay.addWidget(lbl_champ)

        # ── Comparativa vs benchmark de rol ──
        self._seccion(lay, "📊  RENDIMIENTO vs BENCHMARK DEL ROL")
        leyenda = QLabel("Barra llena = referencia del rol · verde supera, ámbar cerca, rojo bajo")
        leyenda.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
        lay.addWidget(leyenda)
        chart = BarComparisonWidget()
        chart.set_data(self._metricas(s))
        lay.addWidget(chart)

        # ── Series por minuto (si hay timeline) ──
        timeline = s.get("timeline") or {}
        if timeline.get("oro") and len(timeline["oro"]) >= 2:
            self._seccion(lay, "📈  EVOLUCIÓN POR MINUTO", ACCENT_TEAL)
            ch_oro = TimelineChartWidget()
            ch_oro.set_data(timeline["oro"], "Oro total", "#f0b232", " oro")
            lay.addWidget(ch_oro)
            if timeline.get("cs"):
                ch_cs = TimelineChartWidget()
                ch_cs.set_data(timeline["cs"], "CS acumulado", ACCENT_TEAL, " CS")
                lay.addWidget(ch_cs)

        # ── Fortalezas / A mejorar ──
        positives = s.get("positives", [])
        negatives = s.get("negatives", [])
        if positives:
            self._seccion(lay, "✅  LO QUE HICISTE BIEN", GREEN_WR)
            for pt in positives:
                l = QLabel(f"•  {pt}"); l.setWordWrap(True)
                l.setStyleSheet(f"color: {GREEN_WR}; font-size: 10px;")
                lay.addWidget(l)
        if negatives:
            self._seccion(lay, "⚠️  A MEJORAR", RED_WR)
            for ng in negatives:
                l = QLabel(f"•  {ng}"); l.setWordWrap(True)
                l.setStyleSheet(f"color: {RED_WR}; font-size: 10px;")
                lay.addWidget(l)

        # ── Veredicto del coach ──
        veredicto = s.get("veredicto") or ([s["tip"]] if s.get("tip") else [])
        if veredicto:
            self._seccion(lay, "🧠  VEREDICTO DEL COACH", YELLOW_WR)
            for v in veredicto:
                l = QLabel(f"▸  {v}"); l.setWordWrap(True)
                l.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; padding: 2px 0;")
                lay.addWidget(l)

        lay.addStretch(1)
        scroll.setWidget(cont)
        card_lay.addWidget(scroll, 1)

        # ── Botones (fijos) ──
        btn_row = QHBoxLayout()
        btn_coach = QPushButton("📖 Ver Coaching")
        btn_coach.setStyleSheet(f"""
            QPushButton {{ background: {BG_CARD}; color: {ACCENT_TEAL}; border: 1px solid {ACCENT_TEAL};
                           border-radius: 5px; padding: 5px 12px; font-size: 11px; }}
            QPushButton:hover {{ background: {ACCENT_TEAL}; color: #000; }}
        """)
        btn_coach.clicked.connect(self._on_coaching)
        btn_row.addWidget(btn_coach)
        btn_row.addStretch()
        btn_ok = QPushButton("Cerrar")
        btn_ok.setStyleSheet(f"""
            QPushButton {{ background: {BG_CARD}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE};
                           border-radius: 5px; padding: 5px 12px; font-size: 11px; }}
            QPushButton:hover {{ color: {TEXT_WHITE}; border-color: {TEXT_WHITE}; }}
        """)
        btn_ok.clicked.connect(self.close)
        btn_row.addWidget(btn_ok)
        card_lay.addLayout(btn_row)

        outer.addWidget(card)

    def _on_coaching(self):
        self.coaching_requested.emit()
        self.close()
