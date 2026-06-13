"""Hoja de estilos global (QSS) de NEXUS.

Extraida de LoLRecommenderApp.aplicar_estilos sin cambios. Usa las
constantes de diseno de ui/design.py.
"""

from ui.design import *


def hoja_estilos_global() -> str:
    return f"""
            QMainWindow {{ background-color: {BG_DARK}; }}
            QWidget {{ 
                color: {TEXT_WHITE}; 
                font-family: {FONT_FAMILY}; 
                font-size: 12px; 
            }}
            
            /* ═══ PANELES / TARJETAS ═══ */
            QFrame#Panel {{ 
                background-color: {BG_PANEL}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 10px; 
                padding: 14px; 
            }}
            QFrame#Panel:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QFrame#CardAlly {{ 
                background-color: {ALLY_BG}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 8px; 
            }}
            QFrame#CardAlly:hover {{ border: 1px solid {ACCENT_TEAL}; }}
            QFrame#CardEnemy {{ 
                background-color: {ENEMY_BG}; 
                border: 1px solid #3b1018; 
                border-radius: 8px; 
            }}
            QFrame#CardEnemy:hover {{ border: 1px solid {RED_WR}; }}
            QFrame#BuildCard {{ 
                background-color: {BG_CARD}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 8px; 
            }}
            QFrame#BuildCard:hover {{ 
                border: 1px solid {BORDER_ACCENT}; 
                background-color: #1a1520; 
            }}
            QFrame#StatCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 10px;
                padding: 12px;
            }}
            QFrame#StatCard:hover {{
                border: 1px solid {BORDER_ACCENT};
            }}
            
            QLabel {{ border: none; background: transparent; }}
            
            /* ═══ BOTONES ═══ */
            QPushButton {{ 
                background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 6px; 
                padding: 8px 18px; 
                font-weight: 600; 
                font-size: 12px; 
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{ 
                background-color: {ACCENT_RED}; 
                color: #ffffff; 
                border: 1px solid {ACCENT_RED}; 
            }}
            QPushButton:pressed {{ 
                background-color: #be123c; 
            }}
            QPushButton:disabled {{ 
                background-color: {BG_CARD_HOVER}; 
                color: {BG_BORDER}; 
                border: 1px solid #334155; 
            }}
            
            /* ═══ PESTAÑAS ═══ */
            QTabWidget::pane {{ 
                border: none; 
                background-color: {BG_PANEL}; 
                border-radius: 10px; 
                border-top-left-radius: 0px; 
                padding: 4px;
            }}
            QTabBar::tab {{ 
                background: transparent; 
                color: {TEXT_MUTED}; 
                padding: 10px 24px; 
                border: none; 
                border-bottom: 2px solid transparent; 
                margin-right: 2px; 
                font-weight: 500; 
                font-size: 12px; 
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            QTabBar::tab:selected {{ 
                color: {ACCENT_RED}; 
                border-bottom: 2px solid {ACCENT_RED};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{ 
                color: {TEXT_WHITE}; 
                border-bottom: 2px solid {TEXT_MUTED};
            }}
            
            /* ═══ COMBOBOX ═══ */
            QComboBox {{ 
                background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                border: 1px solid {BORDER_SUBTLE}; 
                padding: 7px 12px; 
                border-radius: 6px; 
                font-size: 12px; 
                min-height: 20px;
            }}
            QComboBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QComboBox:focus {{ border: 1px solid {ACCENT_RED}; }}
            QComboBox::drop-down {{ 
                border: none; 
                width: 24px; 
            }}
            QComboBox QAbstractItemView {{ 
                background-color: {BG_PANEL}; 
                color: {TEXT_WHITE}; 
                selection-background-color: {ACCENT_RED}; 
                selection-color: #ffffff; 
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 4px;
                outline: 0;
                padding: 4px;
            }}
            
            /* ═══ TABLAS ═══ */
            QTableWidget {{ 
                background-color: {BG_PANEL}; 
                alternate-background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                gridline-color: transparent; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 10px; 
                font-size: 12px; 
                outline: 0; 
            }}
            QTableWidget::item {{ 
                padding: 8px 12px; 
                border-bottom: 1px solid #1a2236; 
            }}
            QTableWidget::item:selected {{ 
                background-color: {ACCENT_RED}; 
                color: #ffffff; 
            }}
            QTableWidget::item:hover {{ 
                background-color: #1a2844; 
            }}
            QHeaderView::section {{ 
                background-color: {BG_CARD}; 
                color: {TEXT_MUTED}; 
                font-weight: 700; 
                padding: 12px 12px; 
                border: none; 
                border-bottom: 2px solid {BORDER_ACCENT}; 
                font-size: 11px; 
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }}
            
            /* ═══ BARRA DE PROGRESO ═══ */
            QProgressBar {{ 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 6px; 
                text-align: center; 
                background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                font-weight: 700; 
                font-size: 11px; 
                height: 18px;
            }}
            QProgressBar::chunk {{ 
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT_RED}, stop:1 {HOVER_GLOW});
                border-radius: 5px; 
            }}
            
            /* ═══ SCROLLBAR ═══ */
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #2a3a5c;
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ACCENT_RED};
            }}
            QScrollBar::handle:vertical:pressed {{
                background: #be123c;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 6px;
                margin: 2px 4px 2px 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: #2a3a5c;
                border-radius: 3px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {ACCENT_RED};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {BORDER_ACCENT};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            
            /* ═══ TOOLTIP ═══ */
            QToolTip {{
                background-color: {BG_PANEL};
                color: {TEXT_WHITE};
                border: 1px solid {BORDER_ACCENT};
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 11px;
            }}
            
            /* ═══ CHECKBOX ═══ */
            QCheckBox {{
                color: {TEXT_WHITE};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {BORDER_SUBTLE};
                background-color: {BG_CARD};
            }}
            QCheckBox::indicator:checked {{
                background-color: {ACCENT_RED};
                border: 1px solid {ACCENT_RED};
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {BORDER_ACCENT};
            }}
            
            /* ═══ SPINBOX / SLIDER ═══ */
            QSpinBox {{
                background-color: {BG_CARD};
                color: {TEXT_WHITE};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QSpinBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {BG_CARD};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT_RED};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {HOVER_GLOW};
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_RED};
                border-radius: 3px;
            }}
        """
