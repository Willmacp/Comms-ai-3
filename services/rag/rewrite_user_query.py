import json
import logging
from typing import List

from anthropic.types import TextBlock
from sqlalchemy import insert

from app.database.models import LLM, Message, RewrittenQuery, SearchIndex, SystemPrompt
from app.database.table import async_db_session

from .rag_llm import RagLlmHandler

logger = logging.getLogger(__name__)


async def rewrite_user_query(
    user_message: str,
    index: SearchIndex,
    message: Message,
    llm: LLM,
    system_prompt: SystemPrompt,
) -> List[str]:
    logger.info("Rewriting user query")

    try:
        rag_llm = RagLlmHandler(llm, system_prompt)
        ai_message, llm_internal_response = await rag_llm.invoke(user_message)

        content = ""
        if isinstance(ai_message, list):
            content_list = [m.text for m in ai_message if isinstance(m, TextBlock)]
            if len(content_list) > 0:
                content = content_list[0]
        else:
            content = ai_message

        logger.debug(f"AI rewritten message: {content}")
        rewritten_queries = []
        try:
            rewritten_queries = json.loads(content)
            logger.debug(f"Successfully parsed AI message as JSON: {rewritten_queries}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI message {content} as JSON: {e}. Using original user message.")

        # Filter rewritten_queries to check they are strings
        rewritten_queries = [query for query in rewritten_queries if isinstance(query, str)]
        if len(rewritten_queries) == 0:
            logger.warning(
                f"No valid rewritten queries found from:\n {rewritten_queries}\n. "
                f"Using original user message: {user_message}"
            )
            return [user_message]

        # Write the rewritten queries to the database
        query_models = [
            {
                "search_index_id": index.id,
                "message_id": message.id,
                "llm_internal_response_id": llm_internal_response.id,
                "content": rewritten_query,
            }
            for rewritten_query in rewritten_queries
        ]
        async with async_db_session() as session:
            await session.execute(insert(RewrittenQuery), query_models)
            logger.info(f"Successfully added {len(query_models)} rewritten queries to the database")

        return rewritten_queries

    except Exception as e:
        logger.exception(f"An unexpected error occurred in rewrite_user_query: {str(e)}")
        return [user_message]
