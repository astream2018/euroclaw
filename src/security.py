import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JWTError
import requests

logger = logging.getLogger("euroclaw.security")

OIDC_ISSUER = os.getenv("OIDC_ISSUER_URL", "http://localhost:8080/realms/euroclaw")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "euroclaw-api")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{OIDC_ISSUER}/protocol/openid-connect/auth",
    tokenUrl=f"{OIDC_ISSUER}/protocol/openid-connect/token",
)


def get_public_keys():
    try:
        jwks_uri = f"{OIDC_ISSUER}/protocol/openid-connect/certs"
        response = requests.get(jwks_uri, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch public keys from IdP: {e}")
        raise


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
        user_id: str = payload.get("sub")
        roles: list = payload.get("realm_access", {}).get("roles", [])

        if user_id is None:
            raise credentials_exception

        return {"user_id": user_id, "roles": roles, "email": payload.get("email", "")}
    except JWTError as e:
        logger.warning(f"Invalid token detected: {e}")
        raise credentials_exception
