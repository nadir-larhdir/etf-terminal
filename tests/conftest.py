"""Shared fixtures. A real in-memory SQLite database is used for store tests, so the SQL
those stores emit is genuinely exercised rather than mocked away.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from db.schema import create_tables


@pytest.fixture
def engine() -> Iterator[Engine]:
    """A fresh, schema-migrated in-memory database per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    create_tables(engine)
    yield engine
    engine.dispose()
