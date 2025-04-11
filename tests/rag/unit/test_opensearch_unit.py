import logging
import time
from unittest.mock import AsyncMock, patch

import pytest
from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestError

from app.services.opensearch import AsyncOpenSearchOperations, list_indexes

load_dotenv()

logger = logging.getLogger(__name__)
index_name = "py_test_index_1"


@pytest.mark.opensearch
class TestOpensearch:
    async def test_create_index(self, db_session, opensearch_client: OpenSearch):
        logger.info("\nSTARTING test_create_index....\n*******************\n\n")

        exists = False

        for idx in await list_indexes(db_session):
            if idx.name == index_name:
                exists = True
                break
        logger.info(f"Index: {index_name} exists? {exists}")

        if not exists:
            logger.info(f"Creating the Index {index_name}")

            created_index = opensearch_client.indices.create(index_name)

            assert created_index is not None, "Index creation failed"

    def test_add_documents_to_index(self, opensearch_client: OpenSearch):
        logger.info("\nSTARTING test_add_documents_to_index....\n*******************\n\n")
        data = [
            {
                "document_name": "Test Document",
                "document_url": "http://testurl.com",
                "document_description": "A test document",
                "chunk_name": "Introduction",
                "chunk_content": "This is the introduction content.",
            },
            {
                "document_name": "Test Document",
                "document_url": "http://testurl.com",
                "document_description": "A test document",
                "chunk_name": "Core Concept",
                "chunk_content": "This is the core concept content.",
            },
            {
                "document_name": "Test Document",
                "document_url": "http://testurl.com",
                "document_description": "A test document",
                "chunk_name": "Conclusion",
                "chunk_content": "This is the conclusion content.",
            },
        ]

        logger.info(f"Length of Data to be added: {len(data)}")

        for i, doc in enumerate(data):
            response = opensearch_client.index(index=index_name, id=i + 1, body=doc)
            print(f"Document {i + 1} insertion response: {response['result']}")
            logger.info("Sleeping for 5 seconds")
            time.sleep(5)
            assert response["result"] in ["created", "updated"], f"Document insertion failed for id={i}"

    def test_get_index_documents(self, opensearch_client: OpenSearch):
        logger.info("\nSTARTING test_get_index_documents....\n*******************\n\n")

        response = opensearch_client.search(
            index=index_name,
            body={"query": {"match_all": {}}},
            size=1000,  # Adjust size based on the number of documents expected
        )

        assert response is not None, "No response was received"
        assert response["timed_out"] is False, "Request has timed out"
        assert response["_shards"]["successful"] == 1, "Request was not successful"

        logger.info(f"Response of searchall is: {len(response['hits']['hits'])}")

    def test_delete_document_by_document_id(self, opensearch_client: OpenSearch):
        logger.info("\nSTARTING test_delete_document_by_document_id....\n*******************\n\n")

        response = opensearch_client.delete(index=index_name, id="1")

        logger.info(f"Response of deleting a documeht by Document ID and Index: {response}\nSleeping for 3 seconds")

        assert response is not None, "No response was received"
        assert response["result"] == "deleted", "Document was not deleted"
        assert response["_shards"]["failed"] == 0, f"Document deletion for index {index_name} failed"

        time.sleep(3)

    def test_delete_all_documents(self, opensearch_client: OpenSearch):
        logger.info("\nSTARTING test_delete_all_documents....\n*******************\n\n")

        response = opensearch_client.delete_by_query(index=index_name, body={"query": {"match_all": {}}})

        logger.info(f"Response of deleting all documents by Index: {response}")

        assert response is not None, "No response was received"
        assert response["timed_out"] is False, "Request has timed out"
        assert response["failures"] == [], f"Request failed:\n {response['failures']}"

    def test_delete_index(self, opensearch_client: OpenSearch):
        logger.info("\nSTARTING test_delete_index....\n*******************\n\n")

        response = opensearch_client.indices.delete(index=index_name)

        logger.info(f"Response of deleting an Index: {response}")
        assert response is not None, "No response was received"

    @patch("app.services.opensearch.opensearch.AsyncOpenSearchClient.get")
    @pytest.mark.parametrize(
        "test_scenario, error_type, search_function",
        [
            (
                "request_error",
                RequestError(
                    400,
                    "search_phase_execution_exception",
                    {
                        "error": {
                            "root_cause": [
                                {"reason": "maxClauseCount is set to 1024", "type": "search_phase_execution_exception"}
                            ]
                        }
                    },
                ),
                AsyncOpenSearchOperations.search_for_chunks("test-query", "test-index"),
            ),
            (
                "transport_error",
                RequestError(
                    500,
                    "search_phase_execution_exception",
                    {
                        "error": {
                            "root_cause": [
                                {"reason": "maxClauseCount is set to 1024", "type": "search_phase_execution_exception"}
                            ]
                        }
                    },
                ),
                AsyncOpenSearchOperations.search_for_chunks("test-query", "test-index"),
            ),
            (
                "request_error",
                RequestError(
                    400,
                    "search_phase_execution_exception",
                    {
                        "error": {
                            "root_cause": [
                                {"reason": "maxClauseCount is set to 1024", "type": "search_phase_execution_exception"}
                            ]
                        }
                    },
                ),
                AsyncOpenSearchOperations.search_user_document_chunks("document-id", "test-query", "test-index"),
            ),
            (
                "transport_error",
                RequestError(
                    500,
                    "search_phase_execution_exception",
                    {
                        "error": {
                            "root_cause": [
                                {"reason": "maxClauseCount is set to 1024", "type": "search_phase_execution_exception"}
                            ]
                        }
                    },
                ),
                AsyncOpenSearchOperations.search_user_document_chunks("document-id", "test-query", "test-index"),
            ),
        ],
    )
    async def test_search_handles_managed_request_and_transport_errors(
        self, mock_opensearch_client, test_scenario, error_type, search_function
    ):
        logger.info("Running test scenario %s", test_scenario)
        # Mock the OpenSearch client
        mock_search = AsyncMock()
        mock_opensearch_client.return_value.search = mock_search

        # Simulate error
        mock_search.side_effect = error_type

        chunks = await search_function

        # Assertions
        assert chunks == []
        mock_search.assert_awaited_once()

    @patch("app.services.opensearch.opensearch.AsyncOpenSearchClient.get")
    @pytest.mark.parametrize(
        "test_scenario, error_type, search_function",
        [
            (
                "request_error",
                RequestError(400, "non-relevant-error"),
                AsyncOpenSearchOperations.search_for_chunks("test-query", "test-index"),
            ),
            (
                "transport_error",
                RequestError(
                    500,
                    "non-relevant-error",
                ),
                AsyncOpenSearchOperations.search_for_chunks("test-query", "test-index"),
            ),
            (
                "request_error",
                RequestError(
                    400,
                    "non-relevant-error",
                ),
                AsyncOpenSearchOperations.search_user_document_chunks("document-id", "test-query", "test-index"),
            ),
            (
                "transport_error",
                RequestError(
                    500,
                    "non-relevant-error",
                ),
                AsyncOpenSearchOperations.search_user_document_chunks("document-id", "test-query", "test-index"),
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_search_raises_unhandled_errors(
        self, mock_opensearch_client, test_scenario, error_type, search_function
    ):
        logger.info("Running test scenario %s", test_scenario)
        # Mock the OpenSearch client
        mock_search = AsyncMock()
        mock_opensearch_client.return_value.search = mock_search

        # Simulate error
        mock_search.side_effect = error_type
        with pytest.raises(Exception) as ex:
            chunks = await search_function

            # Assertions
            assert ex.value == error_type
            assert chunks == []
            mock_search.assert_awaited_once()
