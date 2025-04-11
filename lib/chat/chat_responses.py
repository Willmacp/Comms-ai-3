from app.app_types.message import Message
from app.app_types.responses import ChatWithLatestMessage


def chat_response_with_latest_message(
    chat,
    message: Message,
):
    return ChatWithLatestMessage(
        **chat.client_response(),
        message=message.client_response(),
    )
