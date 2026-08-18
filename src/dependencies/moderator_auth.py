from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from src.config import settings


def get_current_moderator_id(authorization: Optional[str] = Header(None)) -> str:
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
    return str(moderator_id)
