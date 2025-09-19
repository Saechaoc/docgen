"""Link validation helpers."""


class LinkValidator:
    """Ensures generated links are reachable and consistent."""

    def validate(self, markdown: str) -> None:
        raise NotImplementedError
