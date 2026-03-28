from pydantic import BaseModel, Field

from app.models import DisplayStyle, RoomStatus


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCreateRoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    max_players: int = Field(ge=2, le=200, default=20)


class AdminCreateRoomOut(BaseModel):
    room: "AdminRoomOut"
    admin_token: str  # 仅创建时返回一次明文


class AdminRoomOut(BaseModel):
    id: int
    name: str
    max_players: int
    status: RoomStatus

    model_config = {"from_attributes": True}


class AdminPatchRoomIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    max_players: int | None = Field(default=None, ge=2, le=200)
    status: RoomStatus | None = None


class PollTypeCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    display_style: DisplayStyle
    sort_order: int = 0


class PollOptionCreateIn(BaseModel):
    text: str = Field(min_length=1, max_length=256)
    sort_order: int = 0


class PollTypeWithOptionsIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    display_style: DisplayStyle
    sort_order: int = 0
    options: list[PollOptionCreateIn] = Field(min_length=2, max_length=10)


class PollOptionOut(BaseModel):
    id: int
    text: str
    sort_order: int

    model_config = {"from_attributes": True}


class PollTypeDetailOut(BaseModel):
    id: int
    title: str
    display_style: DisplayStyle
    sort_order: int
    options: list[PollOptionOut]

    model_config = {"from_attributes": True}


class PollTypePatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    display_style: DisplayStyle | None = None
    sort_order: int | None = None


class PollOptionPatchIn(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=256)
    sort_order: int | None = None


class PollOptionSingleCreateIn(BaseModel):
    text: str = Field(min_length=1, max_length=256)
    sort_order: int = 0


AdminCreateRoomOut.model_rebuild()
