import asyncio
from typing import List, Optional, Tuple

from app.app_types.gov_uk_search import IsNonRagDocumentRelevantTask, NonRagDocument
from app.config import GOV_UK_SEARCH_MAX_COUNT
from app.database.db_operations import DbOperations
from app.database.table import async_db_session
from app.lib import logger
from app.services.bedrock import BedrockHandler
from app.services.bedrock.bedrock import Result
from app.services.bedrock.tools_use import DOCUMENT_RELEVANCE_ASSESSMENT, DOWNLOAD_URLS, SEARCH_API_SEARCH_TERMS
from app.services.gov_uk_search.gov_uk_search import GovUKSearch
from app.services.web_browser.web_browser import WebBrowserService


async def is_document_relevant(
    llm: BedrockHandler, role: str, query: str, non_rag_document: str, non_rag_document_title: str
) -> Result:
    messages = [
        {
            "role": role,
            "content": (
                f"<user-query>\n\n{query}\n\n</user-qeury>\n\n"
                f"<retrieved-gov-uk-page>\n\n"
                f"<retrieved-gov-uk-page-title>{non_rag_document_title}</retrieved-gov-uk-page-title>\n\n"
                f"<retrieved-gov-uk-page-content>{non_rag_document}</retrieved-gov-uk-page-content>\n\n"
                f"</retrieved-gov-uk-page>"
            ),
        }
    ]
    logger.debug(f"messages: {messages}")

    llm_res = await llm.invoke_async(
        messages=messages,
        tools=DOCUMENT_RELEVANCE_ASSESSMENT["tools"],
    )

    return llm_res


async def wrap_non_rag_document(i: int, document: NonRagDocument) -> str:
    # Build a text blob used to amend the original user prompt
    wrapped_document = ""
    wrapped_document += "\n"
    wrapped_document += f"<gov-uk-search-result-{i}>\n<document-title>{document.title}</document-title>\n"
    wrapped_document += f"<gov-uk-search-result-{i}>\n<document-url>{document.url}</document-url>\n"
    wrapped_document += "<document-body>"
    wrapped_document += document.body
    wrapped_document += f"</document-body></gov-uk-search-result-{i}>"

    return wrapped_document


