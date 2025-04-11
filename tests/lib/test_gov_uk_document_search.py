from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.app_types.gov_uk_search import DocumentBlacklistStatus, NonRagDocument
from app.config import LLM_DEFAULT_MODEL
from app.database.db_operations import DbOperations
from app.database.table import LLMTable, async_db_session
from app.lib.gov_uk_document_search import (
    extract_urls_from_query,
    get_relevant_non_rag_documents_using_gov_uk_search_api,
    get_search_terms_matching_user_query,
    is_document_relevant,
    wrap_non_rag_document,
)
from app.services.bedrock import BedrockHandler, RunMode


async def response():
    document_relevancy = {"content": {"input": {"is_relevant": True}, "type": "tool_use"}}
    return document_relevancy


@patch("app.services.bedrock.bedrock.BedrockHandler")
@pytest.mark.asyncio
async def test_is_document_relevant(mock: MagicMock):
    mock.invoke_async.return_value = response()
    llm = mock

    role = "user"
    query = "Just a test."
    document = "TEST DOC"
    title = "TEST TITLE"

    wrapped_document = await is_document_relevant(
        llm=llm, role=role, query=query, non_rag_document=document, non_rag_document_title=title
    )

    assert "content" in wrapped_document
    assert wrapped_document.get("content").get("input").get("is_relevant") is True
    assert wrapped_document.get("content").get("type") == "tool_use"


@pytest.mark.asyncio
async def test_wrap_non_rag_document():
    document = NonRagDocument(
        url="http://www.example.com/", title="Test Title", body="Test Body", status=DocumentBlacklistStatus.OK
    )
    wrapped_document = await wrap_non_rag_document(i=1, document=document)

    assert "<gov-uk-search-result-1>" in wrapped_document
    assert document.title in wrapped_document
    assert document.body in wrapped_document
    assert document.url in wrapped_document


@patch("app.lib.gov_uk_document_search.DbOperations.insert_llm_internal_response_id_query")
@patch("app.lib.gov_uk_document_search.DbOperations.insert_gov_uk_search_result")
@patch("app.lib.gov_uk_document_search.DbOperations.insert_gov_uk_search_query")
@pytest.mark.asyncio
async def test_get_relevant_non_rag_documents_using_gov_uk_search_api(func1, func2, func3):
    func1 = AsyncMock()  # noqa: F841
    func2 = AsyncMock()  # noqa: F841
    func3 = AsyncMock()  # noqa: F841

    llm_obj = LLMTable().get_by_model(LLM_DEFAULT_MODEL)
    web_browsing_llm = BedrockHandler(llm=llm_obj, mode=RunMode.ASYNC)

    async with async_db_session() as db_session:
        result = await DbOperations.insert_llm_internal_response_id_query(
            db_session=db_session,
            web_browsing_llm=web_browsing_llm,
            content="TEST",
            tokens_in=10,
            tokens_out=100,
            completion_cost=10 * web_browsing_llm.llm.input_cost_per_token
            + 100 * web_browsing_llm.llm.output_cost_per_token,
        )
        internal_response_id_query = result

    relevant_documents = await get_relevant_non_rag_documents_using_gov_uk_search_api(
        llm=web_browsing_llm,
        role="user",
        query="What are current UK Personal Income Tax rates?",
        search_terms=["personal income tax", "capital gains tax"],
        m_user_id=1,
        llm_internal_response_id_query=internal_response_id_query.id,
    )

    assert len(relevant_documents) > 0
    assert relevant_documents[0].url != ""


@pytest.mark.asyncio
async def test_get_search_terms_matching_user_query(user_id):
    llm_obj = LLMTable().get_by_model(LLM_DEFAULT_MODEL)
    web_browsing_llm = BedrockHandler(llm=llm_obj, mode=RunMode.ASYNC)

    search_terms, llm_internal_response_id_query = await get_search_terms_matching_user_query(
        llm=web_browsing_llm,
        role="user",
        query="What are current UK Personal Income Tax rates?",
    )

    assert len(search_terms) > 0
    assert llm_internal_response_id_query is not None


@pytest.mark.asyncio
async def test_extract_urls_from_query(user_id):
    llm_obj = LLMTable().get_by_model(LLM_DEFAULT_MODEL)
    web_browsing_llm = BedrockHandler(llm=llm_obj, mode=RunMode.ASYNC)

    url1 = "http://www.example.com/"
    url2 = "https://aws.amazon.com/"
    url3 = "https://www.gov.uk/"

    urls = await extract_urls_from_query(
        llm=web_browsing_llm, role="user", query=f"I'd like to sumarise {url1}, {url2}, {url3}?"
    )

    assert len(urls) == 3
    assert len([u for u in urls if u.startswith(url1)]) > 0
    assert len([u for u in urls if u.startswith(url2)]) > 0
    assert len([u for u in urls if u.startswith(url3)]) > 0
