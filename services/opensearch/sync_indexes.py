import logging
from datetime import datetime

from opensearchpy import NotFoundError, TransportError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import Document, DocumentChunk, SearchIndex

from .opensearch import CENTRAL_RAG_INDEX_NAME, LABOUR_MANIFESTO_INDEX_NAME, OpenSearchRecord, create_client

logger = logging.getLogger(__name__)


async def sync_central_index(session: AsyncSession) -> bool:
    """Updates the Central RAG OpenSearch index to be in sync with the PostgreSQL tables."""

    logger.debug("Starting synchronization of OpenSearch with PostgreSQL...")
    opensearch_client = create_client()

    # Delete and recreate central index
    try:
        opensearch_client.indices.delete(index=CENTRAL_RAG_INDEX_NAME)
        logger.info(f"Deleted index: {CENTRAL_RAG_INDEX_NAME}")
    except NotFoundError:
        logger.warning(f"Index {CENTRAL_RAG_INDEX_NAME} not found in OpenSearch. Skipping deletion.")
    except Exception as e:
        logger.error(f"Failed to delete index {CENTRAL_RAG_INDEX_NAME}: {str(e)}")
        raise

    try:
        opensearch_client.indices.create(index=CENTRAL_RAG_INDEX_NAME)
        logger.debug(f"Created index: {CENTRAL_RAG_INDEX_NAME}")
    except Exception as e:
        logger.error(f"Failed to create index {CENTRAL_RAG_INDEX_NAME}: {str(e)}")
        raise

    try:
        # Get the central search index from PostgreSQL
        stmt = select(SearchIndex).where(SearchIndex.name == CENTRAL_RAG_INDEX_NAME)
        result = await session.execute(stmt)
        central_index = result.scalar_one()

        # Get all document chunks for this index
        stmt = select(DocumentChunk).where(
            DocumentChunk.search_index_id == central_index.id, DocumentChunk.deleted_at.is_(None)
        )
        result = await session.execute(stmt)
        chunks = result.scalars().all()

        # Get all documents
        stmt = select(Document).where(Document.deleted_at.is_(None))
        result = await session.execute(stmt)
        documents = result.scalars().all()

    except SQLAlchemyError as e:
        logger.error(f"Failed to query database: {str(e)}")
        raise

    try:
        # Add each chunk to OpenSearch and update PostgreSQL
        updated_at = datetime.now()
        for chunk in chunks:
            # Find associated document
            document = next((d for d in documents if d.id == chunk.document_id), None)
            if not document:
                logger.warning(f"No document found for chunk {chunk.uuid}, skipping")
                continue

            # Create OpenSearch record
            record = OpenSearchRecord(
                document_name=document.name,
                document_url=document.url,
                chunk_name=chunk.name,
                chunk_content=chunk.content,
                document_uuid=document.uuid,
            )

            try:
                # Index in OpenSearch
                response = opensearch_client.index(index=CENTRAL_RAG_INDEX_NAME, body=record.to_opensearch_dict())

                # Update PostgreSQL with new OpenSearch ID
                chunk.id_opensearch = response["_id"]
                chunk.updated_at = updated_at

            except TransportError as e:
                logger.error(f"OpenSearch indexing failed for chunk {chunk.uuid}: {str(e)}")
                raise

        try:
            await session.commit()
            logger.info("Successfully synchronized OpenSearch with PostgreSQL")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to commit changes to database: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Unexpected error during synchronization: {str(e)}")
        raise


async def sync_labour_index(session: AsyncSession) -> bool:
    """Updates the Labour Manifesto OpenSearch index to be in sync with the PostgreSQL tables."""

    logger.debug("Starting synchronization of OpenSearch with PostgreSQL...")
    opensearch_client = create_client()

    # Delete and recreate labour index
    try:
        opensearch_client.indices.delete(index=LABOUR_MANIFESTO_INDEX_NAME)
        logger.info(f"Deleted index: {LABOUR_MANIFESTO_INDEX_NAME}")
    except NotFoundError:
        logger.warning(f"Index {LABOUR_MANIFESTO_INDEX_NAME} not found in OpenSearch. Skipping deletion.")
    except Exception as e:
        logger.error(f"Failed to delete index {LABOUR_MANIFESTO_INDEX_NAME}: {str(e)}")
        raise

    try:
        opensearch_client.indices.create(index=LABOUR_MANIFESTO_INDEX_NAME)
        logger.debug(f"Created index: {LABOUR_MANIFESTO_INDEX_NAME}")
    except Exception as e:
        logger.error(f"Failed to create index {LABOUR_MANIFESTO_INDEX_NAME}: {str(e)}")
        raise

    try:
        # Get the labour search index from PostgreSQL
        stmt = select(SearchIndex).where(SearchIndex.name == LABOUR_MANIFESTO_INDEX_NAME)
        result = await session.execute(stmt)
        labour_index = result.scalar_one()

        # Get all document chunks for this index
        stmt = select(DocumentChunk).where(
            DocumentChunk.search_index_id == labour_index.id, DocumentChunk.deleted_at.is_(None)
        )
        result = await session.execute(stmt)
        chunks = result.scalars().all()

        # Get all documents
        stmt = select(Document).where(Document.deleted_at.is_(None))
        result = await session.execute(stmt)
        documents = result.scalars().all()

    except SQLAlchemyError as e:
        logger.error(f"Failed to query database: {str(e)}")
        raise

    try:
        # Add each chunk to OpenSearch and update PostgreSQL
        updated_at = datetime.now()
        for chunk in chunks:
            # Find associated document
            document = next((d for d in documents if d.id == chunk.document_id), None)
            if not document:
                logger.warning(f"No document found for chunk {chunk.uuid}, skipping")
                continue

            # Create OpenSearch record
            record = OpenSearchRecord(
                document_name=document.name,
                document_url=document.url,
                chunk_name=chunk.name,
                chunk_content=chunk.content,
                document_uuid=document.uuid,
            )

            try:
                # Index in OpenSearch
                response = opensearch_client.index(index=LABOUR_MANIFESTO_INDEX_NAME, body=record.to_opensearch_dict())

                # Update PostgreSQL with new OpenSearch ID
                chunk.id_opensearch = response["_id"]
                chunk.updated_at = updated_at

            except TransportError as e:
                logger.error(f"OpenSearch indexing failed for chunk {chunk.uuid}: {str(e)}")
                raise

        try:
            await session.commit()
            logger.info("Successfully synchronized OpenSearch with PostgreSQL")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to commit changes to database: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Unexpected error during synchronization: {str(e)}")
        raise
