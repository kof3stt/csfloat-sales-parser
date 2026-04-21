import time
import logging

from src.parser.parser import CSFloatParser
from src.parser.backup import create_db_backup

logger = logging.getLogger("main")


def run_parser() -> None:
    """
    Application entrypoint.

    Responsibilities:
    - Start parser
    - Wait for completion
    - Ensure all DB tasks are processed
    - Create backup (if enabled)
    - Measure execution time
    """

    start_time = time.perf_counter()

    try:
        with CSFloatParser() as parser:
            parser.login()
            parser.start()

            parser.queue.join()

            logger.info("All queue tasks processed")

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

    print(f"Execution time: {elapsed:.2f}s")


if __name__ == "__main__":
    run_parser()
