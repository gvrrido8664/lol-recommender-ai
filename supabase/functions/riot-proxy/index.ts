/**
 * NEXUS Riot Proxy — Supabase Edge Function
 *
 * Recibe requests del cliente NEXUS con token de app, los reenvia a la API
 * de Riot con la API key server-side, cachea respuestas en la BD y aplica
 * rate limiting basico. Sin dependencias externas (sin Upstash, sin Redis).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ─── Config from Supabase Secrets ──────────────────────────────────────────

const RIOT_API_KEY = Deno.env.get("RIOT_API_KEY")!;
const APP_TOKEN = Deno.env.get("APP_TOKEN")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Precompute token hash once at cold start
const TOKEN_HASH = await crypto.subtle.digest(
  "SHA-256",
  new TextEncoder().encode(APP_TOKEN)
).then(buf =>
  Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("")
);

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// ─── Rate Limiter (simple sliding window via DB) ───────────────────────────

const RATE_SHORT_MAX = 18;
const RATE_SHORT_SECS = 2;

async function checkRateLimit(): Promise<boolean> {
  const now = new Date();
  const windowStart = new Date(now.getTime() - RATE_SHORT_SECS * 1000);

  const { count } = await supabase
    .from("rate_limits")
    .select("*", { count: "exact", head: true })
    .gte("ts", windowStart.toISOString());

  if ((count ?? 0) >= RATE_SHORT_MAX) {
    return false;
  }

  await supabase.from("rate_limits").insert({ ts: now.toISOString() });
  return true;
}

// ─── Auth ──────────────────────────────────────────────────────────────────

async function checkAuth(req: Request): Promise<boolean> {
  const auth = req.headers.get("Authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return false;
  const token = auth.slice(7);
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token))
    .then(buf =>
      Array.from(new Uint8Array(buf))
        .map(b => b.toString(16).padStart(2, "0"))
        .join("")
    );
  return hash === TOKEN_HASH;
}

// ─── Cache ─────────────────────────────────────────────────────────────────

async function getCache(url: string, ttl: number): Promise<object | null> {
  const cutoff = new Date(Date.now() - ttl * 1000).toISOString();
  const { data } = await supabase
    .from("riot_cache")
    .select("data")
    .eq("url", url)
    .gte("ts", cutoff)
    .maybeSingle();

  if (data) {
    const now = new Date();
    const old = new Date(data.ts);
    if (now.getTime() - old.getTime() < ttl * 1000) {
      return data.data;
    }
  }
  return null;
}

async function setCache(url: string, riotData: object): Promise<void> {
  const now = new Date().toISOString();
  await supabase.from("riot_cache").upsert(
    { url, data: riotData, ts: now },
    { onConflict: "url" }
  );
}

// ─── Riot Proxy ────────────────────────────────────────────────────────────

async function fetchRiot(url: string, cacheTtl: number): Promise<Response> {
  const cached = await getCache(url, cacheTtl);
  if (cached) {
    return new Response(JSON.stringify(cached), {
      status: 200,
      headers: { "Content-Type": "application/json", "X-Cache": "HIT" },
    });
  }

  const allowed = await checkRateLimit();
  if (!allowed) {
    return new Response(
      JSON.stringify({ error: "rate_limited", message: "Demasiadas solicitudes. Espera unos segundos." }),
      { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "5" } }
    );
  }

  try {
    const riotResp = await fetch(url, { headers: { "X-Riot-Token": RIOT_API_KEY } });

    if (riotResp.status === 200) {
      const data = await riotResp.json();
      await setCache(url, data);
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Cache": "MISS" },
      });
    }

    if (riotResp.status === 429) {
      const retryAfter = riotResp.headers.get("Retry-After") ?? "10";
      return new Response(
        JSON.stringify({ error: "riot_rate_limited", retry_after: parseInt(retryAfter) }),
        { status: 429, headers: { "Content-Type": "application/json", "Retry-After": retryAfter } }
      );
    }

    if (riotResp.status === 401 || riotResp.status === 403) {
      return new Response(
        JSON.stringify({ error: "riot_unauthorized", message: "API key de Riot invalida o expirada." }),
        { status: 502, headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ error: "riot_error", status: riotResp.status }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "network_error", message: String(err) }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

// ─── CORS ──────────────────────────────────────────────────────────────────

function corsHeaders(): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
  };
}

// ─── Router ────────────────────────────────────────────────────────────────

const ROUTES: Record<string, { buildUrl: (params: string[], query: URLSearchParams) => string; cacheTtl: number }> = {
  "account/by-riot-id": {
    buildUrl: (p, q) => `https://${q.get("routing") ?? "americas"}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/${p[0]}/${p[1]}`,
    cacheTtl: 3600,
  },
  "account/by-puuid": {
    buildUrl: (p, q) => `https://${q.get("routing") ?? "americas"}.api.riotgames.com/riot/account/v1/accounts/by-puuid/${p[0]}`,
    cacheTtl: 3600,
  },
  "summoner/by-puuid": {
    buildUrl: (p, q) => `https://${q.get("region") ?? "la2"}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/${p[0]}`,
    cacheTtl: 300,
  },
  "league/by-puuid": {
    buildUrl: (p, q) => `https://${q.get("platform") ?? "la2"}.api.riotgames.com/lol/league/v4/entries/by-puuid/${p[0]}`,
    cacheTtl: 120,
  },
  "league/by-summoner": {
    buildUrl: (p, q) => `https://${q.get("region") ?? "la2"}.api.riotgames.com/lol/league/v4/entries/by-summoner/${p[0]}`,
    cacheTtl: 120,
  },
  "mastery/top": {
    buildUrl: (p, q) => `https://${q.get("platform") ?? "la2"}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/${p[0]}/top?count=1`,
    cacheTtl: 600,
  },
  "match/by-puuid": {
    buildUrl: (p, q) => {
      const start = q.get("start") ?? "0";
      const count = q.get("count") ?? "100";
      const startTime = q.get("start_time");
      let url = `https://${q.get("routing") ?? "americas"}.api.riotgames.com/lol/match/v5/matches/by-puuid/${p[0]}/ids?start=${start}&count=${count}`;
      if (startTime) url += `&startTime=${startTime}`;
      return url;
    },
    cacheTtl: 60,
  },
  "match/detail": {
    buildUrl: (p, q) => `https://${q.get("routing") ?? "americas"}.api.riotgames.com/lol/match/v5/matches/${p[0]}`,
    cacheTtl: 3600,
  },
  "match/timeline": {
    buildUrl: (p, q) => `https://${q.get("routing") ?? "americas"}.api.riotgames.com/lol/match/v5/matches/${p[0]}/timeline`,
    cacheTtl: 3600,
  },
};

// ─── Main Handler ──────────────────────────────────────────────────────────

serve(async (req: Request): Promise<Response> => {
  const headers = corsHeaders();

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers });
  }

  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "method_not_allowed" }), { status: 405, headers });
  }

  // Auth
  if (!(await checkAuth(req))) {
    return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401, headers });
  }

  // Parse URL path: /{category}/{...path}
  const url = new URL(req.url);
  const path = url.pathname.replace(/^\/+|\/+$/g, ""); // trim slashes
  const parts = path.split("/");

  if (parts.length < 2) {
    return new Response(JSON.stringify({ error: "invalid_route", path }), { status: 404, headers });
  }

  // Match route: first two segments are the route key
  const routeKey = parts.slice(0, 2).join("/");
  let routeParams: string[] = parts.slice(2);

  // Special case: match/detail/{id} and match/timeline/{id}
  if (routeKey === "match" && routeParams.length >= 2 && routeParams[0] === "ids") {
    // match/by-puuid/{puuid}/ids?start=...&count=...
    const rk = "match/by-puuid";
    const handler = ROUTES[rk];
    if (handler) {
      const riotUrl = handler.buildUrl([routeParams[1]], url.searchParams);
      return fetchRiot(riotUrl, handler.cacheTtl).then(r => {
        Object.entries(headers).forEach(([k, v]) => r.headers.set(k, v));
        return r;
      });
    }
  }

  if (routeKey === "match" && routeParams.length === 1) {
    const rk = "match/detail";
    const handler = ROUTES[rk];
    if (handler) {
      const riotUrl = handler.buildUrl([routeParams[0]], url.searchParams);
      return fetchRiot(riotUrl, handler.cacheTtl).then(r => {
        Object.entries(headers).forEach(([k, v]) => r.headers.set(k, v));
        return r;
      });
    }
  }

  if (routeKey === "match" && routeParams.length === 2 && routeParams[1] === "timeline") {
    const rk = "match/timeline";
    const handler = ROUTES[rk];
    if (handler) {
      const riotUrl = handler.buildUrl([routeParams[0]], url.searchParams);
      return fetchRiot(riotUrl, handler.cacheTtl).then(r => {
        Object.entries(headers).forEach(([k, v]) => r.headers.set(k, v));
        return r;
      });
    }
  }

  const handler = ROUTES[routeKey];
  if (!handler) {
    return new Response(JSON.stringify({ error: "unknown_route", route: routeKey }), { status: 404, headers });
  }

  const riotUrl = handler.buildUrl(routeParams, url.searchParams);
  return fetchRiot(riotUrl, handler.cacheTtl).then(r => {
    Object.entries(headers).forEach(([k, v]) => r.headers.set(k, v));
    return r;
  });
});
