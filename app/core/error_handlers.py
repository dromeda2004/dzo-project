from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ErrorDetail, ErrorResponse


def _code_for_status(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return "error"
    return phrase.lower().replace(" ", "_").replace("-", "_").replace("'", "")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=_code_for_status(exc.status_code), message=str(exc.detail))
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields: dict[str, list[str]] = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body") or "__root__"
        fields.setdefault(field, []).append(error["msg"])
    body = ErrorResponse(
        error=ErrorDetail(code="validation_error", message="Invalid request", fields=fields)
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump()
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Every 4xx/5xx from any router comes back as {"error": {"code", "message", "fields"?}}
    — see docs/API_CONVENTIONS.md."""
    # FastAPI/Starlette's add_exception_handler is typed generically over Exception,
    # so a handler typed to a specific exception class always mismatches — this is
    # the standard, harmless workaround.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
