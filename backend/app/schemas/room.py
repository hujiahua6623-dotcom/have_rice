from pydantic import BaseModel, Field

from app.models import DisplayStyle, RoomStatus


class RoomListItem(BaseModel):
    id: int
    name: str
    max_players: int
    member_count: int = 0
    online_count: int = 0
    status: RoomStatus


class RoomJoinOut(BaseModel):
    ok: bool = True
    room_id: int


class PollOptionOut(BaseModel):
    id: int
    text: str
    sort_order: int


class PollTypeOut(BaseModel):
    id: int
    title: str
    display_style: DisplayStyle
    sort_order: int
    options: list[PollOptionOut]


class RoomStateOut(BaseModel):
    room_id: int
    name: str
    poll_types: list[PollTypeOut]
    current_type_id: int | None = None
    phase: str | None = None
    round_id: int | None = None
