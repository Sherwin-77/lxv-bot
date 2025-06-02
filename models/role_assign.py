from sqlalchemy import BIGINT, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import OnlineBase


class RoleAssign(OnlineBase):
    __tablename__ = "role_assigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    role_id: Mapped[int] = mapped_column(BIGINT, nullable=False, index=True)