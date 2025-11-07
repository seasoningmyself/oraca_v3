"""
Base repository with database connection pooling.
"""
import asyncpg
from typing import Optional
from market_data.config import Config
from market_data.utils.logger import get_logger


class BaseRepository:
    """
    Base repository class with connection pooling.
    All repositories should inherit from this.
    """

    _pool: Optional[asyncpg.Pool] = None

    def __init__(self, config: Config):
        """
        Initialize repository with configuration.

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = get_logger(__name__)

    @classmethod
    async def create_pool(cls, config: Config) -> asyncpg.Pool:
        """
        Create a connection pool.

        Args:
            config: Configuration object

        Returns:
            asyncpg.Pool: Connection pool
        """
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                config.db_dsn,
                min_size=config.database.min_pool_size,
                max_size=config.database.max_pool_size
            )
        return cls._pool

    @classmethod
    async def close_pool(cls):
        """Close the connection pool"""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None

    async def get_pool(self) -> asyncpg.Pool:
        """Get the connection pool, creating it if necessary"""
        if self._pool is None:
            self._pool = await self.create_pool(self.config)
        return self._pool

    async def execute(self, query: str, *args):
        """
        Execute a query that doesn't return results.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Query execution result
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """
        Fetch multiple rows.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            List of records
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """
        Fetch a single row.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Single record or None
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """
        Fetch a single value.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Single value
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
