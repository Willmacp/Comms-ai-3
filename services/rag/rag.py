import asyncio
import logging
import os
from typing import List

from sqlalchemy.future import select

from app.database.models import (
    LLM,
    Document,
    DocumentChunk,
    Message,
    MessageSearchIndexMapping,
    SearchIndex,
    SystemPrompt,
)
from app.database.table import async_db_session
from app.services.opensearch import create_client, list_indexes

from ..opensearch import AsyncOpenSearchOperations
from .check_if_query_requires_rag import check_if_query_requires_rag
from .filter_results_coroutine import filter_results_coroutine
from .get_document_chunk_mappings import get_document_chunk_mappings
from .personal_document_rag import personal_document_rag
from .rag_types import RagRequest, RetrievalResult
from .rewrite_user_query import rewrite_user_query

logger = logging.getLogger(__name__)


# This wrapper raises an error if the environment variables are not as expected
def get_env_wrapper(env_variable_name: str):
    try:
        variable = os.getenv(env_variable_name)
    except Exception as e:
        logger.info(f"Could not load env variable {env_variable_name}: {e}")
    if variable is None:
        logger.info(f"Environment variable {env_variable_name} was loaded as a null value")
        # This doesn't seem to work?
        logger.error(f"Environment variable {env_variable_name} was loaded as a null value")
        raise ValueError

    return variable


# Get all the LLM and SystemPrompt objects required
llm_model_index_router = get_env_wrapper("RAG_LLM_MODEL_INDEX_ROUTER")
system_prompt_name_index_router = get_env_wrapper("RAG_SYSTEM_PROMPT_INDEX_ROUTER")

llm_model_query_rewriter = get_env_wrapper("RAG_LLM_MODEL_QUERY_REWRITER")
system_prompt_name_query_rewriter = get_env_wrapper("RAG_SYSTEM_PROMPT_QUERY_REWRITER")

llm_model_chunk_reviewer = get_env_wrapper("RAG_LLM_MODEL_CHUNK_REVIEWER")
system_prompt_name_chunk_reviewer = get_env_wrapper("RAG_SYSTEM_PROMPT_CHUNK_REVIEWER")


class OpenSearchClient:
    """
    Provides a single opensearch client whenever requested.
    """

    __opensearch_client = None

    @classmethod
    def get_client(cls):
        if cls.__opensearch_client is None:
            cls.__opensearch_client = create_client()
        return cls.__opensearch_client


async def search_index_for_chunks(query: str, index: SearchIndex, message: Message):
    # Perform the search
    chunks = await AsyncOpenSearchOperations.search_for_chunks(query, index.name)

    # Process and return retrieval_results
    async with async_db_session() as session:
        retrieval_results = await get_document_chunk_mappings(chunks, index, message, session)
        return retrieval_results


async def process_results(
    unique_results: List[RetrievalResult],
    user_message: str,
    llm_chunk_reviewer: LLM,
    system_prompt_chunk_reviewer: SystemPrompt,
) -> List[RetrievalResult]:
    processed_results = await filter_results_coroutine(
        unique_results, user_message, llm_chunk_reviewer, system_prompt_chunk_reviewer
    )

    return processed_results


