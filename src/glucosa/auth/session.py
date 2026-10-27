from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

EXPIRY_MARGIN = timedelta(seconds=60)


@dataclass(frozen=True)
class AuthSession:
    """Sesión Firebase en memoria. El ID token nunca aparece en ``repr``."""

    uid: str
    email: str | None
    id_token: str = field(repr=False)
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        """Vencida si falta menos del margen de seguridad para expirar."""
        return now + EXPIRY_MARGIN >= self.expires_at
