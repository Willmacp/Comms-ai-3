import datetime


def process_datetime(date_str: str | None, time_of_day: str) -> datetime.datetime | None:
    if not date_str:
        return None

    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

    if time_of_day == "start":
        return datetime.datetime.combine(date, datetime.time.min)
    if time_of_day == "end":
        return datetime.datetime.combine(date, datetime.time.max)
    raise ValueError("time_of_day must be 'start' or 'end'")
