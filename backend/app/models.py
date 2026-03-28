import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    pass


class RoomStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class DisplayStyle(str, enum.Enum):
    plate = "plate"
    square = "square"


class GamePhase(str, enum.Enum):
    waiting = "waiting"
    selecting = "selecting"
    pending_confirm = "pending_confirm"
    countdown_5s = "countdown_5s"
    assist_preview = "assist_preview"
    assist_go = "assist_go"
    computing = "computing"
    marquee = "marquee"
    result = "result"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    max_players: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, native_enum=False, length=16), default=RoomStatus.closed
    )
    admin_token_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    poll_types: Mapped[list["RoomPollType"]] = relationship(
        "RoomPollType", back_populates="room", order_by="RoomPollType.sort_order"
    )


class RoomPollType(Base):
    __tablename__ = "room_poll_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(128))
    display_style: Mapped[DisplayStyle] = mapped_column(
        Enum(DisplayStyle, native_enum=False, length=16)
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    room: Mapped["Room"] = relationship("Room", back_populates="poll_types")
    options: Mapped[list["PollOption"]] = relationship(
        "PollOption",
        back_populates="poll_type",
        order_by="PollOption.sort_order",
        cascade="all, delete-orphan",
    )


class PollOption(Base):
    __tablename__ = "poll_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("room_poll_types.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(256))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    poll_type: Mapped["RoomPollType"] = relationship("RoomPollType", back_populates="options")


class RoomMembership(Base):
    __tablename__ = "room_memberships"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoteRound(Base):
    __tablename__ = "vote_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    type_id: Mapped[int] = mapped_column(ForeignKey("room_poll_types.id", ondelete="CASCADE"))
    phase: Mapped[GamePhase] = mapped_column(
        Enum(GamePhase, native_enum=False, length=32), default=GamePhase.waiting
    )
    phase_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    winning_option_id: Mapped[int | None] = mapped_column(ForeignKey("poll_options.id"), nullable=True)

    room: Mapped["Room"] = relationship("Room")
    poll_type: Mapped["RoomPollType"] = relationship("RoomPollType")


class RoundVote(Base):
    __tablename__ = "round_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("vote_rounds.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    option_id: Mapped[int] = mapped_column(ForeignKey("poll_options.id", ondelete="CASCADE"))

    __table_args__ = (UniqueConstraint("round_id", "user_id", name="uq_round_user_vote"),)


class RoundAssist(Base):
    __tablename__ = "round_assists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("vote_rounds.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    click_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("round_id", "user_id", name="uq_round_user_assist"),)


class RoomChatMessage(Base):
    """房间内聊天消息（持久化，重连后仍可拉取最近记录）。"""

    __tablename__ = "room_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
