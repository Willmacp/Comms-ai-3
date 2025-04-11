import asyncio
import logging
from typing import List

from anthropic.types import TextBlock
from sqlalchemy import insert, update

from app.database.models import LLM, LlmInternalResponse, MessageDocumentChunkMapping, SystemPrompt
from app.database.table import async_db_session
from app.services.bedrock import BedrockHandler, RunMode

from .rag_types import RetrievalResult

logger = logging.getLogger(__name__)


async def _process_result(
    retrieval_result: RetrievalResult,
    user_message: str,
    llm: LLM,
    system_prompt: SystemPrompt,
) -> RetrievalResult:
    """
    Process a single retrieval result by querying the LLM and updating the database.

    Parameters:
        retrieval_result (RetrievalResult): The retrieval result to process.
        user_message (str): The original user query.
        llm (LLM): The language model to use for processing.
        system_prompt (SystemPrompt): The system prompt to use.

    Returns:
        RetrievalResult: The processed retrieval result.
    """
    doc_chunk = retrieval_result.document_chunk
    document = retrieval_result.document
    message_document_chunk_mapping = retrieval_result.message_document_chunk_mapping
    index = retrieval_result.search_index

    system_prompt_compiled = f"{system_prompt.content}.\n\nThe users original query was:\n\n```{user_message}```"
    llm_handler = BedrockHandler(llm=llm, mode=RunMode.ASYNC, max_tokens=1000, system=system_prompt_compiled)

    try:
        response = await llm_handler.invoke_async_with_call_cost_details(
            [
                {
                    "content": f"Document title: {document.name}\n\nSection title: {doc_chunk.name}\n\n"
                    f"Content:{doc_chunk.content}",
                    "role": "user",
                }
            ]
        )
    except Exception as e:
        message = f"Error invoking LLM: {str(e)}"
        logger.exception(message)
        raise Exception(message) from e

    if isinstance(response.content, list):
        ai_message = "".join([m.text for m in response.content if isinstance(m, TextBlock)]).lower()
    else:
        ai_message = response.content.lower()
    logger.debug(f"ai_message in _process_result: {ai_message}")
    tokens_in = response.input_tokens
    tokens_out = response.output_tokens

    use_chunk = ai_message != "n"
    async with async_db_session() as session:
        stmt = (
            insert(LlmInternalResponse)
            .values(
                llm_id=llm.id,
                system_prompt_id=system_prompt.id,
                content=ai_message,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                completion_cost=response.completion_cost,
            )
            .returning(LlmInternalResponse)  # Return the inserted row
        )
        result = await session.execute(stmt)
        llm_internal_response = result.scalar_one()
        result = await session.execute(
            update(MessageDocumentChunkMapping)
            .where(MessageDocumentChunkMapping.id == message_document_chunk_mapping.id)
            .values(llm_internal_response_id=llm_internal_response.id, use_document_chunk=use_chunk)
            .returning(MessageDocumentChunkMapping)
        )
        message_document_chunk_mapping = result.scalar_one()

        return RetrievalResult(
            search_index=index,
            document_chunk=doc_chunk,
            document=document,
            message_document_chunk_mapping=message_document_chunk_mapping,
        )


async def filter_results_coroutine(
    unique_retrieval_results: List[RetrievalResult],
    user_message: str,
    llm: LLM,
    system_prompt: SystemPrompt,
) -> List[RetrievalResult]:
    """
    Filter and process a list of retrieval results asynchronously.
    """
    try:
        logger.debug("filtering retrieval results %s", unique_retrieval_results)

        tasks = [
            _process_result(retrieval_result, user_message, llm, system_prompt)
            for retrieval_result in unique_retrieval_results
        ]
        processed_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out any exceptions and log them
        final_results = []
        for result in processed_results:
            if isinstance(result, Exception):
                logger.error(f"Error processing retrieval result: {str(result)}")
            else:
                final_results.append(result)

        logger.debug("filter_results_coroutine: %s", final_results)
        return final_results
    except Exception as e:
        logger.error(f"An error occurred in filter_results_coroutine: {str(e)}")
        raise
