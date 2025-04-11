import json
import logging

import anyio
from fastapi import APIRouter

from app.database.db_operations import DbOperations
from app.database.table import async_db_session
from app.lib.chat import chat_create_title
from app.lib.dev_operations import request_messages_from_llm
from app.lib.logs_handler import LogsHandler

router = APIRouter()

logger = logging.getLogger()


@router.get("/log_info")
async def custom_logger_info(m="This is a test log message."):
    return logger.info(m)


@router.get("/log_error")
async def custom_logger_error():
    try:
        return 10 / 0
    except Exception as error:
        return LogsHandler.error(error, "dev_test")


@router.get("/get_llm_message")
async def get_message_from_llm(
    q: str = "Hey",
):
    """
    Creates a new chat session and processes the query using a language model.
    """

    response = await request_messages_from_llm(q)

    return response


@router.get("/generate_chat_title")
async def generate_chat_title(
    q: str = """
    Background information: [More children are being categorised as obese than ever before. This puts a strain on
    the NHS and other public services. Childhood health is a very important factor the UK and it comes with many
    benefits for the country.]
    Objectives: [We want to reduce the level of childhood obesity by 20% in the UK before 2030. We want to do this
    through a mixture of encouraging healthy eating and more exercise.]
    Audience: [Our audience is the parents of children under the age of 18 and teenagers themselves between
    the ages of 14-18]
    Strategy: [We want to use a multi channel approach to this campaign, utilising channels that work with both parents
    and young people. This includes social media, partnering with famous influencers and traditional communications too]
    Implementation: [We should begin with smaller, cheaper pieces of communications before building out into more
    detailed and impactful messages, including partnering with sport and health celebrities on TikTok.]
    Scoring: [We need to monitor the public perception of our campaigns in the short term and the level of childhood
    obesity in the long term.]
    """,
    system: str = """Build a detailed OASIS communications plan using the Government Communications Service OASIS
    framework. Use all of the information above to build the OASIS plan, filling in gaps yourself.
    Give several options where there isn't one obvious approach to recommend. For objectives, focus on behaviour change
    as primary objectives, including secondary sub-objectives where needed. For audience, provide some key insights
    about the relevant audiences and carry out a COM-B analysis of behaviour for each relevant audience. For strategy,
    develop options for an overarching communications narrative that will underpin the campaign. For implementation,
    explore the practicalities of delivering the campaign, including timing and channels. For scoring, use the GCS
    Evaluation Framework to suggest appropriate evaluation methods and KPIs. Introduce each section
    with a summary paragraph. At the end, review the plan and list any weaknesses, risks, gaps, or assumptions.
    """,
):
    """
    Generates a title based off the overall user input. this will follow the system / query setup of passing in each
    argument separately so can be played with to improve the overall refinement of the chat.
    """

    return chat_create_title(q=q, system=system)


@router.get("/ping-db")
async def ping_database():
    async with async_db_session() as db_session:
        return await DbOperations.get_ping_database(db_session=db_session)


@router.get("/fetch-all-use-cases")
async def fetch_all_use_cases():
    async with async_db_session() as db_session:
        return await DbOperations.get_all_use_cases(db_session=db_session)


@router.post("/themes/upload")
async def reset_themes_use_cases_in_database():
    async with async_db_session() as db_session:
        async with await anyio.open_file("data/themes.json") as f:
            contents = await f.read()
            data = json.loads(contents)
            return await DbOperations.reset_themes_use_cases(db_session=db_session, data=data)
