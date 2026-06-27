# Migración de la base de datos a Supabase

Render apaga la BD gratuita por inactividad (reintroduce latencia y puede borrar datos).
Migramos a **Supabase** (Postgres gratis). La app no cambia de código: solo el `DATABASE_URL`.

## 1. Crear el proyecto
1. Crear cuenta y proyecto en https://supabase.com (región más cercana a ti; para LAS,
   **South America (São Paulo)** da menor latencia).
2. Anotar la **Database password** que defines al crear el proyecto.

## 2. Connection string correcta (importante)
En *Project Settings → Database → Connection string* usar el **Session pooler** (no la
"Direct connection": en el plan free suele ser solo IPv6 y falla desde muchas redes). Formato:
```
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```
- Puerto **5432** = pooler en modo *session* (ideal para apps persistentes con pool, como esta).
- Si hubiera límite de conexiones, bajar `_PG_MAXCONN` en `src/db_manager.py` (de 10 a ~5).

## 3. Migrar los datos desde Render
Con `pg_dump`/`pg_restore` (vienen con cualquier instalación de Postgres / `psql`):
```bash
# 1) Dump desde Render (reemplazar por tu URL actual de Render)
pg_dump --no-owner --no-privileges -Fc "postgresql://USER:PWD@HOST:5432/DB_RENDER" -f nexus.dump

# 2) Restore a Supabase (usar la Session pooler string)
pg_restore --no-owner --no-privileges -d "postgresql://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:5432/postgres" nexus.dump
```
Tablas que se migran: `matches`, `participantes`, `estado_emocional`, `player_cache`.
Los índices se recrean solos al arrancar la app (`inicializar_db`), pero el dump ya los trae.

> Si el dump es muy grande, puedes migrar solo el esquema + `matches`/`participantes` y dejar que
> el recolector siga llenando. Para empezar pruebas no hace falta migrar todo.

## 4. Apuntar la app a Supabase
Preferí **variable de entorno** (la app prioriza `DATABASE_URL` sobre `config.json`):
- En tu PC: setear `DATABASE_URL` con la Session pooler string, **o**
- En `config.json` (gitignored): `"DATABASE_URL": "postgresql://postgres.<ref>:..."`.

Verificar: `python tests.py` (13/13) y abrir la app → el radar/perfil cargan normalmente.
Mirar la latencia en `nexus.log` (`Radar DB compute: X.XXs`).

## 5. Mantenerla despierta (Supabase pausa tras ~7 días sin uso)
Hay un GitHub Action que hace `SELECT 1` dos veces por semana:
`.github/workflows/keepalive-db.yml`. Para activarlo:
1. En el repo de GitHub: *Settings → Secrets and variables → Actions → New repository secret*.
2. Crear el secret **`DATABASE_URL`** con la Session pooler string de Supabase.
3. El workflow corre lunes y jueves (y se puede disparar a mano con *Run workflow*).

El uso regular de la app también la mantiene activa; el cron es el seguro por si no la abres.
