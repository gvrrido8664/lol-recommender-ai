import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_loggers = {}
_initialized = False


def _get_log_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def init_logging(level=logging.INFO):
    global _initialized
    if _initialized:
        return
    _initialized = True

    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "nexus.log")

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    fh = RotatingFileHandler(log_file, maxBytes=2 * 1024 * 1024, backupCount=3,
                             encoding='utf-8', delay=True)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)


def get_logger(name):
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]
