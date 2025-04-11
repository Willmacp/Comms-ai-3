# ruff: noqa: B008

from typing import List

from fastapi import Body, Depends, HTTPException

from app.api import get_current_session
from app.api.api_config import ApiConfig
from app.api.api_paths import ApiPaths
from app.app_types import RequestStandard
from app.app_types.chat import (
    ChatPost,
)
from app.database.table import UseCaseTable, UserGroupTable
from app.lib import verify_uuid


class ChatRequestData(ChatPost, RequestStandard):
    user_group_ids: List = []
    use_case_id: int = None


def get_user_groups(user_groups_string=ApiConfig.USER_GROUPS):
    user_group_ids = []

    if user_groups_string:
        user_groups = user_groups_string.split(",")
        ug_table = UserGroupTable()
        for group_name in user_groups:
            group = ug_table.upsert_by_name(group_name)
            user_group_ids.append(group.id)

    return user_group_ids


def chat_request_data(
    user=ApiPaths.USER_UUID,
    session=Depends(get_current_session),
    data: ChatPost = Body(...),
    user_group_ids=Depends(get_user_groups),
):
    use_case_id = data.use_case_id
    del data.use_case_id
    data_dict = data.to_dict()

    try:
        if use_case_id:
            use_case_id = verify_uuid("use_case_id", use_case_id)

            data_dict["use_case_id"] = UseCaseTable().get_by_uuid(use_case_id).id

        return ChatRequestData(user_id=user.id, auth_session_id=session.id, user_group_ids=user_group_ids, **data_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
