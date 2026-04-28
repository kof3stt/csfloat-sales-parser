from typing import Union, Any

from src.parser.api_parser import APIParser
from src.parser.base_parser import BaseParser
from src.parser.parser import CSFloatParser


def create_parser(config: Union[object, Any]) -> BaseParser:
    """
    Factory function to create parser instance.

    Args:
        config: Application configuration object.

    Returns:
        BaseParser implementation.

    Raises:
        ValueError: If mechanism is unknown.
    """
    if config.mechanism == "browser":
        return CSFloatParser(config)

    if config.mechanism == "api":
        return APIParser(config)

    raise ValueError(f"Unknown mechanism: {config.mechanism}")
