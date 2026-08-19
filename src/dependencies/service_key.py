from fastapi import Header, HTTPException
from typing import Optional
from src.config import settings


def verify_service_key(x_service_key: Optional[str] = Header(None)):
    if not x_service_key or x_service_key != settings.B2B_TO_MOD_KEY:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_SERVICE_KEY", "message": "Invalid X-Service-Key header"}
        )
    return True
