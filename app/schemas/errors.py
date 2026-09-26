from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: dict[str, list[str]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
