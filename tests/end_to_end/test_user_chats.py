import logging
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from opensearchpy import RequestError, TransportError
from pydantic import ValidationError

# from pydantic import ValidationError
from sqlalchemy.future import select

from app.api import ENDPOINTS, ApiConfig
from app.app_types import ChatWithLatestMessage, FeedbackRequest, ItemTitleResponse
from app.database.models import LLM, Chat, Message, MessageSearchIndexMapping
from app.database.table import ChatTable, FeedbackLabelTable, FeedbackTable
from app.lib.chat.chat_create_message import ChatCreateMessageInput, chat_create_message
from app.lib.llm import LLMTransaction
from app.services.bedrock import BedrockHandler
from tests.mock_request import fail_test

logger = logging.getLogger(__name__)

api = ENDPOINTS()


def validate_message_response(message):
    try:
        if not isinstance(message["content"], str):
            fail_test(f"Message content '{message['content']}' is not a string")
        if message["role"] not in ["user", "assistant"]:
            fail_test(f"Role '{message['role']}' is not valid")

        print("returned successful message from response:", message)

    except (ValidationError, ValueError, KeyError) as e:
        fail_test("Validation failed", e)


def validate_chat_response(response_data, message=True):
    try:
        logger.debug("Validating chat response structure and data app_types.")
        if "uuid" not in response_data:
            fail_test("UUID key is missing in response data")
        uuid.UUID(response_data["uuid"])
        logger.debug("Valid UUID confirmed for chat response.")

        # Check for 'use_rag' key and validate it
        if "use_rag" not in response_data:
            fail_test("use_rag key is missing in chat response data")
        if not isinstance(response_data["use_rag"], bool):
            fail_test("use_rag key is not of boolean type")
        logger.debug("use_rag key is present and is of boolean type : " + str(response_data["use_rag"]))

        # check for use_gov_uk_search_api key and validate it
        if "use_gov_uk_search_api" not in response_data:
            fail_test("use_gov_uk_search_api key is missing in chat response data")
        if not isinstance(response_data["use_gov_uk_search_api"], bool):
            fail_test("use_gov_uk_search_api key is not of boolean type")
        logger.debug(
            "use_gov_uk_search_api key is present and is of boolean type : "
            + str(response_data["use_gov_uk_search_api"])
        )

        if message:
            if "message" not in response_data:
                fail_test("Message key is missing in response data")
            validate_message_response(response_data["message"])

    except (ValidationError, ValueError, KeyError) as e:
        fail_test("Validation failed", e)


class TestUserChats:
    # Tests for GET requests to /user/chats/{id}
    # Test the happy path
    @pytest.mark.asyncio
    async def test_get_user_chats_id(self, async_client, user_id, async_http_requester, session):
        logger.debug("Test the happy path for GET requests to /user/chats/{id}")

        get_url = api.get_chats_by_user(user_id)
        get_response = await async_http_requester("get all chats by user UUID", async_client.get, get_url)

        logging.info(f"GET Response body: {get_response}")

        assert get_response, "The response was empty."
        assert get_response != "", "The response was empty."
        assert isinstance(get_response["chats"], list), "The response was not a list."

    # Tests for GET requests to /user/chats/{id}
    # Test the 400 response (Unauthorised) path
    @pytest.mark.asyncio
    async def test_get_user_chats_id_unauthorised(self, async_client, user_id, async_http_requester, session):
        logger.debug("Test the 400 response (Unauthorised) path for GET requests to /user/chats/{id}")

        non_existent_user_id = uuid.uuid4()
        logger.debug(f"Overriding user_id: {user_id} with {non_existent_user_id}")

        get_url = api.get_chats_by_user(non_existent_user_id)
        get_response = await async_http_requester(
            "get all chats by user UUID", async_client.get, get_url, response_code=400
        )

        logging.info(f"GET Response body: {get_response}")

        assert {"detail": "user UUIDs do not match"} == get_response


