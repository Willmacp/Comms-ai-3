import logging
import os
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from dotenv import load_dotenv
from opensearchpy import AsyncOpenSearch, OpenSearch
from opensearchpy.exceptions import RequestError, TransportError
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_types.opensearch import (
    DocumentChunkResponse,
    ListDocumentChunkResponse,
)
from app.config import env_variable
from app.database.db_operations import DbOperations
from app.database.models import DocumentChunk, SearchIndex
from app.lib import Action, LogsHandler

load_dotenv()

logging.getLogger("opensearch").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

CENTRAL_RAG_INDEX_NAME = "central_guidance"
""" The index name for storing documents that are available to everyone"""

LABOUR_MANIFESTO_INDEX_NAME = "labour_manifesto_2024"
""" The index name for storing documents that are available to everyone"""

PERSONAL_DOCUMENTS_INDEX_NAME = "personal_document_uploads"
""" The index name for storing personal documents uploaded"""


class DocumentOperationError(Exception):
    """
    Exception class representing errors for Opensearch operations
    """

    pass


@dataclass
class OpenSearchRecord:
    """An internal representation of the data we need to submit a record to OpenSearch to create a record."""

    document_name: str
    document_url: str
    chunk_name: str
    chunk_content: str
    document_uuid: str = None

    def to_opensearch_dict(self):
        return {
            "document_name": self.document_name,
            "document_url": self.document_url,
            "chunk_name": self.chunk_name,
            "chunk_content": self.chunk_content,
            "document_uuid": self.document_uuid,
        }


def get_central_index(db_session: AsyncSession):
    return DbOperations.get_index_by_name(db_session=db_session, name=CENTRAL_RAG_INDEX_NAME)


def verify_connection_to_opensearch():
    try:
        client = create_client()
        # Test if the client is created successfully
        assert client is not None

        # Test if the client has the correct attributes
        assert hasattr(client, "search")
        assert hasattr(client, "index")
        assert hasattr(client, "delete")

        # Test if the client can query which indexes are present
        response = client.indices.get_alias("*")
        assert response and len(response) > 0, "No indexes found"
        logger.info("Connection to OpenSearch succesful")
    except Exception as ex:
        traceback_str = traceback.format_exc()
        raise ConnectionError(f"Error connecting with OpenSearch: \n{traceback_str}\n\n") from ex
    logger.info("Succesfully connected to OpenSearch.")
    return


def normalise_string(string):
    """A utility function for making sure index names are allowed by OpenSearch."""

    string = string.strip()
    # Replace all non-letter and non-numerical characters with an underscore
    string = re.sub(r"[^a-zA-Z0-9]", "_", string)
    # Replace all uppercase letters followed by a lowercase letter or a digit with an underscore
    # and the letter in lowercase
    string = re.sub(r"([A-Z]+)([A-Z][a-z]|[0-9])", r"\1_\2", string)
    # Replace all lowercase letters or digits followed by an uppercase letter with the letter, an underscore,
    # and the letter in lowercase
    string = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", string)
    # Convert to lowercase
    string = string.lower()
    # Remove any leading or trailing underscores
    string = string.strip("_")
    # Replace multiple underscores with a single one
    string = re.sub(r"__+", "_", string)

    return string


class OpenSearchClient:
    _instance = None

    @classmethod
    def get_client(cls):
        if cls._instance is None:
            username = os.getenv("OPENSEARCH_USER")
            password = os.getenv("OPENSEARCH_PASSWORD")
            host = os.getenv("OPENSEARCH_HOST")
            port = os.getenv("OPENSEARCH_PORT")
            use_ssl = True
            if env_variable("OPENSEARCH_DISABLE_SSL", False):
                use_ssl = False

            cls._instance = OpenSearch(
                hosts=[{"host": host, "port": port}],
                http_auth=(username, password),
                use_ssl=use_ssl,
                verify_certs=False,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
            )
        return cls._instance


def create_client():
    """Creates or returns existing OpenSearch client."""
    return OpenSearchClient.get_client()


