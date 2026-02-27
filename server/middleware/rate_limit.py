import time
from collections import defaultdict

from fastapi import HTTPException, Request

from server.config import RATE_LIMIT_MAX, RATE_LIMIT_WINDOW

_attempts: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    _attempts[ip] = [t for t in _attempts[ip] if t > window_start]

    if len(_attempts[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(429, "Muitas tentativas. Aguarde 1 minuto.")

    _attempts[ip].append(now)
