"""Pestania COACHING PRO con tabs organizados por categoria y cache."""

from ui.contexto import *
import json
import os
from datetime import datetime, timedelta


class CoachingTabMixin:
    def armar_tab_coaching(self):
        layout = QVBoxLayout(self.tab_coaching)
        layout.setContentsMargins(10, 10, 10, 10)

        self.coaching_tabs = QTabWidget()
        self.coaching_tabs.setObjectName("coachingTabs")
        self.coaching_tabs.setStyleSheet(f"""
            QTabWidget#coachingTabs::pane {{
                border: 1px solid {BG_CARD_HOVER};
                border-radius: 6px;
                background-color: {BG_DARK};
            }}
            QTabBar::tab {{
                background: {BG_CARD};
                color: {TEXT_MUTED};
                padding: 8px 14px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 10px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {BG_CARD_HOVER};
                color: {TEXT_PRIMARY};
                border-bottom: 2px solid {ACCENT_RED};
            }}
            QTabBar::tab:hover {{
                background: {BG_CARD_HOVER};
                color: {TEXT_SECONDARY};
            }}
        """)

        TAB_NAMES = ["Resumen", "Filosofia", "Campeones", "Rendimiento", "Habitos", "Gestion"]
        self._coaching_tab_widgets = {}
        for tab_name in TAB_NAMES:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {BG_DARK}; }}")
            content = QWidget()
            content.setStyleSheet(f"background-color: {BG_DARK};")
            content_layout = QVBoxLayout(content)
            content_layout.setSpacing(8)
            content_layout.setAlignment(Qt.AlignTop)
            scroll.setWidget(content)
            self.coaching_tabs.addTab(scroll, tab_name)
            self._coaching_tab_widgets[tab_name] = content_layout

        layout.addWidget(self.coaching_tabs)

        self._mostrar_placeholder()

    def _mostrar_placeholder(self):
        if not hasattr(self, '_coaching_tab_widgets'):
            return
        self._limpiar_tabs()
        lbl = QLabel(
            '<div style="font-family: \'Segoe UI\', Arial, sans-serif; text-align: center; padding: 30px;">'
            '<p style="font-size: 48px; margin: 0;">🎓</p>'
            '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
            '<p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0; line-height: 1.6;">'
            'Conecta al cliente de LoL para recibir tu analisis personalizado.<br><br>'
            'Aqui encontraras:<br>'
            '🧘 Filosofia de juego y mentalidad<br>'
            '📋 Auditoria de champion pool<br>'
            '⚔️ Rendimiento, dano y objetivos<br>'
            '🔍 Habitos y patrones detectados<br>'
            '🧠 Gestion de fatiga y sesiones<br>'
            '📈 Progresion de ELO y estadisticas</p>'
            '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 14px 0 0 0; font-style: italic;">'
            '✨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demas."</p>'
            '</div>'
        )
        lbl.setTextFormat(Qt.RichText)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        self._agregar_a_tab("Resumen", lbl)
        for layout in self._coaching_tab_widgets.values():
            layout.addStretch()

    def _get_coaching_cache_path(self):
        try:
            from src.paths import _get_writable_dir
            d = _get_writable_dir()
        except Exception:
            d = DATA_DIR
        return os.path.join(d, "coaching_cache.json")

    def _load_coaching_cache(self):
        try:
            path = self._get_coaching_cache_path()
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("_ts", 0)
            age_h = (time.time() - ts) / 3600
            if age_h > 24:
                return None
            return data
        except Exception:
            return None

    def _save_coaching_cache(self, reporte, datos_extra):
        try:
            path = self._get_coaching_cache_path()
            payload = {
                "_ts": time.time(),
                "reporte": reporte,
            }
            if datos_extra:
                payload["datos_extra"] = {
                    "personalidad": datos_extra.get("personalidad"),
                    "insights": datos_extra.get("insights"),
                    "objetivos": datos_extra.get("objetivos"),
                    "emocional": datos_extra.get("emocional"),
                }
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"[CoachingCache] Error guardando: {e}")

    def _crear_card(self, mensaje, color_accent="#e63946", padding="14px"):
        card = QFrame()
        card.setObjectName("CoachingCard")
        card.setStyleSheet(f"""
            QFrame#CoachingCard {{
                border: 1px solid {BG_CARD_HOVER};
                border-left: 3px solid {color_accent};
                border-radius: 6px;
                background-color: {BG_CARD};
                padding: {padding};
                margin-bottom: 4px;
            }}
        """)
        l = QVBoxLayout(card)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        lbl = QLabel(mensaje)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"background: transparent; border: none; color: {TEXT_SECONDARY}; font-size: 12px;")
        l.addWidget(lbl)
        return card

    def _agregar_a_tab(self, tab_name, widget):
        if hasattr(self, '_coaching_tab_widgets') and tab_name in self._coaching_tab_widgets:
            self._coaching_tab_widgets[tab_name].addWidget(widget)

    def _limpiar_tabs(self):
        if not hasattr(self, '_coaching_tab_widgets'):
            return
        for layout in self._coaching_tab_widgets.values():
            clear_layout(layout)

    def _sec_html(self, sec):
        color_borde = sec.get("color", BORDER_SUBTLE)
        return f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
        <p style="font-size: 13px; color: {color_borde}; font-weight: 700; margin: 0 0 6px 0;">
        {sec.get('icono', '📊')} {sec.get('titulo', '')}
        </p>
        {sec.get('html', '')}
        </div>"""

    def _actualizar_coaching(self):
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self._mostrar_placeholder()
            return

        cached = self._load_coaching_cache()
        if cached:
            try:
                reporte = cached.get("reporte", {})
                datos_extra = cached.get("datos_extra", None)
                if reporte and reporte.get("secciones"):
                    self._renderizar_coaching(reporte, datos_extra)
            except Exception:
                pass

        try:
            nombre = "Invocador"
            if hasattr(self, 'lbl_sum_name'):
                nombre = self.lbl_sum_name.text().replace("✓ ", "").strip()
                if nombre == "Esperando al Cliente...":
                    nombre = "Invocador"

            datos_fatiga = None
            if hasattr(self, 'historial_games') and self.historial_games:
                try:
                    datos_fatiga = analizar_fatiga(self.historial_games)
                except:
                    pass

            datos_extra = self._generar_datos_perfil_jugador()
            maestrias = getattr(self, 'maestrias', None)
            lp_history = self._obtener_lp_history()

            reporte = generar_reporte_coach(
                self.historial_games, nombre, datos_extra, datos_fatiga,
                maestrias=maestrias, lp_history=lp_history
            )

            if reporte and reporte.get("secciones"):
                self._renderizar_coaching(reporte, datos_extra)
                self._save_coaching_cache(reporte, datos_extra)
        except Exception as e:
            print(f"[_actualizar_coaching] Error: {e}")
            import traceback
            traceback.print_exc()

    def _obtener_lp_history(self):
        try:
            return obtener_historial_lp("RANKED_SOLO_5x5", dias=30)
        except Exception:
            return None

    def _generar_datos_perfil_jugador(self):
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return None
        try:
            games = self.historial_games
            datos = {}
            datos["personalidad"] = analizar_personalidad(games)
            datos["insights"] = detectar_habitos(games)
            datos["objetivos"] = generar_objetivos_semanales(games)
            datos["emocional"] = analizar_emocional_vs_wr(games)
            return datos
        except Exception as e:
            print(f"[_generar_datos_perfil_jugador] Error: {e}")
            return None

    def _renderizar_coaching(self, reporte, datos_extra=None):
        if not reporte or not hasattr(self, '_coaching_tab_widgets'):
            return

        secciones = reporte.get("secciones", [])
        if not secciones:
            return

        cards_por_tab = {k: [] for k in self._coaching_tab_widgets}

        for sec in secciones:
            titulo = sec.get("titulo", "")
            card = self._crear_card(
                self._sec_html(sec), sec.get("color", BORDER_SUBTLE)
            )
            if "FILOSOFIA" in titulo.upper():
                cards_por_tab["Filosofia"].append(card)
            elif "CHAMPION" in titulo.upper() or "AUDITORIA" in titulo.upper() or "ARSENAL" in titulo.upper() or "MAESTRIA" in titulo.upper():
                cards_por_tab["Campeones"].append(card)
            elif "LINEA" in titulo.upper() or "FARMEO" in titulo.upper() or "RENDIMIENTO" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "SUPERVIVENCIA" in titulo.upper() or "DECISIONES" in titulo.upper() or "TOMA" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "VISION" in titulo.upper() or "PINKS" in titulo.upper() or "CONTROL WARD" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "DANO" in titulo.upper() or "EFICIENCIA" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "ORO" in titulo.upper() or "ECONOMIA" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "OBJETIVOS" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "MASAS" in titulo.upper() or "CC" in titulo.upper():
                cards_por_tab["Rendimiento"].append(card)
            elif "RACHA" in titulo.upper():
                cards_por_tab["Habitos"].append(card)
            elif "GESTION" in titulo.upper() or "SESIONES" in titulo.upper() or "FATIGA" in titulo.upper():
                cards_por_tab["Gestion"].append(card)
            elif "BLOQUES" in titulo.upper():
                cards_por_tab["Gestion"].append(card)
            elif "PRACTICA" in titulo.upper() or "DELIBERADA" in titulo.upper():
                cards_por_tab["Gestion"].append(card)
            elif "PROGRESION" in titulo.upper() or "ELO" in titulo.upper() or "LP" in titulo.upper():
                cards_por_tab["Gestion"].append(card)
            elif "SALUD" in titulo.upper() or "FISIOLOGIA" in titulo.upper():
                cards_por_tab["Gestion"].append(card)
            else:
                cards_por_tab["Resumen"].append(card)

        resumen = reporte.get("resumen", "")
        if resumen:
            cards_por_tab["Resumen"].insert(0, self._crear_card(resumen, ACCENT_RED))

        if datos_extra and datos_extra.get("personalidad"):
            pers = datos_extra["personalidad"]
            estilo = pers.get("estilo", "NEUTRAL")
            perfil_texto = pers.get("perfil", "")
            detalles = pers.get("detalles", {})
            colores_estilo = {"AGRESIVO": ACCENT_RED, "CONSISTENTE": GREEN_WR, "CONTROL": ACCENT_TEAL, "BALANCEADO": TEXT_GOLD}
            color_estilo = colores_estilo.get(estilo, TEXT_WHITE)
            pers_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 14px; color: {color_estilo}; margin: 0 0 8px 0;"><b>🎯 Tu estilo: {estilo}</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">{perfil_texto}</p>
            <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 0;">KDA: {detalles.get('avg_kda','?')} · Clase: {detalles.get('clase_predominante','?')} · Partidas: {detalles.get('total_games','?')}</p>
            </div>"""
            cards_por_tab["Resumen"].insert(1, self._crear_card(pers_html, color_estilo))

        if datos_extra and datos_extra.get("insights"):
            insights = datos_extra["insights"]
            if insights and "Necesitas al menos 5 partidas" not in insights[0]:
                ins_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                ins_html += '<p style="font-size: 13px; color: #f0b232; margin: 0 0 6px 0;"><b>🔍 Lo que detecte en tu juego:</b></p>'
                for ins in insights[:5]:
                    ins_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 3px 0;">• {ins}</p>'
                ins_html += '</div>'
                cards_por_tab["Habitos"].insert(0, self._crear_card(ins_html, "#f0b232"))

        if datos_extra and datos_extra.get("emocional"):
            emocional = datos_extra["emocional"]
            if emocional:
                emo_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                emo_html += '<p style="font-size: 13px; color: "{YELLOW_WARNING}"; margin: 0 0 6px 0;"><b>📊 Rendimiento por estado:</b></p>'
                emoji_map = {"Concentrado": "🔥", "Normal": "😐", "Tilted": "😤", "Cansado": "😴"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "❓")
                    color_wr = "{GREEN_SUCCESS}" if wr_e >= 50 else "{RED_DANGER}"
                    emo_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 2px 0;">{emoji} {estado}: <b style="color:{color_wr};">{wr_e}% WR</b> ({n} partidas)</p>'
                emo_html += '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 6px 0 0 0;">💡 Etiqueta tus partidas en MI PERFIL para ver estos datos.</p>'
                emo_html += '</div>'
                cards_por_tab["Habitos"].append(self._crear_card(emo_html, "{YELLOW_WARNING}"))

        if datos_extra and datos_extra.get("objetivos"):
            objs = datos_extra["objetivos"]
            if objs and "Juega al menos 5 partidas" not in objs[0]:
                obj_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                obj_html += '<p style="font-size: 13px; color: #e63946; margin: 0 0 6px 0;"><b>🎯 Objetivos semanales:</b></p>'
                for obj in objs:
                    obj_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 3px 0;">🎯 {obj}</p>'
                obj_html += '</div>'
                cards_por_tab["Habitos"].append(self._crear_card(obj_html, "#e63946"))

        consejo = reporte.get("consejo_final", "")
        if consejo:
            consejo_html = f'<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;"><p style="font-size: 13px; color: {TEXT_PRIMARY}; margin: 0 0 6px 0;"><b>💬 Mensaje de tu coach:</b></p><p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0; font-style: italic;">{consejo}</p></div>'
            cards_por_tab["Gestion"].append(self._crear_card(consejo_html, ACCENT_RED))

        self._limpiar_tabs()
        for tab_name, cards in cards_por_tab.items():
            for card in cards:
                self._agregar_a_tab(tab_name, card)
        for layout in self._coaching_tab_widgets.values():
            layout.addStretch()