def create_async_client():
    """Creates an AsyncOpenSearch client."""

    username = os.getenv("OPENSEARCH_USER")
    password = os.getenv("OPENSEARCH_PASSWORD")
    host = os.getenv("OPENSEARCH_HOST")
    port = os.getenv("OPENSEARCH_PORT")
    use_ssl = True
    if env_variable("OPENSEARCH_DISABLE_SSL", False):
        use_ssl = False

    client = AsyncOpenSearch(
        hosts=[{"host": host, "port": int(port)}],
        http_auth=(username, password),
        use_ssl=use_ssl,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )

    return client


async def list_indexes(db_session: AsyncSession, include_personal_document_index: bool = False) -> List[SearchIndex]:
    """
    Lists all active indexes in the PostgreSQL database.
    if include_personal_document_index is True, the personal_document_uploads index will be included in the list.
    """
    indexes = await DbOperations.get_active_indexes(
        db_session=db_session,
        personal_documents_index_name=PERSONAL_DOCUMENTS_INDEX_NAME,
        include_personal_document_index=include_personal_document_index,
    )

    return indexes


async def load_chunks_to_central_rag(
    db_session: AsyncSession,
    data: str,  # A serialised string containing JSON data with the relevant keys
) -> bool:
    """Loads document chunks to the PostgreSQL database and then into OpenSearch."""

    search_index = await get_central_index(db_session)
    opensearch_client = create_client()

    try:
        for row in data:
            document_name = row["document_name"]
            document_url = row["document_url"]
            document_description = row["document_description"]
            chunk_name = row["chunk_name"]
            chunk_content = row["chunk_content"]

            # Check if the Document already exists
            existing_document = await DbOperations.get_existing_document(
                db_session=db_session, name=document_name, url=document_url
            )
            if existing_document is None:
                document = await DbOperations.create_central_document(
                    db_session=db_session,
                    name=document_name,
                    description=document_description,
                    url=document_url,
                )
            else:
                document = existing_document

            # Check that the chunk does not already exist for this document
            existing_chunk = await DbOperations.get_existing_chunk(
                db_session=db_session,
                search_index_id=search_index.id,
                document_id=document.id,
                name=chunk_name,
                content=chunk_content,
            )
            if existing_chunk is None:
                # Prepare data for OpenSearch
                doc_to_index = OpenSearchRecord(
                    document_name, document_url, chunk_name, chunk_content
                ).to_opensearch_dict()

                # Index the document in OpenSearch
                response = opensearch_client.index(index=search_index.name, body=doc_to_index)
                id_opensearch = response["_id"]

                # Insert the document chunk into PostgreSQL
                _ = await DbOperations.add_chunk(
                    db_session=db_session,
                    search_index_id=search_index.id,
                    document_id=document.id,
                    name=chunk_name,
                    content=chunk_content,
                    id_opensearch=id_opensearch,
                )
            else:
                continue

        logger.info("Successfully loaded new document chunks")
        return True

    except Exception as e:
        raise RuntimeError(f"Error loading new document chunks: {e}") from e


async def list_chunks_in_central_rag(
    db_session: AsyncSession, show_deleted_chunks: bool = False
) -> List[DocumentChunk]:
    """Lists all active DocumentChunk instances in the PostgreSQL database."""

    # Get all central documents first
    central_documents = await DbOperations.get_central_documents(db_session)
    logger.info(f"{central_documents=}")
    if central_documents:
        first_doc = central_documents[0]
        logger.info(f"First central document attributes: {first_doc._mapping.keys()}")
        logger.info(f"First central document values: {first_doc._asdict()}")
    else:
        logger.info("No central documents found")
    # Create lookup dict of id -> name
    document_names = {doc.id: doc.name for doc in central_documents}
    logger.info(f"{document_names=}")

    # Get all central chunks
    central_index = await get_central_index(db_session)
    chunks = await DbOperations.get_document_chunks_filtered_with_search_index(
        db_session=db_session, search_index_uuid=central_index.uuid, show_deleted_chunks=show_deleted_chunks
    )

    chunks_formatted = [
        DocumentChunkResponse(
            uuid=chunk.uuid,
            created_at=chunk.created_at,
            updated_at=chunk.updated_at,
            deleted_at=chunk.deleted_at,
            document_name=document_names.get(chunk.document_id),
            chunk_name=chunk.name,
            chunk_content=chunk.content,
            id_opensearch=chunk.id_opensearch,
        )
        for chunk in chunks
    ]

    return ListDocumentChunkResponse(document_chunks=chunks_formatted)


