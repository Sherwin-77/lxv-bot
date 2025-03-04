from sqlalchemy import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class CustomRole(BaseModel):
    __tablename__ = "custom_roles"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    role_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False, unique=True)