# ruff: noqa: B008

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.api.endpoint_defaults import get_current_session
from app.app_types.requests import RequestModel
from app.app_types.responses import SuccessResponse
from app.database.db_operations import DbOperations
from app.database.models import ModelEnum
from app.database.table import async_db_session
from app.lib.analytics import parse_end_date, parse_start_date
from app.lib.analytics.analytics import AnalyticsController
from app.lib.tracking import track_user_action

router = APIRouter()


class AnalyticsPost(RequestModel):
    auth_session: str
    data_action: str
    data_property: dict


@router.post("/tracking/activity", response_model=SuccessResponse)
async def track_activity(data: AnalyticsPost = Body(...), session=Depends(get_current_session)):
    async with async_db_session() as db_session:
        return await track_user_action(
            db_session=db_session, user_id=session.user_id, auth_session_id=session.id, **data.to_dict()
        )


@router.get("/tables/{table}")
async def get_analytics_route(
    table: ModelEnum,
    start_date=Depends(parse_start_date),
    end_date=Depends(parse_end_date),
):
    async with async_db_session() as db_session:
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date should be greater than start date",
            )
        return await DbOperations.retrieve_analytics(
            db_session=db_session, table=table, start_date=start_date, end_date=end_date
        )
    return AnalyticsController(table).filter(start_date, end_date)
