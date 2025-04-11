import os
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.app_types.message import Messages
from app.app_types.requests import RequestModel, RequestStandard

TEST_DEFAULT_QUERY = os.getenv("TEST_DEFAULT_QUERY", "")


class ChatLLMResponse(BaseModel):
    content: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]


class ChatBaseRequest(RequestStandard):
    query: str = ""
    system: str = ""
    stream: bool = False
    parent_message_id: Optional[str] = None
    user_group_ids: Optional[List[int]] = []
    use_case_id: Optional[int]
    use_rag: bool = True
    use_gov_uk_search_api: bool = False
    enable_web_browsing: bool = False
    document_uuids: Optional[List[str]] = None


class ChatQueryRequest(RequestModel):
    query: str = Field(TEST_DEFAULT_QUERY)


class ChatRequest(ChatQueryRequest):
    use_case_id: Optional[str] = ""
    use_rag: bool = True
    use_gov_uk_search_api: bool = False
    document_uuids: Optional[List[str]] = None

    @field_validator("query")
    def validate_query(cls, v):
        if not v:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'query' is not present in the request body.",
            )

        return v


class ChatPost(ChatRequest):
    pass


class ChatPut(ChatPost):
    parent_message_id: str = Field(
        None,
        description="The UUID of the parent message to which the new message should be appended.",
    )


class ChatUpsert(BaseModel):
    query: str
    session_id: str
    messages: Messages = []


class MessageFeedbackEnum(int, Enum):
    positive = 1
    negative = -1
    removed = 0


class FeedbackRequest(RequestModel):
    score: int
    freetext: Optional[str] = None
    label: Optional[str] = None


class FeedbackLabelResponse(BaseModel):
    uuid: UUID
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    label: str


class FeedbackLabelListResponse(BaseModel):
    feedback_labels: List[FeedbackLabelResponse]


class ChatCreateMessageInput(ChatBaseRequest):
    use_case: Optional[Any] = None
    initial_call: bool = False
