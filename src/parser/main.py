import time
import logging
from typing import Any

from src.parser.config_loader import load_config
from src.parser.factory import create_parser
from src.parser.backup import create_db_backup

logger = logging.getLogger("main")


def run_parser() -> None:
    """
    Application entrypoint.

    Responsibilities:
    - Load configuration
    - Create parser instance
    - Run parsing lifecycle
    - Ensure DB queue completion
    - Create backup
    - Log execution time
    """

    start_time = time.perf_counter()
    config = load_config()

    parser: Any = None

    try:
        parser = create_parser(config)

        with parser:
            parser.login()
            parser.start()

            logger.info("All tasks processed")

    except KeyboardInterrupt:
        logger.warning("Interrupted by user (KeyboardInterrupt)")

    except Exception as e:
        logger.error(f"Fatal error in parser: {e}", exc_info=True)

    finally:
        try:
            create_db_backup()
        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)

    elapsed = time.perf_counter() - start_time
    logger.info(f"Execution time: {elapsed:.2f}s")


if __name__ == "__main__":
    run_parser()
