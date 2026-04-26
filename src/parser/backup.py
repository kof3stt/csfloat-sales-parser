import os
import subprocess
import logging
from typing import Optional

from src.parser.config import settings

logger = logging.getLogger("backup")


def create_db_backup() -> Optional[str]:
    """
    Create a PostgreSQL database backup using pg_dump.

    The function:
    - checks if backups are enabled via environment variable DB_BACKUP_ENABLED
    - removes previous backup file if it exists
    - creates a new backup using pg_dump (custom format)
    - stores backup in path defined by BACKUP_DIR and BACKUP_FILE

    Returns:
        Path to created backup file if successful, otherwise None
    """

    if os.getenv("DB_BACKUP_ENABLED", "false").lower() != "true":
        logger.info("DB backup disabled via env")
        return None

    backup_dir: str = os.getenv("BACKUP_DIR", "backups")
    backup_file: str = os.getenv("BACKUP_FILE", "csfloat_backup.dump")

    os.makedirs(backup_dir, exist_ok=True)

    backup_path: str = os.path.join(backup_dir, backup_file)

    if os.path.exists(backup_path):
        os.remove(backup_path)
        logger.info("Previous backup removed")

    logger.info("Starting database backup...")

    command: list[str] = [
        "pg_dump",
        "-h",
        str(settings.DB_HOST),
        "-p",
        str(settings.DB_PORT),
        "-U",
        str(settings.DB_USER),
        "-F",
        "c",
        "-b",
        "-f",
        str(backup_path),
        str(settings.DB_NAME),
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD

    try:
        subprocess.run(command, check=True, env=env)
        logger.info(f"Backup created: {backup_path}")
        return backup_path

    except subprocess.CalledProcessError as e:
        logger.error("Backup failed", exc_info=True)
        logger.error(f"pg_dump error: {e}")
        return None
