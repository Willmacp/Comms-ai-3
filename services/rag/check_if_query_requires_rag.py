import logging
from typing import Optional

from anthropic.types import TextBlock
from sqlalchemy import insert

from app.database.models import LLM, LlmInternalResponse, MessageSearchIndexMapping, SearchIndex, SystemPrompt
from app.database.table import MessageTable, async_db_session
from app.services.bedrock import BedrockHandler, RunMode

logger = logging.getLogger(__name__)


async def check_if_query_requires_rag(
    user_message: str,
    index: SearchIndex,
    message: MessageTable,
    llm: LLM,
    system_prompt: SystemPrompt,
) -> Optional[MessageSearchIndexMapping]:
    try:
        logger.info("checking if query requires rag from index %s", index.name)

        index_info = f"Index name: {index.name}\n\nIndex description: {index.description}"
        compiled_system_prompt = f"{index_info}\n\n{system_prompt.content}"

        llm_handler = BedrockHandler(llm=llm, mode=RunMode.ASYNC, system=compiled_system_prompt)

        try:
            response = await llm_handler.invoke_async_with_call_cost_details(
                [{"content": f"User query:\n\n```{user_message}```", "role": "user"}]
            )
        except Exception as e:
            logger.exception("Error invoking LLM", exc_info=True)
            raise Exception(f"Error invoking LLM: {str(e)}") from e

        ai_message = response.content
        tokens_in = response.input_tokens
        tokens_out = response.output_tokens

        ai_message_str = [m.text.lower() for m in ai_message if isinstance(m, TextBlock)][0]
        requires_search_engine = ai_message_str != "n"

        logger.info(f"{index.name}: {requires_search_engine=}")

        logger.debug(f"{index.name}: {ai_message=}")
        async with async_db_session() as session:
            stmt = (
                insert(LlmInternalResponse)
                .values(
                    llm_id=llm.id,
                    system_prompt_id=system_prompt.id,
                    content=ai_message_str,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    completion_cost=response.completion_cost,
                )
                .returning(LlmInternalResponse)  # Return the  inserted row
            )
            result = await session.execute(stmt)
            llm_internal_response = result.scalars().first()

            stmt = (
                insert(MessageSearchIndexMapping)
                .values(
                    search_index_id=index.id,
                    message_id=message.id,
                    llm_internal_response_id=llm_internal_response.id,
                    use_index=requires_search_engine,
                )
                .returning(MessageSearchIndexMapping)  # Return the  inserted row
            )
            result = await session.execute(stmt)
            message_search_index_mapping = result.scalar_one()
            return message_search_index_mapping

    except Exception:
        logger.exception("An error occurred in check_if_query_requires_rag", exc_info=True)
        return None
