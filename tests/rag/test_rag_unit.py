import asyncio
import logging
from unittest.mock import patch

import pytest

from app.config import LLM_DEFAULT_MODEL, LLM_DEFAULT_PROVIDER
from app.database.models import (
    LLM,
    Document,
    DocumentChunk,
    Message,
    MessageDocumentChunkMapping,
    MessageSearchIndexMapping,
    SearchIndex,
    SystemPrompt,
)
from app.services.rag import (
    Claude35SonnetTransaction,
    RagRequest,
    RetrievalResult,
    create_full_query,
    rewrite_user_query,
)

logger = logging.getLogger(__name__)


@pytest.mark.rag
class TestRagUnit:
    @pytest.fixture
    def mock_message(self):
        return Message(id=1)

    @pytest.fixture
    def mock_search_index(self):
        return SearchIndex(id=1, name="test_index", description="Test Index")

    @pytest.fixture
    def mock_search_indexes(self):
        return [
            SearchIndex(id=1, name="test_index_1", description="Test Index 1"),
            SearchIndex(id=2, name="test_index_2", description="Test Index 2"),
            SearchIndex(id=3, name="test_index_3", description="Test Index 3"),
        ]

    @pytest.fixture
    def mock_search_index_mapping(self):
        return MessageSearchIndexMapping(search_index_id=1, message_id=1, llm_internal_response_id=1, use_index=False)

    @pytest.fixture
    def mock_system_prompt(self):
        return SystemPrompt(id=1, name="test_prompt", content="Test prompt content")

    @pytest.fixture
    def mock_llm(self):
        logger.info("Creating LLM Fixture with model: anthropic.claude-v2:1")
        return LLM(id=1, model=LLM_DEFAULT_MODEL, provider=LLM_DEFAULT_PROVIDER)

    @pytest.fixture
    def retrieval_result(self):
        document_chunk = DocumentChunk(
            search_index_id=1,
            document_id="1",
            name="chunk 1",
            content="Chunk content",
            id_opensearch="0hnzn16rbkh3n5t16i",
        )
        document = Document(id=1, name="Document 1", description="This is a test document", url="https://google.com")
        message_document_chunk_mapping = MessageDocumentChunkMapping(
            message_id=1,
            document_chunk_id=1,
            llm_internal_response_id=1,
            opensearch_score=1.0,
            use_document_chunk=True,
        )
        search_index = SearchIndex(name="Test index", description="For testing indexes")

        return RetrievalResult(
            search_index=search_index,
            document_chunk=document_chunk,
            document=document,
            message_document_chunk_mapping=message_document_chunk_mapping,
        )

    @pytest.mark.asyncio
    async def test_async_setup(self):
        async def simple_async_function():
            await asyncio.sleep(1)
            return "async setup works!"

        result = await simple_async_function()
        assert result == "async setup works!"

    async def test_create_full_query(self, retrieval_result):
        search_index_1 = SearchIndex(name="Test index 1", description="For testing index 1")
        document_1 = Document(id=1, name="Document 1", description="This is a test document", url="https://google.com")

        document_chunk_1 = DocumentChunk(
            search_index_id=1,
            document_id=1,
            name="Document Chunk 1",
            content="Test content for document 1 and chunk 1",
            id_opensearch="abcd1234dcba",
        )
        message_document_chunk_mapping_1 = MessageDocumentChunkMapping(
            message_id=1, document_chunk_id=1, llm_internal_response_id=1, opensearch_score=1.0, use_document_chunk=True
        )
        message_search_index_mapping_1 = MessageSearchIndexMapping(
            search_index_id=1, message_id=1, llm_internal_response_id=1, use_index=True
        )

        retrieval_result_1 = RetrievalResult(
            search_index=search_index_1,
            document_chunk=document_chunk_1,
            document=document_1,
            message_document_chunk_mapping=message_document_chunk_mapping_1,
        )

        search_index_2 = SearchIndex(name="Test index 2", description="For testing index 2")
        document_2 = Document(id=2, name="Document 2", description="This is a test document", url="https://bing.com")

        document_chunk_2 = DocumentChunk(
            search_index_id=2,
            document_id=2,
            name="Document Chunk 2",
            content="Test content for document 2 and chunk 2",
            id_opensearch="abcd1234dcbadffdd",
        )
        message_document_chunk_mapping_2 = MessageDocumentChunkMapping(
            message_id=2, document_chunk_id=2, llm_internal_response_id=2, opensearch_score=1.0, use_document_chunk=True
        )
        message_search_index_mapping_2 = MessageSearchIndexMapping(
            search_index_id=2, message_id=2, llm_internal_response_id=2, use_index=True
        )

        retrieval_result_2 = RetrievalResult(
            search_index=search_index_2,
            document_chunk=document_chunk_2,
            document=document_2,
            message_document_chunk_mapping=message_document_chunk_mapping_2,
        )

        logger.info("\n\nTesting with retrieval results")
        query = "How are bananas?"
        rag_request = RagRequest(True, 1, query)

        result = await create_full_query(
            rag_request,
            [],
            [],
            [retrieval_result_1, retrieval_result_2],
            [message_search_index_mapping_1, message_search_index_mapping_2],
        )
        full_query, citation_message = result

        assert type(result) is tuple, "Invalid return type"
        assert len(result) == 2, "Invalid or partial result returned"
        assert result is not None, "None is returned"

        logger.info("\n\nTesting without retrieval results")
        result = await create_full_query(
            rag_request, [], [], [], [message_search_index_mapping_1, message_search_index_mapping_2]
        )
        full_query, citation_message = result

        assert citation_message == [], "Invalid response for citation message"
        assert type(result) is tuple, "Invalid return type"
        assert len(result) == 2, "Invalid or partial result returned"
        assert result is not None, "None is returned"

        logger.info("\n\nTesting without retrieval results and search index mappings")

        result = await create_full_query(rag_request, [], [], [], [])
        full_query, citation_message = result

        assert citation_message == [], "Invalid response for citation message"
        assert type(result) is tuple, "Invalid return type"
        assert len(result) == 2, "Invalid or partial result returned"
        assert result is not None, "None is returned"

    def test_completion_cost(self):
        # Test case 1: Check if the completion cost is calculated correctly for given tokens_in and tokens_out
        logger.info("Testing Completion Cost is computed correctly")
        transaction = Claude35SonnetTransaction(tokens_in=1000, tokens_out=2000)
        expected_cost = (1000 * (3 / 1e6)) + (2000 * (15 / 1e6))
        assert transaction.completion_cost() == expected_cost, "Something wrong with computation"

        # Test case 2: Check if the completion cost is zero when tokens_in and tokens_out are zero
        logger.info("Testing the computation cost is zero when in and out tokens are zone")
        transaction = Claude35SonnetTransaction(tokens_in=0, tokens_out=0)
        expected_cost = 0
        assert transaction.completion_cost() == expected_cost, "Something wrong witgh computation"

        # Test case 3: Check if the completion cost is correct when tokens_in is zero and tokens_out is non-zero
        logger.info("Testing the computation cost is correct tokens in=0 and token out is greater than zero")
        transaction = Claude35SonnetTransaction(tokens_in=0, tokens_out=5000)
        expected_cost = 5000 * (15 / 1e6)
        assert transaction.completion_cost() == expected_cost, "Something wrong with compution"

        # Test case 4: Check if the completion cost is correct when tokens_in is non-zero and tokens_out is zero
        logger.info("Testing the computation cost is correct when tokens in > 0 and tokens_out = 0")
        transaction = Claude35SonnetTransaction(tokens_in=3000, tokens_out=0)
        expected_cost = 3000 * (3 / 1e6)
        assert transaction.completion_cost() == expected_cost, "Something wrong with computation"

    @pytest.mark.asyncio
    async def test_rewrite_user_query(self, mock_search_index, mock_message, mock_llm, mock_system_prompt):
        with patch("app.services.rag.rewrite_user_query") as mocked:
            mocked.return_value = "A comprehensive plan to improve AI"
            original_query = "how to improve AI"
            rewritten_query = await rewrite_user_query(
                original_query, mock_search_index, mock_message, mock_llm, mock_system_prompt
            )
            logger.info(f"Type of rewritten query: {rewritten_query}")
            logger.info("Rewritten query: %s", rewritten_query)
            assert rewritten_query != original_query
