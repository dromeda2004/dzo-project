from pydantic import BaseModel

from app.schemas.base import ORMBase


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMBase):
    id: int
    email: str
    full_name: str
    is_admin: bool
