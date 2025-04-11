from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field


class SearchIndexResponse(BaseModel):
    # id: int
    uuid: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    name: str
    description: str


class ListSearchIndexResponse(BaseModel):
    search_indexes: List[SearchIndexResponse]


class DocumentChunkResponse(BaseModel):
    uuid: UUID4
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    document_name: str
    chunk_name: str
    chunk_content: str
    id_opensearch: str


class ListDocumentChunkResponse(BaseModel):
    document_chunks: List[DocumentChunkResponse]
