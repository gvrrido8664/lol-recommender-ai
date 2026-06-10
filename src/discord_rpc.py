import time
import threading

_RPC_CLIENT = None
_RPC_THREAD = None
_RPC_RUNNING = False
_RPC_LOCK = threading.Lock()


def _get_rpc_client():
    global _RPC_CLIENT
    if _RPC_CLIENT is None:
        try:
            from pypresence import Presence
            _RPC_CLIENT = Presence("1356306895325102150")
        except Exception:
            _RPC_CLIENT = False
    return _RPC_CLIENT


def _rpc_loop():
    global _RPC_RUNNING
    client = _get_rpc_client()
    if not client:
        return
    while _RPC_RUNNING:
        try:
            client.run_callbacks()
        except Exception:
            pass
        time.sleep(2)


def iniciar_discord_rpc():
    global _RPC_RUNNING, _RPC_THREAD
    with _RPC_LOCK:
        if _RPC_RUNNING:
            return
        client = _get_rpc_client()
        if not client:
            return
        try:
            client.connect()
            _RPC_RUNNING = True
            _RPC_THREAD = threading.Thread(target=_rpc_loop, daemon=True)
            _RPC_THREAD.start()
        except Exception:
            pass


def detener_discord_rpc():
    global _RPC_RUNNING
    with _RPC_LOCK:
        _RPC_RUNNING = False
        client = _get_rpc_client()
        if client and client is not False:
            try:
                client.clear()
                client.close()
            except Exception:
                pass


def actualizar_discord_rpc(details="En el cliente de LoL", state="Menu principal",
                           large_image="lol", large_text="League of Legends",
                           small_image=None, small_text=None,
                           start_timestamp=None, party_size=None, party_max=None):
    if not _RPC_RUNNING:
        return
    client = _get_rpc_client()
    if not client:
        return
    try:
        kwargs = {
            "details": details[:128] if details else "En League of Legends",
            "state": state[:128] if state else "",
            "large_image": large_image or "lol",
            "large_text": (large_text or "League of Legends")[:128],
        }
        if small_image:
            kwargs["small_image"] = small_image
        if small_text:
            kwargs["small_text"] = small_text[:128]
        if start_timestamp:
            kwargs["start"] = start_timestamp
        if party_size is not None and party_max is not None:
            kwargs["party_size"] = [party_size, party_max]
        client.update(**kwargs)
    except Exception:
        pass
