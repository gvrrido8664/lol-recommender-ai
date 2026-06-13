"""Pestania PARTIDA EN VIVO + helpers de live game, season y picks.
Extraida de app.py sin cambios."""

from ui.contexto import *


class PartidaTabMixin:
    # ═══════════════════════════════════════════════════════════
    # PARTIDA EN VIVO (Porofessor-style)
    # ═══════════════════════════════════════════════════════════

    def armar_tab_partida(self):
        layout = QVBoxLayout(self.tab_partida)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header
        self.lbl_partida_header = QLabel("🎮 Esperando partida...\n\nLos datos apareceran cuando entres a la Grieta")
        self.lbl_partida_header.setAlignment(Qt.AlignCenter)
        self.lbl_partida_header.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 16px; padding: 20px;")
        layout.addWidget(self.lbl_partida_header)

        # Dashboard compacto
        self.pnl_partida_dash = QFrame()
        self.pnl_partida_dash.setObjectName("Panel")
        self.pnl_partida_dash.setVisible(False)
        dash_layout = QVBoxLayout(self.pnl_partida_dash)
        dash_layout.setSpacing(6)

        # Fila 1: Tu KDA + tiempo
        fila1 = QHBoxLayout()
        self.lbl_partida_kda = QLabel("Tu KDA: --/--/--")
        self.lbl_partida_kda.setStyleSheet(f"color: {TEXT_GOLD}; font-size: 16px; font-weight: bold;")
        fila1.addWidget(self.lbl_partida_kda)
        fila1.addStretch()
        self.lbl_partida_timer = QLabel("00:00")
        self.lbl_partida_timer.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 22px; font-weight: bold; font-family: Consolas;")
        fila1.addWidget(self.lbl_partida_timer)
        self.lbl_partida_cs = QLabel("CS: --")
        self.lbl_partida_cs.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; margin-left: 12px;")
        fila1.addWidget(self.lbl_partida_cs)
        dash_layout.addLayout(fila1)

        layout.addWidget(self.pnl_partida_dash)

        # Dos tablas lado a lado: aliados y enemigos
        tablas_layout = QHBoxLayout()
        tablas_layout.setSpacing(8)

        # ── Aliados ──
        self.tb_partida_aliados = QTableWidget()
        self.tb_partida_aliados.setColumnCount(4)
        self.tb_partida_aliados.setHorizontalHeaderLabels(["Campeon", "KDA", "CS", "Comentario"])
        self._estilizar_tabla_partida(self.tb_partida_aliados, "#0d0b10")
        tablas_layout.addWidget(self.tb_partida_aliados)

        # ── Enemigos ──
        self.tb_partida_enemigos = QTableWidget()
        self.tb_partida_enemigos.setColumnCount(4)
        self.tb_partida_enemigos.setHorizontalHeaderLabels(["Campeon", "KDA", "CS", "Comentario"])
        self._estilizar_tabla_partida(self.tb_partida_enemigos, "#1a0a0f")
        tablas_layout.addWidget(self.tb_partida_enemigos)

        layout.addLayout(tablas_layout, 1)

        # Composición
        self.lbl_partida_comp = QLabel("")
        self.lbl_partida_comp.setAlignment(Qt.AlignCenter)
        self.lbl_partida_comp.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.lbl_partida_comp)

    def _estilizar_tabla_partida(self, tabla, bg_color):
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabla.setSelectionMode(QAbstractItemView.NoSelection)
        tabla.verticalHeader().setDefaultSectionSize(38)
        tabla.verticalHeader().setVisible(False)
        tabla.setStyleSheet(f"""
            QTableWidget {{ background-color: {bg_color}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; font-size: 11px; }}
            QTableWidget::item {{ padding: 2px 6px; border-bottom: 1px solid #1a2236; }}
            QHeaderView::section {{ background-color: {BG_DARK}; color: {TEXT_MUTED}; font-size: 10px; padding: 3px; border: none; }}
        """)

    def actualizar_partida_vivo(self):
        """Actualiza la pestaña de partida en vivo con datos del LiveClient."""
        if not self.lcu or not self.lcu.port:
            return

        fase = self.lcu.obtener_fase_juego()
        if fase not in ("InProgress", "GameStart"):
            if hasattr(self, "overlay") and self.overlay._visible:
                self.overlay.hide_overlay()
            self.pnl_partida_dash.setVisible(False)
            self.tb_partida_aliados.setVisible(False)
            self.tb_partida_enemigos.setVisible(False)
            self.lbl_partida_header.setVisible(True)
            if fase in ("WaitingForStats", "PreEndOfGame", "EndOfGame"):
                self.lbl_partida_header.setText("🏁 Partida terminada\n\nRevisa tu perfil para ver el analisis")
                # Mostrar post-game una sola vez por partida (al transicionar desde InProgress)
                if not self._postgame_shown and self._last_fase in ("InProgress", "GameStart"):
                    self._postgame_shown = True
                    threading.Thread(target=self._preparar_postgame, daemon=True).start()
            else:
                # Nueva fase de lobby → resetear para la próxima partida
                self._postgame_shown = False
                self.lbl_partida_header.setText("🎮 Esperando partida...\n\nLos datos apareceran cuando entres a la Grieta")
            self._last_fase = fase
            return

        # Entró a una partida nueva → resetear el flag
        if self._last_fase not in ("InProgress", "GameStart"):
            self._postgame_shown = False
            self._last_game_stats = {}
        self._last_fase = fase

        # Partida en vivo
        jugadores, game_info = self.lcu.obtener_liveclient_data()

        if jugadores and len(jugadores) >= 2:
            self._renderizar_partida_live(jugadores, game_info)
            return

        # Fallback: LCU (solo campeones, sin KDA)
        jugadores_lcu = self.lcu.obtener_summoners_partida()
        if jugadores_lcu and len(jugadores_lcu) >= 2:
            self._renderizar_partida_lcu(jugadores_lcu)
            return

        # Loading
        if isinstance(game_info, dict) and game_info.get("status") == "loading":
            self.lbl_partida_header.setVisible(True)
            self.pnl_partida_dash.setVisible(False)
            self.tb_partida_aliados.setVisible(False)
            self.tb_partida_enemigos.setVisible(False)
            self.lbl_partida_header.setText("⏳ Entrando a la Grieta...\n\nLos datos apareceran al iniciar la partida")

    def _renderizar_partida_live(self, jugadores, game_info):
        """Renderiza la partida con datos del LiveClient (KDA, CS, etc.)."""
        self.lbl_partida_header.setVisible(False)
        self.pnl_partida_dash.setVisible(True)
        self.tb_partida_aliados.setVisible(True)
        self.tb_partida_enemigos.setVisible(True)

        aliados = [j for j in jugadores if j.get("team") == "ORDER"]
        enemigos = [j for j in jugadores if j.get("team") == "CHAOS"]

        # Buscar nuestro jugador
        mi_nombre_raw = self.lcu.obtener_nombre_invocador() or ""
        mi_nombre = mi_nombre_raw.split("#")[0].strip().lower()
        yo = None
        for j in jugadores:
            sn = (j.get("summonerName", "") or "").lower()
            if sn == mi_nombre or mi_nombre in sn or sn in mi_nombre:
                yo = j
                break

        # Dashboard personal
        game_time = game_info.get("gameTime", 0) if isinstance(game_info, dict) else 0
        mins, secs = int(game_time // 60), int(game_time % 60)
        self.lbl_partida_timer.setText(f"{mins:02d}:{secs:02d}")

        if yo:
            k, d, a = yo.get("kills", 0) or 0, yo.get("deaths", 0) or 0, yo.get("assists", 0) or 0
            cs = yo.get("creepScore", 0) or 0
            cname = yo.get("championName", "?")
            cs_min = cs / max(1, game_time / 60)
            self.lbl_partida_kda.setText(f"🔥 Tu {cname}: {k}/{d}/{a}")
            self.lbl_partida_cs.setText(f"CS: {cs} ({cs_min:.1f}/min)")
            # Cachear para post-game (actualizamos siempre para tener el estado más reciente)
            self._last_game_stats = {
                "champion": cname, "kills": k, "deaths": d, "assists": a,
                "cs": cs, "game_time": game_time,
            }
        else:
            self.lbl_partida_kda.setText("🔥 Tu: (buscando...)")
            self.lbl_partida_cs.setText("CS: --")

        # Tablas aliados/enemigos
        self._llenar_tabla_partida(self.tb_partida_aliados, aliados, "🔵 ALIADOS", BG_DARK, yo)
        self._llenar_tabla_partida(self.tb_partida_enemigos, enemigos, "🔴 ENEMIGOS", "#1a0a0f", yo)

        # Alimentar overlay si está activado
        if self.user_settings.get("overlay_ingame", False):
            if not self.overlay._visible:
                self.overlay.show_overlay()
            self.overlay.feed_live_data(jugadores, game_info, mi_nombre_raw)

        # Composicion
        a_nombres = [j.get("championName", "") for j in aliados if j.get("championName")]
        e_nombres = [j.get("championName", "") for j in enemigos if j.get("championName")]
        if len(a_nombres) >= 3 and len(e_nombres) >= 3:
            try:
                ad_a, ap_a, tk_a = analizar_composicion(a_nombres)
                ad_e, ap_e, tk_e = analizar_composicion(e_nombres)
                self.lbl_partida_comp.setText(
                    f"⚔️ Aliados: AD {ad_a}% / AP {ap_a}% ({tk_a} front)  |  "
                    f"Enemigos: AD {ad_e}% / AP {ap_e}% ({tk_e} front)"
                )
            except Exception:
                self.lbl_partida_comp.setText("")
        else:
            self.lbl_partida_comp.setText("")

    def _renderizar_partida_lcu(self, jugadores):
        """Renderiza la partida usando solo datos LCU (campeones, sin KDA)."""
        self.lbl_partida_header.setVisible(False)
        self.pnl_partida_dash.setVisible(True)
        self.tb_partida_aliados.setVisible(True)
        self.tb_partida_enemigos.setVisible(True)

        # Buscar nuestro jugador en LCU
        mi_nombre_raw = self.lcu.obtener_nombre_invocador() or ""
        mi_nombre = mi_nombre_raw.split("#")[0].strip().lower()
        yo = None
        for j in jugadores:
            sn = (j.get("summonerName", "") or "").lower()
            if sn == mi_nombre or mi_nombre in sn or sn in mi_nombre:
                yo = j
                break

        if yo:
            cid = str(yo.get("championId", "0"))
            cname = self.procesar_nombre_champ(cid, "0") or "Desconocido"
            self.lbl_partida_kda.setText(f"🎮 En partida con {cname} (datos basicos LCU)")
            self._last_game_stats = {"champion": cname, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "game_time": 0}
        else:
            self.lbl_partida_kda.setText("🎮 Partida en vivo (datos basicos LCU)")
        self.lbl_partida_cs.setText("CS: --")
        self.lbl_partida_timer.setText("--:--")

        aliados = [j for j in jugadores if j.get("team") == "ORDER"]
        enemigos = [j for j in jugadores if j.get("team") == "CHAOS"]

        self._llenar_tabla_partida_lcu(self.tb_partida_aliados, aliados, "🔵 ALIADOS", BG_DARK)
        self._llenar_tabla_partida_lcu(self.tb_partida_enemigos, enemigos, "🔴 ENEMIGOS", "#1a0a0f")

        a_nombres = [self.procesar_nombre_champ(str(j.get("championId", 0)), "0") for j in aliados if self.procesar_nombre_champ(str(j.get("championId", 0)), "0")]
        e_nombres = [self.procesar_nombre_champ(str(j.get("championId", 0)), "0") for j in enemigos if self.procesar_nombre_champ(str(j.get("championId", 0)), "0")]
        if len(a_nombres) >= 3 and len(e_nombres) >= 3:
            try:
                ad_a, ap_a, tk_a = analizar_composicion(a_nombres)
                ad_e, ap_e, tk_e = analizar_composicion(e_nombres)
                self.lbl_partida_comp.setText(
                    f"⚔️ Aliados: AD {ad_a}% / AP {ap_a}% ({tk_a} front)  |  "
                    f"Enemigos: AD {ad_e}% / AP {ap_e}% ({tk_e} front)"
                )
            except Exception:
                self.lbl_partida_comp.setText("")
        else:
            self.lbl_partida_comp.setText("")

    def _preparar_postgame(self):
        """Ejecutado en thread: reune datos y emite postgame_ready para mostrar el dialogo."""
        try:
            stats = dict(self._last_game_stats) if self._last_game_stats else {}

            # Obtener datos reales de la ultima partida desde LCU history
            try:
                historial = self.lcu.obtener_historial_extendido(cantidad=1)
                if historial:
                    ult = historial[0]
                    part = ult.get("participants", [{}])[0]
                    part_stats = part.get("stats", {})

                    # Datos basicos de la partida
                    stats["kills"] = part_stats.get("kills", stats.get("kills", 0))
                    stats["deaths"] = part_stats.get("deaths", stats.get("deaths", 0))
                    stats["assists"] = part_stats.get("assists", stats.get("assists", 0))
                    stats["cs"] = part_stats.get("totalMinionsKilled", 0) + part_stats.get("neutralMinionsKilled", 0)
                    stats["game_time"] = ult.get("gameDuration", stats.get("game_time", 0))
                    cid = str(part.get("championId", "0"))
                    stats["champion"] = self.procesar_nombre_champ(cid, "0") or stats.get("champion", "?")
                    win = part_stats.get("win", None)
                    if win is True:
                        stats["resultado"] = "Victoria"
                    elif win is False:
                        stats["resultado"] = "Derrota"

                    # Estadisticas adicionales de la partida
                    stats["vision_score"] = part_stats.get("visionScore", 0)
                    stats["wards_placed"] = part_stats.get("wardsPlaced", 0)
                    stats["control_wards"] = part_stats.get("visionWardsBoughtInGame", 0)
                    stats["damage_dealt"] = part_stats.get("totalDamageDealtToChampions", 0)
                    stats["damage_taken"] = part_stats.get("totalDamageTaken", 0)
                    stats["gold"] = part_stats.get("goldEarned", 0)
                    stats["cc_score"] = part_stats.get("timeCCingOthers", 0)
                    stats["turret_kills"] = part_stats.get("turretKills", 0)
                    stats["objectives"] = (part_stats.get("dragonKills", 0) + part_stats.get("baronKills", 0)
                                          + part_stats.get("turretKills", 0))
                    stats["penta"] = part_stats.get("pentaKills", 0)
                    stats["triple"] = part_stats.get("tripleKills", 0)
                    stats["first_blood"] = part_stats.get("firstBloodKill", False)
            except Exception as e:
                print(f"[PostGame] Error obteniendo datos LCU: {e}")

            # Medias historicas desde BD para comparativa
            try:
                conn = obtener_conexion()
                cur = conn.cursor()
                cur.execute("""
                    SELECT AVG(COALESCE(kills,0)), AVG(COALESCE(deaths,1)), AVG(COALESCE(assists,0))
                    FROM participantes
                    WHERE kills IS NOT NULL
                """)
                row = cur.fetchone()
                conn.close()
                if row and row[0] is not None:
                    stats["avg_k"] = round(float(row[0]), 1)
                    stats["avg_d"] = round(float(row[1]), 1)
                    stats["avg_a"] = round(float(row[2]), 1)
                else:
                    stats.setdefault("avg_k", 5.0)
                    stats.setdefault("avg_d", 4.0)
                    stats.setdefault("avg_a", 7.0)
            except Exception:
                stats.setdefault("avg_k", 5.0)
                stats.setdefault("avg_d", 4.0)
                stats.setdefault("avg_a", 7.0)

            # Analisis completo: puntos fuertes, debiles y consejos
            positives = []
            negatives = []
            tips = []

            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs_val = stats.get("cs", 0)
            game_time = stats.get("game_time", 600)
            avg_k = stats.get("avg_k", 5)
            avg_d = stats.get("avg_d", 4)
            avg_a = stats.get("avg_a", 7)
            result = stats.get("resultado", "")

            if game_time > 60:
                cs_min = cs_val / (game_time / 60)
            else:
                cs_min = 0

            # Puntos fuertes
            if k >= 10:
                positives.append(f"⚔️ {k} kills — excelente presencia ofensiva")
            if d <= 2 and game_time >= 600:
                positives.append(f"🛡️ Solo {d} muertes — muy buena supervivencia")
            if a >= 10:
                positives.append(f"🤝 {a} asistencias — gran impacto en equipo")
            if cs_min >= 7.5 and game_time >= 600:
                positives.append(f"🌾 {cs_min:.1f} CS/min — farmeo solido")
            if k > avg_k * 1.3:
                positives.append(f"📈 +{k - int(avg_k)} kills sobre tu media ({avg_k:.0f})")
            if d < avg_d * 0.7 and d <= avg_d:
                positives.append(f"📉 -{int(avg_d) - d} muertes bajo tu media ({avg_d:.0f})")
            if k + a >= 20:
                positives.append(f"🎯 {k + a} de participacion — muy activo en el mapa")
            if stats.get("vision_score", 0) >= 30:
                positives.append(f"👁️ {stats['vision_score']} de vision — buen control de mapa")
            if stats.get("penta", 0) >= 1:
                positives.append("🔥 PENTAKILL — partida legendaria")
            if stats.get("first_blood", False):
                positives.append("⚡ First Blood — ventaja temprana")

            # Puntos debiles
            if d >= 7:
                negatives.append(f"⚠️ {d} muertes — demasiadas, revisa tu posicionamiento")
            if d > avg_d * 1.5:
                negatives.append(f"📊 +{d - int(avg_d)} muertes sobre tu media — partida atipica o tilt")
            if cs_min < 5.0 and game_time >= 600:
                negatives.append(f"📉 CS/min bajo ({cs_min:.1f}) — practica el farmeo")
            if k + a < d * 1.5 and game_time >= 600:
                negatives.append(f"📉 Baja participacion — K+A ({k + a}) vs D ({d})")
            if stats.get("vision_score", 0) < 5 and game_time >= 900:
                negatives.append(f"🔦 Poca vision ({stats.get('vision_score', 0)}) — compra wards de control")
            if d >= 3 and k == 0 and game_time >= 600:
                negatives.append("😓 Sin kills — enfocate en jugadas seguras")
            if cs_min < 3.5 and game_time >= 900:
                negatives.append("🚫 Farmeo muy bajo — prioriza las oleadas de minions")

            # Consejos de mejora
            if negatives:
                tips.append("Consejo: " + negatives[0].split("—")[-1].strip() if "—" in negatives[0] else negatives[0])
            if d >= 5:
                tips.append("Juega mas conservador si vas detras y espera los powerspikes de tu campeon")
            if k + a < 5 and game_time >= 900:
                tips.append("Intenta rotar mas para ayudar a tu equipo en objetivos (dragon, heraldo)")
            if cs_min < 6.0:
                tips.append("Dedica 10 min en practica de herramientas a farmear bajo torre")
            if result == "Derrota" and k >= 8:
                tips.append("Aunque perdiste, tu desempeno ofensivo fue bueno. Revisa decisiones macro")
            if result == "Victoria" and d >= 7:
                tips.append("Buen resultado pero cuidado con las muertes — en partidas mas dificiles te castigaran")

            stats["positives"] = positives[:4]
            stats["negatives"] = negatives[:4]
            tips_dedup = list(dict.fromkeys(tips))
            stats["tip"] = "  |  ".join(tips_dedup[:3]) if tips_dedup else ""

            self.postgame_ready.emit(stats)
        except Exception as e:
            print(f"[PostGame] Error preparando resumen: {e}")
            import traceback
            traceback.print_exc()

    def _on_postgame_ready(self, stats: dict):
        """Muestra el diálogo de post-game en el hilo principal."""
        try:
            dlg = PostGameDialog(stats, parent=self)
            dlg.coaching_requested.connect(self._ir_a_coaching)
            dlg.show()
        except Exception as e:
            print(f"[PostGame] Error mostrando diálogo: {e}")

    def _on_season_partial(self, batch: list):
        try:
            if not hasattr(self, 'all_games_season'):
                self.all_games_season = []
            seen = {self._gid_or_fallback(g) for g in self.all_games_season}
            nuevos = 0
            for g in batch:
                gid = self._gid_or_fallback(g)
                if gid and gid not in seen:
                    seen.add(gid)
                    self.all_games_season.append(g)
                    nuevos += 1

            if nuevos > 0:
                if not hasattr(self, 'historial_games'):
                    self.historial_games = []
                hseen = {self._gid_or_fallback(g) for g in self.historial_games}
                for g in batch:
                    gid = self._gid_or_fallback(g)
                    if gid and gid not in hseen:
                        hseen.add(gid)
                        self.historial_games.append(g)

                puuid = getattr(self, '_season_puuid', None)
                if puuid and hasattr(self, 'all_games_season'):
                    guardar_season_cache(puuid, self.all_games_season)

                if not hasattr(self, '_partial_refresh_timer'):
                    self._partial_refresh_timer = QTimer(self)
                    self._partial_refresh_timer.setSingleShot(True)
                    self._partial_refresh_timer.timeout.connect(
                        self._on_season_partial_refresh
                    )
                self._partial_refresh_timer.start(2000)
        except Exception as e:
            print(f"[SeasonPartial] Error: {e}")

    def _on_season_partial_refresh(self):
        try:
            if not hasattr(self, 'historial_games') or not self.historial_games:
                return
            if not getattr(self, 'perfil_cargado', False):
                return
            self._renderizar_historial(self.historial_games)
        except Exception as e:
            print(f"[SeasonPartialRefresh] Error: {e}")

    def _ir_a_coaching(self):
        """Navega a la pestaña de Coaching."""
        try:
            for i in range(self.tabview.count()):
                if "coaching" in self.tabview.tabText(i).lower() or "perfil" in self.tabview.tabText(i).lower():
                    self.tabview.setCurrentIndex(i)
                    break
        except Exception:
            pass

    def _llenar_tabla_partida(self, tabla, jugadores, team_label, bg, yo):
        """Llena una tabla con datos de jugadores (LiveClient)."""
        tabla.setRowCount(0)

        # Header row
        row = tabla.rowCount(); tabla.insertRow(row)
        hdr = QTableWidgetItem(team_label)
        hdr.setBackground(QColor(bg)); hdr.setForeground(QColor(BORDER_ACCENT))
        f = hdr.font(); f.setBold(True); hdr.setFont(f)
        tabla.setItem(row, 0, hdr)
        for c in range(1, 4):
            e = QTableWidgetItem(""); e.setBackground(QColor(bg)); tabla.setItem(row, c, e)

        conn_db = obtener_conexion()
        try:
            for j in jugadores:
                cname = j.get("championName", "?") or "?"
                k, d, a_v = j.get("kills", 0) or 0, j.get("deaths", 0) or 0, j.get("assists", 0) or 0
                cs = j.get("creepScore", 0) or 0

                # Comentario: basado en KDA y WR de BD
                kda_val = (k + a_v) / max(1, d)
                comentario, color_com = self._comentar_jugador_partida(cname, k, d, a_v, kda_val, conn=conn_db)

                # WR desde BD
                wr = "--"
                try:
                    cur = conn_db.cursor()
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=%s", (cname,))
                    r = cur.fetchone()
                    if r and r[0]:
                        wr = f"{float(r[0])}%"
                except Exception:
                    pass

                row = tabla.rowCount(); tabla.insertRow(row)
                item_c = QTableWidgetItem(f"  {cname}")
                icon_p = self.descargar_imagen(cname, "champ")
                if icon_p:
                    item_c.setIcon(QIcon(icon_p))
                # Color de nombre segun si es el jugador local
                item_c.setForeground(QColor(TEXT_GOLD if j == yo else TEXT_WHITE))
                tabla.setItem(row, 0, item_c)

                item_kda = QTableWidgetItem(f"{k}/{d}/{a_v}")
                if k + d + a_v > 0:
                    color_kda = GREEN_WR if kda_val >= 3 else YELLOW_WR if kda_val >= 1.5 else RED_WR
                    item_kda.setForeground(QColor(color_kda))
                tabla.setItem(row, 1, item_kda)

                item_cs = QTableWidgetItem(str(cs))
                item_cs.setForeground(QColor(ACCENT_TEAL))
                tabla.setItem(row, 2, item_cs)

                item_com = QTableWidgetItem(f"WR:{wr} {comentario}")
                item_com.setForeground(QColor(color_com))
                tabla.setItem(row, 3, item_com)
        finally:
            conn_db.close()

    def _llenar_tabla_partida_lcu(self, tabla, jugadores, team_label, bg):
        """Llena una tabla con datos de jugadores (LCU, sin KDA)."""
        tabla.setRowCount(0)

        row = tabla.rowCount(); tabla.insertRow(row)
        hdr = QTableWidgetItem(team_label)
        hdr.setBackground(QColor(bg)); hdr.setForeground(QColor(BORDER_ACCENT))
        f = hdr.font(); f.setBold(True); hdr.setFont(f)
        tabla.setItem(row, 0, hdr)
        for c in range(1, 4):
            e = QTableWidgetItem(""); e.setBackground(QColor(bg)); tabla.setItem(row, c, e)

        conn_db = obtener_conexion()
        try:
            for j in jugadores:
                cid = int(j.get("championId", 0))
                cname = self.procesar_nombre_champ(str(cid), "0") or "?"

                # Comentario desde BD
                comentario, color_com = self._comentar_jugador_partida(cname, 0, 0, 0, 0, conn=conn_db)

                wr = "--"
                try:
                    cur = conn_db.cursor()
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=%s", (cname,))
                    r = cur.fetchone()
                    if r and r[0]:
                        wr = f"{float(r[0])}%"
                except Exception:
                    pass

                row = tabla.rowCount(); tabla.insertRow(row)
                item_c = QTableWidgetItem(f"  {cname}")
                icon_p = self.descargar_imagen(cname, "champ")
                if icon_p:
                    item_c.setIcon(QIcon(icon_p))
                tabla.setItem(row, 0, item_c)
                tabla.setItem(row, 1, QTableWidgetItem("--/--/--"))
                tabla.setItem(row, 2, QTableWidgetItem("--"))
                item_com = QTableWidgetItem(f"WR:{wr} {comentario}")
                item_com.setForeground(QColor(color_com))
                tabla.setItem(row, 3, item_com)
        finally:
            conn_db.close()

    def _comentar_jugador_partida(self, champion, k, d, a, kda_val, conn=None):
        """Genera un comentario estilo Porofessor sobre un jugador."""
        close_conn = conn is None
        try:
            if conn is None:
                conn = obtener_conexion()
            cur = conn.cursor()
            # WR y partidas totales
            cur.execute("SELECT COUNT(*), ROUND(AVG(kills),1), ROUND(AVG(deaths),1) FROM participantes WHERE champion=%s", (champion,))
            r = cur.fetchone()
            if r:
                total = int(r[0] or 0)
                avg_k = float(r[1] or 0)
                avg_d = float(r[2] or 0)
            else:
                total, avg_k, avg_d = 0, 0.0, 0.0

            comentarios = []
            color = "#a39a93"  # default gray

            if total < 5:
                comentarios.append("1a vez?")
                color = "#7a6f68"
            else:
                if avg_d and avg_d >= 6:
                    comentarios.append("Muchas muertes")
                if avg_k and avg_k >= 7:
                    comentarios.append("Buenas kills")

            # KDA actual
            if k + d + a > 0:
                if kda_val >= 5:
                    comentarios.append("🔥 En fuego")
                    color = GREEN_WR
                elif kda_val >= 3:
                    comentarios.append("✅ Sólido")
                    color = GREEN_WR
                elif kda_val < 1.0:
                    comentarios.append("💀 Feedeando")
                    color = RED_WR
                elif d >= 5:
                    comentarios.append("⚠️ Frágil")
                    color = YELLOW_WR

            # Racha reciente
            if total >= 5:
                try:
                    cur.execute("""SELECT p.win FROM participantes p JOIN matches m ON p.match_id=m.match_id 
                                  WHERE p.champion=? ORDER BY m.fecha_descarga DESC LIMIT 5""", (champion,))
                    wins = [r2[0] for r2 in cur.fetchall()]
                    if wins:
                        w_count = sum(1 for w in wins if w)
                        if w_count >= 4:
                            comentarios.append("🔥 Racha buena")
                            color = GREEN_WR
                        elif w_count <= 1:
                            comentarios.append("❄️ Racha mala")
                            color = RED_WR if total > 10 else color
                except Exception:
                    pass

            if not comentarios:
                comentarios.append("—")

            return " · ".join(comentarios), color
        except Exception:
            return "—", TEXT_MUTED
        finally:
            if close_conn and conn is not None:
                conn.close()

    def _actualizar_counters_vivo(self, rol_api, enemigo_lane):
        """Actualiza la seccion de counter picks contra el rival de linea."""
        self.last_enemigo_lane = enemigo_lane
        clear_layout(self.fr_counters_vivo)
        if enemigo_lane:
            self.panel_counters_vivo.label_title.setText(
                f"COUNTERS vs {self._nombre_display(enemigo_lane).upper()}"
            )
            counters = obtener_counters(rol_api, enemigo_lane, min_partidas=10)
            counters_filtrados = [(c, wr, p) for c, wr, p in counters 
                                 if c not in self.last_aliados and c not in self.last_enemigos][:6]
            for i, (c, wr, p) in enumerate(counters_filtrados):
                self.renderizar_icono(c, "champ", self.fr_counters_vivo, 0, i,
                    f"{self._nombre_display(c)}\nWR: {wr}% ({p} partidas)", size=35)
            if not counters_filtrados:
                lbl = QLabel("Sin datos suficientes")
                lbl.setStyleSheet("color: gray;")
                self.fr_counters_vivo.addWidget(lbl)
        else:
            self.panel_counters_vivo.label_title.setText("COUNTERS (esperando rival...)")

    def _actualizar_counters_manual(self, rol_api, rival_nombre):
        """Actualiza counters cuando el usuario selecciona un rival manualmente."""
        rival_db = self._nombre_db(rival_nombre)
        if not rival_db or rival_db == "Seleccionar rival...": return
        clear_layout(self.fr_counters_vivo)
        self.panel_counters_vivo.label_title.setText(f"COUNTERS vs {self._nombre_display(rival_db).upper()}")
        counters = obtener_counters(rol_api, rival_db, min_partidas=5)
        counters_filtrados = [(c, wr, p) for c, wr, p in counters 
                             if c not in self.last_aliados and c not in self.last_enemigos][:6]
        for i, (c, wr, p) in enumerate(counters_filtrados):
            self.renderizar_icono(c, "champ", self.fr_counters_vivo, 0, i,
                f"{self._nombre_display(c)}\nWR: {wr}% ({p} partidas)", size=35)
        if not counters_filtrados:
            lbl = QLabel("Sin datos"); lbl.setStyleSheet("color: gray;"); self.fr_counters_vivo.addWidget(lbl)

    def mostrar_equipo_vivo(self, layout, picks, is_ally=True):
        clear_layout(layout)
        if not picks:
            lbl = QLabel("Esperando equipo...")
            lbl.setStyleSheet("color: gray; font-style: italic;")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
            return
            
        for champ in picks:
            card = QFrame()
            card.setObjectName("CardPick")
            border_color = ACCENT_TEAL if is_ally else RED_WR
            card.setStyleSheet(f"""
                QFrame#CardPick {{
                    border: 1px solid {BG_CARD_HOVER};
                    border-left: 3px solid {border_color};
                    border-radius: 4px;
                    background-color: {BG_CARD};
                    margin-bottom: 3px;
                }}
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 4, 8, 4)
            card_layout.setSpacing(6)
            
            icon_layout = QGridLayout()
            self.renderizar_icono(champ, "champ", icon_layout, 0, 0, size=30)
            card_layout.addLayout(icon_layout)
            
            lbl_name = QLabel(self._nombre_display(champ))
            lbl_name.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {TEXT_PRIMARY};")
            card_layout.addWidget(lbl_name)
            card_layout.addStretch()
            layout.addWidget(card)

    def _cargar_stats_season(self):
        """Carga estadisticas de la season. Procesa todas las partidas en memoria,
        guarda la lista completa en self._season_champ_data y renderiza los primeros 15.
        El resto se carga bajo demanda via scroll (lazy loading)."""
        if not hasattr(self, 'all_games_season') or not self.all_games_season:
            if hasattr(self, 'historial_games') and self.historial_games:
                self.all_games_season = list(self.historial_games)
            else:
                return
        try:
            all_games = self.all_games_season
            # DEDUP
            seen_ids = set()
            unique_games = []
            for g in all_games:
                gid = str(g.get("gameId", ""))
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                if gid and gid not in seen_ids:
                    seen_ids.add(gid)
                    unique_games.append(g)
            if len(unique_games) < len(all_games):
                print(f"[_cargar_stats_season] DEDUP: {len(all_games)} -> {len(unique_games)} partidas unicas")
            # Computar stats por campeon (todos, con CS y duracion)
            champ_stats = {}
            for g in unique_games:
                part = g.get("participants", [{}])[0]
                stats = part.get("stats", {})
                cid = str(part.get("championId", "0"))
                cname = self.procesar_nombre_champ(cid, "0") or "?"
                if cname == "?":
                    continue
                if cname not in champ_stats:
                    champ_stats[cname] = {
                        "wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0,
                        "total_cs": 0, "total_duration": 0,
                    }
                cs = champ_stats[cname]
                cs["games"] += 1
                if stats.get("win", False):
                    cs["wins"] += 1
                cs["kills"] += stats.get("kills", 0)
                cs["deaths"] += stats.get("deaths", 0)
                cs["assists"] += stats.get("assists", 0)
                cs["total_cs"] += stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
                cs["total_duration"] += g.get("gameDuration", 0)

            # Ordenar por partidas descendente y guardar lista completa
            sorted_champs = sorted(champ_stats.items(), key=lambda x: x[1]["games"], reverse=True)
            self._season_champ_data = []
            for cname, cs in sorted_champs:
                self._season_champ_data.append({
                    "name": cname,
                    "games": cs["games"],
                    "wins": cs["wins"],
                    "kills": cs["kills"],
                    "deaths": cs["deaths"],
                    "assists": cs["assists"],
                    "total_cs": cs["total_cs"],
                    "total_duration": cs["total_duration"],
                })
            print(f"[_cargar_stats_season] {len(unique_games)} partidas, {len(self._season_champ_data)} campeones totales")
            # Cargar primeros 15 (o menos si hay pocos)
            self._season_offset = 0
            self._cargando_season = False
            self.tb_season_champs.setRowCount(0)
            self._append_champs_season(count=15)
        except Exception as e:
            print(f"[_cargar_stats_season] Error: {e}")

    def _crear_fila_champ_season(self, champ: dict, max_games: int):
        """Construye los 4 widgets de celda para una fila de campeon en la tabla de season."""
        cname = champ["name"]
        games = champ["games"]
        wins = champ["wins"]
        kills = champ["kills"]
        deaths = champ["deaths"]
        assists = champ["assists"]
        total_cs = champ["total_cs"]
        total_dur = max(champ["total_duration"], 1)
        wr_val = round(wins * 100 / games, 1) if games > 0 else 0
        kda_val = round((kills + assists) / max(1, deaths), 2)
        cs_min = round(total_cs / (total_dur / 60), 1)
        bar_pct = int((games / max(1, max_games)) * 100)
        wr_color = GREEN_WR if wr_val >= 50 else RED_WR

        # ── Col 0: Icono + Nombre + CS ──
        w0 = QWidget()
        w0.setStyleSheet("background: transparent;")
        l0 = QHBoxLayout(w0)
        l0.setContentsMargins(4, 3, 4, 3)
        l0.setSpacing(6)
        icon_lbl = QLabel()
        icon_path = self.descargar_imagen(cname, "champ")
        if icon_path:
            icon_lbl.setPixmap(QPixmap(icon_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_lbl.setFixedSize(28, 28)
        l0.addWidget(icon_lbl)
        txt_vbox = QVBoxLayout()
        txt_vbox.setContentsMargins(0, 0, 0, 0)
        txt_vbox.setSpacing(0)
        lbl_name = QLabel(self._nombre_con_dificultad(cname))
        lbl_name.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; font-weight: bold; background: transparent;")
        txt_vbox.addWidget(lbl_name)
        lbl_cs = QLabel(f"CS {total_cs} ({cs_min}/min)")
        lbl_cs.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8px; background: transparent;")
        txt_vbox.addWidget(lbl_cs)
        l0.addLayout(txt_vbox, 1)

        # ── Col 1: Partidas + mini barra ──
        w1 = QWidget()
        w1.setStyleSheet("background: transparent;")
        l1 = QVBoxLayout(w1)
        l1.setContentsMargins(2, 5, 2, 5)
        l1.setSpacing(2)
        lbl_games = QLabel(str(games))
        lbl_games.setAlignment(Qt.AlignCenter)
        lbl_games.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 13px; font-weight: bold; background: transparent;")
        l1.addWidget(lbl_games)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(bar_pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: #1a2332; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {ACCENT_TEAL}; border-radius: 1px; }}
        """)
        l1.addWidget(bar)

        # ── Col 2: WR % ──
        w2 = QLabel(f"{wr_val}%")
        w2.setAlignment(Qt.AlignCenter)
        w2.setStyleSheet(f"color: {wr_color}; font-size: 14px; font-weight: bold; background: transparent; padding: 4px;")

        # ── Col 3: KDA ratio + K/D/A ──
        w3 = QWidget()
        w3.setStyleSheet("background: transparent;")
        l3 = QVBoxLayout(w3)
        l3.setContentsMargins(2, 3, 2, 3)
        l3.setSpacing(0)
        lbl_kda = QLabel(f"{kda_val}:1")
        lbl_kda.setAlignment(Qt.AlignCenter)
        lbl_kda.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; font-weight: bold; background: transparent;")
        l3.addWidget(lbl_kda)
        kda_detail = QLabel()
        kda_detail.setAlignment(Qt.AlignCenter)
        kda_detail.setTextFormat(Qt.RichText)
        avg_k = round(kills / max(1, games))
        avg_d = round(deaths / max(1, games))
        avg_a = round(assists / max(1, games))
        kda_detail.setText(
            f"<span style='color:{GREEN_WR};font-size:9px;'>{avg_k}</span>"
            f"<span style='color:{TEXT_MUTED};font-size:9px;'>/</span>"
            f"<span style='color:{RED_WR};font-size:9px;'>{avg_d}</span>"
            f"<span style='color:{TEXT_MUTED};font-size:9px;'>/</span>"
            f"<span style='color:{YELLOW_WR};font-size:9px;'>{avg_a}</span>"
        )
        l3.addWidget(kda_detail)

        return w0, w1, w2, w3

    def _append_champs_season(self, count=15):
        """Añade los siguientes 'count' campeones a la tabla sin limpiar."""
        if not hasattr(self, '_season_champ_data') or not self._season_champ_data:
            return
        data = self._season_champ_data
        offset = self._season_offset
        end = min(offset + count, len(data))
        if offset >= len(data):
            return
        max_games = data[0]["games"] if data else 1
        for i in range(offset, end):
            champ = data[i]
            w0, w1, w2, w3 = self._crear_fila_champ_season(champ, max_games)
            r = self.tb_season_champs.rowCount()
            self.tb_season_champs.insertRow(r)
            self.tb_season_champs.setCellWidget(r, 0, w0)
            self.tb_season_champs.setCellWidget(r, 1, w1)
            self.tb_season_champs.setCellWidget(r, 2, w2)
            self.tb_season_champs.setCellWidget(r, 3, w3)
            self.tb_season_champs.setRowHeight(r, 52)
        self._season_offset = end
        if end >= len(data):
            print(f"[_cargar_stats_season] Todos los {len(data)} campeones cargados")

    def _on_scroll_season(self, value):
        """Detecta scroll cercano al final y carga mas campeones."""
        sb = self.tb_season_champs.verticalScrollBar()
        if sb.maximum() > 0 and value >= int(sb.maximum() * 0.80):
            if not hasattr(self, '_cargando_season'):
                self._cargando_season = False
            if self._cargando_season:
                return
            self._cargando_season = True
            try:
                self._append_champs_season(count=15)
            finally:
                self._cargando_season = False

    def mostrar_picks_vivo(self, rol, aliados, enemigos):
        clear_layout(self.fr_picks_icons)
        sugerencias = recomendar_picks_vivo(rol, aliados, enemigos)
        col_idx = 0
        
        for categoria, champs in sugerencias.items():
            if not champs: continue
            
            cat_layout = QVBoxLayout()
            cat_layout.setAlignment(Qt.AlignTop)
            lbl_cat = QLabel(categoria)
            lbl_cat.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 10px;")
            lbl_cat.setAlignment(Qt.AlignCenter)
            cat_layout.addWidget(lbl_cat)
            
            grid_icons = QGridLayout()
            grid_icons.setAlignment(Qt.AlignCenter)
            for i, (champ, puntuacion, razon) in enumerate(champs[:4]):
                # Estrellas segun puntuacion (escala 1.0-10.0)
                if puntuacion >= 9.0: estrellas = "⭐⭐⭐⭐⭐"
                elif puntuacion >= 7.0: estrellas = "⭐⭐⭐⭐"
                elif puntuacion >= 5.0: estrellas = "⭐⭐⭐"
                elif puntuacion >= 3.0: estrellas = "⭐⭐"
                else: estrellas = "⭐"
                
                # Color segun puntuacion
                if puntuacion >= 8.0: color_pts = GREEN_WR
                elif puntuacion >= 5.0: color_pts = TEXT_GOLD
                elif puntuacion >= 3.0: color_pts = YELLOW_WR
                else: color_pts = RED_WR
                
                tooltip = (
                    f"{self._nombre_display(champ)}\n"
                    f"⭐ Puntuacion: {puntuacion}/10.0\n"
                    f"📊 {razon}"
                )
                self.renderizar_icono(champ, "champ", grid_icons, i // 2, i % 2,
                    tooltip, size=35)
                
                # Etiqueta de puntuación debajo del icono
                lbl_pts = QLabel(f"{puntuacion}")
                lbl_pts.setAlignment(Qt.AlignCenter)
                lbl_pts.setStyleSheet(f"color: {color_pts}; font-size: 9px; font-weight: bold; padding: 0px;")
                grid_icons.addWidget(lbl_pts, (i // 2) * 2 + 1, i % 2)  # fila impar debajo del icono
                
            cat_layout.addLayout(grid_icons)
            self.fr_picks_icons.addLayout(cat_layout, 0, col_idx)
            col_idx += 1

    def _dificultad_stars(self, champion):
        """Devuelve estrellas de dificultad (1-3) basadas en tags del campeon."""
        try:
            champ_key = champion.replace(" ", "").replace("'", "").replace(".", "").replace("&", "")
            champ_key = self.nombre_interno.get(champ_key, champ_key)
            tag = obtener_tag(champ_key)
            d = tag.get("difficulty", 2)
            return "⭐" * d
        except Exception:
            return "⭐⭐"

    def _nombre_con_dificultad(self, champion):
        """Nombre del campeon con estrellas si mostrar_dificultad esta activo."""
        nombre = self._nombre_display(champion)
        if self.user_settings.get("mostrar_dificultad", True):
            return f"{nombre} {self._dificultad_stars(champion)}"
        return nombre

    def _actualizar_analisis_pro(self, aliados, enemigos):
        """Genera analisis macro avanzado: win conditions, objetivos, sinergias, itemizacion."""
        self.pnl_pro.setVisible(True)
        lines = []

        ad_al, ap_al, tanks_al = analizar_composicion(aliados)
        ad_en, ap_en, tanks_en = analizar_composicion(enemigos)

        poke_al = sum(1 for a in aliados if obtener_tag(a).get("damage_profile") == "poke")
        engage_al = sum(1 for a in aliados if obtener_tag(a).get("sub_class") in ("Vanguard","Catcher"))
        split_al = sum(1 for a in aliados if obtener_tag(a).get("sub_class")=="Skirmisher" and obtener_tag(a).get("scaling") in ("late","hyper"))
        engage_en = sum(1 for e in enemigos if obtener_tag(e).get("sub_class") in ("Vanguard","Catcher"))
        poke_en = sum(1 for e in enemigos if obtener_tag(e).get("damage_profile")=="poke")
        split_en = sum(1 for e in enemigos if obtener_tag(e).get("sub_class")=="Skirmisher" and obtener_tag(e).get("scaling") in ("late","hyper"))

        # Tipo de composicion
        if poke_al >= 2 and engage_al <= 1: comp_al = "Poke/Siege"
        elif engage_al >= 2 and tanks_al >= 2: comp_al = "Engage/Wombo"
        elif split_al >= 1: comp_al = "Split Push"
        elif tanks_al >= 3: comp_al = "Front-to-Back"
        else: comp_al = "Pick/Skirmish"

        if poke_en >= 2 and engage_en <= 1: comp_en = "Poke/Siege"
        elif engage_en >= 2 and tanks_en >= 2: comp_en = "Engage/Wombo"
        elif split_en >= 1: comp_en = "Split Push"
        elif tanks_en >= 3: comp_en = "Front-to-Back"
        else: comp_en = "Pick/Skirmish"

        lines.append("🎯 TU COMP: {}  |  ENEMIGO: {}".format(comp_al, comp_en))

        # Win condition
        if comp_al == "Poke/Siege" and comp_en in ("Engage/Wombo","Front-to-Back"):
            lines.append("🏆 WIN COND: Pokea antes de la pelea. No dejes que engageen. Asedia torres con rango.")
        elif comp_al == "Engage/Wombo" and comp_en in ("Poke/Siege","Pick/Skirmish"):
            lines.append("🏆 WIN COND: Busca el engage 5v5. Ellos colapsan contra all-in coordinado.")
        elif comp_al == "Split Push" and comp_en in ("Engage/Wombo","Front-to-Back"):
            lines.append("🏆 WIN COND: Evita 5v5. Presion lateral con el split pusher. Rotaciones rapidas.")
        elif comp_al == "Front-to-Back" and comp_en == "Pick/Skirmish":
            lines.append("🏆 WIN COND: Agrupaos y proteged al carry. No os separeis, os cazan.")
        else:
            esc_al = sum(1 for a in aliados if obtener_tag(a).get("scaling") in ("late","hyper"))
            esc_en = sum(1 for e in enemigos if obtener_tag(e).get("scaling") in ("late","hyper"))
            if esc_al > esc_en: lines.append("🏆 WIN COND: Escalan mejor. Juega seguro early, ganas a partir de 25 min.")
            elif esc_en > esc_al: lines.append("🏆 WIN COND: Acaba rápido. Ellos escalan mejor. Ventaja temprana y cierra.")
            elif tanks_al > tanks_en: lines.append("🏆 WIN COND: Su frontlane gana. Force objetivos, ellos no pueden contestar.")
            else: lines.append("🏆 WIN COND: Vision + picks. Controla la jungla enemiga y caza rotaciones.")

        # Prioridad de objetivos
        lines.append("\n📋 PRIORIDAD DE OBJETIVOS:")
        if tanks_al >= 3 or engage_al >= 2: lines.append("   🐉 Dragones - su frontlane domina el río")
        if split_al >= 1: lines.append("   🦀 Heraldo > Primeras 2 torres - libera al split pusher")
        if poke_al >= 2: lines.append("   🏰 Torres > Dragones - su rango asedia mejor")
        escalado_al = sum(1 for a in aliados if obtener_tag(a).get("scaling") in ("late","hyper"))
        if escalado_al >= 3: lines.append("   🛡️ Farm + Escalar > Objetivos tempranos")

        # Itemizacion counter
        lines.append("\n🛒 ITEMIZACION CLAVE:")
        ap_en_val = sum(1 for e in enemigos if obtener_dano(e) in ("AP","HYBRID"))
        ad_en_val = sum(1 for e in enemigos if obtener_dano(e) == "AD")
        cc_en = sum(obtener_nivel_cc(e) for e in enemigos)
        tanks_en_val = sum(1 for e in enemigos if es_tanque(e))
        cur = sum(1 for e in enemigos if e in {"Aatrox","Vladimir","Soraka","Swain","Sylas","Warwick","Briar","Fiora","Darius","Illaoi","DrMundo","Olaf"})
        if ap_en_val >= 3: lines.append("   🧪 Fuerza Naturaleza / Rostro Espiritual (mucha AP enemiga)")
        if ad_en_val >= 3: lines.append("   🛡️ Coraza de Espinas / Randuin (mucho AD)")
        if tanks_en_val >= 3: lines.append("   🗡️ Hoja del Rey / Lord Dominik (penetracion vs tanques)")
        if cc_en >= 12: lines.append("   ⛓️ Botas de Mercurio / Fajin (CC masivo)")
        if cur >= 2: lines.append("   🔥 Morellonomicón / Ejecutor (curaciones enemigas)")

        # Sinergias
        lines.append("\nâš¡ SINERGIAS CLAVE:")
        if "Yasuo" in aliados:
            kn = [a for a in aliados if obtener_nivel_cc(a) >= 3 and obtener_tag(a).get("sub_class") in ("Vanguard","Catcher")]
            if kn: lines.append("   🌪️ Yasuo + {} = combo R garantizada".format(kn[0]))
        if "Orianna" in aliados:
            eng = [a for a in aliados if obtener_tag(a).get("sub_class") == "Vanguard"]
            if eng: lines.append("   âš½ Orianna + {} = wombo combo R".format(eng[0]))
        if "Kalista" in aliados:
            supp = [a for a in aliados if es_soporte(a)]
            if supp: lines.append("   🤝 Kalista + {} = engage/doble knockup".format(supp[0]))

        self.lbl_pro.setText("\n".join(lines))

