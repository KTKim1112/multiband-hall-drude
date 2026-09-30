"""Application assembly: the app, codes out of every failure, and the built page.

The mapping from a code to an HTTP status lives in `errors.py`, beside the codes.
Every failure leaves as `{"code", "params"}` -- the application's own, the
library's, a malformed request, and the unforeseen alike (FR-105).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mbfit.core.errors import MbfitError

from . import resources
from .errors import STATUS, AppError, _plain
from .routes import router

VERSION = "0.1.0"

STATIC_DIR = resources.root() / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multiband Hall analysis",
        version=VERSION,
        description="Carrier densities and mobilities from rho_xx(B) and rho_xy(B).",
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=STATUS.get(exc.code, 422), content=exc.payload())

    @app.exception_handler(MbfitError)
    async def _library_error(_: Request, exc: MbfitError) -> JSONResponse:
        return JSONResponse(status_code=422,
                            content={"code": exc.code, "params": _plain(exc.detail)})

    @app.exception_handler(RequestValidationError)
    async def _malformed(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's messages are English sentences; only where they point is kept.
        where = [".".join(str(p) for p in error.get("loc", ())) for error in exc.errors()]
        return JSONResponse(status_code=422,
                            content={"code": "E_REQUEST_INVALID", "params": {"fields": where}})

    @app.get("/api/health")
    def health() -> dict:
        return {"version": VERSION}

    app.include_router(router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built page when there is one. In development Vite serves it."""
    if not STATIC_DIR.is_dir():
        return
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    index = STATIC_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa(full_path: str) -> FileResponse | JSONResponse:
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"code": "E_NOT_FOUND", "params": {}})


app = create_app()
