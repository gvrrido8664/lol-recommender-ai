# Build del ejecutable y notas para antivirus

Objetivo: generar `NEXUS.exe` con la **mayor confianza posible** ante antivirus/SmartScreen
para empezar pruebas. Estrategia: **onedir + sin UPX + icono + metadata de versión + firma**.

## Cómo buildear

```powershell
# requisitos: pip install -r requirements-dev.txt  (incluye pyinstaller)
powershell ./build_exe.ps1            # build limpio  -> build_onedir/NEXUS/NEXUS.exe
powershell ./build_exe.ps1 -Sign      # build + firma self-signed (crea cert CN=NEXUS)
```

Archivos del build (versionados): `build_nexus.spec`, `version_info.txt`, `build_exe.ps1`.
La salida `build_onedir/` está en `.gitignore`.

## Icono (opcional pero recomendado)
`icono_app.ico` está gitignored (lo provee cada quien). Para generarlo desde un PNG 512×512:
```python
from PIL import Image
Image.open("logo.png").save("icono_app.ico", sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
```
Si no existe, el build usa el icono por defecto de PyInstaller (funciona igual).

## Por qué se reducen los falsos positivos
- **onedir (no onefile):** onefile se auto-extrae en %TEMP% en cada arranque → patrón que muchos
  AV marcan. onedir es una carpeta normal.
- **Sin UPX:** los ejecutables empacados con UPX son el disparador #1 de heurísticas de AV.
- **Metadata de versión + icono** (`version_info.txt`): un exe con CompanyName/ProductName/
  versión luce legítimo; un exe anónimo es sospechoso.
- **Escribe en %APPDATA%\LoLRecommender** (no en Program Files): no requiere permisos elevados.

## Imports "sensibles" (todos legítimos y envueltos en try/except)
Documentado para responder ante un análisis de AV / reporte de falso positivo:
- `ctypes.windll.dwmapi.DwmSetWindowAttribute` (app.py): pone la barra de título de Windows en
  modo oscuro. Solo lectura/atributo de la propia ventana.
- `urllib3 ... verify=False` (src/lcu_api.py): el cliente local de LoL (LCU) usa un certificado
  **autofirmado** en `127.0.0.1`; por eso se desactiva la verificación TLS **solo** para esa
  conexión local. No afecta tráfico a internet.
- `winreg` (src/lcu_api.py): localizar la instalación de LoL. Solo lectura del registro.
- `pypresence` (src/discord_rpc.py): Discord Rich Presence (IPC local con Discord). Opcional,
  falla en silencio si Discord no está.
- `psycopg2` / `requests`: conexión a la BD (Supabase) y a la API de Riot/Data Dragon.

`config.json` (con API_KEY/DATABASE_URL) **no** se empaqueta: va en `%APPDATA%\LoLRecommender\`.

## Firma
- **Ahora (pruebas):** self-signed (`build_exe.ps1 -Sign`). El exe queda firmado y con metadata,
  pero SmartScreen **igual avisa** en otras PCs (la firma no es de una CA pública). Sirve para
  que el binario no luzca "anónimo" y para tus pruebas locales.
- **Para distribución pública (futuro):** certificado real de firma de código:
  - **Azure Trusted Signing** (~10 USD/mes, validación de identidad) — la opción más barata que
    elimina el aviso de SmartScreen.
  - **Sectigo / SSL.com OV** (~100–250 USD/año).
  Con reputación acumulada, SmartScreen deja de avisar.

## Checklist antes de distribuir una prueba
- [ ] `build_exe.ps1` corre sin errores y abre la GUI.
- [ ] Se crea `%APPDATA%\LoLRecommender\` (assets/data/logs) y `nexus.log` sin errores.
- [ ] `config.json` con API_KEY + DATABASE_URL está en esa carpeta (no dentro del exe).
- [ ] Subido a https://www.virustotal.com/ → detecciones mínimas/heurísticas (0–3 esperable
      sin cert real). Si un motor marca, reportar falso positivo con esta doc.

## Cómo generar el instalador

```powershell
# Build completo + firma self-signed + instalador
powershell ./build_exe.ps1 -Sign -Installer

# Salida:
#   build_onedir/NEXUS_Setup_1.0.0.exe   ← instalador (firmado)
```

Requisito: [Inno Setup 6](https://jrsoftware.org/isdl.php) instalado.

## Cómo compartir el instalador

### Opción A — Google Drive (simple, gratis)

1. Subir `build_onedir\NEXUS_Setup_1.0.0.exe` a Google Drive
2. Click derecho → Compartir → "Cualquier persona con el enlace"
3. Compartir el link

### Opción B — GitHub Releases (recomendado, público)

1. Ir a https://github.com/<tu-usuario>/<tu-repo>/releases
2. "Create a new release"
3. Tag: `v1.0.0`, título: "NEXUS v1.0.0"
4. Adjuntar `NEXUS_Setup_1.0.0.exe`
5. Publicar y compartir la URL del release

### Opción C — Discord / WhatsApp (rápido, amigos)

Arrastrar el .exe al chat. Si Discord lo bloquea por tamaño (>25MB), usar Google Drive.

## Nota sobre SmartScreen

Con firma **self-signed**, SmartScreen muestra advertencia en otras PCs. El usuario debe
hacer click en "Más información" → "Ejecutar de todas formas".

Para eliminar el aviso completamente necesitas un **certificado de firma de código real**:
- **Azure Trusted Signing** (~$10 USD/mes) — la opción más barata
- **Sectigo / SSL.com OV** (~$100-250 USD/año)

Con reputación acumulada (~1 semana), SmartScreen deja de avisar por completo.
