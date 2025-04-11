import logging
from typing import Dict, List

from sqlalchemy import insert
from sqlalchemy.future import select

from app.database.models import (
    LLM,
    Message,
    MessageSearchIndexMapping,
    SearchIndex,
    SystemPrompt,
)
from app.database.table import async_db_session
from app.services.opensearch import PERSONAL_DOCUMENTS_INDEX_NAME

from ..opensearch import AsyncOpenSearchOperations
from .get_document_chunk_mappings import get_document_chunk_mappings
from .rag_types import RagRequest, RetrievalResult
from .rewrite_user_query import rewrite_user_query

logger = logging.getLogger(__name__)

NUMBER_OF_DOCUMENT_CHUNKS_REQUIRED_FOR_QUERY_REWRITE = 6
"""
The minimum number of document chunks required to query rewrite
"""


async def _get_document_chunks(document_uuid: str, queries: List[str]) -> List[Dict]:
    """
    Retrieves document chunks matching the provided queries from Personal Document index.
    It searches for relevant chunks of a document identified by its UUID
    across multiple queries and combines the results into a list.

    Args:
        document_uuid (str): The uuid of the document to retrieve chunks from.
        queries (List[str]): A list of  opensearch queries used to search for
            matching document chunks.

    Returns:
        List[Dict]: A list of dictionaries representing the retrieved document chunks
        that match the provided queries.

    """
    # Get search results for each rewritten query
    raw_opensearch_retrieval_results = []
    for query in queries:
        chunks = await AsyncOpenSearchOperations.search_user_document_chunks(
            document_uuid, query, PERSONAL_DOCUMENTS_INDEX_NAME
        )
        raw_opensearch_retrieval_results.extend(chunks)

    return raw_opensearch_retrieval_results


async def _get_rewritten_queries(
    query: str,
    search_index: SearchIndex,
    message: Message,
    llm_query_rewriter: LLM,
    system_prompt_query_rewriter: SystemPrompt,
) -> List[str]:
    """
    Generates rewritten queries for improved search results based on the user's chat query.
    Args:
        query (str): The original chat query
        search_index (SearchIndex): The search index instance used for saving generated queries against in the database
        message (Message): A `Message` instance representing the current chat message used for saving generated
        queries against in the database
        llm_query_rewriter (LLM): The LLM instance holding LLM model and LLM provider details.
        system_prompt_query_rewriter (SystemPrompt): The system prompt holding instruction for LLM for
        how to generate opensearch queries

    Returns:
        List[str]: A list of rewritten queries
    """

    # Rewrite the user's query to get better results from the search index
    rewritten_queries = await rewrite_user_query(
        query, search_index, message, llm_query_rewriter, system_prompt_query_rewriter
    )
    return rewritten_queries


async def _retrieve_relevant_chunks(
    rag_request: RagRequest,
    search_index: SearchIndex,
    message: Message,
    llm_query_rewriter: LLM,
    system_prompt_query_rewriter: SystemPrompt,
) -> List[Dict]:
    """
    Retrieves relevant document chunks based on the user's query and request context.
    This function processes documents specified in the RAG request, determines whether
    query rewriting is needed based on the number of available document chunks, and retrieves
    relevant chunks from the search index.

    Args:
        rag_request (RagRequest): The request object containing the user query and the UUIDs
            of the target documents.
        search_index (SearchIndex): The search index db record.
        message (Message): A `Message` instance representing the current chat message
        llm_query_rewriter (LLM): An instance of a LLM model used for rewriting the query.
        system_prompt_query_rewriter (SystemPrompt): A system prompt used
            to instruct the query enhancement process.

    Returns:
        List[Dict]: A list of unique opensearch documents relevant to the user's query, represented as
        dictionaries.

    """
    logger.info("starting to retrieve pdu relevant chunks")

    # check if each document has 5 or more for opensearch
    index_search_outputs = []

    for document_uuid in rag_request.document_uuids:
        # check if there are more document chunks than minimum, warranting a search query rewrite.
        doc_chunks_response = await AsyncOpenSearchOperations.get_document_chunks(
            PERSONAL_DOCUMENTS_INDEX_NAME, document_uuid, NUMBER_OF_DOCUMENT_CHUNKS_REQUIRED_FOR_QUERY_REWRITE
        )
        if len(doc_chunks_response) >= NUMBER_OF_DOCUMENT_CHUNKS_REQUIRED_FOR_QUERY_REWRITE:
            # there are enough document chunks to trigger user query rewrite.
            rewritten_queries = await _get_rewritten_queries(
                rag_request.query, search_index, message, llm_query_rewriter, system_prompt_query_rewriter
            )
            logger.info("Searching document chunks from document %s", document_uuid)
            search_results = await _get_document_chunks(document_uuid, rewritten_queries)
            index_search_outputs.extend(search_results)
        else:
            logger.info(
                "Using all available %s document chunk(s) from document %s", len(doc_chunks_response), document_uuid
            )
            index_search_outputs.extend(doc_chunks_response)

    # de-duplicate document_chunks as each opensearch query may return same documents
    visited_chunks = set()
    unique_chunks = []
    for chunk in index_search_outputs:
        id_opensearch = chunk["_id"]
        if id_opensearch not in visited_chunks:
            visited_chunks.add(id_opensearch)
            unique_chunks.append(chunk)

    return unique_chunks


