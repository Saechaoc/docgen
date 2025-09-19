"""Pipeline orchestration for init/update/regenerate flows."""

from typing import Iterable, Optional


class Orchestrator:
    """Coordinates doc generation pipelines as described in the spec."""

    def __init__(
        self,
    ) -> None:
        # TODO: wire scanners, analyzers, prompting, and runners.
        pass

    def run_init(self, path: str) -> None:
        """Initialize README generation for a repository."""
        raise NotImplementedError

    def run_update(self, path: str, diff_base: str) -> None:
        """Update README content after repository changes."""
        raise NotImplementedError

    def run_regenerate(
        self,
        path: str,
        sections: Optional[Iterable[str]] = None,
    ) -> None:
        """Regenerate README sections on demand."""
        raise NotImplementedError
