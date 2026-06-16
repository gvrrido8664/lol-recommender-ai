import hashlib
import os

API_KEY = os.environ.get("RIOT_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
APP_TOKEN = os.environ.get("APP_TOKEN", "")
PORT = int(os.environ.get("PORT", "8000"))

RIOT_RATE_LIMIT_SHORT = int(os.environ.get("RIOT_RATE_LIMIT_SHORT", "18"))
RIOT_RATE_LIMIT_LONG = int(os.environ.get("RIOT_RATE_LIMIT_LONG", "90"))

_TOKEN_HASH = hashlib.sha256(APP_TOKEN.encode()).hexdigest() if APP_TOKEN else ""


def validar_token(token: str) -> bool:
    if not APP_TOKEN:
        return False
    return hashlib.sha256(token.encode()).hexdigest() == _TOKEN_HASH
