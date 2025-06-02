from sqlalchemy import BigInteger, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import LocalBase


class OwOStat(LocalBase):
    __tablename__ = "owo_stats"
    __table_args__ = (UniqueConstraint("day", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    day: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    owo_count: Mapped[int] = mapped_column(Integer, default=0)
    hunt_count: Mapped[int] = mapped_column(Integer, default=0)
    battle_count: Mapped[int] = mapped_column(Integer, default=0)
    pray_count: Mapped[int] = mapped_column(Integer, default=0)
    curse_count: Mapped[int] = mapped_column(Integer, default=0)
