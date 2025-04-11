import json
from typing import Dict

from app.app_types.message import RoleEnum
from app.database.models import Chat
from app.lib import logger
from app.services.bedrock.bedrock_types import BedrockError, BedrockErrorType


def chat_stream_message(chat: Chat, message_uuid: str, content: str, citations: str) -> Dict:
    response = {
        **chat.client_response(),
        "message_streamed": {
            "uuid": str(message_uuid),
            "role": RoleEnum.assistant,
            "content": content,
            "citations": citations,
        },
    }

    logger.debug(f"API chat_stream_message: {json.dumps(response, indent=5)}")

    return response


def chat_stream_error_message(chat: Chat, ex: Exception, has_documents: bool, is_initial_call: bool) -> str:
    if isinstance(ex, BedrockError) and ex.error_type == BedrockErrorType.INPUT_TOO_LONG:
        if has_documents:
            error_message = "Input is too long, too many documents selected, select fewer documents"
        else:
            if is_initial_call:
                error_message = "Input is too long, reduce input text"
            else:
                error_message = "Input is too long, reduce input text or start a new chat with reduced input text"

        response = {
            **chat.client_response(),
            "error_code": "BEDROCK_SERVICE_INPUT_TOO_LONG_ERROR",
            "error_message": error_message,
        }
    else:
        response = {**chat.client_response(), "error_code": "BEDROCK_SERVICE_ERROR", "error_message": str(ex)}

    logger.debug(f"API chat_stream_message: {json.dumps(response, indent=5)}")

    return json.dumps(response)
