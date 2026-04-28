import threading
import queue
import logging
from typing import Tuple, Dict, Any, List

from src.parser.database import DatabaseManager

logger = logging.getLogger("db_worker")

SaleQueueItem = Tuple[str, Dict[str, Any]]


class DBWorker(threading.Thread):
    """
    Background worker that consumes parsed sales from queue
    and writes them to the database in batches.
    """

    def __init__(
        self,
        db: DatabaseManager,
        q: queue.Queue,
        batch_size: int = 50,
        timeout: int = 5,
    ):
        """
        Args:
            db: Database manager instance
            q: Thread-safe queue with (hash_name, sale_data)
            batch_size: Max number of items per DB transaction
            timeout: Queue polling timeout in seconds
        """
        super().__init__(daemon=True)

        self.db = db
        self.q = q
        self.batch_size = batch_size
        self.timeout = timeout

        self._running = True

    def run(self) -> None:
        """
        Main worker loop.
        Consumes queue items and writes them to DB in batches.
        """
        logger.info("DBWorker started")

        while self._running or not self.q.empty():
            batch: List[SaleQueueItem] = []

            try:
                batch.append(self.q.get(timeout=self.timeout))

                while len(batch) < self.batch_size:
                    try:
                        batch.append(self.q.get_nowait())
                    except queue.Empty:
                        break

                self._process_batch(batch)

            except queue.Empty:
                continue

        logger.info("DBWorker stopped")

    def _process_batch(self, batch: List[SaleQueueItem]) -> None:
        """
        Writes a batch of sales into DB inside a single transaction.
        """
        if not batch:
            return

        with self.db.get_session() as session:
            item_cache: Dict[str, Any] = {}

            for hash_name, sale_data in batch:
                try:
                    if hash_name not in item_cache:
                        item_cache[hash_name] = self.db.get_or_create_item(
                            session, hash_name
                        )

                    item = item_cache[hash_name]
                    self.db.save_sale(session, item, sale_data)

                finally:
                    self.q.task_done()

        logger.debug(f"Saved batch of {len(batch)} sales")

    def stop(self) -> None:
        """
        Stops worker gracefully.
        """
        self._running = False
