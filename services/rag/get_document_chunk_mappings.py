import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import Document, DocumentChunk, Message, MessageDocumentChunkMapping, SearchIndex

from .rag_types import RetrievalResult

logger = logging.getLogger(__name__)


async def get_document_chunk_mappings(
    chunks: List[dict], index: SearchIndex, message: Message, session: AsyncSession, use_chunk: Optional[bool] = None
) -> List[RetrievalResult]:
    """
    Processes a list of document chunks, creates mappings between messages and document chunks,
    and returns a list of RetrievalResult objects.
    """
    retrieval_results = []
    for hit in chunks:
        id_opensearch = hit["_id"]
        logger.debug("get_document_chunk_mappings-id_opensearch %s", id_opensearch)

        execute = await session.execute(select(DocumentChunk).filter(DocumentChunk.id_opensearch == id_opensearch))
        doc_chunk = execute.scalar_one_or_none()
        if not doc_chunk:
            logger.warning(f"DocumentChunk not found for id_opensearch: {id_opensearch}")
            continue

        message_document_chunk_mapping = MessageDocumentChunkMapping(
            message_id=message.id, document_chunk_id=doc_chunk.id, opensearch_score=hit["_score"]
        )
        if use_chunk is not None:
            message_document_chunk_mapping.use_document_chunk = use_chunk

        session.add(message_document_chunk_mapping)

        execute = await session.execute(select(Document).filter(Document.id == doc_chunk.document_id))
        document = execute.scalar_one()

        retrieval_result = RetrievalResult(
            search_index=index,
            document_chunk=doc_chunk,
            document=document,
            message_document_chunk_mapping=message_document_chunk_mapping,
        )

        retrieval_results.append(retrieval_result)

    return retrieval_results
