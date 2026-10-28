"""Dobles de prueba: HTTP, keyring y proveedor de clave en memoria."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeResponse:
    status_code: int = 200
    payload: Any = None

    def json(self) -> Any:
        return self.payload


@dataclass
class FakeHttp:
    """Registra cada POST y devuelve respuestas en orden (o lanza una excepción)."""

    responses: list[Any] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        outcome = self.responses.pop(0) if self.responses else FakeResponse()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeKeyring:
    """Imita la interfaz mínima de ``keyring`` con un diccionario."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


def make_jwt(claims: dict) -> str:
    """JWT sin firma válida: suficiente para probar la lectura de claims."""
    import base64
    import json

    def encode(part: dict) -> str:
        raw = json.dumps(part).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return f"{encode({'alg': 'RS256'})}.{encode(claims)}.firma"
