import asyncio
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from app.api import ENDPOINTS
from app.services.bedrock import BedrockHandler, RunMode
from app.services.bedrock.bedrock_types import BedrockError

api = ENDPOINTS()
logger = logging.getLogger(__name__)


def test_bedrock_service_with_cross_region_inference_with_default_llm_model():
    bedrock = BedrockHandler()

    assert bedrock.model == "us.anthropic.claude-3-7-sonnet-20250219-v1:0"


def test_bedrock_service_with_cross_region_inference_with_selected_llm_model():
    llm = MagicMock()
    llm.model = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock = BedrockHandler(llm=llm)

    assert bedrock.model == "us.anthropic.claude-3-5-sonnet-20240620-v1:0"


def test_bedrock_service_with_no_cross_region_inference_with_selected_llm_model():
    llm = MagicMock()
    llm.model = "gpt-4o-2024-05-13"
    bedrock = BedrockHandler(llm=llm)

    assert bedrock.model == "gpt-4o-2024-05-13"


@patch("app.services.bedrock.bedrock.BedrockHandler._create_chat_title")
async def test_aws_region_failover_for_create_chat_title_success(mock_create_chat_title):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_create_chat_title.side_effect = [Exception("Transient error"), {"result": "success"}]
    title_message = {"role": "user", "content": "content"}
    result = await bedrock.create_chat_title([title_message])
    assert result == {"result": "success"}


@patch("app.services.bedrock.bedrock.BedrockHandler._create_chat_title")
async def test_aws_region_failover_for_create_chat_title_fail(mock_create_chat_title):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_create_chat_title.side_effect = Exception("Transient error1")
    title_message = {"role": "user", "content": "content"}
    with pytest.raises(BedrockError, match="Transient error1"):
        await bedrock.create_chat_title([title_message])


@patch("app.services.bedrock.bedrock.BedrockHandler._invoke_async")
async def test_aws_region_failover_for_llm_invoke_success(mock_invoke):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_invoke.side_effect = [Exception("Transient error invoke"), {"result": "success"}]
    messages = [{"role": "user", "content": "content"}]
    result = await bedrock.invoke_async(messages)
    assert result == {"result": "success"}


@patch("app.services.bedrock.bedrock.BedrockHandler._invoke_async")
async def test_aws_region_failover_for_llm_invoke_fail(mock_invoke, caplog):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_invoke.side_effect = Exception("Transient error invoke")

    messages = [{"role": "user", "content": "content"}]

    with pytest.raises(Exception, match="Transient error invoke"):
        await bedrock.invoke_async(messages)

    assert "Transient error invoke" in caplog.text


@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock.BedrockHandler._invoke_async_with_call_cost_details")
async def test_aws_region_failover_for_llm_invoke_async_success(mock_invoke):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_invoke.side_effect = [Exception("Transient error invoke"), {"result": "success"}]
    messages = [{"role": "user", "content": "content"}]
    result = await bedrock.invoke_async_with_call_cost_details(messages)
    assert result == {"result": "success"}


@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock.BedrockHandler._invoke_async_with_call_cost_details")
async def test_aws_region_failover_for_llm_invoke_async_fail(mock_invoke, caplog):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_invoke.side_effect = Exception("Transient error invoke")

    messages = [{"role": "user", "content": "content"}]

    with pytest.raises(BedrockError, match="Transient error invoke"):
        await bedrock.invoke_async_with_call_cost_details(messages)

    assert "Transient error invoke" in caplog.text


@patch("app.services.bedrock.bedrock.BedrockHandler._stream")
async def test_aws_region_failover_llm_stream_fail(mock_bedrock_stream, caplog):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)
    mock_bedrock_stream.side_effect = Exception("Transient error invoke")

    messages = [{"role": "user", "content": "content"}]
    system_message = "test system message"

    def _error(ex: Exception):
        return f"{ex}"

    result = bedrock.stream(messages, system=system_message, on_error=_error)

    assert await anext(result) == "Transient error invoke"
    assert "Transient error invoke" in caplog.text


