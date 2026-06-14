"""Pestania MI PERFIL + coaching de datos Riot, cache de temporada,
historial y fatiga. Extraida de app.py sin cambios."""

from ui.contexto import *


class PerfilTabMixin:
    def armar_tab_perfil(self):
        layout = QVBoxLayout(self.tab_perfil)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # Boton de refresco manual
        refresh_row = QHBoxLayout()
        refresh_row.addStretch()
        self.btn_refrescar = QPushButton("🔄 Actualizar Perfil")
        self.btn_refrescar.setStyleSheet(f"""
            QPushButton {{ background-color: {BG_CARD}; color: {ACCENT_TEAL};
                           border: 1px solid {ACCENT_TEAL}; border-radius: 4px;
                           font-size: 11px; padding: 4px 12px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #1a3a3a; }}
            QPushButton:disabled {{ color: {BG_BORDER}; border-color: {BG_CARD_HOVER}; }}
        """)
        self.btn_refrescar.clicked.connect(self.refrescar_perfil)
        refresh_row.addWidget(self.btn_refrescar)
        layout.addLayout(refresh_row)

        self.pnl_perfil = QWidget()
        l_pnl = QHBoxLayout(self.pnl_perfil)
        l_pnl.setContentsMargins(0, 0, 0, 0)
        l_pnl.setSpacing(8)
        l_pnl.setAlignment(Qt.AlignTop)
        
        # ===== COLUMNA IZQUIERDA =====
        self.col_id = QVBoxLayout()
        self.col_id.setAlignment(Qt.AlignTop)
        self.col_id.setSpacing(6)
        
        # ===== TARJETA COMPACTA: IDENTIDAD + LIGAS (FUSIONADA) =====
        self.pnl_identity_card = QFrame()
        self.pnl_identity_card.setObjectName("Panel")
        id_card_layout = QHBoxLayout(self.pnl_identity_card)
        id_card_layout.setContentsMargins(10, 10, 10, 10)
        id_card_layout.setSpacing(10)
        
        # Icono perfil (izquierda, 60x60)
        self.lbl_prof_icon = QLabel()
        self.lbl_prof_icon.setFixedSize(60, 60)
        self.lbl_prof_icon.setAlignment(Qt.AlignCenter)
        id_card_layout.addWidget(self.lbl_prof_icon)
        
        # Centro: Nombre + Nivel
        center_info = QVBoxLayout()
        center_info.setSpacing(2)
        self.lbl_sum_name = QLabel("Esperando al Cliente...")
        self.lbl_sum_name.setStyleSheet(f"color: {BORDER_ACCENT}; font-size: 16px; font-weight: bold;")
        center_info.addWidget(self.lbl_sum_name)
        self.lbl_sum_lvl = QLabel("Nivel: --")
        self.lbl_sum_lvl.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        center_info.addWidget(self.lbl_sum_lvl)
        id_card_layout.addLayout(center_info, 1)
        
        # Derecha: SoloQ + Flex (compacto, una linea cada uno)
        ranks_info = QVBoxLayout()
        ranks_info.setSpacing(2)
        self.lbl_soloq_tier = QLabel("⚔️ --")
        self.lbl_soloq_tier.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 11px;")
        ranks_info.addWidget(self.lbl_soloq_tier)
        self.lbl_soloq_stats = QLabel("")
        self.lbl_soloq_stats.setStyleSheet("color: #8fa3b8; font-size: 9px;")
        ranks_info.addWidget(self.lbl_soloq_stats)
        self.lbl_flex_tier = QLabel("🛡️ --")
        self.lbl_flex_tier.setStyleSheet(f"color: {TEXT_GOLD}; font-weight: bold; font-size: 11px;")
        ranks_info.addWidget(self.lbl_flex_tier)
        self.lbl_flex_stats = QLabel("")
        self.lbl_flex_stats.setStyleSheet("color: #8fa3b8; font-size: 9px;")
        ranks_info.addWidget(self.lbl_flex_stats)
        id_card_layout.addLayout(ranks_info)
        
        self.col_id.addWidget(self.pnl_identity_card)
        
        # ===== ESTADÍSTICAS DE LA TEMPORADA (columna izquierda) =====
        self.pnl_season, self.l_season = self.crear_panel("📊 ESTADÍSTICAS DE LA TEMPORADA")
        self.lbl_season_stats = QLabel("")
        self.lbl_season_stats.setVisible(False)
        self.l_season.addWidget(self.lbl_season_stats)
        self.tb_season_champs = QTableWidget()
        self.tb_season_champs.setColumnCount(4)
        self.tb_season_champs.setHorizontalHeaderLabels(["Campeón", "Partidas", "WR", "KDA"])
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tb_season_champs.setColumnWidth(1, 62)
        self.tb_season_champs.setColumnWidth(2, 50)
        self.tb_season_champs.setColumnWidth(3, 70)
        self.tb_season_champs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_season_champs.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_season_champs.setShowGrid(False)
        self.tb_season_champs.setAlternatingRowColors(False)
        self.tb_season_champs.verticalHeader().setVisible(False)
        self.tb_season_champs.horizontalHeader().setVisible(True)
        self.tb_season_champs.verticalHeader().setDefaultSectionSize(52)
        self.tb_season_champs.setIconSize(QSize(28, 28))
        self.tb_season_champs.setMaximumHeight(340)
        self.tb_season_champs.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.tb_season_champs.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tb_season_champs.setStyleSheet("""
            QTableWidget { border: none; background-color: transparent; }
            QHeaderView::section { background-color: #1b1620; border: none; border-bottom: 1px solid #c89b3c; color: #c89b3c; font-weight: bold; padding: 4px; font-size: 10px; }
            QTableWidget::item { border-bottom: 1px solid #1f1a26; padding: 0px; }
        """)
        self.tb_season_champs.verticalScrollBar().valueChanged.connect(self._on_scroll_season)
        self.l_season.addWidget(self.tb_season_champs)
        self.col_id.addWidget(self.pnl_season)
        
        # ===== PANEL DE FATIGA (columna izquierda, abajo) =====
        self.pnl_fatiga, self.l_fatiga = self.crear_panel("🧠 ESTADO MENTAL")
        self.l_fatiga.setAlignment(Qt.AlignTop)
        self.l_fatiga.setSpacing(6)
        self.l_fatiga.setContentsMargins(12, 12, 12, 12)
        
        fr_estado = QFrame()
        fr_estado.setObjectName("InnerPanel")
        l_estado = QHBoxLayout(fr_estado)
        l_estado.setContentsMargins(8, 6, 8, 6)
        l_estado.setSpacing(10)
        l_estado.setAlignment(Qt.AlignLeft)
        
        self.lbl_fatiga_icono = QLabel("⏳")
        self.lbl_fatiga_icono.setFixedSize(46, 46)
        self.lbl_fatiga_icono.setAlignment(Qt.AlignCenter)
        self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
        l_estado.addWidget(self.lbl_fatiga_icono)
        
        fr_texto_estado = QFrame()
        l_texto_estado = QVBoxLayout(fr_texto_estado)
        l_texto_estado.setContentsMargins(0, 0, 0, 0)
        l_texto_estado.setSpacing(2)
        
        self.lbl_fatiga_estado = QLabel("ANALIZANDO...")
        self.lbl_fatiga_estado.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_fatiga_estado.setStyleSheet("color: #8fa3b8; font-size: 16px; font-weight: bold;")
        l_texto_estado.addWidget(self.lbl_fatiga_estado)
        
        self.lbl_fatiga_barra = QFrame()
        self.lbl_fatiga_barra.setFixedHeight(4)
        self.lbl_fatiga_barra.setStyleSheet("background-color: #2f2535; border-radius: 2px;")
        l_texto_estado.addWidget(self.lbl_fatiga_barra)
        
        l_estado.addWidget(fr_texto_estado, 1)
        self.l_fatiga.addWidget(fr_estado)
        
        self.lbl_fatiga_consejo = QLabel("Esperando datos del cliente.")
        self.lbl_fatiga_consejo.setAlignment(Qt.AlignLeft)
        self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
        self.lbl_fatiga_consejo.setWordWrap(True)
        self.l_fatiga.addWidget(self.lbl_fatiga_consejo)
        
        self.col_id.addWidget(self.pnl_fatiga)

        # ── PANEL LP HISTORY ──
        self.pnl_lp, self.l_lp = self.crear_panel("📈 EVOLUCIÓN DE LP (30 DÍAS)")
        lp_header = QHBoxLayout()
        self.cb_lp_queue = QComboBox()
        self.cb_lp_queue.addItems(["Solo/Dúo", "Flex"])
        self.cb_lp_queue.setFixedWidth(90)
        self.cb_lp_queue.currentIndexChanged.connect(self._actualizar_grafica_lp)
        lp_header.addWidget(QLabel("Cola:"))
        lp_header.addWidget(self.cb_lp_queue)
        lp_header.addStretch()
        self.l_lp.addLayout(lp_header)
        self.lp_graph = LPGraphWidget()
        self.lp_graph.setMinimumHeight(130)
        self.l_lp.addWidget(self.lp_graph)
        self.col_id.addWidget(self.pnl_lp)

        l_pnl.addLayout(self.col_id, 35)
        
        # ===== COLUMNA DERECHA: ESTADÍSTICAS + PERFIL + HISTORIAL =====
        self.col_hist = QVBoxLayout()
        self.col_hist.setAlignment(Qt.AlignTop)
        self.col_hist.setSpacing(6)
        
        # 1. Tarjetas de estadísticas (KDA / WR / Más jugado / Mejor WR)
        self.fr_stats_cards = QHBoxLayout()
        self.fr_stats_cards.setSpacing(6)
        
        self.card_wr, self.lbl_card_wr_val = self._crear_stat_card("📊 WINRATE", "--%", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_wr, 1)
        
        self.card_kda, self.lbl_card_kda_val = self._crear_stat_card("⚔️ KDA", "--", ACCENT_TEAL)
        self.fr_stats_cards.addWidget(self.card_kda, 1)
        
        self.card_most, self.lbl_card_most_val = self._crear_stat_card("🔥 +JUGADO", "--", BORDER_ACCENT)
        self.fr_stats_cards.addWidget(self.card_most, 1)
        
        self.card_best, self.lbl_card_best_val = self._crear_stat_card("🏆 MEJOR WR", "--", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_best, 1)
        
        self.col_hist.addLayout(self.fr_stats_cards)
        
        # WR POR LÍNEA
        self.pnl_wr_rol, self.l_wr_rol = self.crear_panel("WINRATE POR LÍNEA")
        self.fr_wr_rol = QHBoxLayout()
        self.fr_wr_rol.setSpacing(4)
        self.labels_wr_rol = {}
        for rol in UI_ROLES:
            lbl = QLabel(f"{rol}\n--")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 10px; color: #8fa3b8; padding: 4px;")
            self.fr_wr_rol.addWidget(lbl)
            self.labels_wr_rol[rol] = lbl
        self.l_wr_rol.addLayout(self.fr_wr_rol)
        self.col_hist.addWidget(self.pnl_wr_rol)
        
        # Filtro por campeón, modo y temporada
        self.fr_filtro = QHBoxLayout()
        lbl_filtro = QLabel("Filtrar:")
        lbl_filtro.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        self.fr_filtro.addWidget(lbl_filtro)
        self.cb_filtro_champ = QComboBox()
        self.cb_filtro_champ.setMinimumWidth(140)
        self.cb_filtro_champ.addItem("Todos los campeones")
        self.cb_filtro_champ.currentTextChanged.connect(self.filtrar_historial)
        self.fr_filtro.addWidget(self.cb_filtro_champ)
        self.cb_filtro_modo = QComboBox()
        self.cb_filtro_modo.setMinimumWidth(100)
        self.cb_filtro_modo.addItem("Todos los modos")
        self.cb_filtro_modo.currentTextChanged.connect(self.filtrar_historial)
        self.fr_filtro.addWidget(self.cb_filtro_modo)
        self.cb_filtro_season = QComboBox()
        self.cb_filtro_season.setMinimumWidth(110)
        self.cb_filtro_season.addItem("Todas las temporadas")
        self.cb_filtro_season.currentTextChanged.connect(self.filtrar_historial)
        self.fr_filtro.addWidget(self.cb_filtro_season)
        self.fr_filtro.addStretch()
        self.col_hist.addLayout(self.fr_filtro)
        
        # 3. HISTORIAL DE PARTIDAS (stretch masivo)
        lbl_h = QLabel("HISTORIAL DE PARTIDAS")
        lbl_h.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 13px; margin-top: 4px;")
        self.col_hist.addWidget(lbl_h)
        
        # Stack: historial table + overlay vacío
        self.historial_stack = QFrame()
        hs_layout = QStackedLayout(self.historial_stack)
        hs_layout.setStackingMode(QStackedLayout.StackAll)
        
        self.tb_historial = QTableWidget()
        self.tb_historial.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.tb_historial.setColumnCount(7)
        self.tb_historial.setHorizontalHeaderLabels(["Campeón", "Resultado", "K/D/A", "CS", "Dur.", "Modo", "Fecha"])
        self.tb_historial.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tb_historial.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tb_historial.horizontalHeader().setMinimumSectionSize(80)
        self.tb_historial.setColumnWidth(1, 90)
        self.tb_historial.setColumnWidth(2, 70)
        self.tb_historial.setColumnWidth(3, 50)
        self.tb_historial.setColumnWidth(4, 60)
        self.tb_historial.setColumnWidth(5, 70)
        self.tb_historial.setColumnWidth(6, 90)
        self.tb_historial.horizontalHeader().setStretchLastSection(False)
        self.tb_historial.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_historial.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_historial.verticalHeader().setDefaultSectionSize(28)
        self.tb_historial.setIconSize(QSize(20, 20))
        self.tb_historial.verticalHeader().setVisible(False)
        self.tb_historial.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tb_historial.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        hs_layout.addWidget(self.tb_historial)
        
        self.lbl_historial_vacio = QLabel(
            '<div style="text-align: center; padding: 40px;">'
            '<p style="font-size: 36px; margin: 0;">📜</p>'
            '<p style="font-size: 14px; color: #7a6f68; margin: 8px 0 0 0;">Esperando datos del cliente...</p>'
            '<p style="font-size: 11px; color: #3a2d3a; margin: 4px 0 0 0;">Conecta al cliente de LoL para ver tu historial de partidas.</p>'
            '</div>'
        )
        self.lbl_historial_vacio.setTextFormat(Qt.RichText)
        self.lbl_historial_vacio.setAlignment(Qt.AlignCenter)
        self.lbl_historial_vacio.setStyleSheet("background: transparent;")
        self.lbl_historial_vacio.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        hs_layout.addWidget(self.lbl_historial_vacio)
        
        self.col_hist.addWidget(self.historial_stack, 1)

        # Logros row
        self.lbl_logros_title = QLabel("LOGROS")
        self.lbl_logros_title.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 13px; margin-top: 8px;")
        self.col_hist.addWidget(self.lbl_logros_title)
        self.fr_logros = QHBoxLayout()
        self.fr_logros.setSpacing(4)
        self.lbl_logros_text = QLabel("Conecta al cliente para ver tus logros...")
        self.lbl_logros_text.setStyleSheet(f"color: {TEXT_SUBTLE}; font-size: 11px;")
        self.lbl_logros_text.setWordWrap(True)
        self.fr_logros.addWidget(self.lbl_logros_text)
        self.fr_logros.addStretch()
        self.col_hist.addLayout(self.fr_logros)

        self.tb_historial.verticalScrollBar().valueChanged.connect(self._on_scroll_historial)
        
        l_pnl.addLayout(self.col_hist, 65)
        layout.addWidget(self.pnl_perfil)

    def _riot_resolve_puuid(self, game_name: str, tag_line: str):
        """Obtiene el PUUID nuevo (match v5) desde el riot id (gameName#tagLine).
        Si no hay tag_line, no hace fallback falso — devuelve None."""
        api_key, region, routing = self._riot_get_config()
        if not api_key or not game_name:
            return None
        if not tag_line:
            return None
        tag = tag_line
        try:
            url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag}"
            res = requests.get(url, headers={"X-Riot-Token": api_key}, timeout=10)
            if res.status_code == 200:
                puuid = res.json().get("puuid")
                print(f"[RiotAPI] PUUID resuelto: {game_name}#{tag} -> {puuid}")
                return puuid
            else:
                print(f"[RiotAPI] HTTP {res.status_code} resolviendo PUUID para {game_name}#{tag}")
        except Exception as e:
            print(f"[RiotAPI] Error resolviendo PUUID: {e}")
        return None

    def _riot_get_config(self):
        """Obtiene api_key, region y routing para llamadas a Riot API."""
        api_key = self.lcu.obtener_api_key_local()
        if not api_key:
            return None, None, None
        region = (self.lcu.obtener_region_local() or "la2").lower()
        routing = "americas" if region in ("la1","la2","na1","br1","oc1","la","lan","las","na","br") else \
                  "europe"   if region in ("euw1","eun1","tr1","ru","euw","eune","tr")             else \
                  "sea"      if region in ("ph2","sg2","th2","tw2","vn2")                           else "asia"
        print(f"[RiotAPI] Region={region}, Routing={routing}")
        return api_key, region, routing

    def _riot_fetch_match_ids(self, puuid: str):
        """Pagina la API de Riot para obtener TODOS los match IDs de la temporada actual.
        Usa count=100, start desde 0 incrementando de 100 en 100, con filtro startTime.
        Rompe cuando la API devuelve []."""
        api_key, region, routing = self._riot_get_config()
        if not api_key:
            return []
        from datetime import timezone as tz
        ahora = datetime.now(tz.utc)
        start_time = int(datetime(ahora.year, 1, 1, tzinfo=tz.utc).timestamp())
        all_ids = []
        offset = 0
        base_url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        hdrs = {"X-Riot-Token": api_key}
        print(f"[RiotAPI] Paginando IDs (region={region}, routing={routing}, startTime={start_time})")
        while True:
            url = f"{base_url}?start={offset}&count=100&startTime={start_time}"
            try:
                res = requests.get(url, headers=hdrs, timeout=15)
                if res.status_code == 429:
                    retry_after = res.headers.get("Retry-After", "10")
                    print(f"[RiotAPI] Rate limit, esperando {retry_after}s...")
                    time.sleep(int(retry_after))
                    continue
                if res.status_code == 400:
                    body = res.text[:300]
                    print(f"[RiotAPI] HTTP 400: {body}")
                    if "startTime" in body.lower() or "parameter" in body.lower():
                        url = f"{base_url}?start={offset}&count=100"
                        print(f"[RiotAPI] Reintentando sin startTime...")
                        res = requests.get(url, headers=hdrs, timeout=15)
                    else:
                        break
                if res.status_code != 200:
                    print(f"[RiotAPI] HTTP {res.status_code} en listado (start={offset})")
                    break
                batch = res.json()
                if not batch:
                    break
                all_ids.extend(batch)
                if len(batch) < 100:
                    break
                offset += 100
            except Exception as e:
                print(f"[RiotAPI] Error obteniendo IDs (start={offset}): {e}")
                break
        print(f"[RiotAPI] {len(all_ids)} IDs de partida obtenidos")
        return all_ids

    def _riot_convert_match(self, raw: dict, my_puuid: str = ""):
        """Convierte una partida de formato Riot API v5 al formato interno de la app.
        Filtra SOLO al participante que coincide con my_puuid y lo pone en [0]."""
        info = raw.get("info", {})
        my_stats = None
        for p in info.get("participants", []):
            if my_puuid and p.get("puuid", "") != my_puuid:
                continue
            my_stats = {
                "championId": int(p.get("championId", 0)),
                "championName": p.get("championName", ""),
                "teamPosition": p.get("teamPosition", ""),
                "puuid": p.get("puuid", ""),
                "stats": {
                    "win": p.get("win", False),
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "assists": p.get("assists", 0),
                    "totalMinionsKilled": p.get("totalMinionsKilled", 0),
                    "neutralMinionsKilled": p.get("neutralMinionsKilled", 0),
                    "totalDamageDealtToChampions": p.get("totalDamageDealtToChampions", 0),
                    "totalDamageTaken": p.get("totalDamageTaken", 0),
                    "goldEarned": p.get("goldEarned", 0),
                    "visionScore": p.get("visionScore", 0),
                    "wardsPlaced": p.get("wardsPlaced", 0),
                    "visionWardsBoughtInGame": p.get("visionWardsBoughtInGame", 0),
                    "pentaKills": p.get("pentaKills", 0),
                    "tripleKills": p.get("tripleKills", 0),
                    "turretKills": p.get("turretKills", 0),
                    "dragonKills": p.get("dragonKills", 0),
                    "baronKills": p.get("baronKills", 0),
                    "timeCCingOthers": p.get("timeCCingOthers", 0),
                    "firstBloodKill": p.get("firstBloodKill", False),
                }
            }
            break
        if not my_stats:
            return None
        game_creation_ms = info.get("gameCreation", 0)
        game_creation_ts = game_creation_ms / 1000 if game_creation_ms else 0
        return {
            "gameId": raw.get("metadata", {}).get("matchId", ""),
            "gameCreation": game_creation_ts,
            "gameCreationDate": datetime.fromtimestamp(game_creation_ts).strftime("%b %d, %Y %I:%M:%S %p") if game_creation_ts else "",
            "gameDuration": info.get("gameDuration", 0),
            "gameMode": info.get("gameMode", "CLASSIC"),
            "participants": [my_stats],
        }

    def _riot_fetch_one_match(self, match_id: str, my_puuid: str = ""):
        """Descarga UNA partida de Riot API. Con backoff exponencial + Retry-After."""
        api_key, region, routing = self._riot_get_config()
        if not api_key:
            return None
        hdrs = {"X-Riot-Token": api_key}
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        for intento in range(4):
            try:
                res = requests.get(url, headers=hdrs, timeout=10)
                if res.status_code == 429:
                    retry = int(res.headers.get("Retry-After", 2 ** intento))
                    time.sleep(min(retry, 15))
                    continue
                if res.status_code == 200:
                    return self._riot_convert_match(res.json(), my_puuid)
                if res.status_code == 404:
                    return None
            except Exception:
                time.sleep(2 ** intento)
        return None

    def _riot_fetch_matches(self, match_ids: list, my_puuid: str = "", max_matches: int = None):
        """Descarga partidas de Riot API en PARALELO (6 workers).
        my_puuid filtra SOLO al jugador correcto. max_matches=None = todas."""
        api_key, region, routing = self._riot_get_config()
        if not api_key:
            return []
        total_ids = len(match_ids)
        if max_matches:
            match_ids = match_ids[:max_matches]
        if not match_ids:
            return []
        print(f"[RiotAPI] Descargando {len(match_ids)}/{total_ids} partidas (6 workers)...")
        games = []
        downloaded = 0
        errores = 0
        t_start = time.time()
        last_emit = 0
        BATCH_EMIT = 30
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(self._riot_fetch_one_match, mid, my_puuid): mid for mid in match_ids}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        games.append(result)
                        downloaded += 1
                    else:
                        errores += 1
                except Exception:
                    errores += 1
                total = downloaded + errores
                if downloaded - last_emit >= BATCH_EMIT:
                    batch = games[last_emit:downloaded]
                    if batch:
                        self.season_partial.emit(list(batch))
                    last_emit = downloaded
                    elapsed = time.time() - t_start
                    print(f"[RiotAPI] {total}/{len(match_ids)} ({(total/len(match_ids)*100):.0f}%) +{len(batch)} en {elapsed:.0f}s")
        if last_emit < downloaded:
            batch = games[last_emit:]
            if batch:
                self.season_partial.emit(list(batch))
        elapsed = time.time() - t_start
        pct = len(match_ids) / max(1, elapsed)
        print(f"[RiotAPI] {downloaded} OK, {errores} err en {elapsed:.0f}s ({pct:.0f}/s)")
        return games

    def _load_season_cache(self, puuid: str):
        return cargar_season_cache(puuid)

    def _save_season_cache(self, puuid: str, games: list):
        guardar_season_cache(puuid, games)

    def _riot_season_background(self, puuid: str, all_games: list, game_name: str, tag_line: str):
        """Ejecutado en hilo separado: descarga partidas de Riot SIN bloquear la UI.
        Usa streaming via season_partial para mostrar datos mientras llegan."""
        try:
            # Intentar cache primero
            cached = self._load_season_cache(puuid)
            if cached:
                existing_gids = {self._gid_or_fallback(g) for g in all_games}
                nuevos_cache = [g for g in cached if self._gid_or_fallback(g) and self._gid_or_fallback(g) not in existing_gids]
                if nuevos_cache:
                    self.season_partial.emit(nuevos_cache)
                    print(f"[RiotAPI] Cache: +{len(nuevos_cache)} partidas streaming")
                return

            # Resolver PUUID nuevo
            riot_puuid = puuid
            new_puuid = self._riot_resolve_puuid(game_name, tag_line)
            if new_puuid and new_puuid != puuid:
                riot_puuid = new_puuid

            # Descargar IDs + partidas (my_puuid = el usado para obtener IDs)
            riot_ids = self._riot_fetch_match_ids(riot_puuid)
            if riot_ids:
                riot_games = self._riot_fetch_matches(riot_ids, my_puuid=riot_puuid)
                # Guardar cache (usar puuid original del LCU, no el resuelto)
                self._save_season_cache(puuid, riot_games)
        except Exception as e:
            print(f"[RiotAPI] Error en background: {e}")

    @staticmethod
    def _gid_or_fallback(g):
        gid = str(g.get("gameId", ""))
        if not gid:
            gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
            return gid
        if '_' in gid:
            gid = gid.rsplit('_', 1)[-1]
        return gid

    # ================= CARGA DE PERFIL (HILO SEGUNDARIO) =================
    def _fetch_perfil(self):
        """Se ejecuta en hilo secundario. Recoge TODOS los datos de LCU sin tocar UI.
        Incluye reintentos con backoff porque la API de LCU tarda unos segundos en
        estar disponible tras abrir el cliente."""
        data = {"ok": False}
        try:
            # ── Fase 1: Perfil base (con reintentos, la API puede no estar lista) ──
            perfil = None
            for intento in range(5):
                perfil = self.lcu.obtener_perfil()
                if perfil and (perfil.get("displayName") or perfil.get("gameName") or perfil.get("summonerName")):
                    break
                print(f"[_fetch_perfil] Intento {intento+1}/5: perfil no disponible, esperando...")
                perfil = None
                time.sleep(2)
            
            if not perfil:
                print("[_fetch_perfil] No se pudo obtener el perfil tras 5 intentos.")
                self._cargando_perfil = False
                self.perfil_listo.emit(data)
                return
            
            data["perfil"] = perfil
            perfil_ok = True
            
            # ── Fase 2: Ligas (con reintentos — la API de ranked tarda en arrancar) ──
            ligas = None
            for intento_l in range(4):
                try:
                    ligas = self.lcu.obtener_ligas()
                    if ligas and ligas.get("queues"):
                        break
                except Exception as e:
                    print(f"[_fetch_perfil] Error ligas intento {intento_l+1}: {e}")
                if intento_l < 3:
                    time.sleep(1.5)
            if not ligas or not ligas.get("queues"):
                print("[_fetch_perfil] No se pudieron obtener ligas (no fatal).")
            data["ligas"] = ligas
            
            # ── Fase 3: Maestrías (no fatal si falla) ──
            maestrias = []
            try:
                maestrias = self.lcu.obtener_maestrias()
            except Exception as e:
                print(f"[_fetch_perfil] Error obteniendo maestrías (no fatal): {e}")
            data["maestrias"] = maestrias[:3] if maestrias else []
            
            # ── Fase 4: Historial (con reintentos, no fatal si falla) ──
            puuid = perfil.get("puuid")
            self._season_puuid = puuid
            historial = None
            if puuid:
                for intento in range(3):
                    try:
                        historial = self.lcu.obtener_historial_extendido(puuid=puuid, inicio=0, cantidad=100)
                        if historial:
                            break
                    except Exception as e:
                        print(f"[_fetch_perfil] Error historial intento {intento+1}: {e}")
                    if intento < 2:
                        time.sleep(2)
                if not historial:
                    print("[_fetch_perfil] No se pudo obtener historial (no fatal).")
            data["historial"] = historial
            
            # ── Fase 5: Season stats (paginación completa para toda la temporada) ──
            all_games = list(historial) if historial else []

            def _gid(g):
                gid = str(g.get("gameId", "") or "")
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                    return gid
                if '_' in gid:
                    gid = gid.rsplit('_', 1)[-1]
                return gid

            if all_games and self.lcu and self.lcu.port:
                try:
                    existing_ids = {_gid(g) for g in all_games}
                    for offset in range(100, 2000, 100):
                        batch = self.lcu.obtener_historial_extendido(puuid=puuid, inicio=offset, cantidad=100)
                        if not batch:
                            break
                        new_batch = [g for g in batch if _gid(g) and _gid(g) not in existing_ids]
                        if not new_batch:
                            break
                        for g in new_batch:
                            existing_ids.add(_gid(g))
                        all_games.extend(new_batch)
                        if len(batch) < 100:
                            break
                    print(f"[_fetch_perfil] Season stats: {len(all_games)} partidas totales (temporada completa)")
                except Exception as e:
                    print(f"[_fetch_perfil] Error paginando season stats (no fatal): {e}")
            data["all_games_season"] = all_games

            # Emitir YA los datos del LCU — no esperar a Riot API
            data["ok"] = perfil_ok
            self.perfil_listo.emit(data)

            # ── Fase 6: Riot API (background, no bloquea la UI) ──
            if puuid and len(all_games) < 500:
                game_name = perfil.get("gameName") or perfil.get("displayName", "").split("#")[0]
                tag_line = perfil.get("tagLine") or ""
                threading.Thread(
                    target=self._riot_season_background,
                    args=(puuid, all_games, game_name, tag_line),
                    daemon=True
                ).start()

        except Exception as e:
            print(f"[_fetch_perfil] Error crítico: {e}")
            data["ok"] = False
            self.perfil_listo.emit(data)

    def refrescar_perfil(self):
        """Fuerza una recarga completa del perfil desde LCU. Util tanto desde el
        boton manual como desde el auto-refresh al terminar una partida."""
        self.perfil_cargado = False
        if not self._cargando_perfil:
            self._cargando_perfil = True
            threading.Thread(target=self._fetch_perfil, daemon=True).start()

    def _on_perfil_listo(self, data):
        """Se ejecuta en el hilo principal. Actualiza la UI con los datos ya recogidos."""
        self._cargando_perfil = False
        
        if not data.get("ok") or not data.get("perfil"):
            print(f"[_on_perfil_listo] Datos insuficientes (ok={data.get('ok')}), se reintentará.")
            return
        
        try:
            perfil = data["perfil"]
            self.perfil_cargado = True
            
            # --- Nombre y nivel ---
            display_name = perfil.get("displayName") or perfil.get("gameName") or perfil.get("summonerName") or perfil.get("name") or "Invocador"
            tagline = perfil.get("tagLine")
            if tagline and tagline not in display_name:
                display_name = f"{display_name}#{tagline}"
            self.lbl_sum_name.setText(display_name)
            self.lbl_sum_lvl.setText(f"Nivel: {perfil.get('summonerLevel', '--')}")
            
            # --- Icono de perfil (tamano compacto para tarjeta fusionada) ---
            icon_id = perfil.get("profileIconId")
            ruta_icon = self.descargar_imagen(icon_id, "profile")
            if ruta_icon:
                self.lbl_prof_icon.setPixmap(QPixmap(ruta_icon).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            # --- Ligas ---
            ligas = data.get("ligas")
            queues = []
            if isinstance(ligas, dict) and "queues" in ligas:
                queues = ligas["queues"]
            elif isinstance(ligas, list):
                queues = ligas

            ranked_solo = None
            ranked_flex = None
            for queue in queues:
                qtype = str(queue.get("queueType") or queue.get("queue") or "").upper()
                tier = str(queue.get("tier") or "").strip()
                division = str(queue.get("division") or queue.get("rankDivision") or queue.get("rank") or "").strip()
                lp = queue.get("leaguePoints") or queue.get("lp") or 0
                wins = queue.get("wins") or queue.get("winCount") or 0
                losses = queue.get("losses") or queue.get("lossCount") or 0
                if not tier:
                    continue
                if "SOLO" in qtype and "FLEX" not in qtype:
                    ranked_solo = {"tier": tier, "division": division, "lp": lp, "wins": wins, "losses": losses}
                elif "FLEX" in qtype:
                    ranked_flex = {"tier": tier, "division": division, "lp": lp, "wins": wins, "losses": losses}
                elif not ranked_solo and ("RANKED" in qtype or "SOLO" in qtype):
                    ranked_solo = {"tier": tier, "division": division, "lp": lp, "wins": wins, "losses": losses}

            print(f"[Perfil] SoloQ: {ranked_solo}, Flex: {ranked_flex}")

            def _format_rank(rank_data, lbl_tier, lbl_stats, prefijo=""):
                """Formato compacto para tarjeta fusionada (1 linea)."""
                if not rank_data or not rank_data.get("tier"):
                    lbl_tier.setText(f"{prefijo}--")
                    lbl_stats.setText("")
                    return
                t = rank_data["tier"]
                d = rank_data.get("division", "").strip()
                lp = rank_data.get("lp", 0)
                w = rank_data.get("wins", 0)
                l = rank_data.get("losses", 0)
                color = self._rank_to_color(t)
                icon = self._rank_icon(t)
                if d not in ("I", "II", "III", "IV"):
                    d = ""
                display_tier = f"{icon} {t.capitalize()} {d}" if d else f"{icon} {t.capitalize()}"
                lbl_tier.setText(display_tier)
                lbl_tier.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")
                total = w + l
                if total > 0:
                    wr = round(w / total * 100)
                    lbl_stats.setText(f"{lp} PL | {total}p | {wr}%")
                else:
                    lbl_stats.setText(f"{lp} PL")

            _format_rank(ranked_solo, self.lbl_soloq_tier, self.lbl_soloq_stats)
            _format_rank(ranked_flex, self.lbl_flex_tier, self.lbl_flex_stats)

            # Registrar LP del día y actualizar gráfica
            try:
                if ranked_solo and ranked_solo.get("tier"):
                    registrar_lp(ranked_solo["tier"], ranked_solo.get("division", ""),
                                 ranked_solo.get("lp", 0), ranked_solo.get("wins", 0),
                                 ranked_solo.get("losses", 0), "RANKED_SOLO_5x5")
                if ranked_flex and ranked_flex.get("tier"):
                    registrar_lp(ranked_flex["tier"], ranked_flex.get("division", ""),
                                 ranked_flex.get("lp", 0), ranked_flex.get("wins", 0),
                                 ranked_flex.get("losses", 0), "RANKED_FLEX_SR")
                self._actualizar_grafica_lp()
            except Exception as _e_lp:
                print(f"[LP] Error registrando: {_e_lp}")

            # --- Historial ---
            historial = data.get("historial")
            if not historial:
                self.lbl_card_wr_val.setText("--%")
                self.lbl_card_kda_val.setText("--")
                self.lbl_card_most_val.setText("--")
                self.lbl_card_best_val.setText("--")
                self.cb_filtro_champ.clear()
                self.cb_filtro_champ.addItem("Todos los campeones")
                self._analizar_fatiga()
                return
            
            # obtener_historial_extendido devuelve lista directa, el viejo devuelve dict
            games = historial if isinstance(historial, list) else historial.get("games", {}).get("games", [])
            # DEDUP: el batching de LCU puede devolver partidas duplicadas entre lotes
            seen = set()
            games_dedup = []
            for g in games:
                gid = self._gid_or_fallback(g)
                if gid and gid not in seen:
                    seen.add(gid)
                    games_dedup.append(g)
            if len(games_dedup) < len(games):
                print(f"[Perfil] DEDUP historial: {len(games)} -> {len(games_dedup)} partidas unicas")
            games = games_dedup
            self.historial_games = games
            self.maestrias = data.get("maestrias", [])
            self.all_games_season = data.get("all_games_season", list(games))
            self._renderizar_historial(games)
        except Exception as e:
            print(f"[_on_perfil_listo] Error renderizando UI: {e}")
            import traceback
            traceback.print_exc()
            # Si falla el renderizado, permitimos reintentar en el siguiente tick
            self.perfil_cargado = False

    def _renderizar_historial(self, games):
        """Renderiza la tabla de historial (reusable para lazy loading)."""
        self.tb_historial.setRowCount(0)

        # DEDUP robusto usando _gid_or_fallback
        seen_gids = set()
        unique = []
        for g in games:
            gid = self._gid_or_fallback(g)
            if gid and gid not in seen_gids:
                seen_gids.add(gid)
                unique.append(g)
        if len(unique) < len(games):
            print(f"[Historial] DEDUP: {len(games)} -> {len(unique)} partidas")
        games = unique

        # Ordenar partidas por fecha (mas reciente primero) usando timestamp
        try:
            games = sorted(games, key=lambda g: (
                self._parse_game_date(g) or datetime(2000,1,1)
            ), reverse=True)
        except Exception:
            pass

        total_k = 0; total_d = 0; total_a = 0; victorias = 0; total_games = 0
        champ_stats = {}
        
        for g in games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
            # LP
            lp_delta = g.get("eloChange") or g.get("playerScoreChange") or stats.get("eloChange")
            if lp_delta is not None:
                lp_str = f"{'+' if lp_delta > 0 else ''}{lp_delta}"
            else:
                lp_str = "--"
            
            # Fecha (usa timestamp gameCreation, fallback a gameCreationDate)
            fecha = self._format_game_date(g)
            
            total_k += k; total_d += d; total_a += a; total_games += 1
            if win: victorias += 1
            
            if champ_name not in champ_stats:
                champ_stats[champ_name] = {"wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0}
            cs_entry = champ_stats[champ_name]
            cs_entry["games"] += 1
            if win: cs_entry["wins"] += 1
            cs_entry["kills"] += k
            cs_entry["deaths"] += d
            cs_entry["assists"] += a
            
            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(champ_name)}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            modo_juego = self._clasificar_modo_juego(g)
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))
            self.tb_historial.setItem(row, 6, QTableWidgetItem(fecha))

        # --- Tarjetas de estadisticas ---
        if total_games > 0:
            wr = round((victorias / total_games) * 100)
            kda = round((total_k + total_a) / max(1, total_d), 2)
            avg_k = round(total_k / total_games, 1)
            avg_d = round(total_d / total_games, 1)
            avg_a = round(total_a / total_games, 1)
            self.lbl_card_wr_val.setText(f"{wr}%")
            self.lbl_card_wr_val.setToolTip(f"{victorias}V / {total_games - victorias}D en {total_games} partidas")
            self.lbl_card_kda_val.setText(f"{kda}")
            self.lbl_card_kda_val.setToolTip(f"Promedio: {avg_k}/{avg_d}/{avg_a} por partida")
            most_played = max(champ_stats, key=lambda c: champ_stats[c]["games"])
            most_g = champ_stats[most_played]["games"]
            self.lbl_card_most_val.setText(most_played[:10])
            self.lbl_card_most_val.setStyleSheet(f"color: {BORDER_ACCENT}; font-size: 16px; font-weight: bold;")
            self.lbl_card_most_val.setToolTip(f"{most_g} partidas con {most_played}")
            best_wr_champs = {c: s for c, s in champ_stats.items() if s["games"] >= 2}
            if best_wr_champs:
                best_champ = max(best_wr_champs, key=lambda c: best_wr_champs[c]["wins"] / best_wr_champs[c]["games"])
                best_wr = round(champ_stats[best_champ]["wins"] / champ_stats[best_champ]["games"] * 100)
                self.lbl_card_best_val.setText(f"{best_champ[:8]} {best_wr}%")
                self.lbl_card_best_val.setStyleSheet(f"color: {GREEN_WR}; font-size: 14px; font-weight: bold;")
                self.lbl_card_best_val.setToolTip(f"{best_wr}% WR con {best_champ} en {champ_stats[best_champ]['games']} partidas")
            else:
                self.lbl_card_best_val.setText("--")
            wr_color = GREEN_WR if wr >= 50 else RED_WR
            self.lbl_card_wr_val.setStyleSheet(f"color: {wr_color}; font-size: 26px; font-weight: bold;")
        else:
            self.lbl_card_wr_val.setText("--%")
            self.lbl_card_kda_val.setText("--")
            self.lbl_card_most_val.setText("--")
            self.lbl_card_best_val.setText("--")

        # --- WR POR LÍNEA (1 sola query para todos los campeones) ---
        conn = obtener_conexion()
        cur = conn.cursor()
        
        # Recoger campeones únicos del historial
        champs_hist = list(set(
            self.procesar_nombre_champ(str(g.get("participants", [{}])[0].get("championId", "0")), "0") or "?"
            for g in self.historial_games
        ))
        
        # 1 sola query: rol más frecuente de cada campeón
        rol_por_champ = {}
        if champs_hist:
            placeholders = ",".join(["%s"] * len(champs_hist))
            cur.execute(f"""
                SELECT champion, team_position FROM (
                    SELECT champion, team_position,
                           ROW_NUMBER() OVER (PARTITION BY champion ORDER BY COUNT(*) DESC) as rn
                    FROM participantes
                    WHERE champion IN ({placeholders})
                    GROUP BY champion, team_position
                ) WHERE rn = 1
            """, champs_hist)
            for row in cur.fetchall():
                rol_por_champ[row["champion"]] = row["team_position"]
        
        rol_stats = {}
        for g in self.historial_games:
            part_info = g.get("participants", [{}])[0]
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            rol_api = rol_por_champ.get(champ_name)
            if not rol_api:
                continue
            rol_ui = API_TO_ROL.get(rol_api.upper(), rol_api.upper())
            if rol_ui not in rol_stats:
                rol_stats[rol_ui] = {"wins": 0, "games": 0}
            win = part_info.get("stats", {}).get("win", False)
            rol_stats[rol_ui]["games"] += 1
            if win:
                rol_stats[rol_ui]["wins"] += 1
        conn.close()
        
        for rol, lbl in self.labels_wr_rol.items():
            if rol in rol_stats and rol_stats[rol]["games"] > 0:
                s = rol_stats[rol]
                wr_rol = round(s["wins"] / s["games"] * 100)
                color = GREEN_WR if wr_rol >= 50 else RED_WR
                lbl.setText(f"{rol}\n{wr_rol}%")
                lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold; padding: 4px;")
                lbl.setToolTip(f"{s['wins']}V / {s['games']-s['wins']}D en {s['games']} partidas")
            else:
                lbl.setText(f"{rol}\n--")
                lbl.setStyleSheet("font-size: 10px; color: #8fa3b8; padding: 4px;")
                lbl.setToolTip("Sin datos en el historial reciente")

        # --- ESTADÍSTICAS DE LA SEASON + FATIGA ---
        self._cargar_stats_season()
        self._analizar_fatiga()

        # --- Filtro de campeones + modos de juego ---
        champs_usados = sorted(set(
            self.procesar_nombre_champ(str(g.get("participants", [{}])[0].get("championId", "0")), "0") or "?"
            for g in self.historial_games
        ))
        self.cb_filtro_champ.blockSignals(True)
        self.cb_filtro_champ.clear()
        self.cb_filtro_champ.addItem("Todos los campeones")
        self.cb_filtro_champ.addItems(champs_usados)
        self.cb_filtro_champ.blockSignals(False)
        
        modos_usados = sorted(set(
            self._clasificar_modo_juego(g)
            for g in self.historial_games
        ))
        self.cb_filtro_modo.blockSignals(True)
        self.cb_filtro_modo.clear()
        self.cb_filtro_modo.addItem("Todos los modos")
        self.cb_filtro_modo.addItems(modos_usados)
        self.cb_filtro_modo.blockSignals(False)
        
        # --- Filtro por temporada ---
        years_usados = sorted(set(
            str(y) for y in (self._extraer_year(g) for g in self.historial_games)
            if y is not None
        ), reverse=True)
        self.cb_filtro_season.blockSignals(True)
        self.cb_filtro_season.clear()
        self.cb_filtro_season.addItem("Todas las temporadas")
        self.cb_filtro_season.addItems(years_usados)
        self.cb_filtro_season.blockSignals(False)

        # ─── FASE 4: COACHING PRO ───
        self._actualizar_coaching()

        # ─── FASE 5: LOGROS ───
        self._cargar_logros()

    def _actualizar_perfil_jugador(self):
        """Puebla el panel de PERFIL DE JUGADOR & OBJETIVOS con datos del historial."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return
        try:
            games = self.historial_games
            
            # 1. Personalidad
            personalidad = analizar_personalidad(games)
            estilo = personalidad.get("estilo", "NEUTRAL")
            perfil_texto = personalidad.get("perfil", "")
            detalles = personalidad.get("detalles", {})
            
            colores_estilo = {
                "AGRESIVO": ACCENT_RED, "CONSISTENTE": GREEN_WR,
                "CONTROL": ACCENT_TEAL, "BALANCEADO": TEXT_GOLD
            }
            color_estilo = colores_estilo.get(estilo, TEXT_WHITE)
            
            self.lbl_personality_style.setText(f"{estilo}")
            self.lbl_personality_style.setStyleSheet(
                f"color: {color_estilo}; font-size: 16px; font-weight: 700; padding: 4px 0;")
            self.lbl_personality_desc.setText(perfil_texto)
            
            # 2. Insights / Habitos
            insights = detectar_habitos(games)
            if insights:
                self.lbl_insights_title.setText("🔍 INSIGHTS DETECTADOS")
                self.lbl_insights.setText("\n".join(f"• {i}" for i in insights[:5]))
            
            # 3. Objetivos semanales
            objetivos = generar_objetivos_semanales(games)
            if objetivos:
                self.lbl_objetivos_title.setText("🎯 OBJETIVOS SEMANALES")
                self.lbl_objetivos.setText("\n".join(objetivos))
            
            # 4. Cruce emocional vs WR
            emocional = analizar_emocional_vs_wr(games)
            if emocional:
                self.lbl_emocional_title.setText("📊 RENDIMIENTO POR ESTADO")
                lineas = []
                emoji_map = {"Concentrado": "🔥", "Normal": "😐", "Tilted": "😤", "Cansado": "😴"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "❓")
                    lineas.append(f"{emoji} {estado}: {wr_e}% WR ({n} partidas)")
                self.lbl_emocional_stats.setText("\n".join(lineas) if lineas else "Etiqueta tus partidas para ver estadísticas")
        except Exception as e:
            print(f"[_actualizar_perfil_jugador] Error: {e}")

    def _actualizar_grafica_lp(self):
        """Refresca la gráfica de LP con los datos de la cola seleccionada."""
        if not hasattr(self, "lp_graph"):
            return
        queue_map = {"Solo/Dúo": "RANKED_SOLO_5x5", "Flex": "RANKED_FLEX_SR"}
        queue = queue_map.get(self.cb_lp_queue.currentText(), "RANKED_SOLO_5x5")
        try:
            history = obtener_historial_lp(queue, dias=30)
            self.lp_graph.set_data(history)
        except Exception as e:
            print(f"[LP Graph] Error: {e}")

    def _analizar_fatiga(self):
        """Analiza fatiga/tilt desde el historial de la LCU y actualiza el dashboard premium."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self.lbl_fatiga_icono.setText("📊")
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText("SIN DATOS")
            self.lbl_fatiga_estado.setStyleSheet("color: #8fa3b8; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_consejo.setText("Esperando datos del cliente.")
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
            return
        try:
            # Solo considerar partidas de hoy para no detectar fatiga de sesiones viejas
            hoy = str(date.today())
            games_hoy = []
            for g in self.historial_games:
                dt = self._parse_game_date(g)
                if dt and str(dt.date()) == hoy:
                    games_hoy.append(g)
            if not games_hoy:
                estado = "fresh"
                mensaje = "🌅 ¡No has jugado hoy! Estás en tu mejor momento."
                recomendacion = "La mente está fresca y los reflejos listos. Calienta con un normal o salta directo a ranked. Hoy es tu día."
            else:
                fatiga = analizar_fatiga(games_hoy)
                estado = fatiga.get("estado", "neutral")
                mensaje = fatiga.get("mensaje", "Sin datos")
                recomendacion = fatiga.get("recomendacion", "")
            
            emojis = {"fresh": "🔥", "neutral": "⚖️", "tired": "🥱", "tilted": "💢"}
            colores = {"fresh": GREEN_WR, "neutral": ACCENT_TEAL, "tired": YELLOW_WR, "tilted": RED_WR}
            textos_color = {"fresh": "#064e3b", "neutral": "#134e4a", "tired": "#713f12", "tilted": "#7f1d1d"}
            textos = {"fresh": "ÓPTIMO", "neutral": "NEUTRAL", "tired": "CANSADO", "tilted": "TILTEADO"}
            
            emoji = emojis.get(estado, "🔥")
            color = colores.get(estado, GREEN_WR)
            bar_color = colores.get(estado, GREEN_WR)
            bar_bg = textos_color.get(estado, "#064e3b")
            estado_txt = textos.get(estado, "ÓPTIMO")
            
            self.lbl_fatiga_icono.setText(emoji)
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText(estado_txt)
            self.lbl_fatiga_estado.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_barra.setStyleSheet(f"background-color: {bar_color}; border-radius: 2px;")
            
            if recomendacion:
                self.lbl_fatiga_consejo.setText(f"💡 {recomendacion}")
            else:
                self.lbl_fatiga_consejo.setText(mensaje)
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
        except Exception as e:
            print(f"[_analizar_fatiga] Error: {e}")
            self.lbl_fatiga_icono.setText("❌")
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText("ERROR")
            self.lbl_fatiga_estado.setStyleSheet(f"color: {RED_WR}; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_consejo.setText("No se pudo analizar el estado mental.")
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")

    def _on_scroll_historial(self, value):
        """Scroll infinito: carga mas partidas cuando el usuario llega al final."""
        # Si ya hay 100+, no cargar mas (el LCU no tiene datos adicionales)
        if hasattr(self, 'historial_games') and len(self.historial_games) >= 100:
            return
        scrollbar = self.tb_historial.verticalScrollBar()
        if scrollbar.maximum() > 0 and value >= scrollbar.maximum() - 50:
            if not hasattr(self, '_cargando_historial'):
                self._cargando_historial = False
            if self._cargando_historial:
                return
            self._cargando_historial = True
            self._cargar_mas_partidas_scroll()

    def _cargar_mas_partidas_scroll(self):
        """Carga 50 partidas ADICIONALES via LCU. Concatena sin borrar la tabla."""
        try:
            if not self.lcu or not self.lcu.port: return
            current = len(self.historial_games) if hasattr(self, 'historial_games') else 0
            if current >= 200: return
            perfil = self.lcu.obtener_perfil()
            if not perfil: return
            puuid = perfil.get("puuid")
            if not puuid: return
            
            nuevas = self.lcu.obtener_historial_extendido(inicio=current, cantidad=50)
            if not nuevas: return
            
            # DEDUP robusto usando mismo criterio que _renderizar_historial
            existing_ids = {self._gid_or_fallback(g) for g in self.historial_games}
            really_new = [g for g in nuevas if self._gid_or_fallback(g) and self._gid_or_fallback(g) not in existing_ids]
            
            if really_new:
                self.historial_games.extend(really_new)
                # Re-ordenar todo para mantener orden por fecha
                self._renderizar_historial(self.historial_games)
            else:
                self._cargando_historial = False
                return
        finally:
            self._cargando_historial = False

    def _append_games_to_table(self, games):
        """Añade partidas a la tabla sin borrar las existentes."""
        for g in games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
            fecha = self._format_game_date(g)
            
            modo_juego = self._clasificar_modo_juego(g)
            
            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(champ_name)}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))
            self.tb_historial.setItem(row, 6, QTableWidgetItem(fecha))

    # ═══════════════════════════════════════════════════════════
    # MOTOR EMOCIONAL — ETIQUETADO DE PARTIDAS (NEXUS)
    # ═══════════════════════════════════════════════════════════

    def _crear_widget_emocional(self, game_id: str, champ_name: str, estado_actual: str = None):
        """Crea un widget con 4 botones de estado emocional para una fila del historial."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        estados = [
            ("🔥", "Concentrado", "#ef4444", "Concentrado: enfoque total"),
            ("😐", "Normal", "#7a6f68", "Normal: estado neutro"),
            ("😤", "Tilted", "#f59e0b", "Tilted: frustrado"),
            ("😴", "Cansado", "#f0b232", "Cansado: fatiga"),
        ]

        for emoji, estado, color, tooltip in estados:
            btn = QPushButton(emoji)
            btn.setFixedSize(28, 24)
            btn.setToolTip(tooltip)
            if estado_actual == estado:
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color: {color}; color: #fff; border: 1px solid {color}; 
                                   border-radius: 3px; font-size: 13px; padding: 0px; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color: transparent; color: {BG_BORDER}; border: 1px solid #251d2b; 
                                   border-radius: 3px; font-size: 13px; padding: 0px; }}
                    QPushButton:hover {{ background-color: {color}; color: #fff; border: 1px solid {color}; }}
                """)
            btn.clicked.connect(lambda checked, gid=game_id, est=estado, ch=champ_name: 
                                self._on_tag_emocional(gid, est, ch))
            layout.addWidget(btn)

        return widget

    def _on_tag_emocional(self, game_id: str, estado: str, champion: str):
        """Guarda el estado emocional y refresca la fila."""
        try:
            # Obtener puuid del perfil actual
            puuid = ""
            if hasattr(self, 'perfil_data') and self.perfil_data:
                puuid = self.perfil_data.get("puuid", "")
            etiquetar_estado_emocional(game_id, estado, puuid, champion)
            # Refrescar solo el historial para mostrar el nuevo estado
            if hasattr(self, 'historial_games'):
                self._renderizar_historial(self.historial_games)
        except Exception as e:
            print(f"[_on_tag_emocional] Error: {e}")

    def filtrar_historial(self, _=None):
        """Filtra la tabla de historial por campeón, modo y temporada."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return
        filtro_champ = self.cb_filtro_champ.currentText()
        filtro_modo = self.cb_filtro_modo.currentText()
        filtro_season = self.cb_filtro_season.currentText()
        
        self.tb_historial.setRowCount(0)
        for g in self.historial_games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            modo_juego = g.get("gameMode", "Draft")
            if modo_juego == "CLASSIC": modo_juego = "Ranked"

            if filtro_champ != "Todos los campeones" and champ_name != filtro_champ:
                continue
            if filtro_modo != "Todos los modos" and modo_juego != filtro_modo:
                continue

            season_year = self._extraer_year(g)
            if filtro_season != "Todas las temporadas" and str(season_year) != filtro_season:
                continue

            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
            # LP delta
            lp_delta = g.get("eloChange") or g.get("playerScoreChange") or stats.get("eloChange")
            if lp_delta is not None:
                lp_str = f"{'+' if lp_delta > 0 else ''}{lp_delta}"
            else:
                lp_str = "--"
            
            # Fecha
            fecha = self._format_game_date(g)

            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(champ_name)}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))
            self.tb_historial.setItem(row, 6, QTableWidgetItem(fecha))

