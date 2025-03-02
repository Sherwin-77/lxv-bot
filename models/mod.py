from sqlalchemy import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Mod(BaseModel):
    __tablename__ = "mods"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)