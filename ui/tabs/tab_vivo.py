"""Pestania RADAR EN VIVO (draft) + deteccion LCU, settings, sonidos y
helpers de nombres. Extraida de app.py sin cambios."""

from ui.contexto import *


class VivoTabMixin:
    # ================= RADAR EN VIVO =================
    def armar_tab_vivo(self):
        layout = QVBoxLayout(self.tab_vivo)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        top_bar = QHBoxLayout()
        self.lbl_estado_lcu = QLabel("Buscando Cliente de LoL...")
        self.lbl_estado_lcu.setStyleSheet(f"color: {YELLOW_WR}; font-weight: bold; font-size: 14px;")
        top_bar.addWidget(self.lbl_estado_lcu)
        top_bar.addStretch()
        
        self.lbl_wr_numero = QLabel("--%")
        self.lbl_wr_numero.setStyleSheet("color: gray; font-family: Impact; font-size: 42px;")
        top_bar.addWidget(self.lbl_wr_numero)
        self.lbl_wr_razon = QLabel("Esperando equipos...")
        self.lbl_wr_razon.setStyleSheet("color: gray; font-style: italic;")
        top_bar.addWidget(self.lbl_wr_razon)
        layout.addLayout(top_bar)

        # Coach tip en Champ Select
        self.lbl_radar_tip = QLabel("ðŸ’¡ <b>Consejo:</b> En Champ Select, prioriza counter-pickear a tu rival de lÃ­nea. Revisa runas y hechizos recomendados abajo.")
        self.lbl_radar_tip.setWordWrap(True)
        self.lbl_radar_tip.setTextFormat(Qt.RichText)
        self.lbl_radar_tip.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; padding: 6px 10px; background-color: {BG_DARK}; border: 1px solid {BG_CARD_HOVER}; border-left: 3px solid {ACCENT_TEAL}; border-radius: 4px; margin-bottom: 2px;")
        layout.addWidget(self.lbl_radar_tip)

        # Tips de matchup (ocultos hasta que haya rival detectado)
        self.lbl_matchup_tips = QLabel("")
        self.lbl_matchup_tips.setWordWrap(True)
        self.lbl_matchup_tips.setTextFormat(Qt.RichText)
        self.lbl_matchup_tips.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; padding: 5px 10px; background-color: #1a1200; border: 1px solid #3d2e00; border-left: 3px solid {YELLOW_WR}; border-radius: 4px; margin-bottom: 2px;")
        self.lbl_matchup_tips.setVisible(False)
        layout.addWidget(self.lbl_matchup_tips)

        draft_layout = QHBoxLayout()
        draft_layout.setAlignment(Qt.AlignTop)

        self.col_enemy, l_enemy = self.crear_panel("Enemigos")
        self.lbl_enemy_stats = QLabel("AD: --% | AP: --% | Tanks: 0")
        self.lbl_enemy_stats.setStyleSheet(f"color: {RED_WR}; font-weight: bold;")
        l_enemy.addWidget(self.lbl_enemy_stats)
        
        self.fr_enemigos_picks = QVBoxLayout()
        l_enemy.addLayout(self.fr_enemigos_picks)
        l_enemy.addStretch()
        
        self.panel_bans_vivo, self.l_bans_vivo = self.crear_panel("Bans Sugeridos (Tu LÃ­nea)")
        self.fr_bans_icons_vivo = QHBoxLayout()
        self.l_bans_vivo.addLayout(self.fr_bans_icons_vivo)
        l_enemy.addWidget(self.panel_bans_vivo)
        
        self.panel_counters_vivo, self.l_counters_vivo = self.crear_panel("Counters vs Rival")
        self.fr_counters_vivo = QHBoxLayout()
        self.l_counters_vivo.addLayout(self.fr_counters_vivo)
        l_enemy.addWidget(self.panel_counters_vivo)
        draft_layout.addWidget(self.col_enemy, 1)

        col_center = QWidget()
        l_center = QVBoxLayout(col_center)
        l_center.setAlignment(Qt.AlignTop)
        
        self.lbl_rol_vivo = QLabel("ASIGNACIÃ“N PENDIENTE")
        self.lbl_rol_vivo.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 18px;")
        self.lbl_rol_vivo.setAlignment(Qt.AlignCenter)
        l_center.addWidget(self.lbl_rol_vivo)
        
        self.panel_sugerencias, self.l_sugerencias = self.crear_panel("Recomendaciones de Pick")
        self.fr_picks_icons = QGridLayout()
        self.l_sugerencias.addLayout(self.fr_picks_icons)
        l_center.addWidget(self.panel_sugerencias, 1)
        
        self.panel_runas_vivo, self.l_runas_vivo = self.crear_panel("Setup Recomendado Integral")
        self.fr_runas_icons_vivo = QVBoxLayout()
        self.fr_runas_icons_vivo.setAlignment(Qt.AlignTop)
        self.l_runas_vivo.addLayout(self.fr_runas_icons_vivo)
        l_center.addWidget(self.panel_runas_vivo, 2)
        self.inicializar_panel_setup(self.fr_runas_icons_vivo)
        
        # Skill Order
        self.panel_skills, self.l_skills = self.crear_panel("ðŸ“– RUTA DE HABILIDADES")
        self.lbl_skill_order = QLabel("Selecciona un campeÃ³n")
        self.lbl_skill_order.setAlignment(Qt.AlignCenter)
        self.lbl_skill_order.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 16px; font-weight: bold; padding: 8px;")
        self.l_skills.addWidget(self.lbl_skill_order)
        self.btn_export_skills = QPushButton("ðŸ“¤ Subir orden al Cliente")
        self.btn_export_skills.setStyleSheet(f"""
            QPushButton {{ background-color: {BG_CARD}; border: 1px solid {ACCENT_TEAL}; border-radius: 4px; color: {ACCENT_TEAL}; font-size: 11px; padding: 6px 16px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #1a3a3a; }}
            QPushButton:disabled {{ color: {BG_BORDER}; border-color: {BG_CARD_HOVER}; }}
        """)
        self.btn_export_skills.clicked.connect(lambda: self.accion_importar_skill_order(self.btn_export_skills))
        self.btn_export_skills.setVisible(False)
        self.l_skills.addWidget(self.btn_export_skills, alignment=Qt.AlignCenter)
        l_center.addWidget(self.panel_skills)

        # â”€â”€ PANEL PATHING JUNGLA (solo visible cuando rol = JUNGLA) â”€â”€
        self.pnl_pathing, self.l_pathing = self.crear_panel("ðŸ—ºï¸ PATHING DE JUNGLA")
        self.lbl_pathing_estilo = QLabel("")
        self.lbl_pathing_estilo.setStyleSheet(f"font-size: 12px; font-weight: bold; padding: 2px 0;")
        self.l_pathing.addWidget(self.lbl_pathing_estilo)
        self.lbl_pathing_inicio = QLabel("")
        self.lbl_pathing_inicio.setWordWrap(True)
        self.lbl_pathing_inicio.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 10px;")
        self.l_pathing.addWidget(self.lbl_pathing_inicio)
        self.lbl_pathing_ruta = QLabel("")
        self.lbl_pathing_ruta.setWordWrap(True)
        self.lbl_pathing_ruta.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 10px;")
        self.l_pathing.addWidget(self.lbl_pathing_ruta)
        self.lbl_pathing_gank = QLabel("")
        self.lbl_pathing_gank.setWordWrap(True)
        self.lbl_pathing_gank.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 10px;")
        self.l_pathing.addWidget(self.lbl_pathing_gank)
        self.lbl_pathing_vs = QLabel("")
        self.lbl_pathing_vs.setWordWrap(True)
        self.lbl_pathing_vs.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; padding-top: 2px;")
        self.l_pathing.addWidget(self.lbl_pathing_vs)
        self.pnl_pathing.setVisible(False)
        l_center.addWidget(self.pnl_pathing)

        draft_layout.addWidget(col_center, 3)

        self.col_ally, l_ally = self.crear_panel("Aliados")
        self.lbl_ally_stats = QLabel("AD: --% | AP: --% | Tanks: 0")
        self.lbl_ally_stats.setStyleSheet(f"color: {ACCENT_TEAL}; font-weight: bold;")
        l_ally.addWidget(self.lbl_ally_stats)
        self.fr_aliados_picks = QVBoxLayout()
        l_ally.addLayout(self.fr_aliados_picks)
        l_ally.addStretch() 
        draft_layout.addWidget(self.col_ally, 1)
        
        layout.addLayout(draft_layout)

    def abrir_settings(self):
        dlg = SettingsDialog(self.user_settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.user_settings = dlg.get_settings()
            guardar_settings(self.user_settings)
            self._aplicar_settings()

    def _aplicar_settings(self):
        """Aplica los settings actuales a los timers y comportamientos."""
        self.timer_lcu.setInterval(self.user_settings.get("frecuencia_radar", 1500))
        if not self.user_settings.get("auto_deteccion", True):
            self.timer_lcu.stop()
        else:
            if not self.timer_lcu.isActive():
                self.timer_lcu.start()

    def _reproducir_sonido(self, tipo="info"):
        """Reproduce un sonido de alerta si los sonidos estan activados."""
        if not self.user_settings.get("sonidos", False):
            return
        try:
            import winsound
            if tipo == "info": winsound.MessageBeep(winsound.MB_ICONINFORMATION)
            elif tipo == "alerta": winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif tipo == "draft": winsound.MessageBeep(winsound.MB_OK)
        except: pass

    def auto_detectar_lcu(self):
        """Solo hace operaciones rÃ¡pidas (leer lockfile). El trabajo pesado (HTTP)
        se lanza en hilos secundarios para no congelar la UI."""
        conectado = self.lcu.conectar()
        
        if not conectado:
            # Cliente cerrado o lockfile desapareciÃ³ â†’ resetear todo
            if self.radar_activo:
                self.radar_activo = False
                self.perfil_cargado = False
                self._cargando_perfil = False
                self._actualizando_radar = False
                self.last_aliados = []
                self.last_enemigos = []
                self.last_my_champ = None
                self.lbl_estado_lcu.setText("Buscando Cliente de LoL... (Abre el juego)")
                self.lbl_estado_lcu.setStyleSheet(f"color: {YELLOW_WR}; font-weight: bold; font-size: 14px;")
            return
        
        # Cliente detectado por primera vez
        if not self.radar_activo:
            self.radar_activo = True
            self._reproducir_sonido("info")
            self.lbl_estado_lcu.setText("âœ“ ENLAZADO AL CLIENTE DE LOL")
            self.lbl_estado_lcu.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 14px;")
            # PequeÃ±a pausa: la API HTTP del cliente tarda ~2s en estar lista tras
            # aparecer el lockfile. Sin esto, el primer fetch falla y el usuario
            # pensarÃ­a que la app no funciona.
            time.sleep(1.5)
        
        # Cargar perfil en hilo secundario (si no estÃ¡ ya cargÃ¡ndose)
        if not self.perfil_cargado and not self._cargando_perfil:
            self._cargando_perfil = True
            threading.Thread(target=self._fetch_perfil, daemon=True).start()
        
        # Actualizar radar/draft en hilo secundario (si no estÃ¡ ya actualizÃ¡ndose)
        if not self._actualizando_radar:
            self._actualizando_radar = True
            threading.Thread(target=self._fetch_radar, daemon=True).start()
        
        # Auto-switch de pestaÃ±as segun fase del juego + notificaciones
        fase = self.lcu.obtener_fase_juego()
        if fase != self._last_fase:
            # Notificaciones de escritorio en transiciones de fase
            if self.user_settings.get("notificaciones_escritorio", True) and hasattr(self, 'tray_icon') and self.tray_icon:
                if fase == "ReadyCheck":
                    self.tray_icon.showMessage("NEXUS", "Partida encontrada", QIcon(), 4000)
                    self._reproducir_sonido("info")
                elif fase == "ChampSelect":
                    self.tray_icon.showMessage("NEXUS", "Champ Select iniciado", QIcon(), 4000)
                elif fase == "PreEndOfGame":
                    self.tray_icon.showMessage("NEXUS", "Partida terminada â€” Ver analisis", QIcon(), 4000)
                    # Marcar ultimo draft como completado
                    try:
                        if hasattr(self, '_draft_id_actual') and self._draft_id_actual:
                            completar_draft_resultado(self._draft_id_actual, None)
                            self._draft_id_actual = None
                    except Exception as e:
                        print(f"[DraftHistory] Error completando draft: {e}")

            # Auto-aceptar partida
            if fase == "ReadyCheck" and self.user_settings.get("auto_aceptar", False):
                try:
                    self.lcu.request('POST', '/lol-matchmaking/v1/ready-check/accept')
                    if hasattr(self, 'tray_icon') and self.tray_icon:
                        self.tray_icon.showMessage("NEXUS", "Partida aceptada automaticamente", QIcon(), 3000)
                except Exception as e:
                    log.warning("Auto-aceptar fallo: %s", e)

            self._last_fase = fase

            # Actualizar Discord Rich Presence
            try:
                if fase in ("GameStart", "InProgress"):
                    actualizar_discord_rpc(
                        details="En partida",
                        state="League of Legends - SoloQ",
                        large_text="Jugando"
                    )
                elif fase == "ChampSelect":
                    actualizar_discord_rpc(
                        details="Seleccion de campeones",
                        state="Champ Select",
                        large_text="Draftero"
                    )
                elif fase == "ReadyCheck":
                    actualizar_discord_rpc(
                        details="Partida encontrada",
                        state="Aceptando...",
                        large_text="En cola"
                    )
                else:
                    actualizar_discord_rpc(
                        details="En el cliente de LoL",
                        state="Menu principal",
                        large_text="League of Legends"
                    )
            except Exception:
                pass

        if fase == "ChampSelect":
            if self.tabview.currentIndex() != 2 and self.user_settings.get("auto_switch_radar", True):
                self.tabview.setCurrentIndex(2)  # RADAR EN VIVO
        elif fase in ("GameStart", "InProgress"):
            if self.tabview.currentIndex() != 3 and self.user_settings.get("auto_switch_radar", True):
                self.tabview.setCurrentIndex(3)  # PARTIDA EN VIVO

    def _clasificar_modo_juego(self, g):
        game_type = g.get("gameType", "")
        game_mode = g.get("gameMode", "")
        queue_id = g.get("queueId", 0)
        if game_type == "CUSTOM_GAME":
            return "Custom"
        if game_type == "PRACTICE_GAME":
            return "vs IA"
        if queue_id == 420:
            return "SoloQ"
        if queue_id == 440:
            return "Flex"
        if queue_id in (400, 430):
            return "Normal"
        if game_mode == "ARAM":
            return "ARAM"
        if game_mode == "CLASSIC":
            return "Normal"
        return game_mode or "Normal"

    def procesar_nombre_champ(self, cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0": return "Wukong" if MAPEO_IDS_CAMPEONES.get(final_id) == "MonkeyKing" else MAPEO_IDS_CAMPEONES.get(final_id, "Desconocido")
        return None

    def _nombre_db(self, nombre):
        """Normaliza un nombre de campeon (posiblemente en espanol) al nombre interno
        en ingles que usa la base de datos y el sistema de tags."""
        if not nombre: return nombre
        return self.nombre_interno.get(nombre, nombre)

    def _nombres_db(self, nombres):
        """Normaliza una lista de nombres para queries SQL."""
        return [self._nombre_db(n) for n in nombres] if nombres else nombres

    def _nombre_display(self, nombre):
        """Traduce nombre interno (EN) a nombre para mostrar en UI (ES)."""
        if not nombre: return nombre
        return self.nombre_display.get(nombre, nombre)

    # ================= RADAR / DRAFT (HILO SEGUNDARIO) =================
    def _fetch_radar(self):
        """Se ejecuta en hilo secundario. Solo obtiene el draft de LCU."""
        try:
            draft = self.lcu.obtener_sesion_draft()
        except Exception as e:
            draft = None
        self.radar_listo.emit(draft)

    def _on_radar_listo(self, draft):
        """Se ejecuta en el hilo principal. Actualiza la UI del radar.
        Si no hay draft activo, simplemente se salta la actualizaciÃ³n SIN desconectar."""
        self._actualizando_radar = False
        
        if not self.radar_activo:
            return
        
        if not draft:
            # No hay sesiÃ³n de draft activa â†’ no desconectar, solo esperar
            return
        
        try:
            rol_api = self.lcu.obtener_mi_rol(draft)
            rol_ui = API_TO_ROL.get(rol_api, "MID")
            self.lbl_rol_vivo.setText(f"LÃNEA ASIGNADA: {rol_ui}")

            picks_al, picks_en = [], []
            pos_al, pos_en = [], []
            mi_campeon = None
            mi_celda = draft.get("localPlayerCellId")

            for j in draft.get("myTeam", []):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ:
                    picks_al.append(champ)
                    pos_al.append(j.get("assignedPosition", "MIDDLE"))
                if j.get("cellId") == mi_celda: mi_campeon = champ
                
            enemigo_lane = None
            posiciones = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
            # Normalizador de posiciones (LCU puede devolver SUPPORT en vez de UTILITY)
            def _normalizar_pos(pos_str):
                p = (pos_str or "").upper().strip()
                mapa = {"SUPPORT": "UTILITY", "ADC": "BOTTOM", "JUNGLA": "JUNGLE", "MID": "MIDDLE"}
                return mapa.get(p, p) if p in posiciones or p in mapa else ""

            # Cache de campeones por rol para inferir rol tipico
            if not hasattr(self, '_cache_rol_tipico'):
                self._cache_rol_tipico = {}
                self._cache_rol_tipico_lock = threading.Lock()
            if rol_api not in self._cache_rol_tipico or not self._cache_rol_tipico.get(rol_api):
                with self._cache_rol_tipico_lock:
                    if rol_api not in self._cache_rol_tipico or not self._cache_rol_tipico.get(rol_api):
                        for rol_key in posiciones:
                            champs_rol = set(obtener_campeones_por_rol(rol_key, min_partidas=5))
                            self._cache_rol_tipico[rol_key] = champs_rol

            enemigos_procesados = []
            for idx, j in enumerate(draft.get("theirTeam", [])):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ:
                    picks_en.append(champ)
                    pos = _normalizar_pos(j.get("assignedPosition", ""))
                    pos_from_lcu = bool(pos)  # Solo confiar en posiciones reales de la LCU
                    if not pos:
                        # Inferir rol por indice (ultimo recurso antes de datos)
                        pos = posiciones[idx] if idx < 5 else "MIDDLE"
                    pos_en.append(pos)
                    enemigos_procesados.append((champ, pos, idx))
                    # Solo asignar rival de linea si la posicion viene de la LCU (no del indice)
                    if pos_from_lcu and pos == rol_api:
                        enemigo_lane = champ
            
            # Fallback inteligente si no se encontro rival de linea por posicion
            if not enemigo_lane and enemigos_procesados:
                # 1. Por CLASE del campeon (mas fiable: Marksmanâ†’BOTTOM, Supportâ†’UTILITY, etc.)
                from src.tags_champions import obtener_tag
                rol_to_class = {
                    "TOP": ("Fighter", "Tank"), "JUNGLE": ("Fighter", "Tank", "Assassin"),
                    "MIDDLE": ("Mage", "Assassin"), "BOTTOM": ("Marksman",),
                    "UTILITY": ("Support",)
                }
                expected = rol_to_class.get(rol_api, ())
                for champ, pos, idx in enemigos_procesados:
                    try:
                        tag = obtener_tag(champ)
                        if tag.get("champion_class", "") in expected:
                            enemigo_lane = champ
                            print(f"[Radar] Rival de linea por clase: {champ} ({tag.get('champion_class')}) en {rol_api}")
                            break
                    except Exception:
                        pass
                
                # 2. Por rol tipico en BD (cache) â€” con tiebreaker: el mas frecuente en este rol
                if not enemigo_lane:
                    cache_rol = self._cache_rol_tipico.get(rol_api, set())
                    candidatos_cache = []
                    conn_radar = obtener_conexion()
                    try:
                        cur = conn_radar.cursor()
                        placeholders = ",".join(["?"] * len(enemigos_procesados))
                        champs_list = [champ for champ, pos, idx in enemigos_procesados]
                        cur.execute(
                            f"SELECT champion, COUNT(*) as cnt FROM participantes "
                            f"WHERE champion IN ({placeholders}) AND team_position = ? "
                            f"GROUP BY champion",
                            champs_list + [rol_api]
                        )
                        freq_map = {row["champion"]: row["cnt"] for row in cur.fetchall()}
                    except Exception:
                        freq_map = {}
                    finally:
                        conn_radar.close()
                    for champ, pos, idx in enemigos_procesados:
                        if champ in cache_rol:
                            freq = freq_map.get(champ, 0)
                            candidatos_cache.append((champ, freq))
                    if candidatos_cache:
                        # Elegir el campeon mas frecuente en este rol, no el primero de la lista
                        candidatos_cache.sort(key=lambda x: x[1], reverse=True)
                        enemigo_lane = candidatos_cache[0][0]
                        print(f"[Radar] Rival de linea inferido por rol tipico (frec={candidatos_cache[0][1]}): {enemigo_lane} en {rol_api}")
                
                # 3. Por posicion normalizada de la LCU (si no coincidio antes por alguna razon)
                if not enemigo_lane:
                    for champ, pos, idx in enemigos_procesados:
                        if pos and pos.upper() == rol_api.upper():
                            enemigo_lane = champ
                            break
                
                # 4. Por indice verificando rol tipico (ultimo recurso)
                if not enemigo_lane:
                    mi_idx = next((i for i, j in enumerate(draft.get("myTeam", [])) if j.get("cellId") == mi_celda), -1)
                    if 0 <= mi_idx < len(enemigos_procesados):
                        champ_idx = enemigos_procesados[mi_idx][0]
                        if champ_idx in cache_rol:
                            enemigo_lane = champ_idx
                            print(f"[Radar] Rival de linea por indice (verificado): {champ_idx} en {rol_api}")
                
            if picks_al != self.last_aliados or picks_en != self.last_enemigos:
                self.last_aliados, self.last_enemigos = picks_al.copy(), picks_en.copy()
                
                self.mostrar_equipo_vivo(self.fr_aliados_picks, picks_al, is_ally=True)
                self.mostrar_equipo_vivo(self.fr_enemigos_picks, picks_en, is_ally=False)
                
                # Normalizar nombres a ingles para queries SQL y tags
                picks_al_db = self._nombres_db(picks_al)
                picks_en_db = self._nombres_db(picks_en)
                
                ad_al, ap_al, tanks_al = analizar_composicion(picks_al_db)
                self.lbl_ally_stats.setText(f"DaÃ±o AD: {ad_al}% | DaÃ±o AP: {ap_al}% | Frontlane: {tanks_al}")
                ad_en, ap_en, tanks_en = analizar_composicion(picks_en_db)
                self.lbl_enemy_stats.setText(f"DaÃ±o AD: {ad_en}% | DaÃ±o AP: {ap_en}% | Frontlane: {tanks_en}")
                
                self.mostrar_picks_vivo(rol_api, picks_al_db, picks_en_db)

                # Actualizar counters si cambia el rival de linea (aunque no haya cambiado mi pick)
                if enemigo_lane != self.last_enemigo_lane:
                    self._actualizar_counters_vivo(rol_api, enemigo_lane)

                if len(picks_al_db) == 5 and len(picks_en_db) == 5:
                    wr = calcular_winrate_5v5(picks_al_db, picks_en_db, pos_al, pos_en)
                    color = GREEN_WR if wr > 52 else RED_WR if wr < 48 else YELLOW_WR
                    tendencia = "â†‘ Ventaja de Sinergia" if wr > 52 else "â†“ Desventaja de Draft" if wr < 48 else "â‰ˆ Matchup Equilibrado"
                    self.lbl_wr_numero.setText(f"{wr}%")
                    self.lbl_wr_numero.setStyleSheet(f"color: {color}; font-family: Impact; font-size: 42px;")
                    self.lbl_wr_razon.setText(tendencia)
                    self.lbl_wr_razon.setStyleSheet(f"color: {color}; font-style: italic;")

                    # Guardar draft en historial
                    if mi_campeon:
                        try:
                            bans_actuales = [self.procesar_nombre_champ(
                                b.get("championId", 0), 0) for b in draft.get("bans", {}).get("myBans", [])]
                            bans_actuales = [b for b in bans_actuales if b]
                            self._draft_id_actual = guardar_draft(mi_campeon, rol_api, bans_actuales, picks_al, picks_en, wr)
                        except Exception as e:
                            print(f"[DraftHistory] Error guardando draft: {e}")

            if mi_campeon != self.last_my_champ or rol_api != self.last_my_role:
                self.last_my_champ = mi_campeon
                self.last_my_role = rol_api
                
                clear_layout(self.fr_bans_icons_vivo)
                if mi_campeon: 
                    self.panel_bans_vivo.label_title.setText(
                        f"BANS SI PICKEO {self._nombre_display(mi_campeon).upper()}"
                    )
                    bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_api, min_partidas=20)
                    # Fallback: si no hay datos para este campeon en este rol (ej. Quinn JG),
                    # usar bans generales del rol
                    if not bans_sugeridos:
                        bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_api, min_partidas=5)
                    if not bans_sugeridos:
                        # Ultimo fallback: bans mas comunes del rol
                        bans_sugeridos = obtenermejoresbaneos(rol_api, min_partidas=20)
                        self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS ({rol_ui})")
                else: 
                    self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS ({rol_ui})")
                    bans_sugeridos = obtenermejoresbaneos(rol_api, min_partidas=20)

                bans_filtrados = [(b, wr, p) for b, wr, p in bans_sugeridos if b not in self.last_aliados and b not in self.last_enemigos][:4]
                if bans_filtrados:
                    for i, (ban, wr, partidas) in enumerate(bans_filtrados): 
                        self.renderizar_icono(ban, "champ", self.fr_bans_icons_vivo, 0, i,
                            f"ðŸš« Baneo sugerido: {self._nombre_display(ban)}\nðŸ“Š WR rival: {wr}% en {partidas} partidas", size=35)
                else: 
                    lbl_noban = QLabel("Sin recomendaciones")
                    lbl_noban.setStyleSheet("color: gray;")
                    self.fr_bans_icons_vivo.addWidget(lbl_noban)

                # â”€â”€ COUNTER PICKS contra el rival de linea â”€â”€
                self._actualizar_counters_vivo(rol_api, enemigo_lane)

                if mi_campeon:
                    ids_runas = obtener_top_runas(mi_campeon, rol_api)
                    ids_runas = ajustar_shards_adaptativos(
                        ids_runas,
                        self._nombre_db(mi_campeon) or mi_campeon,
                        self._nombre_db(enemigo_lane) or enemigo_lane if enemigo_lane else None,
                        [self._nombre_db(c) or c for c in picks_en_db],
                    )
                    ids_spells = obtener_top_hechizos(mi_campeon, rol_api)
                    ids_start, ids_core = obtener_top_items(mi_campeon, rol_api, enemigos=self.last_enemigos)
                    ids_sit = obtener_items_situacionales(
                        self._nombre_db(mi_campeon) or mi_campeon,
                        rol_api,
                        [self._nombre_db(e) or e for e in self.last_enemigos],
                        excluir=ids_core,
                    ) if self.last_enemigos else []
                    self.renderizar_setup_completo(mi_campeon, ids_runas, ids_spells, ids_start, ids_core, self.fr_runas_icons_vivo, ids_sit=ids_sit)
                    
                    # Ruta de habilidades
                    skill_key = self._nombre_db(mi_campeon) or mi_campeon
                    skill_key_sanitized = skill_key.replace(" ", "").replace("'", "").replace(".", "")
                    skill_order = SKILL_ORDERS.get(skill_key_sanitized, SKILL_ORDERS.get(skill_key, "Q>W>E"))
                    self.current_skill_order = skill_order
                    self.lbl_skill_order.setText(f"Max: {skill_order}  (R al 6/11/16)")
                    self.btn_export_skills.setVisible(True)

                    # Auto-import segun configuraciÃ³n
                    if self.user_settings.get("auto_runas", False):
                        self._auto_importar_runas(ids_runas, mi_campeon)
                    if self.user_settings.get("auto_hechizos", False):
                        self._auto_importar_hechizos(ids_spells)
                    if self.user_settings.get("auto_habilidades", False):
                        self._auto_importar_skill_order()
                    if self.user_settings.get("auto_items", False):
                        self._auto_importar_items(mi_campeon, ids_start, ids_core)
                else: 
                    self.current_skill_order = None
                    self.inicializar_panel_setup(self.fr_runas_icons_vivo)
                    self.lbl_skill_order.setText("Selecciona un campeÃ³n")
                    self.btn_export_skills.setVisible(False)
            # â”€â”€ PATHING JUNGLA â”€â”€
            if rol_api == "JUNGLE" and mi_campeon:
                # Buscar jungla enemigo en picks
                enemy_jg = None
                for champ, pos, _ in enemigos_procesados:
                    if pos and pos.upper() == "JUNGLE":
                        enemy_jg = champ
                        break
                pathing = sugerir_pathing_jungla(
                    self._nombre_db(mi_campeon) or mi_campeon,
                    self._nombre_db(enemy_jg) or enemy_jg if enemy_jg else None,
                    [self._nombre_db(c) or c for c in picks_al if c != mi_campeon],
                    [self._nombre_db(c) or c for c in picks_en],
                )
                self.lbl_pathing_estilo.setText(pathing.get("label", ""))
                self.lbl_pathing_estilo.setStyleSheet(
                    f"font-size: 12px; font-weight: bold; color: {pathing.get('color', ACCENT_TEAL)};"
                )
                self.lbl_pathing_inicio.setText(f"ðŸ Inicio: {pathing.get('inicio', '')}")
                self.lbl_pathing_ruta.setText(f"ðŸ“ Ruta: {pathing.get('ruta', '')}")
                self.lbl_pathing_gank.setText(f"ðŸ—¡ï¸ Gank: {pathing.get('prioridad_gank', '')}")
                vs = pathing.get("vs_jungla", "")
                self.lbl_pathing_vs.setText(vs)
                self.lbl_pathing_vs.setVisible(bool(vs))
                self.pnl_pathing.setVisible(True)
            else:
                self.pnl_pathing.setVisible(False)

            # Actualizar tip segÃºn estado del draft
            if mi_campeon and enemigo_lane:
                self.lbl_radar_tip.setText(
                    f"âš¡ <b>Coach:</b> Juegas <b>{self._nombre_display(mi_campeon)}</b> vs <b>{self._nombre_display(enemigo_lane)}</b>. "
                    f"Revisa los counters, runas y hechizos abajo. Â¡Buena suerte!"
                )
            elif mi_campeon and not enemigo_lane:
                self.lbl_radar_tip.setText(
                    f"ðŸŽ¯ <b>Coach:</b> Pickeaste {self._nombre_display(mi_campeon)}. Revisa el setup recomendado abajo. "
                    f"Prioriza runas y objetos segÃºn la composiciÃ³n enemiga."
                )
            elif not mi_campeon and len(picks_al) > 0:
                self.lbl_radar_tip.setText(
                    "ðŸ’¡ <b>Coach:</b> Espera a ver el pick rival antes de elegir. "
                    "Mientras, revisa los bans sugeridos y la composiciÃ³n de tu equipo."
                )
            else:
                self.lbl_radar_tip.setText(
                    "ðŸ’¡ <b>Coach:</b> En Champ Select, prioriza counter-pickear a tu rival de lÃ­nea. "
                    "Revisa runas y hechizos recomendados abajo."
                )

            # Tips de matchup especÃ­ficos
            if enemigo_lane:
                enemy_db = self._nombre_db(enemigo_lane) or enemigo_lane
                tips = obtener_tips_matchup(enemy_db)
                if tips:
                    tips_html = "  |  ".join(f"â€¢ {t}" for t in tips[:2])
                    self.lbl_matchup_tips.setText(
                        f"ðŸ—¡ï¸ <b>vs {self._nombre_display(enemigo_lane)}:</b>  {tips_html}"
                    )
                    self.lbl_matchup_tips.setVisible(True)
                else:
                    self.lbl_matchup_tips.setVisible(False)
            else:
                self.lbl_matchup_tips.setVisible(False)
        except Exception:
            pass

