from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

class LocalBase(AsyncAttrs, DeclarativeBase):
    pass

class OnlineBase(AsyncAttrs, DeclarativeBase):
    pass