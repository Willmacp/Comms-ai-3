from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"


class MessageDefaults(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    chat_id: int
    auth_session_id: int
    interrupted: bool = False
    llm_id: int
    tokens: int = 0


class Message(BaseModel):
    uuid: str
    content: str
    role: RoleEnum
    redacted: bool = False
    redaction_message: str = ""
    redaction_alert_level: bool = False
    interrupted: bool = False


class ChatResponse(BaseModel):
    id: int
    uuid: UUID
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    user_id: int
    use_case_id: int
    title: str
    from_open_chat: bool
    use_rag: bool


class MessageResponse(BaseModel):
    uuid: UUID
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    content: str
    role: RoleEnum
    interrupted: bool
    citation: str


Messages = list[Message]


class DocumentAccessError(Exception):
    def __init__(self, *args, document_uuids: List[str]):
        super().__init__(*args)
        self.document_uuids = document_uuids
