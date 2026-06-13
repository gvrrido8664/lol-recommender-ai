"""Pestania COACHING PRO. Extraida de app.py sin cambios."""

from ui.contexto import *


class CoachingTabMixin:
    def armar_tab_coaching(self):
        """PestaÃ±a COACHING PRO con scroll, perfil de jugador y reporte de coaching completo."""
        layout = QVBoxLayout(self.tab_coaching)
        layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scrollCoaching")
        scroll.setStyleSheet(f"QScrollArea#scrollCoaching {{ border: none; background-color: {BG_DARK}; }} QWidget#scrollAreaWidgetContents {{ background-color: {BG_DARK}; }}")
        
        content = QWidget()
        content.setObjectName("scrollAreaWidgetContents")
        content.setStyleSheet(f"background-color: {BG_DARK};")
        self.coaching_scroll_content = QVBoxLayout(content)
        self.coaching_scroll_content.setSpacing(10)
        self.coaching_scroll_content.setAlignment(Qt.AlignTop)
        
        # â”€â”€ Saludo inicial â”€â”€
        lbl_espera = QLabel(
            '<div style="font-family: \'Segoe UI\', Arial, sans-serif; text-align: center; padding: 30px;">'
            '<p style="font-size: 48px; margin: 0;">ðŸŽ“</p>'
            '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
            '<p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0; line-height: 1.6;">'
            'Conecta al cliente de LoL para recibir tu anÃ¡lisis personalizado.<br><br>'
            'AquÃ­ encontrarÃ¡s:<br>'
            'ðŸ§˜ FilosofÃ­a de juego y mentalidad<br>'
            'ðŸ“‹ AuditorÃ­a de champion pool<br>'
            'ðŸ¦¾ PrÃ¡ctica deliberada personalizada<br>'
            'âš”ï¸ AnÃ¡lisis de farmeo y fase de lÃ­neas<br>'
            'ðŸ›¡ï¸ GestiÃ³n de muertes y toma de decisiones<br>'
            'ðŸ‘ï¸ Control de visiÃ³n<br>'
            'ðŸ§Š Sistema de juego por bloques (3 partidas)<br>'
            'ðŸ§  GestiÃ³n de fatiga y sesiones<br>'
            'ðŸ’š Tips de salud mental y fisiologÃ­a<br>'
            'ðŸ’¬ Consejos personalizados de tu coach</p>'
            '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 14px 0 0 0; font-style: italic;">'
            'âœ¨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demÃ¡s."</p>'
            '</div>'
        )
        lbl_espera.setTextFormat(Qt.RichText)
        lbl_espera.setAlignment(Qt.AlignCenter)
        lbl_espera.setWordWrap(True)
        self.coaching_scroll_content.addWidget(lbl_espera)
        self.coaching_scroll_content.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _actualizar_coaching(self):
        """Puebla la pestaÃ±a de coaching con el reporte completo y empÃ¡tico."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self._mostrar_coaching_vacio()
            return
        try:
            # Obtener nombre del invocador
            nombre = "Invocador"
            if hasattr(self, 'lbl_sum_name'):
                nombre = self.lbl_sum_name.text().replace("âœ“ ", "").strip()
                if nombre == "Esperando al Cliente...":
                    nombre = "Invocador"
            
            # Datos de fatiga para el reporte
            datos_fatiga = None
            if hasattr(self, 'historial_games') and self.historial_games:
                try:
                    datos_fatiga = analizar_fatiga(self.historial_games)
                except: pass
            
            # Datos de personalidad, hÃ¡bitos y objetivos
            datos_extra = self._generar_datos_perfil_jugador()
            
            reporte = generar_reporte_coach(self.historial_games, nombre, datos_extra, datos_fatiga)
            self._renderizar_coaching(reporte, datos_extra)
        except Exception as e:
            print(f"[_actualizar_coaching] Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _generar_datos_perfil_jugador(self):
        """Genera datos de personalidad, hÃ¡bitos y objetivos sin tocar UI."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return None
        try:
            games = self.historial_games
            datos = {}
            
            personalidad = analizar_personalidad(games)
            datos["personalidad"] = personalidad
            
            insights = detectar_habitos(games)
            datos["insights"] = insights
            
            objetivos = generar_objetivos_semanales(games)
            datos["objetivos"] = objetivos
            
            emocional = analizar_emocional_vs_wr(games)
            datos["emocional"] = emocional
            
            return datos
        except Exception as e:
            print(f"[_generar_datos_perfil_jugador] Error: {e}")
            return None
    
    def _mostrar_coaching_vacio(self):
        """Muestra el estado inicial sin datos."""
        if hasattr(self, 'coaching_scroll_content'):
            clear_layout(self.coaching_scroll_content)
            lbl = QLabel(
                '<div style="font-family: \'Segoe UI\', Arial, sans-serif; text-align: center; padding: 30px;">'
                '<p style="font-size: 48px; margin: 0;">ðŸŽ“</p>'
                '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
                '<p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0; line-height: 1.6;">'
                'Conecta al cliente de LoL para recibir tu anÃ¡lisis personalizado.<br><br>'
                'AquÃ­ encontrarÃ¡s:<br>'
                'ðŸ§˜ FilosofÃ­a de juego y mentalidad<br>'
                'ðŸ“‹ AuditorÃ­a de champion pool<br>'
                'âš”ï¸ AnÃ¡lisis de farmeo y fase de lÃ­neas<br>'
                'ðŸ›¡ï¸ GestiÃ³n de muertes y toma de decisiones<br>'
                'ðŸ‘ï¸ Control de visiÃ³n<br>'
                'ðŸ§  GestiÃ³n de fatiga y sesiones<br>'
                'ðŸ’¬ Consejos personalizados de tu coach</p>'
                '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 14px 0 0 0; font-style: italic;">'
                'âœ¨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demÃ¡s."</p>'
                '</div>'
            )
            lbl.setTextFormat(Qt.RichText)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            self.coaching_scroll_content.addWidget(lbl)
            self.coaching_scroll_content.addStretch()
    
    def _renderizar_coaching(self, reporte, datos_extra=None):
        """Renderiza el reporte de coaching en la UI."""
        if not hasattr(self, 'coaching_scroll_content') or not reporte:
            return
        
        clear_layout(self.coaching_scroll_content)
        
        def _crear_card(mensaje, color_accent="#e63946", padding="16px"):
            """Crea un QFrame con borde izquierdo de acento."""
            card = QFrame()
            card.setObjectName("CoachingCard")
            card.setStyleSheet(f"""
                QFrame#CoachingCard {{ 
                    border: 1px solid {BG_CARD_HOVER}; 
                    border-left: 3px solid {color_accent}; 
                    border-radius: 6px; 
                    background-color: {BG_CARD}; 
                    padding: {padding}; 
                    margin-bottom: 6px; 
                }}
            """)
            l = QVBoxLayout(card)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(0)
            lbl = QLabel(mensaje)
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("background: transparent; border: none; color: {TEXT_SECONDARY}; font-size: 12px;")
            l.addWidget(lbl)
            return card
        
        # â”€â”€ 1. Resumen inicial â”€â”€
        resumen = reporte.get("resumen", "")
        if resumen:
            self.coaching_scroll_content.addWidget(_crear_card(resumen, ACCENT_RED))
        
        # â”€â”€ 2. Estilo de juego (personalidad) â”€â”€
        if datos_extra and datos_extra.get("personalidad"):
            pers = datos_extra["personalidad"]
            estilo = pers.get("estilo", "NEUTRAL")
            perfil_texto = pers.get("perfil", "")
            detalles = pers.get("detalles", {})
            
            colores_estilo = {"AGRESIVO": ACCENT_RED, "CONSISTENTE": GREEN_WR, "CONTROL": ACCENT_TEAL, "BALANCEADO": TEXT_GOLD}
            color_estilo = colores_estilo.get(estilo, TEXT_WHITE)
            
            pers_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 14px; color: {color_estilo}; margin: 0 0 8px 0;"><b>ðŸŽ¯ Tu estilo: {estilo}</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">{perfil_texto}</p>
            <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 0;">KDA: {detalles.get('avg_kda','?')} Â· Clase preferida: {detalles.get('clase_predominante','?')} Â· Partidas: {detalles.get('total_games','?')}</p>
            </div>"""
            self.coaching_scroll_content.addWidget(_crear_card(pers_html, color_estilo))
        
        # â”€â”€ 3. Insights / hÃ¡bitos â”€â”€
        if datos_extra and datos_extra.get("insights"):
            insights = datos_extra["insights"]
            if insights and insights[0] != "âš ï¸ Necesitas al menos 5 partidas para detectar patrones.":
                ins_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                ins_html += '<p style="font-size: 13px; color: #2dd4bf; margin: 0 0 6px 0;"><b>ðŸ” Lo que detectÃ© en tu juego:</b></p>'
                for ins in insights[:5]:
                    ins_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 3px 0;">â€¢ {ins}</p>'
                ins_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(ins_html, "#2dd4bf"))
        
        # â”€â”€ 4. Secciones de anÃ¡lisis â”€â”€
        secciones = reporte.get("secciones", [])
        for sec in secciones:
            color_borde = sec.get("color", BORDER_SUBTLE)
            html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 13px; color: {color_borde}; font-weight: 700; margin: 0 0 6px 0;">
            {sec.get('icono', 'ðŸ“Š')} {sec.get('titulo', '')}
            </p>
            {sec.get('html', '')}
            </div>"""
            self.coaching_scroll_content.addWidget(_crear_card(html, color_borde, "14px"))
        
        # â”€â”€ 5. Objetivos semanales â”€â”€
        if datos_extra and datos_extra.get("objetivos"):
            objs = datos_extra["objetivos"]
            if objs and "Juega al menos 5 partidas" not in objs[0]:
                obj_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                obj_html += '<p style="font-size: 13px; color: #e63946; margin: 0 0 6px 0;"><b>ðŸŽ¯ Tus objetivos para esta semana:</b></p>'
                for obj in objs:
                    obj_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 3px 0;">ðŸŽ¯ {obj}</p>'
                obj_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(obj_html, "#e63946"))
        
        # â”€â”€ 6. Rendimiento emocional â”€â”€
        if datos_extra and datos_extra.get("emocional"):
            emocional = datos_extra["emocional"]
            if emocional:
                emo_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                emo_html += '<p style="font-size: 13px; color: {YELLOW_WARNING}; margin: 0 0 6px 0;"><b>ðŸ“Š Rendimiento por estado de Ã¡nimo:</b></p>'
                emoji_map = {"Concentrado": "ðŸ”¥", "Normal": "ðŸ˜", "Tilted": "ðŸ˜¤", "Cansado": "ðŸ˜´"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "â“")
                    color_wr = "{GREEN_SUCCESS}" if wr_e >= 50 else "{RED_DANGER}"
                    emo_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 2px 0;">{emoji} {estado}: <b style="color:{color_wr};">{wr_e}% WR</b> ({n} partidas)</p>'
                emo_html += '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 6px 0 0 0;">ðŸ’¡ Etiqueta tus partidas en MI PERFIL para ver estadÃ­sticas emocionales.</p>'
                emo_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(emo_html, "{YELLOW_WARNING}"))
        
        # â”€â”€ 7. Consejo final â”€â”€
        consejo = reporte.get("consejo_final", "")
        if consejo:
            consejo_html = f'<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;"><p style="font-size: 13px; color: {TEXT_PRIMARY}; margin: 0 0 6px 0;"><b>ðŸ’¬ Mensaje de tu coach:</b></p><p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0; font-style: italic;">{consejo}</p></div>'
            self.coaching_scroll_content.addWidget(_crear_card(consejo_html, ACCENT_RED))
        
        # AÃ±adir stretch al final
        self.coaching_scroll_content.addStretch()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # RIOT API â€” PARTIDAS DE LA TEMPORADA (para _fetch_perfil)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

