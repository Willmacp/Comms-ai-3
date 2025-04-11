import logging

import pytest

from app.lib.chat.chat_system_prompt import chat_system_prompt

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_return_type():
    response = await chat_system_prompt()
    logging.info(f"Generated system prompt: {response}")
    assert isinstance(response, str)
