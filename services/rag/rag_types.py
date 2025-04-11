# ruff: noqa: A005
from dataclasses import dataclass
from typing import List, Optional

from app.database.models import (
    Document,
    DocumentChunk,
    MessageDocumentChunkMapping,
    SearchIndex,
)


# This class collects various SqlAlchemy data objects into a single object to be passed around
@dataclass
class RetrievalResult:
    search_index: SearchIndex
    document_chunk: DocumentChunk
    document: Document
    message_document_chunk_mapping: MessageDocumentChunkMapping = None


@dataclass
class RagRequest:
    use_central_rag: bool
    user_id: int
    query: str
    document_uuids: Optional[List[str]] = None
