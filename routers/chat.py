# ruff: noqa: B008

import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from app.api import ENDPOINTS, endpoint_defaults
from app.api.api_paths import ApiPaths
from app.app_types.chat import (
    ChatRequest,
)
from app.app_types.responses import ChatSuccessResponse, ChatWithAllMessages, ChatWithLatestMessage
from app.database.table import (
    ChatTable,
    UserTable,
    async_db_session,
)
from app.lib.chat import (
    ChatCreateInput,
    chat_add_message,
    chat_create,
    chat_get_messages,
    chat_request_data,
    patch_chat_title,
    update_chat_title,
)

router = APIRouter()

logger = logging.getLogger()


def chat_validator(chat_uuid: str = Path(..., description="Chat UUID"), user_uuid: str = Path(...)):
    try:
        chat_uuid = UUID(chat_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'id' parameter '{chat_uuid}' is not a valid UUID",
        ) from e

    chat = ChatTable().get_by_uuid(chat_uuid)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No chat found with UUID '{chat_uuid}'",
        )

    user = UserTable().get_one_by("id", chat.user_id)
    if str(user.uuid) != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Access denied to chat '{chat_uuid}'",
        )

    return chat


chat_endpoint_defaults = {
    **endpoint_defaults(
        extra_dependencies=[
            ApiPaths.USER_UUID,
            # Depends(chat_common_params),
        ],
    ),
}


@router.post(ENDPOINTS.CHATS, **chat_endpoint_defaults, response_model=ChatWithLatestMessage)
async def create_new_chat(data=Depends(chat_request_data)):
    chat_input = ChatCreateInput(**data.dict())
    return await chat_create(chat_input)


@router.get(ENDPOINTS.CHAT_ITEM, **chat_endpoint_defaults, response_model=ChatWithAllMessages)
async def get_chat_entry(
    chat=Depends(chat_validator),
):
    logger.info("Calling chat item")
    return await chat_get_messages(chat)


@router.put(ENDPOINTS.CHAT_ITEM, **chat_endpoint_defaults, response_model=ChatWithLatestMessage)
async def add_new_chat_message(chat=Depends(chat_validator), data=Depends(chat_request_data)):
    return await chat_add_message(chat, data)


@router.get(
    ENDPOINTS.CHAT_MESSAGES,
    **chat_endpoint_defaults,
    response_model=ChatWithAllMessages,
)
async def get_chat_messages(
    chat=Depends(chat_validator),
):
    logger.info("Calling chat messages")
    return await chat_get_messages(chat)


@router.put(ENDPOINTS.CHAT_TITLE, **chat_endpoint_defaults)
async def create_chat_title(
    chat=Depends(chat_validator),
    data: ChatRequest = Body(...),
):
    async with async_db_session() as db_session:
        return await update_chat_title(db_session=db_session, chat=chat, data=data)


@router.get(ENDPOINTS.CHAT_TITLE, **chat_endpoint_defaults)
async def get_chat_title(chat=Depends(chat_validator)) -> ChatSuccessResponse:
    """
    Get the title of a chat.

    Args:
        chat: Chat object from chat_validator dependency

    Returns:
        ChatSuccessResponse: Response containing chat details including title
    """
    return ChatSuccessResponse(uuid=chat.uuid, created_at=chat.created_at, updated_at=chat.updated_at, title=chat.title)


@router.patch(ENDPOINTS.CHAT_TITLE, **chat_endpoint_defaults)
async def user_update_chat_title(
    chat=Depends(chat_validator), title: str = Body(..., embed=True)
) -> ChatSuccessResponse:
    """
    Update the title of an existing chat.

    Args:
        chat (Chat): Chat object obtained from chat_validator dependency.
            Contains the existing chat details and validates user permissions.
        title (str): The new title to be assigned to the chat.

    Returns:
        ChatSuccessResponse: Response object containing:
            - uuid: The chat's unique identifier
            - created_at: Original creation timestamp
            - updated_at: Last update timestamp
            - title: The newly updated chat title
            - status: Success status
            - status_message: Success message
    """
    async with async_db_session() as db_session:
        return await patch_chat_title(db_session=db_session, chat=chat, title=title)
