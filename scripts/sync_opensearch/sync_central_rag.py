# ruff: noqa: E402
import asyncio
import logging
import sys
from pathlib import Path

# Add the root project directory to Python path at runtime
# This allows the script to import app modules
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from app.database.table import async_db_session
from app.services.opensearch import sync_central_index, sync_labour_index

logger = logging.getLogger(__name__)
if __name__ == "__main__":

    async def sync():
        async with async_db_session() as db_session:
            await sync_central_index(db_session)

        async with async_db_session() as db_session:
            await sync_labour_index(db_session)

    asyncio.run(sync())
