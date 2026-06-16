# build_exe.ps1 - Build de NEXUS con PyInstaller (onedir, sin UPX, anti-falsos-positivos).
# Uso:
#   powershell ./build_exe.ps1            # build limpio
#   powershell ./build_exe.ps1 -Sign      # build + firma self-signed (crea cert si no existe)
param(
    [switch]$Sign
)
$ErrorActionPreference = "Stop"
$ExePath = "build_onedir\NEXUS\NEXUS.exe"

Write-Host "== Limpiando builds anteriores ==" -ForegroundColor Cyan
Remove-Item -Recurse -Force "build_onedir", "build_temp" -ErrorAction SilentlyContinue

if (-not (Test-Path "icono_app.ico")) {
    Write-Host "AVISO: icono_app.ico no encontrado -> se usa icono por defecto de PyInstaller." -ForegroundColor Yellow
}

Write-Host "== Ejecutando PyInstaller (build_nexus.spec) ==" -ForegroundColor Cyan
pyinstaller build_nexus.spec --noconfirm --distpath build_onedir --workpath build_temp
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: PyInstaller fallo." -ForegroundColor Red; exit 1 }

if (-not (Test-Path $ExePath)) { Write-Host "ERROR: no se genero $ExePath" -ForegroundColor Red; exit 1 }
$sizeMB = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
Write-Host "OK: $ExePath ($sizeMB MB)" -ForegroundColor Green

if ($Sign) {
    Write-Host "== Firma self-signed ==" -ForegroundColor Cyan
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
            Where-Object { $_.Subject -eq "CN=NEXUS" } | Select-Object -First 1
    if (-not $cert) {
        Write-Host "Creando certificado self-signed CN=NEXUS (valido 5 anios)..." -ForegroundColor Yellow
        $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=NEXUS" `
                -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(5)
    }
    Set-AuthenticodeSignature -FilePath $ExePath -Certificate $cert `
        -TimestampServer "http://timestamp.digicert.com" | Out-Null
    $sig = Get-AuthenticodeSignature $ExePath
    Write-Host "Firma: $($sig.Status) por $($cert.Subject)" -ForegroundColor Green
    Write-Host "NOTA: una firma self-signed NO quita el aviso de SmartScreen en otras PCs." -ForegroundColor Yellow
}

Write-Host "`n== LISTO ==" -ForegroundColor Green
Write-Host "Probar:   & '$ExePath'"
Write-Host "VirusTotal: subir el .exe a https://www.virustotal.com/ y revisar detecciones."
