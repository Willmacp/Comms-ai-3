import json

import sqlalchemy
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_types import ChatCreateMessageInput
from app.app_types.message import DocumentAccessError, MessageDefaults, RoleEnum
from app.config import LLM_DEFAULT_MODEL
from app.database.db_operations import DbOperations
from app.database.models import (
    Chat,
    ChatDocumentMapping,
    Document,
    DocumentUserMapping,
    Message,
)
from app.database.table import LLMTable, MessageTable, async_db_session
from app.lib import env_variable, logger
from app.lib.chat.chat_save_llm_output import chat_save_llm_output
from app.lib.chat.chat_stream_message import chat_stream_error_message, chat_stream_message
from app.lib.chat.chat_system_prompt import chat_system_prompt
from app.services.bedrock import BedrockHandler, MessageFunctions, RunMode
from app.services.rag import run_rag
from app.services.rag.rag_types import RagRequest

from .chat_enhance_user_prompt import enhance_user_prompt
from .chat_user_group_mapping import chat_user_group_mapping


async def chat_create_message(chat: Chat, input_data: ChatCreateMessageInput):
    if not chat:
        raise Exception("Chat not found")

    chat_id = chat.id
    llm_obj = LLMTable().get_by_model(LLM_DEFAULT_MODEL)

    if not llm_obj:
        raise Exception("LLM not found with name: " + LLM_DEFAULT_MODEL)

    message_defaults = {
        "chat_id": chat_id,
        "auth_session_id": input_data.auth_session_id,
        "llm_id": llm_obj.id,
    }

    logger.debug(f"chat_create_message called with the following parameters: {input_data}")

    message_repo = MessageTable()
    messages = []
    parent_message_id = None

    if not input_data.initial_call:
        messages = message_repo.get_by_chat(chat_id)
        parent_message_id = messages[-1].id

    m_user = message_repo.create(
        {
            "content": input_data.query,
            "role": RoleEnum.user,
            "parent_message_id": parent_message_id,
            **MessageDefaults(**message_defaults).dict(),
        }
    )

    logger.debug(f"User message created: {m_user}")

    ai_message = MessageDefaults(**message_defaults)

    system = await chat_system_prompt()
    # if input_data.use_case:
    #     system = input_data.use_case.instruction

    if input_data.user_group_ids:
        chat_user_group_mapping(m_user, input_data.user_group_ids)

    llm = BedrockHandler(llm=llm_obj, mode=RunMode.ASYNC, system=system)

    non_rag_citations = []

    # Do we use GOV UK Search API?
    if input_data.use_gov_uk_search_api or input_data.enable_web_browsing:
        # Call the LLM to obtain search terms to be used in Search API calls and
        # extract URL for query, if any were provided by the user.
        wrapped_non_rag_documents, non_rag_citations_list = await enhance_user_prompt(
            chat=chat, input_data=input_data, m_user_id=m_user.id
        )
        logger.debug(f"non_rag_citations_list ----: {non_rag_citations_list}")
        input_data.query += "\n\nWhen replying, make use of the following documents:\n\n"
        input_data.query += wrapped_non_rag_documents
        input_data.query += "\n\n"

        for cited_document in non_rag_citations_list:
            logger.debug(f"cited_document: {cited_document}")
            non_rag_citations.append(cited_document)

    # If we use RAG, then alter the user's query for passing to the LLM.
    # We don't use the altered query in the message history.
    use_rag_env = env_variable("USE_RAG", False)
    logger.info(f"{use_rag_env=}")
    # Default to None so it writes as Null into the database if the RAG errors out of the try block.
    query_enhanced_with_rag = None
    citations = None
    is_central_enabled = use_rag_env and input_data.use_rag
    rag_request = RagRequest(
        use_central_rag=is_central_enabled,
        user_id=chat.user_id,
        query=input_data.query,
        document_uuids=input_data.document_uuids,
    )

    # check if there are documents referenced in the chat request
    if rag_request.document_uuids and input_data.initial_call:
        async with async_db_session() as db_session:
            await _check_document_access(db_session, rag_request)
            await _save_chat_documents(db_session, m_user, rag_request)

    # extend document expiry time and update last_used time
    if rag_request.document_uuids:
        await _extend_document_expiry_and_last_used_time(rag_request)

    if is_central_enabled or rag_request.document_uuids:
        try:
            logger.info("Starting RAG process")
            query_enhanced_with_rag, citations = await run_rag(rag_request, m_user)
            logger.debug(f"{query_enhanced_with_rag=}")
            logger.debug(f"{citations=}")

        except Exception as error_message:
            logger.exception(f"{error_message=}")
    # Update the Message instance with the enhanced query and citation message
    if not citations:
        citations = non_rag_citations
    else:
        citations += non_rag_citations
    m_user = message_repo.update(
        m_user,
        {
            "content_enhanced_with_rag": query_enhanced_with_rag,
            "citation": json.dumps(citations),
        },
    )

    formatted_messages = MessageFunctions.format_messages(
        input_data.query,
        query_enhanced_with_rag,
        messages,
    )

    def on_complete(response):
        formatted_response = llm.format_response(response)
        result = chat_save_llm_output(
            ai_message_defaults=ai_message,
            user_message=m_user,
            llm=llm_obj,
            llm_response=formatted_response,
        )
        return result

    if input_data.stream:

        def parse_data(text, citations):
            return chat_stream_message(
                chat=chat,
                message_uuid=ai_message.uuid,
                content=text,
                citations=citations,
            )

        def on_error(ex: Exception):
            has_documents = bool(input_data.document_uuids)
            return chat_stream_error_message(
                chat, ex, has_documents=has_documents, is_initial_call=input_data.initial_call
            )

        stream_res = llm.stream(
            formatted_messages,
            on_error=on_error,
            user_message=m_user,
            system=system,
            parse_data=parse_data,
            on_complete=on_complete,
        )

        return stream_res

    response = await llm.invoke_async(formatted_messages)
    result = on_complete(response)

    return result


