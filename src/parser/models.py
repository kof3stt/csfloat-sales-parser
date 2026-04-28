from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    DECIMAL,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Item(Base):
    """
    CS item entity (weapon/skin).

    Represents unique skin definition (not a specific sale).
    """

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    is_souvenir: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_stattrak: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sales: Mapped[List["Sale"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @staticmethod
    def from_hash_name(hash_name: str) -> "Item":
        """
        Create Item from CSFloat hash name string.
        """
        return Item(
            name=hash_name,
            is_souvenir=hash_name.startswith("Souvenir"),
            is_stattrak="StatTrak" in hash_name,
        )

    def __repr__(self) -> str:
        return f"Item(id={self.id}, name={self.name})"


class Sale(Base):
    """
    Market sale record for an item.
    """

    __tablename__ = "sale"

    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "sold_at",
            "price",
            "paint_seed",
            name="uq_sale_unique",
        ),
        Index("idx_sale_item_id", "item_id"),
        Index("idx_sale_seed", "paint_seed"),
        Index("idx_sale_pattern_data", "pattern_data", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    item_id: Mapped[int] = mapped_column(
        ForeignKey("item.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    sold_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)

    base_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    global_listings: Mapped[Optional[int]] = mapped_column(Integer)

    float_value: Mapped[Optional[float]] = mapped_column(Float)
    paint_seed: Mapped[Optional[int]] = mapped_column(SmallInteger)

    pattern_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    item: Mapped["Item"] = relationship(back_populates="sales")

    stickers: Mapped[List["Sticker"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Sale(id={self.id}, price={self.price}, "
            f"item_id={self.item_id}, sold_at={self.sold_at})"
        )


class Sticker(Base):
    """
    Sticker applied to a sale.
    """

    __tablename__ = "sticker"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sale.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)

    wear: Mapped[Optional[float]] = mapped_column(Float)
    slot: Mapped[Optional[int]] = mapped_column(SmallInteger)

    x: Mapped[Optional[float]] = mapped_column(Float)
    y: Mapped[Optional[float]] = mapped_column(Float)
    rotation: Mapped[Optional[float]] = mapped_column(Float)

    reference_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    global_listings: Mapped[Optional[int]] = mapped_column(SmallInteger)

    sale: Mapped["Sale"] = relationship(back_populates="stickers")

    def __repr__(self) -> str:
        return f"Sticker(id={self.id}, name={self.name}, slot={self.slot})"