async def get_relevant_non_rag_documents_using_gov_uk_search_api(
    llm: BedrockHandler,
    role: str,
    query: str,
    search_terms: List[Optional[str]],
    m_user_id: int,
    llm_internal_response_id_query: int,
) -> List[Optional[NonRagDocument]]:
    logger.debug(f"Searching GOV UK for documents matching the following search terms: {search_terms}")

    gov_uk_search = GovUKSearch()
    gov_uk_search_tasks = []
    found_documents = []

    async with asyncio.TaskGroup() as tg:
        for term in search_terms:
            gov_uk_search_tasks.append(
                tg.create_task(
                    gov_uk_search.simple_search(
                        query=term,
                        count=GOV_UK_SEARCH_MAX_COUNT,
                        llm_internal_response_id_query=llm_internal_response_id_query,
                    )
                )
            )

    logger.debug(f"gov_uk_search_tasks: {gov_uk_search_tasks}")
    for task in gov_uk_search_tasks:
        result = task.result()
        found_documents.append(result)
        logger.debug(f"gov_uk_search result: {result}")

    found_urls = {}
    for document in found_documents:
        for results in document[0].get("results", []):
            if results.get("link") not in found_urls:
                document_link = WebBrowserService.strip_url(results.get("link"))
                found_urls[document_link] = document[1]

    non_rag_documents = await WebBrowserService.get_documents(urls=list(found_urls.keys()))
    logger.debug(f"--- found_urls: {found_urls}")
    logger.debug(f"--- non_rag_documents: {non_rag_documents}")

    # check document relevancy
    is_document_relevant_tasks = []
    async with asyncio.TaskGroup() as tg:
        for document in non_rag_documents:
            doc_path = WebBrowserService.strip_url(document.url)
            is_document_relevant_tasks.append(
                (
                    IsNonRagDocumentRelevantTask(
                        document=document,
                        task=tg.create_task(
                            is_document_relevant(
                                llm=llm,
                                role=role,
                                query=query,
                                non_rag_document=document.body,
                                non_rag_document_title=document.title,
                            )
                        ),
                    ),
                    found_urls[doc_path],
                )
            )

    relevant_documents = []
    for document in is_document_relevant_tasks:
        position = 1
        try:
            document_relevancy = document[0].task.result()
            document_relevancy_dict = document_relevancy.dict()
        except Exception as e:
            logger.exception("LLM response cannot be cast into a dict: %s", e)
            continue

        content = document_relevancy_dict.get("content")
        is_doc_relevant = [
            item.get("input", {}).get("is_relevant", False) for item in content if item.get("type") == "tool_use"
        ]

        # Log the llm internal response (document relevancy to the given query) to the database
        async with async_db_session() as db_session:
            response = await DbOperations.insert_llm_internal_response_id_query(
                db_session=db_session,
                web_browsing_llm=llm.llm,
                content=document_relevancy.content[0].text,
                tokens_in=document_relevancy.usage.input_tokens,
                tokens_out=document_relevancy.usage.output_tokens,
                completion_cost=document_relevancy.usage.input_tokens * llm.llm.input_cost_per_token
                + document_relevancy.usage.output_tokens * llm.llm.output_cost_per_token,
            )
            llm_internal_response_id_search_result = response.id

        # This is needed, because the LLM will sometimes return relevancy as a bool or a bool string
        # madness...
        is_used = False
        if isinstance(is_doc_relevant, list):
            if len(is_doc_relevant) > 0:
                if is_doc_relevant[0] == "True" or True:
                    is_used = True
                if is_doc_relevant[0] == "False" or False:
                    is_used = False

        async with async_db_session() as db_session:
            await DbOperations.insert_gov_uk_search_result(
                db_session=db_session,
                llm_internal_response_id=llm_internal_response_id_search_result,
                message_id=m_user_id,
                gov_uk_search_query_id=document[1].id,
                url=document[0].document.url,
                content=document[0].document.body,
                is_used=is_used,
                position=position,
            )
            position += 1

        if is_used:
            relevant_documents.append(document[0].document)

    logger.debug(f"all documents retrieved using search API: {len(non_rag_documents)}")
    logger.debug(f"all documents relevant to query: {len(relevant_documents)}")
    logger.debug(f"all relevant_documents to query-: {relevant_documents}")

    return relevant_documents