class TestUserChatsV1:
    async def test_accessing_another_user_chat_denied(
        self,
        chat,
        user_id,
        async_client,
        async_http_requester,
        auth_token,
        another_user_auth_session,
    ):
        # create endpoint with other user
        non_owning_user = str(uuid.uuid4())
        # create session for other user
        other_session = await another_user_auth_session(non_owning_user)

        non_owning_user_session_params = {
            ApiConfig.USER_KEY_UUID_ALIAS: non_owning_user,
            ApiConfig.SESSION_AUTH_ALIAS: other_session,
            ApiConfig.AUTH_TOKEN_ALIAS: auth_token,
        }
        chat_url = api.get_chat_item(non_owning_user, chat.uuid)
        response = await async_http_requester(
            "get_chat_item",
            async_client.get,
            chat_url,
            response_code=401,
            headers=non_owning_user_session_params,
        )
        assert response == {"detail": f"Access denied to chat '{chat.uuid}'"}

    async def test_accessing_another_user_chat_messages_denied(
        self,
        chat,
        user_id,
        async_client,
        async_http_requester,
        auth_token,
        another_user_auth_session,
    ):
        # create endpoint with other user
        non_owning_user = str(uuid.uuid4())
        # create session for other user
        other_session = await another_user_auth_session(non_owning_user)

        non_owning_user_session_params = {
            ApiConfig.USER_KEY_UUID_ALIAS: non_owning_user,
            ApiConfig.SESSION_AUTH_ALIAS: other_session,
            ApiConfig.AUTH_TOKEN_ALIAS: auth_token,
        }
        chat_messages_url = api.get_chat_messages(non_owning_user, chat.uuid)
        response = await async_http_requester(
            "get_chat_messages",
            async_client.get,
            chat_messages_url,
            response_code=401,
            headers=non_owning_user_session_params,
        )
        assert response == {"detail": f"Access denied to chat '{chat.uuid}'"}

    async def test_posting_another_user_chat_messages_denied(
        self,
        chat,
        user_id,
        async_client,
        async_http_requester,
        auth_token,
        another_user_auth_session,
    ):
        # create endpoint with other user
        non_owning_user = str(uuid.uuid4())
        # create session for other user
        other_session = await another_user_auth_session(non_owning_user)

        non_owning_user_session_params = {
            ApiConfig.USER_KEY_UUID_ALIAS: non_owning_user,
            ApiConfig.SESSION_AUTH_ALIAS: other_session,
            ApiConfig.AUTH_TOKEN_ALIAS: auth_token,
        }
        chat_messages_url = api.get_chat_item(non_owning_user, chat.uuid)
        response = await async_http_requester(
            "posting_to_another_user_chat",
            async_client.put,
            chat_messages_url,
            response_code=401,
            headers=non_owning_user_session_params,
        )
        assert response == {"detail": f"Access denied to chat '{chat.uuid}'"}

    async def test_create_chat_title_for_another_user_chat_denied(
        self,
        chat,
        user_id,
        async_client,
        async_http_requester,
        auth_token,
        another_user_auth_session,
    ):
        # create endpoint with other user
        non_owning_user = str(uuid.uuid4())
        # create session for other user
        other_session = await another_user_auth_session(non_owning_user)

        non_owning_user_session_params = {
            ApiConfig.USER_KEY_UUID_ALIAS: non_owning_user,
            ApiConfig.SESSION_AUTH_ALIAS: other_session,
            ApiConfig.AUTH_TOKEN_ALIAS: auth_token,
        }
        chat_messages_url = api.create_chat_title(non_owning_user, chat.uuid)
        response = await async_http_requester(
            "create_chat_title",
            async_client.put,
            chat_messages_url,
            response_code=401,
            headers=non_owning_user_session_params,
        )
        assert response == {"detail": f"Access denied to chat '{chat.uuid}'"}

    async def test_add_message_to_chat_stream_for_another_user_chat_denied(
        self,
        chat,
        user_id,
        async_client,
        async_http_requester,
        auth_token,
        another_user_auth_session,
    ):
        # create endpoint with other user
        non_owning_user = str(uuid.uuid4())
        # create session for other user
        other_session = await another_user_auth_session(non_owning_user)

        non_owning_user_session_params = {
            ApiConfig.USER_KEY_UUID_ALIAS: non_owning_user,
            ApiConfig.SESSION_AUTH_ALIAS: other_session,
            ApiConfig.AUTH_TOKEN_ALIAS: auth_token,
        }
        chat_messages_url = api.get_chat_stream(non_owning_user, chat.uuid)
        response = await async_http_requester(
            "create_chat_title",
            async_client.put,
            chat_messages_url,
            response_code=401,
            headers=non_owning_user_session_params,
        )
        assert response == {"detail": f"Access denied to chat '{chat.uuid}'"}

    @pytest.mark.asyncio
    async def test_post_chat(self, async_client, user_id, async_http_requester):
        logger.debug(f"Creating chat for user ID: {user_id}")
        url = api.chats(user_uuid=user_id)
        response = await async_http_requester("chat_endpoint", async_client.post, url, json={"query": "hello"})
        validate_chat_response(response)

    @pytest.mark.asyncio
    async def test_post_chat_unauthorised(self, async_client, user_id, async_http_requester):
        logger.debug("Test the 400 response (Unauthorised) path for GET requests to /user/chats/")

        non_existent_user_id = uuid.uuid4()
        logger.debug(f"Overriding user_id: {user_id} with {non_existent_user_id}")

        logger.debug(f"Creating chat for user ID: {non_existent_user_id}")
        url = api.chats(user_uuid=non_existent_user_id)
        post_response = await async_http_requester(
            "chat_endpoint",
            async_client.post,
            url,
            response_code=400,
            json={"query": "hello"},
        )

        logger.debug(f"GET Response body: {post_response}")
        assert {"detail": "user UUIDs do not match"} == post_response

    @pytest.mark.asyncio
    async def test_get_chat(self, async_client, chat_item, user_id, async_http_requester):
        url = api.get_chat_item(user_id, chat_item["uuid"])
        logger.debug(f"GET chat_endpoint: {url}")
        data = await async_http_requester("test_get_chat", async_client.get, url)

        validate_chat_response(data, message=False)
        previous_timestamp = None
        for message in data["messages"]:
            validate_message_response(message)

            current_timestamp = message["created_at"]
            if previous_timestamp is not None:
                assert current_timestamp >= previous_timestamp, "Messages are not in the correct order"

            previous_timestamp = current_timestamp

    @pytest.mark.asyncio
    async def test_put_chat(self, async_client, chat_item, user_id, async_http_requester):
        url = api.get_chat_item(user_id, chat_item["uuid"])
        response = await async_http_requester("test_put_chat", async_client.put, url, json={"query": "how are you"})

        validate_chat_response(response)
        logger.debug("test_put_chat passed.")

    @pytest.mark.asyncio
    async def test_chat_create_message_no_rag(self, monkeypatch, mocker, mock_message_table, mock_bedrock_handler):
        monkeypatch.setenv("USE_RAG", "true")

        input_data = ChatCreateMessageInput(
            query="hey",
            user_id=1,
            initial_call=True,
            auth_session_id=1,
            user_group_ids=[],
            stream=True,
            system="",
            use_rag=False,
            use_case_id=None,
        )

        chat = Mock()
        chat.id = 123

        mock_run_rag = mocker.patch("app.lib.chat.chat_create_message.run_rag")
        await chat_create_message(chat, input_data)
        mock_run_rag.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_response(self, async_client, user_id, async_http_requester):
        """
        Checks that a long response can be generated and is at least 1800 characters long.
        """
        # Although the test is for 1800 characters, we request the LLM to produce
        # an answer that is 2000 characters to give it room for error.

        # Previously, the default LiteLLM settings resulted in answers that
        # were about 1200 characters long and would stop mid-sentence.
        # The LiteLLM max_token has been manually set to counteract this.
        # On gpt-4-turbo-2024-04-09 the response to this prompt has 3914 characters (accessed on 2024-05-07).
        prompt_for_long_response = """Give me 10 ideas for using Large Language Models in GCS.
        For each idea identify a risk. Make sure the response is at least 2500 tokens long."""
        logger.debug("Testing that a long response can be generated in full.")
        url = api.chats(user_uuid=user_id)
        response_data = await async_http_requester(
            "test_long_response",
            async_client.post,
            url,
            json={"query": prompt_for_long_response},
        )

        message = response_data["message"]
        if message["role"] == "assistant":
            test_string = message["content"]

            logger.debug(f"Long chat generated: '{test_string}'")
            if len(test_string) < 1800:
                fail_test(
                    f"The response from the LLM was not long enough. Length: {len(test_string)}. "
                    "Response: {test_string}"
                )

        logger.debug("test_long_response passed")

    # @pytest.mark.asyncio
    async def test_create_chat_title_does_not_interfere_with_previous_chats(
        self, async_client, chat, user_id, async_http_requester, caplog
    ):
        """
        Creates two chat and chat titles, and checks second chat title does not use messages constructed for the first
        chat. Each chat title creation should use its own messages, and should not interfere with other chat messages.
        """
        with patch.object(
            BedrockHandler,
            "create_chat_title",
            return_value=LLMTransaction(
                input_tokens=1,
                output_tokens=1,
                input_cost=0,
                output_cost=0,
                completion_cost=0,
                content="",
            ),
        ) as mock_create_chat_title:
            mocked_first_chat_content = "random chat text"

            create_chat_title_url = api.create_chat_title(user_uuid=user_id, chat_uuid=chat.uuid)
            await async_http_requester(
                "test_create_chat_title_does_not_interfere_with_previous_chats",
                async_client.put,
                create_chat_title_url,
                json={"query": mocked_first_chat_content},
            )

            args, kwargs = mock_create_chat_title.call_args

            assert len(args) == 1  # check only one-message length array constructed when calling LLM
            function_arg = args[0]
            title_content_dict = function_arg[0]  # it is a list with dictionary
            assert mocked_first_chat_content in title_content_dict["content"]

            # make another chat
            url = api.chats(user_uuid=user_id)
            response = await async_http_requester(
                "chat_endpoint",
                async_client.post,
                url,
                json={"query": "generate a number between 0 and 10 and only include the number in the response"},
            )
            mocked_second_chat_content = "this is a different chat"

            chat2 = ChatWithLatestMessage(**response)

            # generate chat title for the second chat
            create_chat_title_url = api.create_chat_title(user_uuid=user_id, chat_uuid=chat2.uuid)
            await async_http_requester(
                "test_create_chat_title_does_not_interfere_with_previous_chats",
                async_client.put,
                create_chat_title_url,
                json={"query": mocked_second_chat_content},
            )

            args, _ = mock_create_chat_title.call_args

            assert len(args) == 1  # check only one-message length array constructed when calling LLM
            function_arg = args[0]
            title_content_dict = function_arg[0]  # it is a list with dictionary

            assert mocked_first_chat_content not in title_content_dict["content"]
            assert mocked_second_chat_content in title_content_dict["content"]

    # Chat title generation tests
    async def test_create_chat_title_success(self, async_client, user_id, chat, async_http_requester):
        """
        Creates a new chat and tests the chat_create_title function with a successful response.
        Checks Chat title has been updated with the generated title in the database.
        """

        chat_content = chat.message.content
        create_chat_title_url = api.create_chat_title(user_uuid=user_id, chat_uuid=chat.uuid)
        title_success_response = await async_http_requester(
            "test_create_title_success",
            async_client.put,
            create_chat_title_url,
            json={"query": chat_content},
        )

        chat_response = ItemTitleResponse(**title_success_response)
        title = chat_response.title
        assert len(title) < 255, f"Chat title is too long (max 255 characters), received: {title}"
        chat_model = ChatTable().get_by_uuid(chat.uuid)
        assert chat_model.title == title

    @pytest.mark.asyncio
    async def test_create_chat_title_too_long_is_logged_and_trimmed(
        self, async_client, user_id, chat, async_http_requester, caplog
    ):
        """
        Creates a new chat and tests the chat_create_title function with a title that is too long.
        Mocks the BedrockHandler create_chat_title method to return a long response.
        Checks Chat title has been updated with the generated title in the database.
        """
        with patch.object(
            BedrockHandler,
            "create_chat_title",
            return_value=LLMTransaction(
                input_tokens=1,
                output_tokens=1,
                input_cost=0,
                output_cost=0,
                completion_cost=0,
                content="X" * 256,
            ),
        ):
            chat_content = chat.message.content
            create_chat_title_url = api.create_chat_title(user_uuid=user_id, chat_uuid=chat.uuid)
            title_response = await async_http_requester(
                "test_create_chat_title_too_long_is_logged",
                async_client.put,
                create_chat_title_url,
                json={"query": chat_content},
            )

            chat_response = ItemTitleResponse(**title_response)
            title = chat_response.title
            assert len(title) == 255
            assert "Title exceeds 255 characters. Truncating:" in caplog.text
            chat_model = ChatTable().get_by_uuid(chat.uuid)
            assert chat_model.title == title

    async def test_create_chat_title_throws_exception(self, async_client, user_id, chat, async_http_requester, caplog):
        """
        Creates a new chat and tests the chat_create_title function throwing an exception.
        Mocks the BedrockHandler create_chat_title method to throw an exception.
        Checks an exception is thrown and logged.
        """
        excepted_exception = Exception("An error occurred")
        with patch.object(BedrockHandler, "create_chat_title", side_effect=excepted_exception):
            chat_content = chat.message.content
            create_chat_title_url = api.create_chat_title(user_uuid=user_id, chat_uuid=chat.uuid)

            with pytest.raises(Exception) as ex:
                await async_http_requester(
                    "test_create_chat_title_too_long_is_logged",
                    async_client.put,
                    create_chat_title_url,
                    response_code=500,
                    json={"query": chat_content},
                )
                assert ex == excepted_exception

            assert "Error in chat_create_title:" in caplog.text

    # Chat message id and parent id association test
    @pytest.mark.asyncio
    async def test_create_chat_messages_linked_by_parent_id(
        self, async_client, user_id, chat, async_http_requester, db_session, caplog
    ):
        """
        Creates a new chat and sends two messages to the chat.
        Checks that messages are linked by parent_message_id in the database.
        Checks that the role of the messages are correct,
        where first message's role is user and second message's role is assistant.
        """

        # second text
        create_chat_message_url = api.get_chat_item(user_uuid=user_id, chat_uuid=chat.uuid)
        await async_http_requester(
            "test_create_chat_messages_linked_by_parent_id",
            async_client.put,
            create_chat_message_url,
            json={"query": "Shorten the answer"},
        )

        # third text
        create_chat_message_url = api.get_chat_item(user_uuid=user_id, chat_uuid=chat.uuid)
        await async_http_requester(
            "test_create_chat_messages_linked_by_parent_id",
            async_client.put,
            create_chat_message_url,
            json={"query": "Lengthen the answer"},
        )

        execute = await db_session.execute(select(Chat).filter(Chat.uuid == chat.uuid))
        chat_model = execute.scalar_one()
        execute = await db_session.execute(
            select(Message).filter(Message.chat_id == chat_model.id).order_by(Message.created_at)
        )
        messages = list(execute.scalars())
        assert len(messages) == 6, f"Expected 6 messages, but got {len(messages)}"
        for idx, message in enumerate(messages):
            if idx == 0:
                assert message.parent_message_id is None
            else:
                assert message.parent_message_id == messages[idx - 1].id

            # assert roles, first message is user, second is assistant
            if idx % 2 == 0:
                assert message.role == "user"
            else:
                assert message.role == "assistant"
        assert messages[1].content == chat.message.content, "Assistant's first response is empty"
        assert messages[2].content == "Shorten the answer", "Second user message content doesn't match"
        assert messages[3].content != "", "Assistant's second response is empty"
        assert messages[4].content == "Lengthen the answer", "Third user message content doesn't match"
        assert messages[5].content != "", "Assistant's third response is empty"

        assert all(message.chat_id == chat_model.id for message in messages), (
            "Not all messages have the correct chat_id"
        )

    @pytest.mark.asyncio
    async def test_calculate_message_completion_cost(
        self, async_client, user_id, chat, async_http_requester, db_session, caplog
    ):
        """
        Creates a new chat and sends two messages to the chat.
        Checks that message completion cost is calculated correctly
        and completion cost is applied to assistant (AI) messages only
        """

        # second text
        create_chat_message_url = api.get_chat_item(user_uuid=user_id, chat_uuid=chat.uuid)
        await async_http_requester(
            "test_create_chat_messages_linked_by_parent_id",
            async_client.put,
            create_chat_message_url,
            json={"query": "Shorten the answer"},
        )

        # third text
        create_chat_message_url = api.get_chat_item(user_uuid=user_id, chat_uuid=chat.uuid)
        await async_http_requester(
            "test_create_chat_messages_linked_by_parent_id",
            async_client.put,
            create_chat_message_url,
            json={"query": "Lengthen the answer"},
        )

        execute = await db_session.execute(select(Chat).filter(Chat.uuid == chat.uuid))
        chat_model = execute.scalar_one()

        # should have 6 messages in total, one pair for each request and response
        execute = await db_session.execute(
            select(Message).filter(Message.chat_id == chat_model.id).order_by(Message.created_at)
        )
        messages = list(execute.scalars())

        assert len(messages) == 6, f"Expected 6 messages, but got {len(messages)}"
        input_token = 0
        for idx, message in enumerate(messages):
            llm_id = message.llm_id
            execute = await db_session.execute(select(LLM).filter(LLM.id == llm_id))
            llm = execute.scalar_one()
            # todo: change llm table  input_cost_per_token and input_cost_per_token to decimal from double.
            # as it causes rounding issues.
            llm_input_cost_per_token = round(Decimal(llm.input_cost_per_token), 10)
            llm_output_cost_per_token = round(Decimal(llm.output_cost_per_token), 10)

            if idx % 2 == 0:
                # number of input tokens are saved in the user message, not stored in the assistant message.
                # therefore need to capture input token from previous user message.
                input_token = message.tokens
                assert message.completion_cost is None, "Cost calculation does not apply to user messages"

            # check cost calculation assistant message
            if idx % 2 == 1:
                # number of output tokens are saved in the assistant message
                # check completion cost for each assistant message
                output_token = message.tokens
                message_cost = round(message.completion_cost, 10)
                logger.info(
                    "input_cost_per_token %s, output_cost_per_token %s, input_token %s, output_token %s"
                    % (
                        llm_input_cost_per_token,
                        llm_output_cost_per_token,
                        input_token,
                        output_token,
                    )
                )

                completion_cost = (input_token * llm_input_cost_per_token) + (output_token * llm_output_cost_per_token)
                assert message_cost > 0
                assert message_cost == completion_cost

    @pytest.mark.asyncio
    async def test_get_feedback_labels(self, async_client, async_http_requester):
        get_feedback_labels_url = api.get_feedback_labels()
        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.get,
            get_feedback_labels_url,
        )

        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_add_negative_feedback_with_label_to_chat_messages(
        self, async_client, user_id, chat, async_http_requester
    ):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)
        label_model = FeedbackLabelTable().get_one_by("label", "Not factually correct")

        feedback_request_json = FeedbackRequest(
            score=-1, freetext="Needs improvement", label=str(label_model.uuid)
        ).to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)
        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]
        # check negative score stored in the table, negative score is stored as 1 in the database table
        assert feedback.feedback_score_id == 1
        # check label is same as the one sent
        assert feedback.feedback_label_id == label_model.id

    @pytest.mark.asyncio
    async def test_add_negative_feedback_to_chat_messages_without_label(
        self, async_client, user_id, chat, async_http_requester
    ):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)

        feedback_request_json = FeedbackRequest(score=-1, freetext="Needs improvement").to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)
        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]

        # check negative score stored in the table, negative score is stored as 1 in the database table
        assert feedback.feedback_score_id == 1

        assert feedback.feedback_label_id is None

    @pytest.mark.asyncio
    async def test_add_positive_feedback_to_chat_messages(self, async_client, user_id, chat, async_http_requester):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)

        # check labels are ignored for positive feedbacks
        label_model = FeedbackLabelTable().get_one_by("label", "Not factually correct")

        feedback_request_json = FeedbackRequest(
            score=1, label=str(label_model.uuid), freetext="Needs improvement"
        ).to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)
        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]

        # check positive score, which is stored as 1 in the database table
        assert feedback.feedback_score_id == 2

        # check labels are ignored for positive feedbacks
        assert feedback.feedback_label_id is None

    @pytest.mark.asyncio
    async def test_add_negative_feedback_to_chat_messages_without_freetext(
        self, async_client, user_id, chat, async_http_requester
    ):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)
        label_model = FeedbackLabelTable().get_one_by("label", "Not factually correct")

        feedback_request_json = FeedbackRequest(score=-1, label=str(label_model.uuid)).to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)
        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]
        # check negative score, which is stored as 1 in the database table
        assert feedback.feedback_score_id == 1
        # check label is same as the one sent
        assert feedback.feedback_label_id == label_model.id

    @pytest.mark.asyncio
    async def test_add_negative_feedback_without_label_to_chat_messages_without_freetext(
        self, async_client, user_id, chat, async_http_requester
    ):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)

        feedback_request_json = FeedbackRequest(score=-1).to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)
        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]
        # check negative score stored in the table, negative score is stored as 1 in the database table
        assert feedback.feedback_score_id == 1

        assert feedback.feedback_label_id is None

    @pytest.mark.asyncio
    async def test_add_positive_feedback_to_chat_messages_without_freetext(
        self, async_client, user_id, chat, async_http_requester
    ):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)

        feedback_request_json = FeedbackRequest(score=1).to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)
        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]
        # check score is same as the one sent
        # check positive score , which  is stored as 2 in the database table
        assert feedback.feedback_score_id == 2

        assert feedback.feedback_label_id is None

    @pytest.mark.asyncio
    async def test_remove_negative_feedback_then_update_as_positive_feedback(
        self, async_client, user_id, chat, async_http_requester
    ):
        create_feedback_url = api.add_message_feedback(user_uuid=user_id, message_uuid=chat.message.uuid)
        label_model = FeedbackLabelTable().get_one_by("label", "Not factually correct")

        # Step 1: send negative feedback
        feedback_request_json = FeedbackRequest(
            score=-1, label=str(label_model.uuid), freetext="Needs improvement"
        ).to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)

        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]
        # check score is same as the one sent
        # check positive score , which  is stored as 2 in the database table
        assert feedback.feedback_score_id == 1

        # check label is same as the one sent
        assert feedback.feedback_label_id == label_model.id

        # Step 2: remove feedback
        feedback_request_json = FeedbackRequest(score=0, freetext="Needs improvement").to_dict()

        response = await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )

        feedback_uuid = response["uuid"]
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)

        # check freetext is same as the one sent
        assert feedback.deleted_at is not None

        # Step 3: send positive feedback
        feedback_request_json = FeedbackRequest(score=1, freetext="Needs improvement").to_dict()
        await async_http_requester(
            "test_add_feedback_to_chat_messages",
            async_client.put,
            create_feedback_url,
            json=feedback_request_json,
        )
        feedback = FeedbackTable().get_by_uuid(feedback_uuid)

        # check freetext is same as the one sent
        assert feedback.freetext == feedback_request_json["freetext"]
        # check score is same as the one sent
        # check positive score , which  is stored as 2 in the database table
        assert feedback.feedback_score_id == 2

        # check label is removed as the feedback is positive
        assert feedback.feedback_label_id is None
        assert feedback.deleted_at is None

    @pytest.mark.asyncio
    async def test_chat_rag_process_does_not_use_personal_document_index(
        self, async_client, user_id, chat, async_http_requester, db_session, caplog
    ):
        """
        Creates a new chat and sends a default message to the chat.
        Then it verifies personal document index is not used in the default RAG process.
        """
        execute = await db_session.execute(select(Chat).filter(Chat.uuid == chat.uuid))
        chat_db_obj = execute.scalar_one()
        execute = await db_session.execute(
            select(Message).filter(Message.chat_id == chat_db_obj.id, Message.role == "user")
        )
        user_messages = list(execute.scalars())
        user_message = user_messages[0]

        execute = await db_session.execute(
            select(MessageSearchIndexMapping).filter(MessageSearchIndexMapping.message_id == user_message.id)
        )

        query_result = list(execute.scalars())

        indices = [r.search_index_id for r in query_result]

        personal_document_index_id = 3
        assert personal_document_index_id not in indices

    @patch("app.services.opensearch.opensearch.AsyncOpenSearchClient.get")
    @patch("app.services.rag.rag.check_if_query_requires_rag")
    @pytest.mark.parametrize(
        "test_scenario, error_type",
        [
            (
                "request_error",
                RequestError(
                    400,
                    "search_phase_execution_exception",
                    {
                        "error": {
                            "root_cause": [
                                {
                                    "reason": "maxClauseCount is set to 1024",
                                    "type": "search_phase_execution_exception",
                                }
                            ]
                        }
                    },
                ),
            ),
            (
                "transport_error",
                TransportError(
                    500,
                    "search_phase_execution_exception",
                    {
                        "error": {
                            "root_cause": [
                                {
                                    "reason": "maxClauseCount is set to 1024",
                                    "type": "search_phase_execution_exception",
                                }
                            ]
                        }
                    },
                ),
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_chat_rag_process_skips_opensearch_errors(
        self,
        mock_rag,
        mock_opensearch_client,
        test_scenario,
        error_type,
        async_client,
        user_id,
        async_http_requester,
        caplog,
    ):
        """
        Creates a new chat and sends a default message to the chat.
        Then it simulates opensearch RequestError/TransportError exceptions with 1024 too many clause
        and checks these specific errors are handled and search result returns empty match.
        Then checks chat response generated without search resul input.
        """
        logger.info("Running test scenario %s", test_scenario)
        # Mock the OpenSearch client

        mock_rag.return_value = MessageSearchIndexMapping(search_index_id=-1, use_index=True, message_id=-1)

        # Mock the OpenSearch client
        mock_search = AsyncMock()
        mock_opensearch_client.return_value.search = mock_search

        # Simulate a TransportError
        mock_search.side_effect = [error_type]

        url = api.chats(user_uuid=user_id)
        await async_http_requester(
            "test_chat_rag_process_skip_opensearch_errors",
            async_client.post,
            url,
            json={
                "query": "you MUST use the documents MCOM 3.0 and GCS Accessibility Standards to answer this prompt."
                " Give me a brief one paragraph summary of accessible content in GCS",
                "use_rag": True,
            },
        )
        assert "Search error" in caplog.text
