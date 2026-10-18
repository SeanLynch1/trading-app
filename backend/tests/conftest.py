"""Shared test setup: a separate database, trading_test, rebuilt with the Alembic migrations on every run.

pytest loads this file automatically, so every test file can use the `session` fixture.
"""
import asyncio
import os

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import DATABASE_URL
from models import Base

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the backend folder, where alembic.ini lives
TEST_URL = os.getenv("TEST_DATABASE_URL", DATABASE_URL.rsplit("/", 1)[0] + "/trading_test")   # same server, other database
TEST_DB = TEST_URL.rsplit("/", 1)[1].split("?")[0]                       # "trading_test"


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Once per test run: recreate an empty trading_test database, then build its tables with Alembic."""
    async def recreate():
        server = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")   # asyncpg wants a plain postgresql:// address
        conn = await asyncpg.connect(server)                                 # connect to the main database...
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')   # ...to drop and recreate the test one
        await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
        await conn.close()
    asyncio.run(recreate())

    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL.replace("%", "%%"))       # point Alembic at the test database
    command.upgrade(cfg, "head")                                             # run every migration, like on a new server
    yield


@pytest_asyncio.fixture
async def session():
    """A fresh connection to the test database for one test. Tables are emptied afterwards."""
    engine = create_async_engine(TEST_URL)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    async with engine.begin() as conn:                                       # wipe every table, reset ids to 1
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest.fixture
def test_url():
    """The test database's address, for tests that need their own connection (e.g. test_api.py)."""
    return TEST_URL
