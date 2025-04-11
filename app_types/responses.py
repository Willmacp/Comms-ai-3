from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, Field

from app.app_types.message import RoleEnum
from app.app_types.themes_use_cases import PrebuiltPrompt


class SuccessResponse(BaseModel):
    status: str = "success"
    status_message: str = "success"


class ItemResponse(BaseModel):
    uuid: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True


class ItemTitleResponse(ItemResponse):
    title: str


class ThemeResponseData(ItemTitleResponse):
    subtitle: str
    position: Optional[int] = None


class UseCaseResponseData(ItemTitleResponse):
    theme_uuid: UUID
    instruction: str
    user_input_form: str
    position: Optional[int] = None


class ThemeResponse(SuccessResponse, ThemeResponseData):
    pass


class ThemesResponse(SuccessResponse):
    themes: List[ThemeResponseData]


class UseCaseResponse(SuccessResponse, UseCaseResponseData):
    pass


class UseCasesResponse(SuccessResponse, ItemTitleResponse):
    use_cases: List[UseCaseResponseData]


class PrebuiltPromptsResponse(SuccessResponse):
    prompts: List[PrebuiltPrompt]


class Document(BaseModel):
    name: str
    uuid: UUID4
    created_at: datetime
    expired_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    last_used: Optional[datetime] = Field(default=None)


class MessageBasicResponse(ItemResponse):
    content: str
    role: RoleEnum
    redacted: bool = False
    redaction_message: str = ""
    redaction_alert_level: bool = False
    interrupted: bool = False
    citation: str = ""


class ChatBasicResponse(ItemTitleResponse):
    from_open_chat: bool
    use_rag: bool = True
    use_gov_uk_search_api: bool = False
    documents: Optional[List[Document]] = None


class UserChatsResponse(SuccessResponse, ItemResponse):
    chats: List[ChatBasicResponse] = []


class ChatSuccessResponse(SuccessResponse, ItemTitleResponse):
    pass


class ChatWithLatestMessage(SuccessResponse, ChatBasicResponse):
    message: MessageBasicResponse


class ChatWithAllMessages(SuccessResponse, ChatBasicResponse):
    messages: List[MessageBasicResponse] = []


class MessageFeedbackResponse(SuccessResponse, ItemResponse):
    pass
