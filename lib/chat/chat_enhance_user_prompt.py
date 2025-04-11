import asyncio

from app.app_types.chat import ChatCreateMessageInput
from app.app_types.message import RoleEnum
from app.config import LLM_DEFAULT_MODEL, LLM_DOCUMENT_RELEVANCY_MODEL
from app.database.models import (
    Chat,
)
from app.database.table import LLMTable
from app.lib import logger
from app.lib.gov_uk_document_search import (
    extract_urls_from_query,
    get_relevant_non_rag_documents_using_gov_uk_search_api,
    get_search_terms_matching_user_query,
    wrap_non_rag_document,
)
from app.services.bedrock import BedrockHandler, RunMode

from ...app_types.gov_uk_search import DocumentBlacklistStatus
from ...services.web_browser.web_browser import WebBrowserService


async def enhance_user_prompt(chat: Chat, input_data: ChatCreateMessageInput, m_user_id: int):
    if not chat:
        raise Exception("Chat not found")

    llm_obj = LLMTable().get_by_model(LLM_DEFAULT_MODEL)
    llm_document_relevancy_obj = LLMTable().get_by_model(LLM_DOCUMENT_RELEVANCY_MODEL)

    if not llm_obj:
        raise Exception("LLM not found with name: " + LLM_DEFAULT_MODEL)

    web_browsing_llm = BedrockHandler(llm=llm_obj, mode=RunMode.ASYNC)
    document_relevancy_llm = BedrockHandler(llm=llm_document_relevancy_obj, mode=RunMode.ASYNC)

    non_rag_document_urls = []
    non_rag_citations = []
    search_terms = []

    # Do we use GOV UK Search API?

    # Call the LLM to obtain search terms to be used in Search API calls and
    # extract URL for query, if any were provided by the user.
    get_search_terms_matching_user_query_task = None
    extract_urls_from_query_task = None

    async with asyncio.TaskGroup() as tg:
        if input_data.use_gov_uk_search_api:
            get_search_terms_matching_user_query_task = tg.create_task(
                get_search_terms_matching_user_query(llm=web_browsing_llm, role=RoleEnum.user, query=input_data.query)
            )
        if input_data.enable_web_browsing:
            extract_urls_from_query_task = tg.create_task(
                extract_urls_from_query(llm=web_browsing_llm, role=RoleEnum.user, query=input_data.query)
            )

    llm_internal_response_id_query = None
    if input_data.use_gov_uk_search_api:
        search_terms, llm_internal_response_id_query = get_search_terms_matching_user_query_task.result()
        logger.debug(f"search terms matching the user query: {search_terms}")

    if input_data.enable_web_browsing:
        non_rag_document_urls = extract_urls_from_query_task.result()
        logger.debug(f"non_rag_document_urls found in the user query: {non_rag_document_urls}")

    get_relevant_non_rag_documents_using_gov_uk_search_api_task = None
    get_non_rag_documents_mentioned_in_the_query_task = None

    async with asyncio.TaskGroup() as tg:
        if input_data.use_gov_uk_search_api:
            get_relevant_non_rag_documents_using_gov_uk_search_api_task = tg.create_task(
                get_relevant_non_rag_documents_using_gov_uk_search_api(
                    llm=document_relevancy_llm,
                    role=RoleEnum.user,
                    query=input_data.query,
                    search_terms=search_terms,
                    m_user_id=m_user_id,
                    llm_internal_response_id_query=llm_internal_response_id_query,
                )
            )
        if input_data.enable_web_browsing:
            get_non_rag_documents_mentioned_in_the_query_task = tg.create_task(
                WebBrowserService.get_documents(urls=non_rag_document_urls)
            )

    cited_relevant_documents_obtained_using_gov_uk_search_api = []
    cited_documents_obtained_using_user_provided_urls = []
    blacklisted_documents = []

    if input_data.use_gov_uk_search_api:
        documents_retrieved_using_gov_uk_search = get_relevant_non_rag_documents_using_gov_uk_search_api_task.result()
        logger.debug(f"documents_retrieved_using_gov_uk_search: {documents_retrieved_using_gov_uk_search}")

        for non_rag_document in documents_retrieved_using_gov_uk_search:
            if non_rag_document.status == DocumentBlacklistStatus.BLACKLISTED:
                blacklisted_documents.append(non_rag_document)
                continue
            cited_relevant_documents_obtained_using_gov_uk_search_api.append(non_rag_document)

    if input_data.enable_web_browsing:
        documents_explicitly_requested = get_non_rag_documents_mentioned_in_the_query_task.result()

        for non_rag_document in documents_explicitly_requested:
            if non_rag_document.status == DocumentBlacklistStatus.BLACKLISTED:
                blacklisted_documents.append(non_rag_document)
                continue
            cited_documents_obtained_using_user_provided_urls.append(non_rag_document)

    # Amend user prompt
    non_rag_document_list = (
        cited_relevant_documents_obtained_using_gov_uk_search_api + cited_documents_obtained_using_user_provided_urls
    )
    non_rag_documents = ""
    for c, i in enumerate(non_rag_document_list, 1):
        non_rag_documents += await wrap_non_rag_document(c, i)
        non_rag_documents += "\n\n"

    for document in non_rag_document_list:
        non_rag_citations.append({"docname": document.title, "docurl": document.url})

    return non_rag_documents, non_rag_citations
