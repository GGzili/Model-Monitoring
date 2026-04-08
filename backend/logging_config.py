"""应用业务日志：独立 StreamHandler，不依赖 uvicorn 对 uvicorn.error 的 handler 配置。"""
from __future__ import annotations

import logging
import sys

_APP_LOGGER_NAME = "modelmonitor"


def log_stderr_line(msg: str) -> None:
    """直接写 stderr 并 flush，不经过 logging；Docker / uvicorn 下仍会在 docker logs 里出现。"""
    sys.stderr.write("[modelmonitor] " + msg + "\n")
    sys.stderr.flush()


def get_app_logger() -> logging.Logger:
    lg = logging.getLogger(_APP_LOGGER_NAME)
    if lg.handlers:
        return lg
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(levelname)s [modelmonitor] %(message)s"))
    lg.addHandler(h)
    lg.setLevel(logging.INFO)
    lg.propagate = False
    return lg