async def get_search_terms_matching_user_query(
    llm: BedrockHandler, role: str, query: str
) -> Tuple[List[Optional[str]], int]:
    logger.debug(f"Tool use (call_gov_uk_search_api) using LLM: {llm}")

    search_terms_list = []

    # prepare message for the LLM
    message_tool_use_call_gov_uk_search_api = [
        {
            "role": role,
            "content": (
                "Get documents that best match the query below using search terms"
                " that best match that query. Only use the call_gov_uk_search_api tool"
            )
            + "\n\n"
            + query,
        }
    ]
    logger.debug(f"Tool use (call_gov_uk_search_api) call message -> {message_tool_use_call_gov_uk_search_api}")

    # Ask the LLM to return a call_gov_uk_search_api function call object
    logger.debug(f"message_tool_use_call_gov_uk_search_api: {message_tool_use_call_gov_uk_search_api}")
    llm_response_call_gov_uk_search_api = await llm.invoke_async(
        message_tool_use_call_gov_uk_search_api, tools=SEARCH_API_SEARCH_TERMS["tools"]
    )

    logger.debug(f"llm_response_call_gov_uk_search_api: {llm_response_call_gov_uk_search_api}")

    # Log response to the tool use (function calling) prompt asking the
    # LLM for a list of search terms to be used with GOV UK Search API
    # Log the raw LLM response to the database to allow:
    # - tracking the cost of the query and the raw response
    # - debugging issues with the query
    async with async_db_session() as db_session:
        llm_internal_response_query = await DbOperations.insert_llm_internal_response_id_query(
            db_session=db_session,
            web_browsing_llm=llm.llm,
            content=llm_response_call_gov_uk_search_api.content[0].text,
            tokens_in=llm_response_call_gov_uk_search_api.usage.input_tokens,
            tokens_out=llm_response_call_gov_uk_search_api.usage.output_tokens,
            completion_cost=llm_response_call_gov_uk_search_api.usage.input_tokens * llm.llm.input_cost_per_token
            + llm_response_call_gov_uk_search_api.usage.output_tokens * llm.llm.output_cost_per_token,
        )
        llm_internal_response_id_query = llm_internal_response_query.id

    call_gov_uk_search_api_obj = {}
    try:
        call_gov_uk_search_api_obj = llm_response_call_gov_uk_search_api.dict()
        logger.debug(f"Tool use (call_gov_uk_search_api) response as dict: {call_gov_uk_search_api_obj}")

    except Exception as e:
        logger.exception(
            "Tool use (call_gov_uk_search_api) failed with %s \nSkipping GOV UK search, because of %s",
            call_gov_uk_search_api_obj,
            e,
        )

    logger.debug(f"call_gov_uk_search_api_obj: {call_gov_uk_search_api_obj}")

    if call_gov_uk_search_api_obj:
        try:
            if not isinstance(call_gov_uk_search_api_obj, dict):
                raise TypeError("call_gov_uk_search_api_obj not a dict")
            llm_response_content = call_gov_uk_search_api_obj.get("content", [])
            for content_item in llm_response_content:
                logger.debug(f"terms item: {content_item}")
                content_type = content_item.get("type", False)
                if content_type and content_type == "tool_use":
                    search_terms = content_item.get("input", {}).get("search_terms", [])
                    search_terms_list += search_terms
        except Exception as e:
            logger.exception(
                "call_gov_uk_search_api_obj dict() %s exception: %s", llm_response_call_gov_uk_search_api, e
            )

    # dedup list
    found_search_terms = set(search_terms_list)
    found_search_terms_str = ",".join(found_search_terms)
    logger.debug(f"found_search_terms_str: {found_search_terms_str}")
    return list(found_search_terms), llm_internal_response_id_query


async def extract_urls_from_query(llm: BedrockHandler, role: str, query: str) -> List[Optional[str]]:
    logger.debug(f"Tool use (download_urls) using LLM: {llm}")

    # prepare message for the LLM
    message_tool_use_download_urls = [
        {
            "role": role,
            "content": ("Get documents whose URLs are listed in the query. Only use the download_urls tool")
            + "\n\n"
            + query,
        }
    ]
    logger.debug(f"Tool use (download_urls) call message -> {message_tool_use_download_urls}")

    # Ask the LLM to return a download_urls function call object
    llm_response_download_urls = await llm.invoke_async(message_tool_use_download_urls, tools=DOWNLOAD_URLS["tools"])
    logger.debug(f"llm_response_download_urls: {llm_response_download_urls}")

    # See if any URLs were in the user's query
    llm_response_download_urls_obj = {}
    try:
        llm_response_download_urls_obj = llm_response_download_urls.dict()
        logger.debug(f"Tool use (llm_response_download_urls_obj) response as dict: {llm_response_download_urls_obj}")
    except Exception as e:
        logger.exception(
            "Tool use (llm_response_download_urls_obj) response %s to_dict() exception: %s",
            llm_response_download_urls_obj,
            e,
        )

    urls = []
    if not llm_response_download_urls_obj:
        logger.debug("Tool use (llm_response_download_urls_obj) failed, skipping web search")
    else:
        try:
            if not isinstance(llm_response_download_urls_obj, dict):
                raise TypeError("llm_response_download_urls_obj not a dict")
            llm_response_content = llm_response_download_urls_obj.get("content", {})
            urls = []
            for tool_response_item in llm_response_content:
                if tool_response_item.get("type") == "tool_use":
                    urls += tool_response_item.get("input", {}).get("urls", [])
                urls += tool_response_item.get("input", {}).get("urls", [])
            logger.debug(f"Found URLs: {urls}")
        except Exception as e:
            logger.exception(
                "llm_response_download_urls_obj dict() %s exception: %s", llm_response_download_urls_obj, e
            )

    dedup_url_list = set(urls)
    return list(dedup_url_list)
