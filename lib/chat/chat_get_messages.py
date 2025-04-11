from app.api import api_wrapper
from app.app_types.responses import ChatWithAllMessages, Document, MessageBasicResponse
from app.database.db_operations import DbOperations
from app.database.models import Chat
from app.database.table import async_db_session


@api_wrapper(task="chat_get_messages")
async def chat_get_messages(chat: Chat):
    """
    Retrieves all messages for a specific chat, including related documents.
    Args:
        chat (Chat): The Chat instance representing the chat for which messages
                      are to be retrieved.

    Returns:
        ChatWithAllMessages: A response model containing the chat details and
                             a list of messages, including document details.

    """
    async with async_db_session() as db_session:
        chat = await DbOperations.get_chat_with_messages(db_session, chat.id, chat.user_id)
        chat_response = ChatWithAllMessages(
            uuid=chat.uuid,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            title=chat.title,
            from_open_chat=chat.from_open_chat,
            use_rag=chat.use_rag,
            use_gov_uk_search_api=chat.use_gov_uk_search_api,
            documents=[
                Document(
                    uuid=d.document_uuid,
                    name=d.document.name,
                    created_at=d.document.user_mappings[0].created_at,
                    expired_at=d.document.user_mappings[0].expired_at,
                    deleted_at=d.document.user_mappings[0].deleted_at,
                    last_used=d.document.user_mappings[0].last_used,
                )
                for d in chat.chat_document_mapping
            ],
            messages=[
                MessageBasicResponse(
                    uuid=m.uuid,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    content=m.content,
                    role=m.role,
                    interrupted=m.interrupted,
                    citation=m.citation or "",
                )
                for m in chat.messages
            ],
        )
        return chat_response
