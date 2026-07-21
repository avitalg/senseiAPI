from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


@lru_cache
def get_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(database_url), expire_on_commit=False)


async def get_db_session(settings: SettingsDep) -> AsyncGenerator[AsyncSession]:
    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        yield session


async def get_optional_db_session(
    settings: SettingsDep,
) -> AsyncGenerator[AsyncSession | None]:
    """Yield a DB session when configured; otherwise ``None`` (unit tests / no Postgres)."""
    if not settings.database_url:
        yield None
        return
    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
OptionalSessionDep = Annotated[AsyncSession | None, Depends(get_optional_db_session)]


async def _migrate_next_meeting_reports(conn: AsyncConnection) -> None:
    """Add meeting_id to legacy next_meeting_reports (pre meeting-bound schema)."""
    table_exists = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'next_meeting_reports'"
        )
    )
    if table_exists.scalar_one_or_none() is None:
        return

    cols = set(
        (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'next_meeting_reports'"
                )
            )
        )
        .scalars()
        .all()
    )
    if "meeting_id" in cols:
        return

    await conn.execute(text("DELETE FROM next_meeting_reports"))
    await conn.execute(
        text(
            "ALTER TABLE next_meeting_reports "
            "ADD COLUMN IF NOT EXISTS meeting_id UUID "
            "REFERENCES calendar_events(id) ON DELETE CASCADE"
        )
    )
    await conn.execute(
        text(
            "ALTER TABLE next_meeting_reports "
            "DROP CONSTRAINT IF EXISTS next_meeting_reports_patient_id_key"
        )
    )
    await conn.execute(
        text(
            "ALTER TABLE next_meeting_reports "
            "DROP CONSTRAINT IF EXISTS next_meeting_reports_meeting_id_key"
        )
    )
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_next_meeting_reports_meeting_id "
            "ON next_meeting_reports(meeting_id)"
        )
    )
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_next_meeting_reports_patient_id "
            "ON next_meeting_reports(patient_id)"
        )
    )
    await conn.execute(
        text("ALTER TABLE next_meeting_reports ALTER COLUMN meeting_id SET NOT NULL"),
    )


async def _migrate_patients_archive(conn: AsyncConnection) -> None:
    """Add archived / archived_at to legacy patients tables."""
    table_exists = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'patients'"
        )
    )
    if table_exists.scalar_one_or_none() is None:
        return

    cols = set(
        (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'patients'"
                )
            )
        )
        .scalars()
        .all()
    )
    if "archived" not in cols:
        await conn.execute(
            text("ALTER TABLE patients ADD COLUMN archived BOOLEAN NOT NULL DEFAULT false")
        )
    if "archived_at" not in cols:
        await conn.execute(text("ALTER TABLE patients ADD COLUMN archived_at TIMESTAMPTZ NULL"))


async def init_database(settings: Settings) -> None:
    """Create tables for all imported ORM models.

    ``create_all`` does not alter existing tables. If a stale ``users`` stub is
    missing auth columns (pre-security schema), recreate that table so
    register/token do not fail with 502.
    """
    if not settings.database_url:
        return

    import auth.orm  # noqa: F401
    import calendar_events.orm  # noqa: F401
    import patients.orm  # noqa: F401
    import reports.orm  # noqa: F401
    import summaries.orm  # noqa: F401
    import transcripts.orm  # noqa: F401

    engine = get_engine(settings.database_url)
    async with engine.begin() as conn:
        users_cols = (
            (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'users'"
                    )
                )
            )
            .scalars()
            .all()
        )
        if users_cols and "password_hash" not in set(users_cols):
            await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))

        await _migrate_next_meeting_reports(conn)
        await _migrate_patients_archive(conn)
        await conn.run_sync(Base.metadata.create_all)


async def ping_database(settings: Settings) -> bool:
    engine = get_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def close_database(database_url: str) -> None:
    engine = get_engine(database_url)
    await engine.dispose()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
