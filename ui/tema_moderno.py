"""Tema visual base moderno (pyqtdarktheme-fork) por debajo del QSS de NEXUS.

Da una base oscura coherente y con acento rojo NEXUS a los widgets que el QSS
propio NO estiliza: menus (bandeja/contextuales), QMessageBox/QDialog, anillos
de foco y estados disabled. El QSS custom (ui/theme_qss.py) se sigue aplicando
ENCIMA a nivel de ventana, de modo que la identidad visual de NEXUS manda donde
esta definida (paneles, tablas, botones, tabs, scrollbars, tooltips...).

Degradacion elegante: si la libreria no esta instalada (p. ej. en un build sin
empaquetar), la app sigue funcionando solo con el QSS propio.
"""

# Acento NEXUS (rojo carmesi). Coincide con BORDER_ACCENT/ACCENT_RED de ui/design.
_ACCENT = "#e63946"

# Paleta NEXUS para alinear los widgets "de base" con el resto de la app.
_BG_PANEL = "#0c101a"
_BG_CARD = "#111827"
_BORDER = "#2a3050"
_TEXT = "#f1f5f9"

# QSS extra (sabor NEXUS) para lo que qdarktheme deja con su gris generico.
# Solo cubrimos huecos reales: menus, dialogos/mensajes. Lo demas ya lo
# estiliza el QSS propio a nivel de ventana.
_QSS_EXTRA = f"""
QMenu {{
    background-color: {_BG_CARD};
    border: 1px solid {_BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {_ACCENT};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {_BORDER};
    margin: 4px 8px;
}}
QMessageBox, QDialog {{
    background-color: {_BG_PANEL};
}}
QMessageBox QLabel {{
    color: {_TEXT};
}}
"""


def habilitar_hidpi():
    """Activa el manejo de High-DPI. Llamar ANTES de crear QApplication."""
    try:
        import qdarktheme
        qdarktheme.enable_hi_dpi()
    except Exception:
        pass


def aplicar_tema_base() -> bool:
    """Aplica el tema base oscuro con acento NEXUS a la QApplication actual.

    Llamar DESPUES de crear QApplication y ANTES de construir la ventana
    (la ventana aplica su QSS propio encima en aplicar_estilos()).
    Devuelve True si se aplico qdarktheme, False si no estaba disponible.
    """
    try:
        import qdarktheme
        qdarktheme.setup_theme(
            "dark",
            custom_colors={"primary": _ACCENT},
            additional_qss=_QSS_EXTRA,
        )
        return True
    except Exception as e:
        print(f"[tema] qdarktheme no disponible; se usa solo el QSS propio ({e})")
        return False
