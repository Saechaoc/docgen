"""Tests for structure analyzer."""

from __future__ import annotations

import json

from docgen.analyzers.structure import StructureAnalyzer
from tests._fixtures.repo_builder import RepoBuilder


def test_structure_analyzer_detects_fastapi_and_spring_endpoints(repo_builder: RepoBuilder) -> None:
    repo_builder.write(
        {
            "api/users.py": """
                from fastapi import APIRouter

                router = APIRouter()

                @router.get("/users/{id}")
                def get_user(user_id: int):
                    return {"id": user_id}
            """,
            "src/UserController.java": """
                import org.springframework.web.bind.annotation.GetMapping;
                import org.springframework.web.bind.annotation.PathVariable;
                import org.springframework.web.bind.annotation.RequestMapping;
                import org.springframework.web.bind.annotation.RestController;

                @RestController
                @RequestMapping("/v1")
                public class UserController {
                    @GetMapping("/users/{id}")
                    public String get(@PathVariable String id) {
                        return "ok";
                    }
                }
            """,
        }
    )

    manifest = repo_builder.scan()
    signals = list(StructureAnalyzer().analyze(manifest))
    api_signals = [sig for sig in signals if sig.name == "architecture.api"]

    values = sorted(sig.value for sig in api_signals)
    assert "GET /users/{id}" in values
    assert "GET /v1/users/{id}" in values

    fastapi_signal = next(sig for sig in api_signals if sig.metadata.get("framework") == "FastAPI")
    spring_signal = next(sig for sig in api_signals if sig.metadata.get("framework") == "Spring")
    assert fastapi_signal.metadata["confidence"] >= 0.9
    assert spring_signal.metadata["confidence"] >= 0.9


def test_structure_analyzer_prefers_openapi_spec(repo_builder: RepoBuilder) -> None:
    repo_builder.write(
        {
            "app/routes.py": """
                from fastapi import FastAPI

                app = FastAPI()

                @app.get("/users/{id}")
                def get_user(user_id: int):
                    return {"id": user_id}
            """,
            "docs/openapi.json": json.dumps(
                {
                    "openapi": "3.0.0",
                    "paths": {
                        "/users/{id}": {
                            "get": {
                                "summary": "Fetch a user",
                            }
                        }
                    },
                }
            ),
        }
    )

    manifest = repo_builder.scan()
    signals = list(StructureAnalyzer().analyze(manifest))
    api_signals = [sig for sig in signals if sig.name == "architecture.api"]

    assert api_signals
    spec_signal = next(sig for sig in api_signals if sig.metadata.get("framework") == "spec")
    assert spec_signal.metadata["file"] == "docs/openapi.json"
    assert spec_signal.metadata["confidence"] == 1.0


def test_structure_analyzer_summarises_modules(repo_builder: RepoBuilder) -> None:
    repo_builder.write(
        {
            "services/svc.py": "print('hi')\n",
            "services/__init__.py": "",
            "docs/readme.md": "# Docs\n",
        }
    )

    manifest = repo_builder.scan()
    signals = list(StructureAnalyzer().analyze(manifest))

    modules = next(sig for sig in signals if sig.name == "architecture.modules")
    module_names = [module["name"] for module in modules.metadata["modules"]]
    assert "services" in module_names


def test_spring_method_level_request_mapping(repo_builder: RepoBuilder) -> None:
    repo_builder.write(
        {
            "src/PingController.java": """
                import org.springframework.web.bind.annotation.RequestMapping;
                import org.springframework.web.bind.annotation.RestController;
                import org.springframework.web.bind.annotation.RequestMethod;

                @RestController
                public class PingController {
                    @RequestMapping(value = "/ping", method = RequestMethod.GET)
                    public String ping() {
                        return "pong";
                    }
                }
            """,
        }
    )

    manifest = repo_builder.scan()
    signals = list(StructureAnalyzer().analyze(manifest))
    api_paths = {sig.metadata["path"] for sig in signals if sig.name == "architecture.api"}
    assert "/ping" in api_paths
