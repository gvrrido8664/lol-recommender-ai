-- NEXUS Edge Function — Tablas de cache y rate limit
-- Ejecutar en el SQL Editor de Supabase

CREATE TABLE IF NOT EXISTS riot_cache (
    url TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    ts TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_riot_cache_ts ON riot_cache(ts);

CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_ts ON rate_limits(ts);
