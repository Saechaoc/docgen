"""FastAPI service exposing docgen operations."""

from .app import create_app, run_service

__all__ = ["create_app", "run_service"]