# Does not soft delete the Document object as the Document may be used across multiple indexes.
async def delete_chunk_in_central_rag(db_session: AsyncSession, document_chunk_uuid: UUID):
    opensearch_client = create_client()

    deleted_at = datetime.now()

    central_index = await get_central_index(db_session)

    # Start with deleting the document chunk in PostgreSQL
    document_chunk = await DbOperations.get_document_chunk_by_uuid(
        db_session=db_session, document_chunk_uuid=document_chunk_uuid
    )
    if document_chunk:
        document_chunk.deleted_at = deleted_at
    else:
        logger.info(f"No SearchIndex found with uuid: {document_chunk_uuid}")

    response = opensearch_client.delete(index=central_index.name, id=document_chunk.id_opensearch)
    logger.info(f"{response=}")
    if response["result"] == "deleted":
        logger.info(f"DocumentChunk '{document_chunk.name}' has been successfully deleted.")
    else:
        raise RuntimeError(f"Failed to delete DocumentChunk '{document_chunk.name}'.")

    return True


class AsyncOpenSearchClient:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = create_async_client()
        return cls._instance


class AsyncOpenSearchOperations:
    @staticmethod
    def _collect_errors(response: Dict, action_type: str) -> List[str]:
        errors = []
        for item in response.get("items", []):
            action = item.get(action_type, {})
            if "error" in action:
                error_type = action["error"].get("type", "Unknown")
                reason = action["error"].get("reason", "Unknown")
                status = action.get("status", "Unknown")
                doc_id = action.get("_id", "Unknown ID")
                msg = (
                    f"Document {action_type} error for ID {doc_id}: "
                    f"Status {status}, Error Type: {error_type}, Reason: {reason}"
                )
                errors.append(msg)
        return errors

    @staticmethod
    async def index_document_chunks(index: str, document_list: List[Dict]):
        """
        Indexes a list of document chunks into the specified OpenSearch index using Opensearch async bulk operation.
        If the indexing operation encounters errors, it collects the errors and raises a `DocumentOperationError`.

        Args:
            index (str): The name of the OpenSearch index to which documents should be added.
            document_list (List[Dict]): A list of dictionaries representing the documents to be indexed.

        Returns:
            Dict: The response from the OpenSearch bulk indexing API if the operation completes without errors.

        Raises:
            DocumentOperationError: If any errors occur during the indexing operation, this exception is raised
                                    with the details of the errors.

        """

        logger.info("Indexing % documents to index %s", len(document_list), index)
        docs = []
        doc_header = {"index": {"_index": index}}
        for d in document_list:
            docs.append(doc_header)
            docs.append(d)

        index_action = AsyncOpenSearchClient.get().bulk(body=docs)
        response = await LogsHandler.with_logging(Action.OPENSEARCH_INDEX_DOCUMENT, index_action)

        if not response.get("errors", False):
            return response

        # collect errors and raise exception
        errors = AsyncOpenSearchOperations._collect_errors(response, action_type="index")
        if not errors:
            return response

        exception_msg = "\n".join(errors)
        logger.error(exception_msg)
        raise DocumentOperationError(exception_msg)

    @staticmethod
    async def delete_document_chunks(index: str, ids: List[str]) -> Optional[Dict]:
        """
        Deletes multiple document chunks from the specified OpenSearch index using async bulk.

        If any errors occur during deletion, they are logged, and a `DocumentOperationError`
        is raised with details.

        Args:
            index (str): The name of the OpenSearch index from which the documents will be deleted.
            ids (List[str]): A list of document IDs to be deleted.

        Returns:
            dict: The OpenSearch bulk deletion response if successful and no errors occur.

        Raises:
            DocumentOperationError: If there are errors during the deletion process, an exception
                is raised containing the error details.

        """
        if not ids:
            logger.info("No document IDs provided for deletion. Skipping deletion process.")
            return None

        logger.info("Deleting %s document chunks from index %s", len(ids), index)
        # build bulk request
        request = [{"delete": {"_index": index, "_id": _id}} for _id in ids]
        delete_action = AsyncOpenSearchClient.get().bulk(body=request)
        response = await LogsHandler.with_logging(Action.OPENSEARCH_DELETE_DOCUMENT, delete_action)

        if not response.get("errors", False):
            return response

        errors = AsyncOpenSearchOperations._collect_errors(response, action_type="delete")
        if not errors:
            return response

        exception_msg = "\n".join(errors)
        logger.error(exception_msg)
        raise DocumentOperationError(exception_msg)

    @staticmethod
    async def get_document_chunks(index: str, document_uuid: str, max_size: int = 6) -> List[Dict]:
        """
        Gets document chunks from `from the index and document uuid provided.

        Args:
            index (str): The name of the OpenSearch index from which the documents will be retrieved.
            document_uuid (str): The document uuid to get chunks for.
            max_size (int): The maximum number of document chunks to fetch from index for the document_uuid.
            The default is set to 6 because this method is used to detect if a document contains more than 5 chunks.
        Returns:
            List[Dict]: The document chunks retrieved from the index, from the document_uuid provided

        """

        logger.info(
            "Attempting to retrieve max %s document chunks  from index %s for document %s",
            max_size,
            index,
            document_uuid,
        )
        request_body = {
            "query": {"bool": {"filter": [{"terms": {"document_uuid.keyword": [document_uuid]}}]}},
            "size": max_size,
        }

        action = AsyncOpenSearchClient.get().search(request_body, index=index)
        response = await LogsHandler.with_logging(Action.OPENSEARCH_SEARCH_DOCUMENT, action)
        hit_elements = response["hits"]["hits"]
        logger.info("Found %s document chunks for document %s", len(hit_elements), document_uuid)
        return hit_elements

    @staticmethod
    async def search_user_document_chunks(document_uuid: str, query: str, index: str) -> List[Dict]:
        logger.debug("searching index: %s  with document: %s and user query: %s", index, document_uuid, query)

        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["document_name", "chunk_name", "chunk_content"],
                            }
                        }
                    ],
                    "filter": [
                        {"terms": {"document_uuid.keyword": [document_uuid]}},
                    ],
                }
            },
            "size": 5,
        }
        logger.debug("built search query %s", search_body)
        # Perform the search
        try:
            response = await AsyncOpenSearchClient.get().search(body=search_body, index=index)
            chunks = response["hits"]["hits"]
            logger.info(
                "%s chunks retrieved from %s using doc %s",
                len(chunks),
                index,
                document_uuid,
            )
            return chunks
        except Exception as e:
            AsyncOpenSearchOperations._handle_search_error(e, query, index, str(search_body))

        # return no match
        return []

    @staticmethod
    async def search_for_chunks(query: str, index: str) -> List[Dict]:
        logger.info("Searching central index for chunks: %s", index)

        # Prepare the search body
        search_body = {
            "query": {"multi_match": {"query": query, "fields": ["document_name", "chunk_name", "chunk_content"]}},
            "size": 3,
        }

        # Perform the search
        try:
            response = await AsyncOpenSearchClient.get().search(body=search_body, index=index)
            chunks = response["hits"]["hits"]
            logger.info(f"{len(chunks)} chunks retrieved from {index}")
            return chunks
        except Exception as e:
            AsyncOpenSearchOperations._handle_search_error(e, query, index, str(search_body))

        # return no match
        return []

    @staticmethod
    def _handle_search_error(ex: Exception, query: str, index: str, search_body: str):
        if not isinstance(ex, (RequestError, TransportError)):
            raise ex

        # skip large text user queries and log as error
        if (
            ex.status_code in [400, 500]
            and ex.error == "search_phase_execution_exception"
            and "maxClauseCount is set to 1024" in str(ex)
        ):
            logger.error("Search error\nIndex:%s\nUser query:%s\nSearch body:%s", index, query, search_body)
        else:
            raise ex
