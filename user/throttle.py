"""
Rate limiter simples baseado no cache do Django (sem dependência externa).

Uso:
    from .throttle import rate_limit

    class MinhaView(LoginRequiredMixin, View):
        @method_decorator(rate_limit(rate='10/m', key='ip'))
        def dispatch(self, request, *args, **kwargs):
            return super().dispatch(request, *args, **kwargs)

Rate suportado: 'N/s', 'N/m', 'N/h', 'N/d' (N = número inteiro).
"""
import re
import time
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse


def _get_client_ip(request):
    """Obtém IP real do cliente sem confiar em header externo (evita spoofing)."""
    # Em ambiente atrás de proxy confiável, use REMOTE_ADDR ou X-Forwarded-For
    # apenas se configurado. Por padrão, usa REMOTE_ADDR (impossível falsificar).
    return request.META.get("REMOTE_ADDR", "unknown")


def _parse_rate(rate):
    """Converte '10/m' em (quantidade, janela_em_segundos)."""
    m = re.match(r"^(\d+)/([smhd])$", rate)
    if not m:
        raise ValueError(f"Rate inválido: {rate}")
    num = int(m.group(1))
    unit = m.group(2)
    seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return num, seconds


def rate_limit(rate="10/m", key="ip", method="POST", block=True):
    """
    Limita requisições por IP ou por usuário.

    key: 'ip' | 'user' | 'user_or_ip'
    block: True -> retorna 429/403 quando excedido; False -> apenas loga (não implementado).
    """
    num, window = _parse_rate(rate)

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if request.method != method and method != "*":
                return func(request, *args, **kwargs)

            # Define a chave de rate limit
            if key == "user":
                ident = getattr(request.user, "username", "anon") if request.user.is_authenticated else f"ip:{_get_client_ip(request)}"
            elif key == "user_or_ip":
                ident = getattr(request.user, "username", None) if request.user.is_authenticated else None
                ident = ident or _get_client_ip(request)
            else:  # ip
                ident = _get_client_ip(request)

            cache_key = f"ratelimit:{getattr(request, '_rate_limit_name_', 'default')}:{key}:{ident}"
            now = int(time.time())
            window_start = now - window

            # Lista de timestamps de requisições recentes
            hits = cache.get(cache_key) or []
            hits = [t for t in hits if t > window_start]

            if len(hits) >= num:
                if block:
                    retry = int(hits[0] + window - now)
                    resp = JsonResponse(
                        {"success": False, "message": "Limite de requisições atingido. Tente novamente em breve."},
                        status=429,
                    )
                    resp["Retry-After"] = str(max(retry, 1))
                    return resp
                # não bloqueia: apenas registra
                hits.append(now)
                cache.set(cache_key, hits, timeout=window)
                return func(request, *args, **kwargs)

            hits.append(now)
            cache.set(cache_key, hits, timeout=window)
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
