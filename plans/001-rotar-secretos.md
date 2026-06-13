# Plan 001: Rotar credenciales expuestas y purgarlas del repo

> **Instrucciones para el ejecutor**: Seguí este plan paso a paso. Corré cada
> comando de verificación y confirmá el resultado esperado antes de avanzar. Si
> ocurre algo de la sección "Condiciones STOP", pará y reportá — no improvises.
> Al terminar, actualizá la fila de este plan en `plans/README.md`.
>
> **Chequeo de drift (correr primero)**:
> `git diff --stat e31df97..HEAD -- PLAN_DE_MEJORAS.md .gitignore config.example.json`
> Si alguno cambió desde que se escribió este plan, compará los excerpts de
> "Estado actual" con el código vivo antes de seguir; si no coincide, es STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `e31df97`, 2026-06-13

## Por qué importa

Las credenciales de producción del proyecto (clave de API de Riot y la
`DATABASE_URL` de PostgreSQL con contraseña) están **expuestas de forma
permanente**: (1) `config.json` estuvo trackeado en git y sigue en el historial
(commits `7d45c4c` y `a24a826`), y (2) el documento `PLAN_DE_MEJORAS.md` —que
está commiteado— las reproduce en texto plano. Cualquiera con acceso al repo o
su historial puede extraerlas. Una credencial commiteada se considera **quemada
aunque se borre**: la única remediación real es **rotarla**. Este plan rota,
purga el texto plano del árbol actual y documenta (sin ejecutar) la opción de
reescribir el historial.

> **Regla de manejo de secretos**: en ningún archivo que generes (planes,
> commits, código) debe aparecer el VALOR de una credencial. Referenciá solo
> `archivo:línea` y el tipo de credencial.

## Estado actual

- `PLAN_DE_MEJORAS.md:264-265` — reproduce en texto plano la clave de API de Riot
  (`API_KEY`) y la `DATABASE_URL` de PostgreSQL (con usuario y contraseña). Están
  dentro de un bloque que documenta el problema original; hay que **redactarlas**.
  (Las líneas 595-596 del mismo archivo son el ejemplo con placeholders `xxxx` —
  NO son secretos reales; no las toques salvo para confirmar que son placeholders.)
- `.gitignore:28` — contiene `config.json` (correcto: el archivo ya NO se trackea).
- `config.example.json` — plantilla sin valores reales (correcto, ya existe).
- `config.json` (en disco, NO trackeado) — contiene los valores reales en uso por
  la app. No se toca; es local.
- Historial: `git log --all --oneline -- config.json` muestra que el archivo se
  commiteó en el pasado → los valores viven en el historial.
- `git-filter-repo==2.47.0` ya está en `requirements.txt` (herramienta disponible
  para reescritura de historial, si se decide).

## Comandos que vas a necesitar

| Propósito | Comando | Esperado |
|-----------|---------|----------|
| Tests baseline | `python tests.py` | imprime `13/13 pasaron` |
| Ver si config.json se trackea | `git ls-files config.json` | salida vacía |
| Confirmar gitignore | `grep -n "config.json" .gitignore` | `28:config.json` (o similar) |
| Buscar secretos restantes | `git grep -nE "RGAPI-\|postgresql://" -- '*.md' '*.json' '*.py'` | tras el fix, solo placeholders |

## Alcance

**En alcance** (lo único que modificás como código/archivos):
- `PLAN_DE_MEJORAS.md` — redactar las líneas 264-265.

**Acciones MANUALES del humano (no son edición de código; documentalas, no las ejecutes):**
- Rotar la clave de API de Riot en el portal de desarrollador de Riot.
- Rotar la contraseña/credenciales de la base PostgreSQL en el panel de Render
  y actualizar el `config.json` local y la variable de entorno `DATABASE_URL`.
- (Opcional, destructivo) Reescribir el historial de git para purgar `config.json`.

**Fuera de alcance** (NO tocar):
- `config.json` real en disco (local, ya gitignored).
- `config.example.json` (ya correcto).
- Cualquier lógica de carga de config en `src/config.py` / `src/db_manager.py`
  (la ruta por env var + config.json ya funciona; no cambiar el contrato).

## Git workflow

