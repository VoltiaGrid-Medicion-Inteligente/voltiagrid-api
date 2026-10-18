"""JWT issuing and validation with roles (US-13, T-13.1).

A token carries who the caller is, never what they ask for:

    sub   customer code (CU-MAC000002) or "internal"
    role  "customer" | "internal"
    iss   "voltiagrid"
    iat / exp   issued at / expiry (JWT_EXPIRE_MINUTES, default 60)

Signed with HS256 and the JWT_SECRET environment variable. See ADR-010.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from app.core.config import get_settings

Role = Literal["customer", "internal"]
ROLES = ("customer", "internal")


class InvalidToken(Exception):
    """The token is missing a claim, expired, or not signed by us."""


def issue_token(role: Role, customer_code: str | None = None, expires_minutes: int | None = None) -> str:
    if role not in ROLES:
        raise ValueError(f"unknown role '{role}'")
    if role == "customer" and not customer_code:
        raise ValueError("a customer token needs the customer code")
    settings = get_settings()
    now = datetime.now(timezone.utc)
    minutes = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes
    claims = {
        "sub": customer_code if role == "customer" else "internal",
        "role": role,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Claims of a valid token. Raises InvalidToken otherwise."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "role", "exp", "iat", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidToken("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidToken("Invalid token") from exc
    if claims["role"] not in ROLES:
        raise InvalidToken("Invalid token")
    return claims
