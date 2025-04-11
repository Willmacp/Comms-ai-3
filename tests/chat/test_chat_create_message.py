import pytest

from app.database.models import Chat, Message
from app.lib.chat import ChatCreateMessageInput
from app.lib.chat.chat_create_message import chat_create_message


@pytest.mark.asyncio
async def test_rag_enhanced_content_used_in_subsequent_chat_message(mocker):
    """
    Test case for verifying RAG enhanced content usage in subsequent chat messages.
    It ensures that RAG-enhanced content from previous messages is correctly retrieved and included in subsequent
    chat conversations sent to the LLM.

    Verifies that the LLM invocation includes the correct conversation history, including RAG-enhanced content from
      previous messages and the new user message.
    """

    # setup mocks
    mocker.patch("app.lib.chat.chat_create_message.chat_save_llm_output")
    bedrock_handler = mocker.AsyncMock()
    mocker.patch("app.lib.chat.chat_create_message.BedrockHandler", return_value=bedrock_handler)
    message_table = mocker.Mock()
    mocker.patch("app.lib.chat.chat_create_message.MessageTable", return_value=message_table)
    mocker.patch("app.lib.chat.chat_create_message.LLMTable")

    # setup chat
    chat = Chat(id=1, user_id=1)

    # setup first chat message with initial_call=True
    first_msg = ChatCreateMessageInput(
        user_id=1, initial_call=True, query="Test message", auth_session_id=1, use_rag=True, use_case_id=1
    )

    # setup rag response for first and second chat messages
    run_rag = mocker.patch("app.lib.chat.chat_create_message.run_rag")
    first_message_response = ("first message enhanced", ["first dummy citations"])
    second_message_response = ("second message enhanced", ["second dummy citations"])
    run_rag.side_effect = [first_message_response, second_message_response]

    # first chat call.
    await chat_create_message(chat, first_msg)

    # setup messages stored in the db for the first message.
    messages = [
        Message(
            role="user",
            content="first message",
            content_enhanced_with_rag="first message enhanced",
            citation='["first dummy citations"]',
        ),
        Message(role="assistant", citation='["first dummy citations"]', content="AI generated content"),
    ]
    message_table.get_by_chat.return_value = messages

    # second chat call.
    second_message = ChatCreateMessageInput(
        user_id=1, query="Second message", auth_session_id=1, use_rag=True, use_case_id=1
    )
    await chat_create_message(chat, second_message)

    # assert LLM invocation contains previous RAG enhanced messages and current enhanced message.
    expected_invocation = [
        {
            "content": "first message enhanced",
            "role": "user",
        },
        {
            "content": "AI generated content",
            "role": "assistant",
        },
        {
            "content": "second message enhanced",
            "role": "user",
        },
    ]
    bedrock_handler.invoke_async.assert_called_with(expected_invocation)
