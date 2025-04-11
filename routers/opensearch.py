# ruff: noqa: B008, E501

from uuid import UUID

from fastapi import APIRouter, Body, Depends

from app.api import ENDPOINTS
from app.api.auth_token import auth_token_validator_no_user
from app.app_types.opensearch import ListDocumentChunkResponse
from app.database.table import async_db_session
from app.services.opensearch import (
    delete_chunk_in_central_rag,
    list_chunks_in_central_rag,
    load_chunks_to_central_rag,
    sync_central_index,
)

router = APIRouter()


@router.get(ENDPOINTS.CENTRAL_RAG_DOCUMENT_CHUNKS, dependencies=[Depends(auth_token_validator_no_user)])
async def get_chunks() -> ListDocumentChunkResponse:
    """Lists all the document chunks stored in the PostgreSQL database."""
    async with async_db_session() as db_session:
        return await list_chunks_in_central_rag(db_session)


@router.post(
    ENDPOINTS.CENTRAL_RAG_DOCUMENT_CHUNKS,
    dependencies=[Depends(auth_token_validator_no_user)],
)
async def create_chunks(
    chunks: list = Body(
        [
            {
                "document_name": "Modern Communications Operating Model 3.0",
                "document_url": "https://gcs.civilservice.gov.uk/modern-communications-operating-model-3-0/",
                "document_description": """The Modern Communications Operating Model (MCOM) 3.0 brings together all GCS policies and guidance needed to build and lead a team of governmnet communicators. It contains information on: GCS Strategy; team design principles; equality diversity and inclusion; recruitment; learning and development; propriety and ethics; generative AI; procurement and spend; data handling; data protection; accessible communications; His Majesty's Government brand guidelines; OASIS campaign planning; innovating ethically; crisis communication;strategic communication; behavioural science / COM-B;influencer marketing; communications disciplines; media monitoring unit.""",
                "chunk_name": "Introduction: how to use MCOM 3.0",
                "chunk_content": """"The purpose of this new Modern Communications Operating Model (MCOM) is to provide simplicity and clarity about the expectations of teams and leaders within the Government Communication Service (GCS).

MCOM brings together all the policies and guidance needed to build and lead a team that delivers the GCS vision of exceptional communications that make a difference.

This updated MCOM uses a *must*, *should*, *could* framework to provide complete clarity on: the policies teams must follow; those that we recommend they should follow; and guidance that is available to consult and apply where needed.

The GCS Strategy and Government Communications Plan set the overarching strategy framework for government communications. The MCOM ‘house’ sits underneath this with three pillars: People & Structure, Policies, and Guidance & Tools.

Whether you are new to GCS, or an established leader who wants an accessible guide to best practice, this MCOM is for you. It is a living document and will be updated regularly, so we welcome ongoing feedback to ensure it remains relevant to you.

We hope that this updated approach enables you to use the recommendations and supporting guidance within MCOM to its best and fullest effect. We look forward to working together to continue delivering world class communications.""",
            },
        ],
    ),
) -> bool:
    async with async_db_session() as db_session:
        return await load_chunks_to_central_rag(db_session=db_session, data=chunks)


@router.delete(ENDPOINTS.CENTRAL_RAG_DOCUMENT_CHUNK, dependencies=[Depends(auth_token_validator_no_user)])
async def delete_chunk(document_chunk_uuid: UUID) -> bool:
    """Soft deletes document chunks in the PostgreSQL database and hard deletes the document chunk in OpenSearch."""
    async with async_db_session() as db_session:
        return await delete_chunk_in_central_rag(db_session, document_chunk_uuid)


@router.put(ENDPOINTS.CENTRAL_RAG_SYNC, dependencies=[Depends(auth_token_validator_no_user)])
async def sync_indexes() -> bool:
    """Synchronises OpenSearch with the PostgreSQL representation of the search indexes and document chunks."""
    async with async_db_session() as db_session:
        return await sync_central_index(db_session)
