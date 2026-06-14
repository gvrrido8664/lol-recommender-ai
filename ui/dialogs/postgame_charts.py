"""Widgets de grafico para la revision post-partida (QPainter nativo, sin
dependencias externas). Mismo patron que ui/dialogs/lp_graph.py."""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt

from ui.design import *


class BarComparisonWidget(QWidget):
    """Barras horizontales: tu metrica de la partida vs un benchmark.

    set_data recibe una lista de dicts: {label, valor (texto), ratio (valor/benchmark)}.
    La barra se llena segun el ratio (1.0 = benchmark) y se colorea verde/ambar/rojo.
    """
    _ROW_H = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics = []
        self.setMinimumHeight(self._ROW_H)

    def set_data(self, metrics: list):
        self._metrics = metrics or []
        self.setMinimumHeight(max(self._ROW_H, len(self._metrics) * self._ROW_H + 8))
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG_CARD))
        if not self._metrics:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(0, 0, w, h, Qt.AlignCenter, "Sin datos")
            p.end()
            return

        lbl_w = 96            # ancho de la etiqueta
        val_w = 92            # ancho del valor a la derecha
        bar_x = lbl_w + 6
        bar_w = max(40, w - bar_x - val_w - 8)
        max_ratio = 1.5       # tope visual de la barra (150% del benchmark)
        bench_x = bar_x + int(bar_w * (1.0 / max_ratio))

        for i, m in enumerate(self._metrics):
            y = 4 + i * self._ROW_H
            cy = y + self._ROW_H // 2

            # Etiqueta
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(2, y, lbl_w, self._ROW_H, Qt.AlignLeft | Qt.AlignVCenter, m.get("label", ""))

            # Track de la barra
            track_h = 12
            ty = cy - track_h // 2
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor("#241c2a")))
            p.drawRoundedRect(bar_x, ty, bar_w, track_h, 3, 3)

            # Relleno segun ratio
            ratio = max(0.0, float(m.get("ratio", 0) or 0))
            fill = int(bar_w * min(ratio, max_ratio) / max_ratio)
            if ratio >= 1.0:
                col = GREEN_SUCCESS
            elif ratio >= 0.7:
                col = YELLOW_WARNING
            else:
                col = RED_DANGER
            p.setBrush(QBrush(QColor(col)))
            if fill > 0:
                p.drawRoundedRect(bar_x, ty, fill, track_h, 3, 3)

            # Marca del benchmark (100%)
            p.setPen(QPen(QColor(TEXT_SUBTLE), 1, Qt.DashLine))
            p.drawLine(bench_x, ty - 2, bench_x, ty + track_h + 2)

            # Valor a la derecha
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.setPen(QColor(col))
            p.drawText(bar_x + bar_w + 6, y, val_w, self._ROW_H,
                       Qt.AlignRight | Qt.AlignVCenter, m.get("valor", ""))

        p.end()


class TimelineChartWidget(QWidget):
    """Linea de una metrica por minuto (oro/CS/dano acumulado del jugador)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._puntos = []
        self._titulo = ""
        self._color = ACCENT_TEAL
        self._sufijo = ""
        self.setMinimumHeight(110)

    def set_data(self, puntos: list, titulo: str, color: str = None, sufijo: str = ""):
        self._puntos = puntos or []
        self._titulo = titulo
        self._color = color or ACCENT_TEAL
        self._sufijo = sufijo
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 10, 12, 22, 18
        p.fillRect(0, 0, w, h, QColor(BG_CARD))

        # Titulo
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(self._color))
        p.drawText(pad_l, 2, w - pad_l - pad_r, 16, Qt.AlignLeft | Qt.AlignVCenter, self._titulo)

        if len(self._puntos) < 2:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(0, 0, w, h, Qt.AlignCenter, "Sin timeline disponible")
            p.end()
            return

        vals = self._puntos
        mn, mx = min(vals), max(vals)
        rng = max(mx - mn, 1)
        n = len(vals)

        def to_px(i):
            return pad_l + int(i / max(1, n - 1) * (w - pad_l - pad_r))

        def to_py(v):
            return h - pad_b - int((v - mn) / rng * (h - pad_t - pad_b))

        points = [(to_px(i), to_py(v)) for i, v in enumerate(vals)]

        # Linea
        p.setPen(QPen(QColor(self._color), 2))
        for i in range(1, len(points)):
            p.drawLine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])

        # Valor final
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(self._color))
        ultimo = f"{vals[-1]:,}{self._sufijo}".replace(",", ".")
        p.drawText(w - 110, 2, 98, 16, Qt.AlignRight | Qt.AlignVCenter, ultimo)

        # Marcas de minutos en el eje X
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor(TEXT_MUTED))
        for i in {0, n // 2, n - 1}:
            px, _ = points[i]
            p.drawText(px - 14, h - pad_b + 2, 28, 14, Qt.AlignCenter, f"{i}'")

        p.end()
