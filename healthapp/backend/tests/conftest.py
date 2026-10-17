import os
import pathlib
import uuid

import asyncpg
import pytest_asyncio

SCHEMA = pathlib.Path(__file__).parent.parent / "sql" / "001_schema.sql"


@pytest_asyncio.fixture
async def pool():
    """Needs a throwaway Postgres: TEST_DATABASE_URL=postgresql://user:pw@host/db
    (its public schema is wiped). Skipped when the variable is not set."""
    import pytest
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    p = await asyncpg.create_pool(url, min_size=1, max_size=4)
    async with p.acquire() as con:
        await con.execute("drop schema public cascade; create schema public;")
        await con.execute(SCHEMA.read_text())
    yield p
    await p.close()


@pytest_asyncio.fixture
async def user_id(pool):
    uid = uuid.uuid4()
    async with pool.acquire() as con:
        await con.execute("insert into users (id) values ($1)", uid)
    return uid