@patch("app.services.bedrock.bedrock.BedrockHandler._stream")
async def test_aws_region_failover_llm_stream_success(mock_bedrock_stream):
    bedrock = BedrockHandler(mode=RunMode.ASYNC)

    # Creating an async generator to simulate the stream
    async def mock_stream_generator(messages, system, on_error, other_param):
        yield {"result": "success"}

    mock_bedrock_stream.side_effect = [
        Exception("Transient error invoke"),
        mock_stream_generator(None, None, None, None),
    ]
    messages = [{"role": "user", "content": "content"}]
    system_message = "test system message"

    def _error(ex: Exception):
        return f"{ex}"

    stream_result = bedrock.stream(messages, system=system_message, on_error=_error)
    assert await anext(stream_result) == {"result": "success"}


@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock.BedrockHandler._stream")
async def test_chat_returns_bedrock_error(mock_bedrock, async_client, user_id, async_http_requester, caplog):
    """
    Simulates and  tests AWS Bedrock error handled during a new chat request and Bedrock error returned as
    custom json message
    """

    async def _stream(*args, **kwargs):
        yield json.dumps({"result": "success"})
        raise Exception("Some Bedrock error")

    mock_bedrock.side_effect = _stream

    url = api.create_chat_stream(user_uuid=user_id)
    response = await async_http_requester(
        "chat_endpoint_bedrock_error",
        async_client.post,
        url,
        response_type="text",
        response_code=200,
        json={"query": "hello"},
    )
    text_response = str(response)
    assert '{"result": "success"}' in text_response
    assert '"error_code": "BEDROCK_SERVICE_ERROR", "error_message": "Some Bedrock error"' in text_response

    # check error is logged
    assert "AWS Bedrock error through streaming, exception: Some Bedrock error" in caplog.text


@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock.BedrockHandler._stream")
async def test_chat_add_message_returns_bedrock_error(
    mock_bedrock, chat, async_client, user_id, async_http_requester, caplog
):
    """
    Simulates and  tests AWS Bedrock error handled in a chat  and Bedrock error returned as
    http status code 200 and payload contains below json structure.

    """

    async def _stream(*args, **kwargs):
        yield json.dumps({"result": "success"})
        raise Exception("Some Bedrock error")

    mock_bedrock.side_effect = _stream
    url = api.get_chat_stream(user_uuid=user_id, chat_uuid=chat.uuid)
    response = await async_http_requester(
        "chat_add_message_endpoint_bedrock_error",
        async_client.put,
        url,
        response_code=200,
        response_type="text",
        json={"query": "hello"},
    )

    text_response = str(response)
    assert '{"result": "success"}' in text_response
    assert '"error_code": "BEDROCK_SERVICE_ERROR", "error_message": "Some Bedrock error"' in text_response

    # check error is logged
    assert "AWS Bedrock error through streaming, exception: Some Bedrock error" in caplog.text


@pytest.mark.asyncio
@patch("app.services.bedrock.bedrock.BedrockHandler._stream")
async def test_slow_streaming_process_does_not_block_fastapi(
    mock_bedrock, chat, async_client, user_id, async_http_requester, caplog
):
    """
    Simulates a slow streaming response and checks in  other requests that FastAPI is not blocked.
    """

    async def _stream(*args, **kwargs):
        await asyncio.sleep(10)
        yield json.dumps({"result": "success"})

    mock_bedrock.side_effect = _stream
    url = api.get_chat_stream(user_uuid=user_id, chat_uuid=chat.uuid)
    chat_stream_request = async_http_requester(
        "chat_add_message_endpoint_slow_response_timeout",
        async_client.put,
        url,
        response_code=200,
        response_type="text",
        json={"query": "hello"},
    )

    # check health endpoint
    url = api.get_chat_item(user_uuid=user_id, chat_uuid=chat.uuid)
    chat_item_requests = [
        async_http_requester(
            "chat_add_message_endpoint_slow_response_timeout",
            async_client.get,
            url,
            response_code=200,
            response_type="json",
        )
        for _ in range(3)
    ]

    results = await asyncio.gather(chat_stream_request, *chat_item_requests, return_exceptions=True)
    # expect a string response
    assert results[0] == b'{"result": "success"}'
    # assert no exceptions
    assert all(not isinstance(r, Exception) for r in results)