- Rama: `advisor/001-rotar-secretos`
- Commit estilo repo (conventional commits en español + trailer). Ejemplo:
  `security: redactar credenciales en PLAN_DE_MEJORAS.md`
- No pushear ni abrir PR salvo que el operador lo pida.

## Steps

### Step 1: Redactar los secretos en PLAN_DE_MEJORAS.md

Abrí `PLAN_DE_MEJORAS.md`, líneas 264-265. Reemplazá los VALORES reales de
`API_KEY` y `DATABASE_URL` por placeholders redactados, conservando la estructura
del texto. El resultado debe quedar así (valores redactados):

```json
"API_KEY": "RGAPI-***REDACTADO-ROTAR***",
"DATABASE_URL": "postgresql://***REDACTADO-ROTAR***"
```

No cambies el resto del párrafo ni las líneas 595-596 (ya son placeholders).

**Verify**: `git grep -nE "RGAPI-[0-9a-f]{8}|nexus_.*_user|:[^/@]+@" -- PLAN_DE_MEJORAS.md`
→ sin coincidencias (ningún valor real de clave ni de contraseña/usuario queda).

### Step 2: Confirmar que config.json no se trackea y está ignorado

No requiere edición; es verificación. Si `git ls-files config.json` devuelve algo,
es STOP (alguien lo re-trackeó).

**Verify**:
- `git ls-files config.json` → salida vacía
- `grep -n "config.json" .gitignore` → al menos una línea

### Step 3: Documentar las acciones manuales de rotación

Añadí al final de `PLAN_DE_MEJORAS.md` una sección breve `## Rotación pendiente
(acción manual)` que liste, SIN valores: (a) rotar API key de Riot, (b) rotar
credenciales de Render y actualizar `config.json` local + env `DATABASE_URL`,
(c) opción de purgar historial con `git filter-repo` (marcada como destructiva,
requiere `--force` y coordinación; no ejecutar automáticamente).

**Verify**: `grep -n "Rotación pendiente" PLAN_DE_MEJORAS.md` → 1 coincidencia.

### Step 4: Verificar que la app y los tests siguen intactos

No se tocó código ejecutable; confirmá que nada se rompió.

**Verify**: `python tests.py` → `13/13 pasaron`

## Test plan

No hay tests nuevos (cambio documental + acciones manuales). La verificación es:
- `git grep` no encuentra valores reales de credenciales en archivos versionados.
- `python tests.py` sigue en `13/13`.

## Done criteria

Machine-checkable, TODAS deben cumplirse:

- [ ] `git grep -nE "RGAPI-[0-9a-f]{8}|:[^/@]+@[^/]+/" -- '*.md' '*.json'` (excluyendo
      placeholders con `xxxx`/`REDACTADO`) no devuelve secretos reales
- [ ] `git ls-files config.json` vacío
- [ ] `python tests.py` imprime `13/13 pasaron`
- [ ] `PLAN_DE_MEJORAS.md` tiene la sección "Rotación pendiente (acción manual)"
- [ ] Ningún archivo fuera de `PLAN_DE_MEJORAS.md` fue modificado (`git status`)
- [ ] Fila de 001 actualizada en `plans/README.md`

## Condiciones STOP

Pará y reportá (no improvises) si:

- `git ls-files config.json` devuelve el archivo (fue re-trackeado): hace falta
  `git rm --cached config.json` y revisar por qué volvió — reportá antes de tocar.
- Encontrás los mismos valores en MÁS archivos de los listados (p.ej. en código
  `.py`, en `README.md`, o en otros `.md`): listá las ubicaciones (sin valores) y
  reportá; el alcance del plan crece.
- Te piden ejecutar `git filter-repo` o un `push --force`: es destructivo y
  reescribe historial compartido — NO lo hagas; reportá para decisión humana.

## Notas de mantenimiento

- La rotación de credenciales es responsabilidad del humano dueño del repo; el
  ejecutor solo redacta el texto y documenta los pasos.
- Si en el futuro se decide purgar el historial, hacerlo con `git filter-repo`
  (ya en requirements) sobre un clon espejo, y coordinar con cualquiera que tenga
  forks/clones (el historial reescrito invalida sus copias).
- Revisor del PR: confirmar que ningún valor real de credencial quedó en el diff.
