"""
forge/core/security.py

Local single-user authentication via a bearer token stored at ~/.forge/auth.key.
No internet, no email, no third-party service required.
"""
from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from forge.core.config import settings

_bearer = HTTPBearer(auto_error=False)


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    """
    FastAPI dependency.  Raises 401 if the bearer token doesn't match
    the key stored in ~/.forge/auth.key.

    Usage::

        @router.get("/protected")
        async def endpoint(_key: str = Depends(verify_api_key)):
            ...
    """
    expected = settings.get_or_create_api_key()

    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