async def _message_search_index_mapping_record(message: Message) -> (MessageSearchIndexMapping, SearchIndex):
    """
    Creates a search index mapping record for the given message and retrieves the associated search index.
    Logs the mapping of the message to personal document upload index.

    Args:
        message (Message): The chat message for which the search index mapping record is created.

    Returns:
        tuple: containing:
            - `MessageSearchIndexMapping`: The record linking the message to the search index.
            - `SearchIndex`: The associated search index object.

    """
    async with async_db_session() as session:
        execute = await session.execute(select(SearchIndex).where(SearchIndex.name == PERSONAL_DOCUMENTS_INDEX_NAME))
        pdu_search_index = execute.scalar()

        # create a search index mapping record to log personal index used for the message
        stmt = (
            insert(MessageSearchIndexMapping)
            .values(
                search_index_id=pdu_search_index.id,
                message_id=message.id,
                llm_internal_response_id=None,
                use_index=True,
            )
            .returning(MessageSearchIndexMapping)
        )
        result = await session.execute(stmt)
        pdu_message_search_index_mapping = result.scalars().first()
        logger.info("Added index mapping %s for message %s", pdu_search_index.id, message.id)
    return pdu_message_search_index_mapping, pdu_search_index


async def _convert_to_retrieval_results(
    document_chunks: List[Dict], search_index: SearchIndex, message: Message
) -> List[RetrievalResult]:
    # associate document chunks with the user message and save in the database
    async with async_db_session() as db_session:
        document_chunks_retrieved = await get_document_chunk_mappings(
            document_chunks, search_index, message, db_session, use_chunk=True
        )

    return document_chunks_retrieved


async def personal_document_rag(
    rag_request: RagRequest, message: Message, llm_query_rewriter: LLM, system_prompt_query_rewriter: SystemPrompt
) -> Dict:
    """
    Processes the chat message and augments the chat query sent to the LLM, using the documents referenced in
     rag_request, using llm_query_rewriter and system_prompt_query_rewriter for customizing chat message.

    Args:
        rag_request (RagRequest): The request object containing chat message, referenced documents, user_id
        message (Message): A `Message` instance containing chat message details.
        llm_query_rewriter (LLM): An instance of LLM used for generating opensearch compliant text queries from
            the chat message.
        system_prompt_query_rewriter (SystemPrompt): The system prompt for instructing how to generate opensearch
        text queries.

    Returns:
        Dict: A dictionary containing RAG retrieval results ad message index mapping record.
    """

    # create record for personal index usage
    message_search_index_mapping, pdu_search_index = await _message_search_index_mapping_record(message)

    relevant_chunks = await _retrieve_relevant_chunks(
        rag_request, pdu_search_index, message, llm_query_rewriter, system_prompt_query_rewriter
    )

    retrieval_results = await _convert_to_retrieval_results(relevant_chunks, pdu_search_index, message)
    personal_document_rag_result = {
        "retrieval_results": retrieval_results,
        "message_search_index_mappings": [message_search_index_mapping],
    }
    return personal_document_rag_result
