import logging
from typing import Optional

from app.app_types.message import MessageDefaults, RoleEnum
from app.database.models import LLM, Message
from app.database.table import MessageTable
from app.lib.llm import LLMResponse, llm_transaction

logger = logging.getLogger(__name__)


def chat_save_llm_output(
    ai_message_defaults: MessageDefaults,
    llm_response: LLMResponse,
    user_message: Message,
    llm: LLM,
) -> Optional[Message]:
    try:
        logger.info(f"Starting chat_save_llm_output for user message ID: {user_message.id}")

        transaction = llm_transaction(llm, llm_response)
        logger.info(
            f"LLM transaction created: input_cost={transaction.input_cost}, output_cost={transaction.output_cost}",
        )

        message_repo = MessageTable()
        logger.info(f"Message defaults set: {ai_message_defaults}")

        try:
            logger.info(f"Updating user message ID: {user_message.id}")
            message_repo.update(
                user_message,
                {
                    "tokens": llm_response.input_tokens,
                },
            )
            logger.info(
                f"User message updated successfully. Tokens: {llm_response.input_tokens}, "
                f"Completion cost: {transaction.input_cost}",
            )
        except Exception as e:
            logger.error(f"Failed to update user message ID {user_message.id}: {str(e)}")
            # Continue execution, as this is not a critical error

        try:
            logger.info("Creating AI message")
            content_list = [text_block.text for text_block in llm_response.content if text_block.type == "text"]
            if content_list:
                content = ", ".join(content_list)
            else:
                content = ""
            ai_message = message_repo.create(
                {
                    **ai_message_defaults.dict(),
                    "parent_message_id": user_message.id,
                    "completion_cost": transaction.completion_cost,
                    "role": RoleEnum.assistant,
                    "content": content,
                    "tokens": llm_response.output_tokens,
                    "citation": user_message.citation,
                },
            )
            logger.info(f"AI message created successfully. Message ID: {ai_message.id}")
            logger.debug(
                f"AI message details: role={ai_message.role}, tokens={ai_message.tokens}, "
                f"completion_cost={ai_message.completion_cost}",
            )
        except Exception as e:
            logger.exception(f"Failed to create AI message: {e}")
            return None
        return ai_message

    except Exception as e:
        logger.error(f"An unexpected error occurred in chat_save_llm_output: {str(e)}")
        return None
