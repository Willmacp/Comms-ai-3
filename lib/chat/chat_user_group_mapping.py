from typing import List

from app.database.models import Message
from app.database.table import MessageUserGroupMappingTable


def chat_user_group_mapping(message: Message, user_group_ids: List[int]):
    user_group_mapping_table = MessageUserGroupMappingTable()

    for user_group_id in user_group_ids:
        user_group_mapping_table.create({"message_id": message.id, "user_group_id": user_group_id})
