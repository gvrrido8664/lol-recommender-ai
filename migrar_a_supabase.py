"""Migra los datos de la BD actual (Render, leida de config.json) a Supabase.

No requiere pg_dump/psql: usa psycopg2 (ya instalado) con COPY en formato texto,
que round-trippea perfecto incluido JSONB. Es idempotente (TRUNCATE antes de copiar).

Uso:
  1) Poner la connection string del *Session pooler* de Supabase en una de estas:
       - variable de entorno  SUPABASE_URL
       - archivo              supabase_url.txt  (en la raiz, gitignored)
  2) python migrar_a_supabase.py
  3) Si todo ok, actualizar DATABASE_URL en config.json a la de Supabase.
"""
import io
import os
import sys
import json
import psycopg2

# Orden importante: matches antes que participantes (FK)
TABLAS = ["matches", "participantes", "estado_emocional", "player_cache"]
# Tablas con id SERIAL cuya secuencia hay que reajustar tras el COPY
SECUENCIAS = [("participantes", "id"), ("estado_emocional", "id")]


def _url_origen():
    with open("config.json", encoding="utf-8") as f:
        url = json.load(f).get("DATABASE_URL", "")
    if not url:
        sys.exit("No hay DATABASE_URL en config.json (origen).")
    return url


def _url_destino():
    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url and os.path.exists("supabase_url.txt"):
        with open("supabase_url.txt", encoding="utf-8") as f:
            url = f.read().strip()
    if not url:
        sys.exit("Falta la URL de Supabase: setea SUPABASE_URL o crea supabase_url.txt")
    return url


def _host(url):
    try:
        return url.split("@", 1)[1].split("/", 1)[0]
    except Exception:
        return "?"


def main():
    src_url = _url_origen()
    tgt_url = _url_destino()
    print(f"Origen : {_host(src_url)}")
    print(f"Destino: {_host(tgt_url)}")

    # 1) Crear el esquema en el destino (tablas + indices) reusando inicializar_db
    print("\n[1/3] Creando esquema en Supabase...")
    os.environ["DATABASE_URL"] = tgt_url  # la app prioriza la env var
    from src.db_manager import inicializar_db
    inicializar_db()

    src = psycopg2.connect(src_url, connect_timeout=30)
    tgt = psycopg2.connect(tgt_url, connect_timeout=30)
    try:
        # 2) Vaciar destino (idempotente) y copiar con COPY texto
        print("[2/3] Copiando datos...")
        with tgt.cursor() as c:
            c.execute("TRUNCATE participantes, matches, estado_emocional, player_cache "
                      "RESTART IDENTITY CASCADE")
        tgt.commit()

        for t in TABLAS:
            buf = io.StringIO()
            with src.cursor() as cs:
                cs.copy_expert(f"COPY {t} TO STDOUT", buf)
            buf.seek(0)
            with tgt.cursor() as ct:
                ct.copy_expert(f"COPY {t} FROM STDIN", buf)
            tgt.commit()
            with tgt.cursor() as ct:
                ct.execute(f"SELECT COUNT(*) FROM {t}")
                print(f"   {t}: {ct.fetchone()[0]:,} filas")

        # 3) Reajustar secuencias SERIAL
        print("[3/3] Reajustando secuencias...")
        with tgt.cursor() as c:
            for tabla, col in SECUENCIAS:
                c.execute(
                    f"SELECT setval(pg_get_serial_sequence('{tabla}','{col}'), "
                    f"COALESCE((SELECT MAX({col}) FROM {tabla}), 1))")
        tgt.commit()

        print("\nOK. Migracion completa. Ahora actualiza DATABASE_URL en config.json "
              "a la URL de Supabase y verifica con: python tests.py")
    finally:
        src.close()
        tgt.close()


if __name__ == "__main__":
    main()
