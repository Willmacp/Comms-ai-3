import datetime
from typing import Optional

from fastapi import HTTPException, status

from app.api import api_wrapper
from app.database.models import ModelEnum, get_model_class
from app.database.table import Table
from app.lib.datetime.process_datetime import process_datetime


def parse_start_date(start_date: str = "") -> datetime.date | None:
    return process_datetime(start_date, "start")


def parse_end_date(end_date: str = "") -> datetime.date | None:
    return process_datetime(end_date, "end")


class AnalyticsController(Table):
    def __init__(self, model: ModelEnum):
        super().__init__(model=get_model_class(model))

    @api_wrapper(task="filter analytics data")
    def filter(
        self,
        start_date: Optional[datetime.date],
        end_date: Optional[datetime.date],
    ):
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date should be greater than start date",
            )

        data = self.fetch_all(most_recent=True)

        try:
            if start_date and end_date:
                if start_date == end_date:
                    data = data.filter(self.model.created_at == start_date)
                else:
                    data = data.filter(self.model.created_at.between(start_date, end_date))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
        if data:
            data_dict = [msg.__dict__ for msg in data]
            return data_dict
        return []  # Return an empty list if 'data' is falsy
