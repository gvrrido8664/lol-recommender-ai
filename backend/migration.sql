-- NEXUS Backend — Migracion inicial de esquema
-- Ejecutar UNA sola vez en el SQL Editor de Render/Supabase.
-- El rol de la app SOLO necesita SELECT, INSERT, UPDATE en estas tablas.
-- NO otorgar CREATE, ALTER, DROP, TRUNCATE al rol de la app.

-- Tablas
CREATE TABLE IF NOT EXISTS drafts_history (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    campeon TEXT NOT NULL,
    rol TEXT NOT NULL,
    bans JSONB DEFAULT '[]',
    aliados JSONB DEFAULT '[]',
    enemigos JSONB DEFAULT '[]',
    wr_predicho DOUBLE PRECISION,
    resultado TEXT DEFAULT 'desconocido',
    ganada BOOLEAN
);

CREATE TABLE IF NOT EXISTS estado_emocional (
    game_id TEXT PRIMARY KEY,
    puuid TEXT DEFAULT '',
    champion TEXT DEFAULT '',
    estado TEXT NOT NULL,
    fecha_tag TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lp_history (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tier TEXT NOT NULL,
    division TEXT NOT NULL,
    lp INTEGER NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    queue_type TEXT DEFAULT 'RANKED_SOLO_5x5',
    lp_total INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS player_cache (
    puuid TEXT PRIMARY KEY,
    season_games JSONB,
    season_ts TIMESTAMP,
    coaching_report JSONB,
    coaching_ts TIMESTAMP
);

-- Indices
CREATE UNIQUE INDEX IF NOT EXISTS idx_lp_unique ON lp_history(fecha, queue_type);
CREATE INDEX IF NOT EXISTS idx_emocional_estado ON estado_emocional(estado);
CREATE INDEX IF NOT EXISTS idx_cache_puuid ON player_cache(puuid);

-- ============================================================================
-- ROL MINIMO — ejecutar despues de crear las tablas:
--
--   CREATE ROLE nexus_app WITH LOGIN PASSWORD '<password>';
--   GRANT CONNECT ON DATABASE <dbname> TO nexus_app;
--   GRANT USAGE ON SCHEMA public TO nexus_app;
--   GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO nexus_app;
--   GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
--
-- NUNCA ejecutar: GRANT CREATE, ALTER, DROP, TRUNCATE TO nexus_app;
-- ============================================================================
