import requests
import os

GITHUB_REPO = "anomalyco/lol-recommender-v2"
CURRENT_VERSION = "2.1.0"


def _get_version_file():
    from src.logger import _get_log_dir
    return os.path.join(_get_log_dir(), "app_version.txt")


def get_current_version():
    vf = _get_version_file()
    if os.path.exists(vf):
        with open(vf, "r", encoding="utf-8") as f:
            return f.read().strip()
    return CURRENT_VERSION


def check_for_update():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return None
        latest = resp.json().get("tag_name", "").lstrip("v")
        if not latest:
            return None
        current = get_current_version()
        if latest != current:
            return {
                "current": current,
                "latest": latest,
                "url": resp.json().get("html_url", ""),
                "body": resp.json().get("body", "")[:200],
            }
        return None
    except Exception:
        return None


def set_current_version(version):
    vf = _get_version_file()
    os.makedirs(os.path.dirname(vf), exist_ok=True)
    with open(vf, "w", encoding="utf-8") as f:
        f.write(version)
