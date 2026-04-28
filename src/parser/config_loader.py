import tomllib
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass(frozen=True)
class BrowserConfig:
    """
    Configuration for browser-based parser.
    """

    parse_interval_hours: int
    timeout_policy: List[int]
    min_timeout: float


@dataclass(frozen=True)
class LoggingConfig:
    """
    Logging configuration.
    """

    dir: str
    level: str


@dataclass(frozen=True)
class AppConfig:
    """
    Root application configuration.
    """

    mechanism: str
    currency: str
    browser: BrowserConfig
    logging: LoggingConfig
    items: List[Dict[str, Any]]


def load_config(path: str = "config.toml") -> AppConfig:
    """
    Load application configuration from TOML file.

    Args:
        path: Path to config file.

    Returns:
        AppConfig instance
    """
    with open(path, "rb") as file:
        raw: Dict[str, Any] = tomllib.load(file)

    browser_raw: Dict[str, Any] = raw.get("browser", {})
    logging_raw: Dict[str, Any] = raw.get("logging", {})

    browser_config = BrowserConfig(
        parse_interval_hours=browser_raw.get("parse_interval_hours", 24),
        timeout_policy=browser_raw.get("timeout_policy", []),
        min_timeout=browser_raw.get("min_timeout", 0.0),
    )

    logging_config = LoggingConfig(
        dir=logging_raw.get("dir", "logs"),
        level=logging_raw.get("level", "INFO"),
    )

    return AppConfig(
        mechanism=raw.get("mechanism", "browser"),
        currency=raw.get("currency", "USD"),
        browser=browser_config,
        logging=logging_config,
        items=raw.get("items", []),
    )
