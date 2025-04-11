# ruff: noqa: B008
import logging

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api import ENDPOINTS
from app.lib.chat import chat_request_data
from app.lib.chat.chat_create import ChatCreateInput
from app.lib.chat.chat_methods import chat_add_message_stream, chat_create_stream
from app.routers.chat import chat_endpoint_defaults, chat_validator

router = APIRouter()
logger = logging.getLogger()


@router.post(ENDPOINTS.CHAT_CREATE_STREAM, **chat_endpoint_defaults)
async def create_new_chat_stream(data=Depends(chat_request_data)) -> StreamingResponse:
    logger.info("Calling new chat stream")
    return await chat_create_stream(ChatCreateInput(**data.dict()))


@router.put(ENDPOINTS.CHAT_UPDATE_STREAM, **chat_endpoint_defaults)
async def add_new_message_stream(chat=Depends(chat_validator), data=Depends(chat_request_data)):
    logger.info("Calling add message to chat stream")
    return await chat_add_message_stream(chat, data)
