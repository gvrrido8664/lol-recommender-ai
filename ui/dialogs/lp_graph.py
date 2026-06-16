"""Widget de grafica LP estilo op.gg — curvas bezier, bandas de tier, fill degradado."""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QLinearGradient, QFont
from PySide6.QtCore import Qt

from ui.design import *


class LPGraphWidget(QWidget):
    TIER_BANDS = [
        (0,    400,  "Iron",     "#6b7280"),
        (400,  800,  "Bronze",   "#b45309"),
        (800,  1200, "Silver",   "#a39a93"),
        (1200, 1600, "Gold",     "#f59e0b"),
        (1600, 2000, "Plat",     "#c89b3c"),
        (2000, 2400, "Emerald",  "#22c55e"),
        (2400, 2800, "Diamond",  "#f0b232"),
        (2800, 3200, "Master+",  "#e879f9"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self.setMinimumHeight(160)

    def set_data(self, history: list):
        self._data = history
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 52, 16, 18, 28

        p.fillRect(0, 0, w, h, QColor(BG_CARD))

        if not self._data:
            p.setPen(QColor(TEXT_MUTED))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(0, 0, w, h, Qt.AlignCenter, "Sin datos de LP")
            p.end()
            return

        values = [d["lp_total"] for d in self._data]
        mn, mx = min(values), max(values)
        rng = max(mx - mn, 200)
        mn -= rng * 0.08
        mx += rng * 0.08
        rng = mx - mn

        n = len(self._data)

        def to_x(i):
            return pad_l + int(i / max(1, n - 1) * (w - pad_l - pad_r))

        def to_y(val):
            return h - pad_b - int((val - mn) / rng * (h - pad_t - pad_b))

        chart_bottom = h - pad_b
        chart_top = pad_t
        chart_h = chart_bottom - chart_top

        # ── Bandas de tier ──
        for lo, hi, name, color in self.TIER_BANDS:
            if hi <= mn or lo >= mx:
                continue
            y1 = to_y(hi) if hi <= mx else chart_top
            y2 = to_y(lo) if lo >= mn else chart_bottom
            band_y = min(y1, y2)
            band_h = abs(y2 - y1)
            if band_h < 1:
                continue
            band_color = QColor(color)
            band_color.setAlpha(18)
            p.fillRect(pad_l, band_y, w - pad_l, band_h, band_color)

            # Label del tier (minúscula, sutil)
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QColor(color))
            mid_y = band_y + band_h // 2
            p.drawText(2, mid_y - 7, pad_l - 6, 14, Qt.AlignRight | Qt.AlignVCenter, name)

        # ── Curva bezier ──
        pts = [(to_x(i), to_y(values[i])) for i in range(n)]

        if n >= 2:
            path = QPainterPath()
            path.moveTo(pts[0][0], pts[0][1])

            for i in range(1, n):
                x0, y0 = pts[i - 1]
                x1, y1 = pts[i]
                dx = (x1 - x0) * 0.35
                c1x, c1y = x0 + dx, y0
                c2x, c2y = x1 - dx, y1
                path.cubicTo(c1x, c1y, c2x, c2y, x1, y1)

            # Fill degradado bajo la curva
            fill_path = QPainterPath(path)
            fill_path.lineTo(pts[-1][0], chart_bottom)
            fill_path.lineTo(pts[0][0], chart_bottom)
            fill_path.closeSubpath()

            grad = QLinearGradient(0, chart_top, 0, chart_bottom)
            grad.setColorAt(0.0, QColor(ACCENT_TEAL))
            grad.setColorAt(0.35, QColor(ACCENT_TEAL))
            grad.setColorAt(1.0, QColor(ACCENT_TEAL))
            gcol = QColor(ACCENT_TEAL)
            gcol_top = QColor(ACCENT_TEAL); gcol_top.setAlpha(55)
            gcol_bot = QColor(ACCENT_TEAL); gcol_bot.setAlpha(8)
            grad.setColorAt(0.0, gcol_top)
            grad.setColorAt(1.0, gcol_bot)
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawPath(fill_path)

            # Línea principal
            pen = QPen(QColor(ACCENT_TEAL), 2.2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

        # ── Puntos ──
        p.setPen(Qt.NoPen)
        for i, (px, py) in enumerate(pts):
            outer = QColor(ACCENT_TEAL)
            outer.setAlpha(35)
            r = 5
            p.setBrush(QBrush(outer))
            p.drawEllipse(px - r, py - r, r * 2, r * 2)
            p.setBrush(QBrush(QColor(ACCENT_TEAL)))
            p.drawEllipse(px - 3, py - 3, 6, 6)

        # ── LP actual (esquina sup derecha) ──
        last = self._data[-1]
        tier_name = last.get("tier", "").title()
        div = last.get("division", "").strip()
        label = f"{tier_name} {div} {last['lp']} LP"
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor(ACCENT_TEAL))
        p.drawText(w - 160, pad_t, 152, 18, Qt.AlignRight | Qt.AlignVCenter, label)

        # ── Fechas (eje X) ──
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor("#6b7a8d"))
        step = max(1, n // 5)
        shown = set()
        for i in range(n):
            if i == 0 or i == n - 1 or i % step == 0:
                px = pts[i][0]
                fecha = self._data[i]["fecha"][5:]  # MM-DD
                key = fecha[:5]
                if key not in shown:
                    shown.add(key)
                    p.drawText(px - 20, h - pad_b + 4, 40, 14, Qt.AlignCenter, fecha)

        p.end()
