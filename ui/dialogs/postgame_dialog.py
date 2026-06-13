"""Dialogo de resumen post-partida. Extraido de app.py sin cambios."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
                               QLabel, QPushButton)
from PySide6.QtCore import Qt, Signal

from ui.design import *


class PostGameDialog(QDialog):
    """Resumen rÃ¡pido al terminar partida: KDA, CS/min, comparativa y consejo del coach."""

    coaching_requested = Signal()

    def __init__(self, stats: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resumen de Partida")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(420)
        self._build_ui(stats)
        if parent:
            pr = parent.frameGeometry()
            self.move(pr.center().x() - self.width() // 2, pr.top() + 80)

    def _build_ui(self, s):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("pgCard")
        card.setStyleSheet(f"""
            QWidget#pgCard {{
                background: {BG_PANEL};
                border: 2px solid {BORDER_ACCENT};
                border-radius: 10px;
            }}
            QLabel {{ color: {TEXT_WHITE}; background: transparent; }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        # TÃ­tulo + resultado
        hdr = QHBoxLayout()
        lbl_title = QLabel("ðŸ  RESUMEN DE PARTIDA")
        lbl_title.setStyleSheet(f"color: {ACCENT_RED}; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        resultado = s.get("resultado", "")
        if resultado == "Victoria":
            lbl_res = QLabel("  VICTORIA  ")
            lbl_res.setStyleSheet(f"background: {GREEN_WR}; color: #fff; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 2px 6px;")
        elif resultado == "Derrota":
            lbl_res = QLabel("  DERROTA  ")
            lbl_res.setStyleSheet(f"background: {RED_WR}; color: #fff; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 2px 6px;")
        else:
            lbl_res = QLabel("")
        hdr.addWidget(lbl_res)
        btn_close = QPushButton("âœ•")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet(f"background: transparent; border: none; color: {TEXT_MUTED}; font-size: 12px;")
        btn_close.clicked.connect(self.close)
        hdr.addWidget(btn_close)
        lay.addLayout(hdr)

        sep = QLabel(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_SUBTLE};")
        lay.addWidget(sep)

        # CampeÃ³n
        champ = s.get("champion", "?")
        lbl_champ = QLabel(f"ðŸŽ®  {champ}")
        lbl_champ.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {ACCENT_TEAL};")
        lay.addWidget(lbl_champ)

        # KDA
        k, d, a = s.get("kills", 0), s.get("deaths", 0), s.get("assists", 0)
        avg_k = s.get("avg_k", 0)
        avg_d = s.get("avg_d", 1)
        avg_a = s.get("avg_a", 0)

        kda_row = QHBoxLayout()
        kda_row.setSpacing(4)
        for val, ref, label, good_high in [(k, avg_k, "K", True), (d, avg_d, "D", False), (a, avg_a, "A", True)]:
            col = GREEN_WR if (val >= ref if good_high else val <= ref) else RED_WR
            lbl = QLabel(f"<b style='color:{col};font-size:22px;'>{val}</b><span style='color:{TEXT_MUTED};font-size:10px;'> {label}</span>")
            lbl.setAlignment(Qt.AlignCenter)
            kda_row.addWidget(lbl)
            if label != "A":
                kda_row.addWidget(QLabel("/"))
        kda_row.addStretch()

        avg_kda_str = f"Tu media: {avg_k:.1f}/{avg_d:.1f}/{avg_a:.1f}"
        lbl_avg = QLabel(avg_kda_str)
        lbl_avg.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        lbl_avg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        kda_row.addWidget(lbl_avg)
        lay.addLayout(kda_row)

        # CS/min
        cs = s.get("cs", 0)
        game_time = s.get("game_time", 1)
        cs_min = cs / max(1, game_time / 60)
        cs_ref = 6.5
        cs_color = GREEN_WR if cs_min >= cs_ref else (YELLOW_WR if cs_min >= 5.0 else RED_WR)
        lbl_cs = QLabel(f"ðŸŒ¾  CS: {cs}  ({cs_min:.1f}/min)  â€” ref. {cs_ref}/min")
        lbl_cs.setStyleSheet(f"color: {cs_color}; font-size: 11px;")
        lay.addWidget(lbl_cs)

        # Vision y objetivos
        vision = s.get("vision_score", 0)
        wards = s.get("wards_placed", 0)
        cwards = s.get("control_wards", 0)
        objectives = s.get("objectives", 0)
        dmg = s.get("damage_dealt", 0)
        if game_time > 0:
            dmg_min = dmg / (game_time / 60)
            dmg_str = f"{dmg_min/1000:.1f}k/min" if dmg > 0 else ""
        else:
            dmg_str = ""
        extras = []
        if vision > 0:
            extras.append(f"ðŸ‘ Vision {vision}")
        if wards > 0:
            extras.append(f"ðŸ® Wards {wards}")
        if cwards > 0:
            extras.append(f"ðŸ”® Control {cwards}")
        if objectives > 0:
            extras.append(f"ðŸŽ¯ Objs {objectives}")
        if dmg_str:
            extras.append(f"âš”ï¸ Dano {dmg_str}")
        if extras:
            lbl_extras = QLabel("  |  ".join(extras))
            lbl_extras.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; padding: 2px 0;")
            lay.addWidget(lbl_extras)

        # Coaching tip
        tip = s.get("tip", "")
        positives = s.get("positives", [])
        negatives = s.get("negatives", [])

        if positives or negatives:
            sep2 = QLabel(); sep2.setFixedHeight(1)
            sep2.setStyleSheet(f"background: {BORDER_SUBTLE};")
            lay.addWidget(sep2)

            if positives:
                for pt in positives:
                    lbl_p = QLabel(pt)
                    lbl_p.setWordWrap(True)
                    lbl_p.setStyleSheet(f"color: {GREEN_WR}; font-size: 10px; padding: 1px 0;")
                    lay.addWidget(lbl_p)

            if negatives:
                for ng in negatives:
                    lbl_n = QLabel(ng)
                    lbl_n.setWordWrap(True)
                    lbl_n.setStyleSheet(f"color: {RED_WR}; font-size: 10px; padding: 1px 0;")
                    lay.addWidget(lbl_n)

        if tip:
            sep3 = QLabel(); sep3.setFixedHeight(1)
            sep3.setStyleSheet(f"background: {BORDER_SUBTLE};")
            lay.addWidget(sep3)
            lbl_tip = QLabel(tip)
            lbl_tip.setWordWrap(True)
            lbl_tip.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; padding: 4px 0;")
            lay.addWidget(lbl_tip)

        # Botones
        btn_row = QHBoxLayout()
        btn_coach = QPushButton("ðŸ“– Ver Coaching")
        btn_coach.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; color: {ACCENT_TEAL};
                border: 1px solid {ACCENT_TEAL}; border-radius: 5px;
                padding: 5px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {ACCENT_TEAL}; color: #000; }}
        """)
        btn_coach.clicked.connect(self._on_coaching)
        btn_row.addWidget(btn_coach)
        btn_row.addStretch()
        btn_ok = QPushButton("Cerrar")
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; color: {TEXT_MUTED};
                border: 1px solid {BORDER_SUBTLE}; border-radius: 5px;
                padding: 5px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ color: {TEXT_WHITE}; border-color: {TEXT_WHITE}; }}
        """)
        btn_ok.clicked.connect(self.close)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

        outer.addWidget(card)

    def _on_coaching(self):
        self.coaching_requested.emit()
        self.close()
