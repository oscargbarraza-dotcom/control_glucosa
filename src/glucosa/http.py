"""Contrato HTTP mínimo e inyectable, de solo ``post``.

``default_http()`` NO devuelve el módulo ``requests`` completo: devuelve un
adaptador que solo expone ``post`` y desactiva las redirecciones. Así, ninguna
capa de la aplicación puede emitir ``PUT``/``PATCH``/``DELETE`` con el token del
usuario por esta vía, y un servidor no puede redirigir el token a otro destino.
Firestore usa POST únicamente para ``runQuery``/``runAggregationQuery``
(lecturas).
"""

from typing import Any, Protocol

DEFAULT_TIMEOUT_SECONDS = 20


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> HttpResponse: ...


class ReadOnlyHttp:
    """Adaptador que solo permite ``post`` y bloquea redirecciones."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def post(self, url: str, **kwargs: Any) -> HttpResponse:
        kwargs["allow_redirects"] = False
        return self._transport.post(url, **kwargs)


def default_http() -> HttpClient:
    import requests

    return ReadOnlyHttp(requests)
