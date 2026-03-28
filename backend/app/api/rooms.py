from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Room, RoomMembership, RoomStatus, User
from app.schemas.room import RoomJoinOut, RoomListItem
from app.services.room_runtime import online_count

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomListItem])
def list_open_rooms(db: Annotated[Session, Depends(get_db)]) -> list[RoomListItem]:
    rows = (
        db.query(Room)
        .filter(Room.status == RoomStatus.open)
        .order_by(Room.id.desc())
        .all()
    )
    out: list[RoomListItem] = []
    for r in rows:
        member_count = (
            db.query(func.count())
            .select_from(RoomMembership)
            .filter(RoomMembership.room_id == r.id)
            .scalar()
        )
        out.append(
            RoomListItem(
                id=r.id,
                name=r.name,
                max_players=r.max_players,
                member_count=int(member_count or 0),
                online_count=online_count(r.id),
                status=r.status,
            )
        )
    return out


@router.post("/{room_id}/join", response_model=RoomJoinOut)
def join_room(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RoomJoinOut:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "房间不存在")
    if room.status != RoomStatus.open:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "房间未开放")

    old = db.query(RoomMembership).filter(RoomMembership.user_id == user.id).first()
    old_room_id = old.room_id if old else None
    if old:
        db.delete(old)
        db.commit()

    count = (
        db.query(func.count())
        .select_from(RoomMembership)
        .filter(RoomMembership.room_id == room_id)
        .scalar()
    )
    if int(count or 0) >= room.max_players:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "房间已满")

    db.add(RoomMembership(user_id=user.id, room_id=room_id))
    db.commit()

    return RoomJoinOut(room_id=room_id)


@router.post("/{room_id}/leave")
def leave_room(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    m = (
        db.query(RoomMembership)
        .filter(RoomMembership.user_id == user.id, RoomMembership.room_id == room_id)
        .first()
    )
    if m:
        db.delete(m)
        db.commit()
    return {"ok": True}
