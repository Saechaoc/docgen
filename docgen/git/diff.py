"""Diff inspection utilities."""


class DiffAnalyzer:
    """Maps repository changes to affected README sections."""

    def compute(self, repo_path: str, diff_base: str):
        raise NotImplementedError
