from app.api import api_wrapper
from app.app_types import ChatBaseRequest
from app.app_types.responses import ChatWithLatestMessage
from app.database.table import (
    ChatTable,
)
from app.lib import logger

from .chat_create_message import ChatCreateMessageInput, chat_create_message


class ChatCreateInput(ChatBaseRequest):
    pass
    # generate_title: bool = False


@api_wrapper(task="create chat")
async def chat_create(input_data: ChatCreateInput) -> ChatWithLatestMessage:
    """
    Takes a chat creation request and creates a new chat with the message.
    Creates chat and message objects and saves them in the database,
    marks the message as the initial call (e.g. parent is null).
    if input request contains a use_case_id flag, then the chat is created from an open chat and use_case_id is set.

    Return a ChatWithLatestMessage instance, wrapping chat and the message details.
    """
    logger.debug("---------")
    logger.debug(f"{input_data=}")
    title = "New chat"

    from_open_chat = True
    if input_data.use_case_id:
        from_open_chat = False

    logger.debug("starting creating db item")
    chat_repo = ChatTable()
    chat = chat_repo.create(
        {
            "user_id": input_data.user_id,
            "from_open_chat": from_open_chat,
            "use_case_id": input_data.use_case_id,
            "title": title,
            "use_rag": input_data.use_rag,
            "use_gov_uk_search_api": input_data.use_gov_uk_search_api,
        }
    )
    logger.debug("starting create message")

    logger.debug(f"input_data.to_dict(): {input_data.to_dict()}")

    message = await chat_create_message(
        chat=chat, input_data=ChatCreateMessageInput(**input_data.to_dict(), initial_call=True)
    )

    logger.debug("starting return")

    if input_data.stream:
        return message

    return ChatWithLatestMessage(**chat.dict(), message=message.dict())
