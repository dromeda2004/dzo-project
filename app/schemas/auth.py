from typing import Annotated

from pydantic import AfterValidator, BaseModel

from app.schemas.base import ORMBase

MIN_PASSWORD_LENGTH = 8
# bcrypt only uses the first 72 bytes and bcrypt>=5 rejects anything longer.
MAX_PASSWORD_BYTES = 72


def validate_new_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return value


NewPassword = Annotated[str, AfterValidator(validate_new_password)]


class LoginRequest(BaseModel):
    email: str
    password: str
    # A 30-day login instead of 24 hours, for a shared device such as a
    # restaurant's kitchen tablet.
    stay_signed_in: bool = False


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: NewPassword


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Seconds until the token expires, so a client knows when to log in again.
    expires_in: int


class UserOut(ORMBase):
    id: int
    email: str
    full_name: str
    is_admin: bool
