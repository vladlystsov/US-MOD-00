from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": "HTTP_ERROR", "message": str(exc.detail)}
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION_ERROR", "message": str(exc.errors())}
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION_ERROR", "message": str(exc.errors())}
        )
