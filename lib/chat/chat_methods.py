from typing import Dict

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_wrapper
from app.app_types import ChatSuccessResponse
from app.app_types.responses import ChatWithLatestMessage
from app.database.db_operations import DbOperations
from app.database.models import Chat
from app.database.table import (
    async_db_session,
)
from app.lib.chat import (
    ChatCreateMessageInput,
    ChatTitleRequest,
    chat_create,
    chat_create_title,
)
from app.lib.chat.chat_create import ChatCreateInput
from app.lib.chat.chat_create_message import chat_create_message


@api_wrapper(task="chat_create_stream")
async def chat_create_stream(data: ChatCreateInput):
    data.stream = True
    response = await chat_create(data)

    return StreamingResponse(response, media_type="text/event-stream")


async def _chat_message_with_documents(chat: Chat, db_session: AsyncSession, request_input: Dict):
    """
    Checks if the chat item has documents referenced, then associates those documents under document_uuids key
     to the request input.
    Args:
        chat (Chat): The Chat object containing the chat information (e.g., `id`).
        db_session (AsyncSession): The asynchronous database session to be used for the query.
        request_input (Dict): The dictionary containing the initial request input.

    Returns:
        Dict: The updated request input dictionary, with "document_uuids" key if there are chat
        documents in the database.
    """
    chat_document_mappings = await DbOperations.fetch_undeleted_chat_documents(db_session, chat.user_id, chat.id)
    if chat_document_mappings:
        document_uuids = [str(doc.uuid) for doc in chat_document_mappings]
        request_input["document_uuids"] = document_uuids
    return request_input


@api_wrapper(task="chat_add_message_stream")
async def chat_add_message_stream(chat: Chat, data):
    chat_message = data.to_dict()
    # check if there are chat documents, then fetch and append them to the request
    async with async_db_session() as db_session:
        chat_message = await _chat_message_with_documents(chat, db_session, chat_message)

    response = await chat_create_message(chat, ChatCreateMessageInput(**chat_message, stream=True))
    return StreamingResponse(response, media_type="text/event-stream")


@api_wrapper(task="chat_add_message")
async def chat_add_message(chat: Chat, data):
    request_input = data.to_dict()
    # check if there are chat documents, then fetch and append them to the request
    async with async_db_session() as db_session:
        request_input = await _chat_message_with_documents(chat, db_session, request_input)

    message = await chat_create_message(chat, ChatCreateMessageInput(**request_input))

    return ChatWithLatestMessage(
        **chat.client_response(),
        message=message.client_response(),
    )


@api_wrapper(task="update_chat_title")
async def update_chat_title(db_session: AsyncSession, chat: Chat, data) -> ChatSuccessResponse:
    # update chat title
    title = await chat_create_title(ChatTitleRequest(**data.to_dict()))
    chat_result = await DbOperations.chat_update_title(db_session, chat, title)

    return ChatSuccessResponse(**chat_result.client_response())


@api_wrapper(task="patch_chat_title")
async def patch_chat_title(db_session: AsyncSession, chat: Chat, title) -> ChatSuccessResponse:
    """
    Updates the title of a chat.

    Args:
        db_session (AsyncSession): The active database session for performing the update.
        chat (Chat): The chat object to be updated.
        title (str): The new title to be assigned to the chat.

    Returns:
        ChatSuccessResponse: Response object containing:
            - uuid: The chat's unique identifier
            - created_at: Original creation timestamp
            - updated_at: Last update timestamp
            - title: The updated chat title
            - status: Success status
            - status_message: Success message

    Note:
        This method is wrapped with api_wrapper decorator for consistent error handling
        and uses existing DbOperations.chat_update_title for the actual database update.
    """
    chat_result = await DbOperations.chat_update_title(db_session, chat, title)

    return ChatSuccessResponse(**chat_result.client_response())
