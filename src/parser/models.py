from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    DECIMAL,
    Text,
    SmallInteger,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Item(Base):
    """
    CS item entity (weapon/skin).

    Represents unique skin definition (not a specific sale).
    """

    __tablename__ = "item"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(Text, unique=True, nullable=False)
    is_souvenir = Column(Boolean, nullable=False, default=False)
    is_stattrak = Column(Boolean, nullable=False, default=False)

    sales = relationship(
        "Sale",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @classmethod
    def from_hash_name(cls, hash_name: str) -> "Item":
        """
        Create Item from CSFloat hash name string.
        """
        return cls(
            name=hash_name,
            is_souvenir=hash_name.startswith("Souvenir"),
            is_stattrak=hash_name.startswith("StatTrak"),
        )

    def __repr__(self) -> str:
        return f"Item(id={self.id}, name='{self.name}')"


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

    id = Column(Integer, primary_key=True, autoincrement=True)

    item_id = Column(
        Integer,
        ForeignKey("item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sold_at = Column(DateTime, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)

    base_price = Column(DECIMAL(10, 2))
    global_listings = Column(Integer)

    float_value = Column(Float)
    paint_seed = Column(SmallInteger)

    pattern_data = Column(JSONB)

    item = relationship("Item", back_populates="sales")
    stickers = relationship(
        "Sticker",
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

    id = Column(Integer, primary_key=True, autoincrement=True)

    sale_id = Column(
        Integer,
        ForeignKey("sale.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(Text, nullable=False)

    wear = Column(Float)
    slot = Column(SmallInteger)

    x = Column(Float)
    y = Column(Float)
    rotation = Column(Float)

    reference_price = Column(DECIMAL(10, 2))
    global_listings = Column(SmallInteger)

    sale = relationship("Sale", back_populates="stickers")

    def __repr__(self) -> str:
        return f"Sticker(id={self.id}, name='{self.name}', slot={self.slot})"
