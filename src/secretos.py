"""Descifrado en runtime de los secretos embebidos (API_KEY, DATABASE_URL).

Los secretos NO viajan en texto plano en el instalador. En su lugar, el build
genera `secretos.bin` (un blob cifrado con Fernet) que se empaqueta dentro del
.exe. Aqui se descifra **solo en memoria** — nunca se escribe el plano a disco.

OJO (security through obscurity): la clave de descifrado se deriva de piezas
ofuscadas que viven en el propio binario, asi que un atacante decidido puede
extraer los secretos. Esto sube la barrera contra usuarios casuales y evita que
la cadena de conexion quede a la vista en claro, pero NO es proteccion real. La
solucion robusta seria un backend proxy. Ver el plan de distribucion segura.

`scripts/cifrar_secretos.py` (build-time) importa `_derivar_clave()` de aqui para
cifrar con exactamente la misma clave que se usa al descifrar.
"""
import base64
import json
import os

from src.paths import BASE_DIR

# Nombre del blob cifrado dentro del bundle.
NOMBRE_BLOB = "secretos.bin"

# --- Derivacion de clave -----------------------------------------------------
# La clave Fernet se reconstruye combinando varias piezas. No se guarda entera
# en claro en ningun sitio. Estas constantes parecen datos inocuos.
_PIEZA_A = b"n3xus-lol-2024-draft-radar-coach"
_PIEZA_B = b"\x5a\x13\x9c\x2f\x71\xe8\x04\xbd\x6a\x37\x88\xc1\x4e\x90\x2d\xf5"
_PIEZA_C = b"riot-supabase-bridge-salt-v1"


def _derivar_clave() -> bytes:
    """Deriva la clave Fernet (32 bytes url-safe base64) via PBKDF2-HMAC-SHA256.

    Determinista: misma entrada -> misma clave, en cualquier maquina. Lo usan
    tanto el cifrado (build) como el descifrado (runtime)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    material = bytes(a ^ b for a, b in zip(
        _PIEZA_A, (_PIEZA_B * 2)[:len(_PIEZA_A)]
    ))
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_PIEZA_C,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(material))


def _ruta_blob() -> str:
    return os.path.join(BASE_DIR, NOMBRE_BLOB)


def cargar_secretos_embebidos() -> dict:
    """Descifra `secretos.bin` y devuelve {"API_KEY": ..., "DATABASE_URL": ...}.

    Solo en memoria. Si el blob no existe o falla el descifrado, devuelve {}."""
    ruta = _ruta_blob()
    if not os.path.exists(ruta):
        return {}
    try:
        from cryptography.fernet import Fernet

        with open(ruta, "rb") as f:
            blob = f.read()
        plano = Fernet(_derivar_clave()).decrypt(blob)
        datos = json.loads(plano.decode("utf-8"))
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}
