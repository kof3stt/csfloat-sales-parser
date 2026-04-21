from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from src.parser.models import Base, Item, Sale, Sticker

logger = logging.getLogger("database")


class DatabaseManager:
    """
    Database access layer.

    Responsibilities:
    - create database (if missing)
    - manage SQLAlchemy engine
    - provide session scope
    - persist domain objects (Item, Sale, Sticker)
    """

    def __init__(self, connection_string: str, echo: bool = False) -> None:
        """
        Initialize database manager.

        Args:
            connection_string: PostgreSQL SQLAlchemy URL
            echo: enable SQL logging
        """
        self.connection_string: str = connection_string

        self._ensure_database_exists(connection_string)

        self.engine: Engine = create_engine(
            connection_string,
            echo=echo,
            pool_size=5,
            max_overflow=10,
        )

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )

    @staticmethod
    def _ensure_database_exists(connection_string: str) -> None:
        """
        Create database if it does not exist.

        This connects to default 'postgres' database first,
        then checks and creates target database.
        """
        url = make_url(connection_string)

        db_name: str = url.database
        admin_url = url.set(database="postgres")

        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

        try:
            with engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": db_name},
                ).scalar()

                if not exists:
                    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                    logger.info(f"Created database: {db_name}")

        finally:
            engine.dispose()

    def create_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Tables created successfully")

    def drop_tables(self) -> None:
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Tables dropped")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Provide transactional DB session.

        Yields:
            SQLAlchemy Session
        """
        session: Session = self.SessionLocal()

        try:
            yield session
            session.commit()

        except Exception:
            session.rollback()
            logger.exception("Database transaction failed")
            raise

        finally:
            session.close()

    def get_or_create_item(self, session: Session, hash_name: str) -> Item:
        """
        Get existing item or create new one.

        Args:
            session: active DB session
            hash_name: item name

        Returns:
            Item instance
        """
        item = session.query(Item).filter_by(name=hash_name).first()

        if item:
            return item

        item = Item.from_hash_name(hash_name)
        session.add(item)
        session.flush()

        logger.info(f"Created new item: {hash_name}")
        return item

    def save_sale(
        self,
        session: Session,
        item: Item,
        sale_data: Dict[str, Any],
    ) -> Optional[Sale]:
        """
        Save sale with stickers and metadata.

        Args:
            session: DB session
            item: related item
            sale_data: parsed scraper data

        Returns:
            Sale or None if duplicate
        """

        try:
            base: Dict[str, Any] = sale_data.get("base_data") or {}
            badge: Dict[str, Any] = sale_data.get("badge") or {}

            sale = Sale(
                item_id=item.id,
                sold_at=sale_data["datetime"],
                price=sale_data["price"],
                base_price=base.get("base_price"),
                global_listings=base.get("global_listings"),
                float_value=sale_data["float"],
                paint_seed=sale_data["seed"],
                pattern_data=badge,
            )

            session.add(sale)
            session.flush()

            for sticker_data in sale_data.get("stickers", []):
                if not sticker_data.get("name"):
                    continue

                session.add(
                    Sticker(
                        sale_id=sale.id,
                        name=sticker_data["name"],
                        wear=sticker_data.get("wear"),
                        slot=sticker_data.get("slot"),
                        x=sticker_data.get("x"),
                        y=sticker_data.get("y"),
                        rotation=sticker_data.get("rotation"),
                        reference_price=sticker_data.get("reference_price"),
                        global_listings=sticker_data.get("global_listings"),
                    )
                )

            logger.debug(
                "Saved sale: %s | %s | %s",
                item.name,
                sale.price,
                sale.sold_at,
            )

            return sale

        except IntegrityError:
            session.rollback()
            logger.debug("Duplicate sale skipped")
            return None

        except Exception:
            session.rollback()
            logger.exception("Failed to save sale")
            raise

    def sale_exists(
        self,
        session,
        item_id: int,
        sold_at,
        price,
        paint_seed,
    ) -> bool:
        return (
            session.query(Sale.id)
            .filter_by(
                item_id=item_id,
                sold_at=sold_at,
                price=price,
                paint_seed=paint_seed,
            )
            .first()
            is not None
        )
