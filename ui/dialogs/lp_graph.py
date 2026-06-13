"""Widget de grafica LP/MMR con QPainter nativo. Extraido de app.py sin cambios."""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt

from ui.design import *


class LPGraphWidget(QWidget):
    """GrÃ¡fica de lÃ­nea LP/MMR usando QPainter nativo â€” sin dependencias externas."""

    TIER_LABELS = [
        (0,    "Iron"),   (400,  "Bronze"), (800,  "Silver"), (1200, "Gold"),
        (1600, "Plat"),   (2000, "Emerald"),(2400, "Diamond"),(2800, "Master+"),
    ]
    TIER_COLORS = {
        "Iron": "#6b7280", "Bronze": "#b45309", "Silver": "{TEXT_MUTED}",
        "Gold": "{YELLOW_WARNING}", "Plat": "#14b8a6", "Emerald": "{GREEN_SUCCESS}",
        "Diamond": "#818cf8", "Master+": "#e879f9",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self.setMinimumHeight(120)

    def set_data(self, history: list):
        self._data = history
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 48, 12, 10, 24

        # Fondo
        p.fillRect(0, 0, w, h, QColor(BG_CARD))

        if not self._data or len(self._data) < 2:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(0, 0, w, h, Qt.AlignCenter, "Sin datos suficientes (mÃ­n. 2 dÃ­as)")
            p.end()
            return

        values = [d["lp_total"] for d in self._data]
        mn, mx = min(values), max(values)
        rng = max(mx - mn, 200)

        n = len(self._data)
        def to_px(i):
            return pad_l + int(i / max(1, n - 1) * (w - pad_l - pad_r))

        def to_py(val):
            return h - pad_b - int((val - mn) / rng * (h - pad_t - pad_b))

        # LÃ­neas de tier en gris sutil
        p.setFont(QFont("Segoe UI", 7))
        for base, name in self.TIER_LABELS:
            if mn - 100 <= base <= mx + 100:
                py = to_py(base)
                if pad_t <= py <= h - pad_b:
                    p.setPen(QPen(QColor("{BG_CARD_HOVER}"), 1, Qt.DashLine))
                    p.drawLine(pad_l, py, w - pad_r, py)
                    p.setPen(QColor(self.TIER_COLORS.get(name, "{TEXT_SUBTLE}")))
                    p.drawText(2, py - 6, pad_l - 4, 14, Qt.AlignRight | Qt.AlignVCenter, name)

        # LÃ­nea de LP
        points = [(to_px(i), to_py(self._data[i]["lp_total"]))
                  for i in range(len(self._data))]

        pen = QPen(QColor(ACCENT_TEAL), 2)
        p.setPen(pen)
        for i in range(1, len(points)):
            p.drawLine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])

        # Puntos
        p.setPen(Qt.NoPen)
        for i, (px, py) in enumerate(points):
            p.setBrush(QBrush(QColor(ACCENT_TEAL)))
            p.drawEllipse(px - 3, py - 3, 6, 6)

        # Fechas en el eje X (cada ~5 puntos o primero/Ãºltimo)
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor(TEXT_MUTED))
        indices = [0, n - 1] if n <= 4 else list(range(0, n, max(1, n // 4))) + [n - 1]
        for i in set(indices):
            px, _ = points[i]
            fecha_str = self._data[i]["fecha"][5:]  # MM-DD
            p.drawText(px - 18, h - pad_b + 4, 36, 14, Qt.AlignCenter, fecha_str)

        # LP actual en esquina superior derecha
        last = self._data[-1]
        label = f"{last['tier'].title()} {last['division']} {last['lp']} LP"
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(ACCENT_TEAL))
        p.drawText(w - 140, pad_t, 136, 16, Qt.AlignRight | Qt.AlignVCenter, label)

        p.end()
