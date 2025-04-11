import logging

from anthropic.types import TextBlock

from app.app_types.requests import RequestModel
from app.lib import ErrorMessages
from app.services.bedrock import BedrockHandler, RunMode


class ChatTitleRequest(RequestModel):
    query: str = ""
    system: str = ""


logger = logging.getLogger(__name__)


async def chat_create_title(data: ChatTitleRequest):
    logger.info("Starting chat_create_title function")
    try:
        system_prompt_title = """The assistant is a title generator called Title Bot. \
Title Bot creates short titles with a maximum of 5 words. \
Title Bot creates titles that are useful for identifying the subject of the provided human query. \
The human query is provided between XML tags as shown: \
<human-query>This is an example message from the human.</human-query>. \
When responding, Title Bot only provides the title. \
Title Bot does not provide ANY chain of thought in it's response. Title Bot ONLY provides the title. \
Title Bot formats it's response using title case. Title Bot does not use a full stop at the end of the title. \
Title Bot does not enclose the title in quotes. \
If Title Bot does not have enough information to generate a title, Title Bot gives it's best attempt. \
The next message received is the human's query.
    """

        logger.debug(f"Constructed title_system: {system_prompt_title}")
        chat = BedrockHandler(system=system_prompt_title, mode=RunMode.ASYNC)

        user_query_for_title_generation = (
            data.query if len(data.query) < 200 else data.query[0:100] + data.query[-100:-1]
        )
        logger.debug(f"Query extract for title generation: {user_query_for_title_generation}")

        formatted_user_query_for_title_generation = f"<human-query>{user_query_for_title_generation}</human-query>"
        messages = chat.format_content_for_chat_title(formatted_user_query_for_title_generation)

        result = await chat.create_chat_title(messages)

        logger.debug(f"Raw LLM result: {result.content}")
        if isinstance(result.content, list):
            content = [m.text for m in result.content if isinstance(m, TextBlock)]
            if len(content) > 0:
                title = content[0].split("\n")[0]
            else:
                title = ""
        else:
            title = result.content

        logger.info(f"Extracted title: {title}")

        if len(title) > 255:
            logger.warning(f"Title exceeds 255 characters. Truncating: {title}")
            title = title[:252] + "..."
            logger.info(f"Truncated title: {title}")

        logger.info("chat_create_title function completed successfully")
        return title
    except Exception as error:
        logger.error(f"Error in chat_create_title: {str(error)}", exc_info=True)
        raise Exception(ErrorMessages.CHAT_TITLE_NOT_CREATED, error) from error
