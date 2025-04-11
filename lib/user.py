from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_wrapper
from app.app_types.responses import ChatBasicResponse, UserChatsResponse
from app.database.db_operations import DbOperations
from app.database.models import User


@api_wrapper(task="get_all_user_chats")
async def get_all_user_chats(db_session: AsyncSession, user: User):
    chats = await DbOperations.get_chats_by_user(db_session=db_session, user_id=user.id)

    return UserChatsResponse(chats=[ChatBasicResponse.model_validate(chat) for chat in chats], **user.client_response())
