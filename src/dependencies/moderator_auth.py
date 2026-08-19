from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from src.config import settings


def _jwt_payload(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid authorization"},
        )
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid authorization"},
        )
    moderator_id = payload.get("sub")
    if not moderator_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid authorization"},
        )
    return payload


def get_current_moderator_id(authorization: Optional[str] = Header(None)) -> str:
    return str(_jwt_payload(authorization)["sub"])


def get_current_admin_id(authorization: Optional[str] = Header(None)) -> str:
    payload = _jwt_payload(authorization)
    roles = payload.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    is_admin = payload.get("is_admin") is True or payload.get("role") in {"admin", "moderator_admin"} or "admin" in roles
    if not is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Administrator role is required"},
        )
    return str(payload["sub"])
