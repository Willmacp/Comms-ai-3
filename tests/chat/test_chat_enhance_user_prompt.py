# noqa: F841

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lib.chat import enhance_user_prompt


@patch("app.lib.gov_uk_document_search.DbOperations.insert_llm_internal_response_id_query")
@patch("app.lib.gov_uk_document_search.DbOperations.insert_gov_uk_search_result")
@patch("app.lib.gov_uk_document_search.DbOperations.insert_gov_uk_search_query")
@pytest.mark.asyncio
async def test_enhance_user_prompt(func1, func2, func3):
    chat = MagicMock()
    func1 = AsyncMock()  # noqa: F841
    func2 = AsyncMock()  # noqa: F841
    func3 = AsyncMock()  # noqa: F841

    input_data = MagicMock()
    input_data.use_gov_uk_search_api = True
    input_data.enable_web_browsing = True
    input_data.query = "What are the current tax rates?"

    found_url = "https://www.gov.uk"
    blacklisted_url = "https://www.gov.uk/publications"

    non_rag_documents, non_rag_citations = await enhance_user_prompt(chat=chat, input_data=input_data, m_user_id=None)

    assert found_url in non_rag_documents
    assert len([doc.get("docurl") for doc in non_rag_citations if doc.get("docurl").startswith(found_url)]) > 0
    assert len([doc.get("docurl") for doc in non_rag_citations if doc.get("docurl").startswith(blacklisted_url)]) == 0
