import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BlockingReasonCreateRequest(BaseModel):
    code: str = Field(..., max_length=64)
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    hard_block: bool

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z_]+", value):
            raise ValueError("code must contain only uppercase letters and underscores")
        return value


class BlockingReasonUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class BlockingReasonResponse(BaseModel):
    id: str
    code: str
    title: str
    description: Optional[str] = None
    hard_block: bool
    is_active: bool

    model_config = {"from_attributes": True}
