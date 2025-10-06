"""FastAPI application entrypoint for docgen service mode."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

try:  # pragma: no cover - optional dependency
    from fastapi import Depends, FastAPI
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    _FASTAPI_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - service mode optional
    FastAPI = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False

from ..orchestrator import Orchestrator, UpdateOutcome


class InitRequest(BaseModel):
    path: str
    skip_validation: bool = False


class InitResponse(BaseModel):
    readme_path: str


class UpdateRequest(BaseModel):
    path: str
    diff_base: str = "origin/main"
    dry_run: bool = False
    skip_validation: bool = False


class UpdateResponse(BaseModel):
    status: str
    readme_path: Optional[str] = None
    diff: Optional[str] = None
    dry_run: Optional[bool] = None


class HealthResponse(BaseModel):
    status: str


def _default_orchestrator() -> Orchestrator:
    return Orchestrator()


def create_app(
    orchestrator_factory: Callable[[], Orchestrator] = _default_orchestrator,
) -> FastAPI:
    """Create the FastAPI application exposing docgen operations."""

    if not _FASTAPI_AVAILABLE:  # pragma: no cover - validated via unit tests
        raise RuntimeError(
            "FastAPI is required for service mode. Install it with `pip install fastapi uvicorn`."
        )

    app = FastAPI(title="DocGen Service", version="1.0.0")

    async def get_orchestrator() -> Orchestrator:
        # Lazy-instantiate per request to keep state predictable.
        return orchestrator_factory()

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/init", response_model=InitResponse)
    async def init_repo(
        payload: InitRequest,
        orchestrator: Orchestrator = Depends(get_orchestrator),
    ) -> InitResponse:
        def _run_init() -> Path:
            return orchestrator.run_init(
                payload.path, skip_validation=payload.skip_validation
            )

        try:
            loop = asyncio.get_running_loop()
        except (
            RuntimeError
        ):  # pragma: no cover - fallback path when not in async context
            readme_path = _run_init()
        else:
            readme_path = await loop.run_in_executor(None, _run_init)
        return InitResponse(readme_path=str(readme_path))

    @app.post("/update", response_model=UpdateResponse)
    async def update_repo(
        payload: UpdateRequest,
        orchestrator: Orchestrator = Depends(get_orchestrator),
    ) -> UpdateResponse:
        def _run_update() -> UpdateOutcome | None:
            return orchestrator.run_update(
                payload.path,
                payload.diff_base,
                dry_run=payload.dry_run,
                skip_validation=payload.skip_validation,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover
            result = _run_update()
        else:
            result = await loop.run_in_executor(None, _run_update)

        if result is None:
            return UpdateResponse(status="skipped")

        return UpdateResponse(
            status="ok",
            readme_path=str(result.path),
            diff=result.diff,
            dry_run=result.dry_run,
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(
        _: Any, exc: FileNotFoundError
    ) -> JSONResponse:  # pragma: no cover - simple mapping
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(
        _: Any, exc: RuntimeError
    ) -> JSONResponse:  # pragma: no cover - simple mapping
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


def run_service(
    host: str = "0.0.0.0", port: int = 8000
) -> None:  # pragma: no cover - integration path
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is required for service mode. Install it with `pip install fastapi uvicorn`."
        )

    try:
        import uvicorn
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "uvicorn is required to run the service. Install it with `pip install uvicorn`."
        ) from exc

    app = create_app()
    uvicorn.run(app, host=host, port=port)
