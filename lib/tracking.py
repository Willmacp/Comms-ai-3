from app.api import api_wrapper
from app.app_types.requests import RequestStandard
from app.app_types.responses import SuccessResponse
from app.database.table import ActionTypeTable, UserActionTable


class TrackRequest(RequestStandard):
    data_property: dict


@api_wrapper(task="track activity")
def track_user_action(user_id: int, auth_session_id: int, data_action: str, data_property: dict):
    action = ActionTypeTable().upsert("action_name", data_action)

    UserActionTable().create(
        {
            "user_id": user_id,
            "auth_session_id": action.auth,
            "action_type_id": action.id,
            "action_properties": data_property,
        },
    )

    return SuccessResponse(status_message="Activity tracked successfully")
