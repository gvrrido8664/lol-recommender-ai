"""Pestania COACHING PRO con tabs organizados por categoria y cache."""

from ui.contexto import *
import json
import os
import unicodedata
from datetime import datetime, timedelta


def _norm(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').upper()


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
            '<p style="font-size: 12px; color: #a39a93; margin: 0; line-height: 1.6;">'
            'Conecta al cliente de LoL para recibir tu analisis personalizado.<br><br>'
            'Aqui encontraras:<br>'
            '🧘 Filosofia de juego y mentalidad<br>'
            '📋 Auditoria de champion pool<br>'
            '⚔️ Rendimiento, dano y objetivos<br>'
            '🔍 Habitos y patrones detectados<br>'
            '🧠 Gestion de fatiga y sesiones<br>'
            '📈 Progresion de ELO y estadisticas</p>'
            '<p style="font-size: 10px; color: #7a6f68; margin: 14px 0 0 0; font-style: italic;">'
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
        # El contenido (html) ya trae su propio encabezado con el veredicto/dato,
        # así que no repetimos aquí el título de sección (evita título + subtítulo
        # duplicados). El color de la sección queda en el borde de la tarjeta.
        return f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
        {sec.get('html', '')}
        </div>"""

    def _dashboard_html(self, m):
        """Tablero compacto de métricas clave (foco en por-partida)."""
        wr = m.get("wr", 0)
        wr_col = GREEN_WR if wr >= 50 else RED_WR
        kda = m.get("kda", 0)
        kda_col = GREEN_WR if kda >= 3 else (YELLOW_WR if kda >= 2 else RED_WR)
        avg_d = m.get("avg_d", 0)
        d_col = GREEN_WR if avg_d <= 4.5 else (YELLOW_WR if avg_d <= 6.5 else RED_WR)
        cs = m.get("avg_cs", 0)
        cs_col = GREEN_WR if cs >= 6.5 else (YELLOW_WR if cs >= 5 else RED_WR)

        def fila(label, valor, color=TEXT_PRIMARY):
            return (f'<tr><td style="padding:3px 14px 3px 0; color:{TEXT_MUTED}; font-size:11px;">{label}</td>'
                    f'<td style="padding:3px 0; color:{color}; font-size:12px; font-weight:700;">{valor}</td></tr>')

        filas = ""
        filas += fila("Winrate", f"{wr:.0f}%", wr_col)
        filas += fila("KDA", f"{kda:.2f}  ({m.get('avg_k',0):.1f}/{m.get('avg_d',0):.1f}/{m.get('avg_a',0):.1f})", kda_col)
        filas += fila("CS / min", f"{cs:.1f}", cs_col)
        filas += fila("Muertes / partida", f"{avg_d:.1f}", d_col)
        filas += fila("Daño / partida", f"{m.get('avg_dmg_game',0):,.0f}")
        filas += fila("Oro / partida", f"{m.get('avg_gold_game',0):,.0f}")
        filas += fila("Visión / partida", f"{m.get('avg_vision_game',0):.0f}")
        filas += fila("First Blood", f"{m.get('primer_sangre_pct',0):.0f}%")
        filas += fila("Campeones distintos", f"{m.get('unique_champs','?')}")

        return f"""<div style="font-family: 'Segoe UI', Arial, sans-serif;">
        <p style="font-size: 14px; color: {ACCENT_TEAL}; margin: 0 0 8px 0;"><b>📊 Tus números ({m.get('total_all','?')} partidas)</b></p>
        <table style="border-collapse: collapse;">{filas}</table>
        </div>"""

    def _fortalezas_html(self, m):
        """Lista automática de fortalezas y áreas de mejora según las métricas."""
        fuertes, debiles = [], []
        wr = m.get("wr", 0); kda = m.get("kda", 0); cs = m.get("avg_cs", 0)
        avg_d = m.get("avg_d", 0); vis = m.get("avg_vision_game", 0)
        eff = m.get("dmg_eff", 0); fb = m.get("primer_sangre_pct", 0)
        uniq = m.get("unique_champs", 0)

        if wr >= 53: fuertes.append("Winrate sólido: estás ganando más de lo que pierdes con claridad.")
        if kda >= 3.2: fuertes.append("KDA alto: participas en jugadas sin morir de más.")
        if cs >= 6.5: fuertes.append("Buen farmeo (CS/min): tu economía de línea es fuerte.")
        if avg_d <= 4.5: fuertes.append("Mueres poco: buena toma de decisiones y supervivencia.")
        if vis >= 28: fuertes.append("Visión alta: das información a tu equipo.")
        if eff >= 1.15: fuertes.append("Buen intercambio de daño: infliges más del que recibes.")
        if fb >= 30: fuertes.append("Agresividad early efectiva: consigues muchos First Bloods.")

        if wr < 47: debiles.append("Winrate bajo: enfócate en UNA mejora a la vez para revertirlo.")
        if kda < 2.0: debiles.append("KDA bajo: estás muriendo demasiado para tu impacto.")
        if cs < 5.0: debiles.append("Farmeo flojo (CS/min): es tu mayor palanca de oro.")
        if avg_d >= 7: debiles.append("Mueres demasiado: cada muerte regala ~300g al rival.")
        if 0 < vis < 15: debiles.append("Visión baja: compra control wards y vacía el trinket.")
        if 0 < eff < 0.8: debiles.append("Recibes más daño del que infliges: posicionamiento.")
        if uniq > 8: debiles.append("Pool muy amplia: enfoca 2-3 campeones para acumular maestría.")

        if not fuertes and not debiles:
            return ""
        html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.6;">'
        html += f'<p style="font-size: 14px; color: {GREEN_WR}; margin: 0 0 6px 0;"><b>⚖️ Fortalezas y áreas de mejora</b></p>'
        if fuertes:
            html += f'<p style="font-size: 11px; color: {GREEN_WR}; margin: 4px 0 2px 0;"><b>Lo que haces bien</b></p>'
            for f in fuertes:
                html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 1px 0 1px 12px;">+ {f}</p>'
        if debiles:
            html += f'<p style="font-size: 11px; color: {RED_WR}; margin: 8px 0 2px 0;"><b>Dónde ganar más LP</b></p>'
            for d in debiles:
                html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 1px 0 1px 12px;">− {d}</p>'
        html += '</div>'
        return html

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
            t = _norm(titulo)
            card = self._crear_card(
                self._sec_html(sec), sec.get("color", BORDER_SUBTLE)
            )
            if "FILOSOFIA" in t:
                cards_por_tab["Filosofia"].append(card)
            elif "CHAMPION" in t or "AUDITORIA" in t or "ARSENAL" in t or "MAESTRIA" in t:
                cards_por_tab["Campeones"].append(card)
            elif "LINEA" in t or "FARMEO" in t or "RENDIMIENTO" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "SUPERVIVENCIA" in t or "DECISIONES" in t or "TOMA" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "VISION" in t or "PINKS" in t or "CONTROL WARD" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "DANO" in t or "EFICIENCIA" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "ORO" in t or "ECONOMIA" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "OBJETIVOS" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "MASAS" in t or "CC" in t:
                cards_por_tab["Rendimiento"].append(card)
            elif "RACHA" in t:
                cards_por_tab["Habitos"].append(card)
            elif "GESTION" in t or "SESIONES" in t or "FATIGA" in t:
                cards_por_tab["Gestion"].append(card)
            elif "BLOQUES" in t:
                cards_por_tab["Gestion"].append(card)
            elif "PRACTICA" in t or "DELIBERADA" in t:
                cards_por_tab["Gestion"].append(card)
            elif "PROGRESION" in t or "ELO" in t or "LP" in t:
                cards_por_tab["Gestion"].append(card)
            elif "SALUD" in t or "FISIOLOGIA" in t:
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

        metricas = reporte.get("metricas", {})
        if metricas:
            cards_por_tab["Resumen"].insert(2, self._crear_card(self._dashboard_html(metricas), ACCENT_TEAL))
            fort_html = self._fortalezas_html(metricas)
            if fort_html:
                cards_por_tab["Resumen"].insert(3, self._crear_card(fort_html, GREEN_WR))

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
                emo_html += '<p style="font-size: 13px; color: "#f59e0b"; margin: 0 0 6px 0;"><b>📊 Rendimiento por estado:</b></p>'
                emoji_map = {"Concentrado": "🔥", "Normal": "😐", "Tilted": "😤", "Cansado": "😴"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "❓")
                    color_wr = "#22c55e" if wr_e >= 50 else "#ef4444"
                    emo_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 2px 0;">{emoji} {estado}: <b style="color:{color_wr};">{wr_e}% WR</b> ({n} partidas)</p>'
                emo_html += '<p style="font-size: 10px; color: #7a6f68; margin: 6px 0 0 0;">💡 Etiqueta tus partidas en MI PERFIL para ver estos datos.</p>'
                emo_html += '</div>'
                cards_por_tab["Habitos"].append(self._crear_card(emo_html, "#f59e0b"))

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
