import logging
import os

logger = logging.getLogger(__name__)


def database_url():
    db_name = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", 5432)

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
    logger.debug(f"Using sync database url: {url}")

    return url


def async_database_url():
    db_name = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", 5432)

    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    logger.debug(f"Using async database url: {url}")

    return url
