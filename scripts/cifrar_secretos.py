"""Cifra los secretos (API_KEY, DATABASE_URL) en build-time -> secretos.bin.

Lee el config.json REAL de la raiz (gitignored, nunca se shippea), extrae solo
los secretos y los cifra con Fernet usando la MISMA clave que reconstruye
src/secretos.py en runtime. El blob resultante se empaqueta dentro del .exe.

Uso (lo invoca build_exe.ps1 -Installer):
    python scripts/cifrar_secretos.py [salida]

`salida` por defecto = build_onedir/secretos.bin
"""
import json
import os
import sys

# Permitir importar src/ ejecutando desde la raiz del repo.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from cryptography.fernet import Fernet

from src.secretos import _derivar_clave, NOMBRE_BLOB

CLAVES_SECRETAS = ("API_KEY", "DATABASE_URL")


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join("build_onedir", NOMBRE_BLOB)

    config_path = os.path.join(_RAIZ, "config.json")
    if not os.path.exists(config_path):
        print(f"ERROR: no se encuentra {config_path} (config.json real con secretos).")
        return 1

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    secretos = {k: config[k] for k in CLAVES_SECRETAS if config.get(k)}
    faltan = [k for k in CLAVES_SECRETAS if not secretos.get(k)]
    if faltan:
        print(f"AVISO: secretos ausentes en config.json: {', '.join(faltan)}")
    if not secretos:
        print("ERROR: config.json no tiene ningun secreto que cifrar.")
        return 1

    blob = Fernet(_derivar_clave()).encrypt(
        json.dumps(secretos, separators=(",", ":")).encode("utf-8")
    )

    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    with open(salida, "wb") as f:
        f.write(blob)

    print(f"OK: secretos cifrados -> {salida} ({len(blob)} bytes, claves: {', '.join(secretos)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
