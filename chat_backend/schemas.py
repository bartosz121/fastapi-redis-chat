from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    MESSAGE = "message"
    INTERNAL_USER_ID = "internal_user_id"


class Message(BaseModel):
    type: MessageType
    sender: str
    msg: str
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    channel: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {datetime: lambda dt: int(dt.timestamp())}

    # sets "created_at" to camelCase on msg.json()
    def json(self, *args, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().json(*args, **kwargs)

    @classmethod
    def create_welcome_message(cls, sender: str) -> "Message":
        return cls(
            type=MessageType.INTERNAL_USER_ID,
            sender="SERVER",
            msg=sender,
        )

    @classmethod
    def create_connect_message(cls, sender: str) -> "Message":
        return cls(
            type=MessageType.MESSAGE,
            sender="SERVER",
            msg=f"{sender} connected",
        )

    @classmethod
    def create_disconnect_message(cls, sender: str) -> "Message":
        return cls(
            type=MessageType.MESSAGE,
            sender="SERVER",
            msg=f"{sender} disconnected",
        )
