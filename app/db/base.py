"""Declarative base for all SQLAlchemy ORM models.

A single shared base so Alembic's autogenerate can discover every mapped
table through one `Base.metadata`.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