async def retrieve_relevant_chunks(
    rag_request: RagRequest,
    search_indexes: list,
    message: Message,
    llm_index_router: LLM,
    llm_query_rewriter: LLM,
    llm_chunk_reviewer: LLM,
    system_prompt_index_router: SystemPrompt,
    system_prompt_query_rewriter: SystemPrompt,
    system_prompt_chunk_reviewer: SystemPrompt,
    index_chunk_search_fn,
    always_use_index: bool = False,
):
    logger.info("starting to retrieve relevant chunks")

    async def process_chunks_from_index(search_index):
        processed_retrieval_results = []
        message_search_index_mapping = None

        # Get an LLM to decide if the index is relevant
        if not always_use_index:
            message_search_index_mapping = await check_if_query_requires_rag(
                rag_request.query, search_index, message, llm_index_router, system_prompt_index_router
            )

        # Only search OpenSearch if the index was deemed relevant or index use is always
        if always_use_index or message_search_index_mapping.use_index is True:
            # Rewrite the user's query to get better results from the search index
            rewritten_queries = await rewrite_user_query(
                rag_request.query, search_index, message, llm_query_rewriter, system_prompt_query_rewriter
            )

            # Get search results for each rewritten query
            raw_opensearch_retrieval_results = []
            for rewritten_query in rewritten_queries:
                raw_opensearch_retrieval_results += await index_chunk_search_fn(rewritten_query, search_index, message)

            # Process search results using an LLM to identify if they are suitable for the user query
            processed_retrieval_results += await process_results(
                raw_opensearch_retrieval_results, rag_request.query, llm_chunk_reviewer, system_prompt_chunk_reviewer
            )

        return {
            # This value might be an empty if no relevant chunks are found.
            "processed_retrieval_results": processed_retrieval_results,
            # We return this seperately so we can
            "message_search_index_mapping": message_search_index_mapping,
        }

    # Search each index and process the results with an LLM
    index_search_outputs = await asyncio.gather(
        *[process_chunks_from_index(search_index) for search_index in search_indexes]
    )

    # Unpack the index search results
    processed_retrieval_results = [
        search_output["processed_retrieval_results"] for search_output in index_search_outputs
    ]

    message_search_index_mappings = [
        search_output["message_search_index_mapping"] for search_output in index_search_outputs
    ]

    # Flatten the results from each index into a single list.
    processed_retrieval_results = [item for sublist in processed_retrieval_results for item in sublist]

    # Filter out any results that were deemed irrelevant
    filtered_retrieval_results = [
        result for result in processed_retrieval_results if result.message_document_chunk_mapping.use_document_chunk
    ]

    # De-duplicate retrieval results
    unique_retrieval_results = {}
    for retrieval_result in filtered_retrieval_results:
        doc_chunk_id = retrieval_result.document_chunk.id
        if doc_chunk_id not in unique_retrieval_results:
            unique_retrieval_results[doc_chunk_id] = retrieval_result

    unique_retrieval_results = list(unique_retrieval_results.values())

    return {
        "retrieval_results": unique_retrieval_results,
        "message_search_index_mappings": message_search_index_mappings,
    }


def _generate_doc_chunk_reference(doc_chunk: DocumentChunk, document: Document):
    result_string = (
        f"\n\n---\n\nDocument title:\n{document.name}\n\nSection title:\n{doc_chunk.name}\n\n"
        f"Content:\n{doc_chunk.content}"
    )
    return result_string


async def create_full_query(
    rag_request: RagRequest,
    user_message_search_index_mappings: List[MessageSearchIndexMapping],
    user_retrieval_results: List[RetrievalResult],
    retrieval_results: List[RetrievalResult],
    message_search_index_mappings: List[MessageSearchIndexMapping],
):
    # initial citation and prompt segment values
    citation_message = []
    prompt_segment_retrieval = ""
    user_message = rag_request.query

    if retrieval_results or user_retrieval_results:
        prompt_segment_retrieval = "\n\nSearch engine results:\n\n```"
        citation_message = []
        central_doc_citations = {}

        # generate record for each retrieval result
        for retrieval_result in retrieval_results:
            document = retrieval_result.document
            # save the document that has retrieval chunk
            central_doc_citations[str(document.uuid)] = {"docname": document.name, "docurl": document.url}
            doc_chunk = retrieval_result.document_chunk
            result_string = _generate_doc_chunk_reference(doc_chunk, document)
            prompt_segment_retrieval += result_string

        citation_message = citation_message + list(central_doc_citations.values())

        # user retrievals are stored in single index
        # keep a single doc citation if multiple chunks used from same document.
        user_doc_citations = {}

        for retrieval_result in user_retrieval_results:
            document = retrieval_result.document
            user_doc_citations[str(document.uuid)] = {"docname": document.name, "docurl": document.url}

            doc_chunk = retrieval_result.document_chunk
            result_string = _generate_doc_chunk_reference(doc_chunk, document)
            prompt_segment_retrieval += result_string

        citation_message = citation_message + list(user_doc_citations.values())

        prompt_segment_retrieval += "\n\n```"

        full_query = f"{user_message}{prompt_segment_retrieval}"
        return (full_query, citation_message)

    # If no results are retrieved but we DID search an index, we include the fact that we searched the documents
    # in the index but we did not find anything.
    searched_index_ids = [
        message_search_index_mapping.search_index_id
        for message_search_index_mapping in message_search_index_mappings
        if message_search_index_mapping.use_index
    ]

    if (
        (len(retrieval_results) == 0)
        and (len(searched_index_ids) > 0)
        or (len(user_retrieval_results) == 0)
        and (len(user_message_search_index_mappings) > 0)
    ):
        # set prompt segment if any index found.
        prompt_segment_retrieval = (
            "\n\nThe following document(s) were searched but no relevant material was found:\n\n```"
        )

    # central index results
    async with async_db_session() as session:
        if (len(retrieval_results) == 0) and (len(searched_index_ids) > 0):
            for searched_index_id in searched_index_ids:
                execute = await session.execute(
                    select(Document)
                    .distinct(Document.id)
                    .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                    .join(SearchIndex, SearchIndex.id == DocumentChunk.search_index_id)
                    .where(SearchIndex.id == searched_index_id)
                    .where(SearchIndex.id == searched_index_id)
                )
                documents = execute.scalars().all()
                for document in documents:
                    prompt_segment_retrieval += f"\n{document.name}"

        # check user indexes
        if (len(user_retrieval_results) == 0) and (len(user_message_search_index_mappings) > 0):
            user_searched_index_ids = [
                message_search_index_mapping.search_index_id
                for message_search_index_mapping in user_message_search_index_mappings
                if message_search_index_mapping.use_index
            ]
            for searched_index_id in user_searched_index_ids:
                execute = await session.execute(
                    select(Document)
                    .distinct(Document.id)
                    .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                    .join(SearchIndex, SearchIndex.id == DocumentChunk.search_index_id)
                    .where(SearchIndex.id == searched_index_id)
                    .where(Document.uuid.in_(rag_request.document_uuids))
                )
                documents = execute.scalars().all()
                for document in documents:
                    prompt_segment_retrieval += f"\n{document.name}"

        # check if prompt was updated, then add closing ticks (```)
        if prompt_segment_retrieval != "":
            prompt_segment_retrieval += "\n```"

        full_query = f"{user_message}{prompt_segment_retrieval}"

        return (full_query, citation_message)


