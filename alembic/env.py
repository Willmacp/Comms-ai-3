# ruff: noqa: E402
# adjust this to fit your actual Base import
import logging.config
import os
import sys

from alembic import context
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

logging.config.fileConfig("alembic.ini")
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_dir)

# Adjust this to fit your actual Base import
from database.models import Base

# Load with dotenv if it finds the .env file
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
print(f"Loading .env file from: {env_path}")
if os.path.exists(env_path):
    # By default load_dotenv doesn't overwrite existing environment variables
    # We must set it explicitly
    load_dotenv(env_path, override=True)
else:
    print(f".env file not found at: {env_path}")

print(f"alembic env.py is using POSTGRES_DB = {os.getenv('POSTGRES_DB')}")


def database_url():
    db_name = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")

    url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    return url


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.


def run_migrations_online():
    print("running migrations online")

    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    alembic_cfg = Config("alembic.ini")
    configuration = alembic_cfg.get_section(alembic_cfg.config_ini_section)

    configuration["sqlalchemy.url"] = database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)

        with context.begin_transaction():
            context.execute("SET search_path TO public")
            context.run_migrations()


""" Run all migrations """
run_migrations_online()
