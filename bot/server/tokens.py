import time
import secrets
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenInfo:
    token: str
    file_path: str
    user_id: int
    created_at: float
    expires_at: float
    consumed: bool = False


class TokenStore:
    """In-memory store for one-time download tokens."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._tokens: dict[str, TokenInfo] = {}

    def create(self, file_path: str, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._tokens[token] = TokenInfo(
            token=token,
            file_path=file_path,
            user_id=user_id,
            created_at=now,
            expires_at=now + self.ttl,
        )
        return token

    def validate(self, token: str) -> Optional[TokenInfo]:
        info = self._tokens.get(token)
        if info is None:
            return None
        if info.consumed or time.time() > info.expires_at:
            return None
        return info

    def consume(self, token: str) -> Optional[TokenInfo]:
        info = self.validate(token)
        if info is None:
            return None
        info.consumed = True
        return info

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            t for t, info in self._tokens.items()
            if info.consumed or now > info.expires_at
        ]
        for t in expired:
            del self._tokens[t]
        return len(expired)

    @property
    def active_count(self) -> int:
        now = time.time()
        return sum(
            1 for info in self._tokens.values()
            if not info.consumed and now <= info.expires_at
        )
