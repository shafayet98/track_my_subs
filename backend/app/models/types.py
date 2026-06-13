"""Shared column helpers used across models."""

import uuid

from sqlalchemy import String
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Portable UUID column: stored as CHAR(36) so it works on Postgres and SQLite."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value


def uuid_pk() -> uuid.UUID:
    return uuid.uuid4()


# Alias for readability in models
StringType = String
