from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    """
    Abstract base class for all parsers.

    Defines a common lifecycle interface:
    - initialization
    - optional login step
    - main start method
    - context manager support
    """

    def __init__(self, config: Any) -> None:
        """
        Initialize parser with configuration.

        Args:
            config: Application configuration object.
        """
        self.config = config

    def __enter__(self) -> "BaseParser":
        """
        Enter context manager.

        Returns:
            BaseParser instance
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit context manager.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Traceback
        """
        return None

    def login(self) -> None:
        """
        Optional authentication step.

        Browser-based parsers may override this method.
        API-based parsers can ignore it.
        """
        return None

    @abstractmethod
    def start(self) -> None:
        """
        Main parsing entry point.

        Must be implemented by subclasses.
        """
        raise NotImplementedError
