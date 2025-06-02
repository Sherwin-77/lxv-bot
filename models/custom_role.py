from sqlalchemy import BIGINT, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import OnlineBase


class CustomRole(OnlineBase):
    __tablename__ = "custom_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False, unique=True)