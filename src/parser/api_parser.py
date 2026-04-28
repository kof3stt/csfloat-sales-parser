from typing import Any

from src.parser.base_parser import BaseParser


class APIParser(BaseParser):
    """
    Parser implementation for API-based data source.

    Currently not implemented.
    """

    def __init__(self, config: Any) -> None:
        """
        Initialize API parser.

        Args:
            config: Application configuration object.
        """
        super().__init__(config)

    def __enter__(self) -> "APIParser":
        """
        Enter context manager.

        Returns:
            APIParser instance
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit context manager.
        """
        return None

    def start(self) -> None:
        """
        Main API parsing logic.

        Raises:
            NotImplementedError: Always, since API parser is not implemented yet.
        """
        raise NotImplementedError("API parser is not implemented yet")
