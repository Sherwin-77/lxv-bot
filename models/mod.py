from sqlalchemy import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import OnlineBase


class Mod(OnlineBase):
    __tablename__ = "mods"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)