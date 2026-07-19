"""OIDC / OAuth2 bearer-token authentication.

Validates RS256 JWTs against the IdP's JWKS. The JWKS is cached in-process with
a TTL (the previous version fetched it from the IdP on every single request,
making the IdP a per-request hard dependency and latency bottleneck).
"""

import logging
import time

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import JWTError, jwt

from euroclaw.settings import current_settings

logger = logging.getLogger("euroclaw.security")

_settings = current_settings()
OIDC_ISSUER = _settings.oidc_issuer_url
OIDC_AUDIENCE = _settings.oidc_audience

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{OIDC_ISSUER}/protocol/openid-connect/auth",
    tokenUrl=f"{OIDC_ISSUER}/protocol/openid-connect/token",
    auto_error=True,
)

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0


def get_public_keys(force: bool = False) -> dict:
    """Fetch and cache the IdP JWKS with a TTL."""
    global _jwks_cache, _jwks_fetched_at
    ttl = current_settings().jwks_cache_ttl_seconds
    now = time.time()
    if not force and _jwks_cache is not None and (now - _jwks_fetched_at) < ttl:
        return _jwks_cache
    jwks_uri = f"{OIDC_ISSUER}/protocol/openid-connect/certs"
    response = requests.get(jwks_uri, timeout=10)
    response.raise_for_status()
    _jwks_cache = response.json()
    _jwks_fetched_at = now
    return _jwks_cache


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate enterprise credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        jwks = get_public_keys()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=OIDC_AUDIENCE,
            issuer=OIDC_ISSUER,
        )
    except JWTError as exc:
        logger.warning("Invalid token: %s", exc)
        raise credentials_exception from exc
    except requests.RequestException as exc:
        logger.error("JWKS fetch failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity provider unavailable",
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception
    roles = payload.get("realm_access", {}).get("roles", [])
    return {"user_id": user_id, "roles": roles, "email": payload.get("email", "")}