async def rag(rag_request: RagRequest, message: Message):
    logger.info("starting rag()")
    # Get all the index objects from the database
    async with async_db_session() as session:
        indexes = await list_indexes(session, include_personal_document_index=False)
        execute = await session.execute(select(LLM).filter(LLM.model == llm_model_index_router))
        llm_index_router = execute.scalar_one()

        execute = await session.execute(select(LLM).filter(LLM.model == llm_model_query_rewriter))
        llm_query_rewriter = execute.scalar_one()

        execute = await session.execute(select(LLM).filter(LLM.model == llm_model_chunk_reviewer))
        llm_chunk_reviewer = execute.scalar_one()

        execute = await session.execute(
            select(SystemPrompt).filter(SystemPrompt.name == system_prompt_name_index_router)
        )
        system_prompt_index_router = execute.scalar_one()

        execute = await session.execute(
            select(SystemPrompt).filter(SystemPrompt.name == system_prompt_name_query_rewriter)
        )
        system_prompt_query_rewriter = execute.scalar_one()

        execute = await session.execute(
            select(SystemPrompt).filter(SystemPrompt.name == system_prompt_name_chunk_reviewer)
        )
        system_prompt_chunk_reviewer = execute.scalar_one()

    # Retrieve relevant search results from the search engine if central rag enabled.
    central_rag = (
        await retrieve_relevant_chunks(
            rag_request,
            indexes,
            message,
            llm_index_router,
            llm_query_rewriter,
            llm_chunk_reviewer,
            system_prompt_index_router,
            system_prompt_query_rewriter,
            system_prompt_chunk_reviewer,
            index_chunk_search_fn=search_index_for_chunks,
        )
        if rag_request.use_central_rag
        else {"retrieval_results": [], "message_search_index_mappings": []}
    )

    retrieval_results = central_rag["retrieval_results"]
    message_search_index_mappings = central_rag["message_search_index_mappings"]

    # rag with personal document index
    pdu_rag_output = (
        await personal_document_rag(
            rag_request,
            message,
            llm_query_rewriter,
            system_prompt_query_rewriter,
        )
        if rag_request.document_uuids
        else {}
    )

    # Unpack the data
    pdu_retrieval_results = pdu_rag_output.get("retrieval_results", [])

    pdu_message_search_index_mappings = pdu_rag_output.get("message_search_index_mappings", [])

    # Use the search results to create an enriched query
    # If the list of retrieval_results is empty, then the returned query will simply be the original user query.
    # The citation_message is appended to the AI message.
    full_query, citation_message = await create_full_query(
        rag_request,
        pdu_message_search_index_mappings,
        pdu_retrieval_results,
        retrieval_results,
        message_search_index_mappings,
    )
    logger.info("Citation is %s", citation_message)
    return (full_query, citation_message)


async def run_rag(rag_request: RagRequest, message: Message):
    """
    Runs RAG process to search information related to the user's query and
    inject that information to the user query sent to the LLM model.
    """
    logger.debug("starting to run rag with %s", rag_request)
    try:
        return await rag(rag_request, message)
    except Exception:
        logger.exception("Rag process got error")
        raise
