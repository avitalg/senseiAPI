from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt

from auth.models import AuthUser

TOKEN_ALGORITHM = "HS256"
REQUIRED_CLAIMS = ["exp", "iat"]


class InvalidTokenError(Exception):
    """Raised when an access token is missing, malformed, or invalid."""


def create_access_token(
    user: AuthUser,
    *,
    secret_key: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user.user_id),
        "email": user.email,
        "full_name": user.full_name,
        "auth_type": user.auth_type.value,
        "role": user.role.value,
        "token_version": user.token_version,
        "exp": issued_at + timedelta(seconds=ttl_seconds),
        "iat": issued_at,
    }
    return jwt.encode(payload, secret_key, algorithm=TOKEN_ALGORITHM)


def verify_access_token(
    token: str,
    *,
    secret_key: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    options: dict[str, object] = {"require": REQUIRED_CLAIMS}
    if now is not None:
        options["verify_exp"] = False
        options["verify_iat"] = False

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[TOKEN_ALGORITHM],
            options=cast(Any, options),
        )
        if now is not None:
            _verify_time_claims(payload, now=now)
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("invalid token") from exc

    if not isinstance(payload, dict):
        raise InvalidTokenError("invalid token")
    return payload


def _verify_time_claims(payload: dict[str, Any], *, now: datetime) -> None:
    checked_at = int(now.timestamp())
    expires_at = payload.get("exp")
    issued_at = payload.get("iat")
    if not isinstance(expires_at, int):
        raise InvalidTokenError("missing token expiration")
    if not isinstance(issued_at, int):
        raise InvalidTokenError("missing token issued-at")
    if expires_at <= checked_at:
        raise InvalidTokenError("token expired")
    if issued_at > checked_at:
        raise InvalidTokenError("token issued in the future")