async def _save_chat_documents(db_session: AsyncSession, user_message: Message, rag_request: RagRequest):
    """
    Saves documents referenced in chat message to the database.
    """
    insert_records = [
        {"chat_id": user_message.chat_id, "document_uuid": doc_uuid} for doc_uuid in rag_request.document_uuids
    ]
    await DbOperations.save_records(db_session, ChatDocumentMapping, insert_records)


async def _extend_document_expiry_and_last_used_time(rag_request: RagRequest):
    """
    Extends the expiry date of the documents referenced in the rag_request parameter by 90 days from today onwards.
    And updates the last used time of the documents referenced.
    """
    document_uuids = rag_request.document_uuids
    user_id = rag_request.user_id
    async with async_db_session() as db_session:
        await DbOperations.update_document_expiry_and_last_used_time(db_session, document_uuids, user_id)


async def _check_document_access(db_session: AsyncSession, rag_request: RagRequest):
    """
    Checks if the user has access to the specified documents.

    Raises:
        DocumentAccessError: Raised if the user does not have access to the requested documents
    """
    logger.info(
        "Checking document access for user %s for documents %s", rag_request.user_id, rag_request.document_uuids
    )
    result = await db_session.execute(
        select(cast(Document.uuid, sqlalchemy.String))
        .select_from(DocumentUserMapping)
        .join(Document, Document.id == DocumentUserMapping.document_id)
        .where(
            DocumentUserMapping.user_id == rag_request.user_id,
            Document.uuid.in_(rag_request.document_uuids),
            DocumentUserMapping.deleted_at.is_(None),
            Document.deleted_at.is_(None),
        )
    )
    docs_allowed = result.scalars().all()
    docs_not_allowed = [requested for requested in rag_request.document_uuids if requested not in docs_allowed]
    if docs_not_allowed:
        raise DocumentAccessError(
            "User not allowed for access",
            document_uuids=docs_not_allowed,
        )
