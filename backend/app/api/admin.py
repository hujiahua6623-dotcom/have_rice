"""管理端 API：控制台账号 JWT + 房间级 X-Admin-Token 二选一。"""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.security import (
    create_admin_console_token,
    decode_admin_console_token,
    generate_admin_token,
    hash_admin_token,
)
from app.database import get_db
from app.models import PollOption, Room, RoomMembership, RoomPollType, RoomStatus, VoteRound
from app.schemas.admin import (
    AdminCreateRoomIn,
    AdminCreateRoomOut,
    AdminLoginIn,
    AdminLoginOut,
    AdminPatchRoomIn,
    AdminRoomOut,
    PollOptionOut,
    PollOptionPatchIn,
    PollOptionSingleCreateIn,
    PollTypeDetailOut,
    PollTypePatchIn,
    PollTypeWithOptionsIn,
)
from app.schemas.room import RoomListItem
from app.services.room_runtime import drop_room_runtime, get_room_runtime, online_count, ws_message

router = APIRouter(prefix="/admin", tags=["admin"])


def admin_room_creds(
    authorization: Annotated[str | None, Header()] = None,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> tuple[str | None, str | None]:
    return authorization, x_admin_token


def _poll_type_or_404(room_id: int, type_id: int, db: Session) -> RoomPollType:
    pt = db.get(RoomPollType, type_id)
    if pt is None or pt.room_id != room_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    return pt


def _option_count(type_id: int, db: Session) -> int:
    return db.query(PollOption).filter(PollOption.type_id == type_id).count()


def _verify_room(
    room_id: int,
    db: Session,
    x_admin_token: str | None,
    authorization: str | None,
) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "房间不存在")

    bearer: str | None = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization[7:].strip()
    if bearer and decode_admin_console_token(bearer):
        return room

    if not x_admin_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 X-Admin-Token 或管理员 Bearer")
    if room.admin_token_hash != hash_admin_token(x_admin_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin Token 无效")
    return room


def _require_admin_console(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要管理员登录")
    raw = authorization[7:].strip()
    if not decode_admin_console_token(raw):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "管理员凭证无效或已过期")


def _password_ok(plain: str, expected: str) -> bool:
    if len(plain) != len(expected):
        return False
    return secrets.compare_digest(plain.encode("utf-8"), expected.encode("utf-8"))


@router.post("/login", response_model=AdminLoginOut)
def admin_login(body: AdminLoginIn) -> AdminLoginOut:
    if not _password_ok(body.username, settings.admin_console_username):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not _password_ok(body.password, settings.admin_console_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    return AdminLoginOut(access_token=create_admin_console_token())


@router.post("/rooms", response_model=AdminCreateRoomOut)
def create_room(
    body: AdminCreateRoomIn,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> AdminCreateRoomOut:
    _require_admin_console(authorization)
    plain = generate_admin_token()
    room = Room(
        name=body.name,
        max_players=body.max_players,
        status=RoomStatus.closed,
        admin_token_hash=hash_admin_token(plain),
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return AdminCreateRoomOut(room=AdminRoomOut.model_validate(room), admin_token=plain)


@router.get("/rooms", response_model=list[RoomListItem])
def list_rooms_admin(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> list[RoomListItem]:
    _require_admin_console(authorization)
    rows = db.query(Room).order_by(Room.id.desc()).all()
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


@router.get("/rooms/{room_id}", response_model=AdminRoomOut)
def get_room(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> AdminRoomOut:
    authorization, x_admin_token = creds
    r = _verify_room(room_id, db, x_admin_token, authorization)
    return AdminRoomOut.model_validate(r)


@router.patch("/rooms/{room_id}", response_model=AdminRoomOut)
async def patch_room(
    room_id: int,
    body: AdminPatchRoomIn,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> AdminRoomOut:
    authorization, x_admin_token = creds
    r = _verify_room(room_id, db, x_admin_token, authorization)
    if body.name is not None:
        r.name = body.name
    if body.max_players is not None:
        r.max_players = body.max_players
    if body.status is not None:
        r.status = body.status
    db.commit()
    db.refresh(r)
    if body.status is not None and body.status == RoomStatus.closed:
        rt = get_room_runtime(room_id)
        await rt.broadcast_json(ws_message("room_closed", {"reason": "closed"}))
    return AdminRoomOut.model_validate(r)


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> dict[str, bool]:
    authorization, x_admin_token = creds
    r = _verify_room(room_id, db, x_admin_token, authorization)
    rt = get_room_runtime(room_id)
    await rt.broadcast_json(ws_message("room_closed", {"reason": "deleted"}))
    db.delete(r)
    db.commit()
    drop_room_runtime(room_id)
    return {"ok": True}


@router.post("/rooms/{room_id}/poll-types")
def add_poll_type(
    room_id: int,
    body: PollTypeWithOptionsIn,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> dict:
    authorization, x_admin_token = creds
    r = _verify_room(room_id, db, x_admin_token, authorization)
    if (
        db.query(RoomPollType)
        .filter(RoomPollType.room_id == room_id)
        .count()
        >= 1
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "每个房间仅支持一道题，请先删除已有题目",
        )
    if len(body.options) < 2 or len(body.options) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "选项数量为 2～10")
    _ = r
    pt = RoomPollType(
        room_id=room_id,
        title=body.title,
        display_style=body.display_style,
        sort_order=body.sort_order,
    )
    db.add(pt)
    db.flush()
    for o in body.options:
        db.add(PollOption(type_id=pt.id, text=o.text, sort_order=o.sort_order))
    db.commit()
    db.refresh(pt)
    return {"id": pt.id, "title": pt.title}


@router.get("/rooms/{room_id}/poll-types", response_model=list[PollTypeDetailOut])
def list_poll_types(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> list[PollTypeDetailOut]:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    rows = (
        db.query(RoomPollType)
        .options(joinedload(RoomPollType.options))
        .filter(RoomPollType.room_id == room_id)
        .order_by(RoomPollType.sort_order, RoomPollType.id)
        .all()
    )
    out: list[PollTypeDetailOut] = []
    for pt in rows:
        opts = sorted(pt.options, key=lambda o: (o.sort_order, o.id))
        out.append(
            PollTypeDetailOut(
                id=pt.id,
                title=pt.title,
                display_style=pt.display_style,
                sort_order=pt.sort_order,
                options=[PollOptionOut.model_validate(o) for o in opts],
            )
        )
    return out


@router.get("/rooms/{room_id}/poll-types/{type_id}", response_model=PollTypeDetailOut)
def get_poll_type(
    room_id: int,
    type_id: int,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> PollTypeDetailOut:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    pt = (
        db.query(RoomPollType)
        .options(joinedload(RoomPollType.options))
        .filter(RoomPollType.id == type_id, RoomPollType.room_id == room_id)
        .first()
    )
    if not pt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    opts = sorted(pt.options, key=lambda o: (o.sort_order, o.id))
    return PollTypeDetailOut(
        id=pt.id,
        title=pt.title,
        display_style=pt.display_style,
        sort_order=pt.sort_order,
        options=[PollOptionOut.model_validate(o) for o in opts],
    )


@router.patch("/rooms/{room_id}/poll-types/{type_id}", response_model=PollTypeDetailOut)
def patch_poll_type(
    room_id: int,
    type_id: int,
    body: PollTypePatchIn,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> PollTypeDetailOut:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    pt = _poll_type_or_404(room_id, type_id, db)
    if body.title is not None:
        pt.title = body.title
    if body.display_style is not None:
        pt.display_style = body.display_style
    if body.sort_order is not None:
        pt.sort_order = body.sort_order
    db.commit()
    db.refresh(pt)
    opts = (
        db.query(PollOption)
        .filter(PollOption.type_id == pt.id)
        .order_by(PollOption.sort_order, PollOption.id)
        .all()
    )
    return PollTypeDetailOut(
        id=pt.id,
        title=pt.title,
        display_style=pt.display_style,
        sort_order=pt.sort_order,
        options=[PollOptionOut.model_validate(o) for o in opts],
    )


@router.delete("/rooms/{room_id}/poll-types/{type_id}")
def delete_poll_type(
    room_id: int,
    type_id: int,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> dict[str, bool]:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    pt = _poll_type_or_404(room_id, type_id, db)
    # 先删回合：vote_rounds.winning_option_id 指向 poll_options，若先删题目/选项会触发外键错误
    db.query(VoteRound).filter(
        VoteRound.room_id == room_id,
        VoteRound.type_id == type_id,
    ).delete(synchronize_session=False)
    db.delete(pt)
    db.commit()
    drop_room_runtime(room_id)
    return {"ok": True}


@router.post("/rooms/{room_id}/poll-types/{type_id}/options", response_model=PollOptionOut)
def add_option(
    room_id: int,
    type_id: int,
    body: PollOptionSingleCreateIn,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> PollOptionOut:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    _poll_type_or_404(room_id, type_id, db)
    n = _option_count(type_id, db)
    if n >= 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "每题最多 10 个选项")
    o = PollOption(type_id=type_id, text=body.text, sort_order=body.sort_order)
    db.add(o)
    db.commit()
    db.refresh(o)
    return PollOptionOut.model_validate(o)


@router.patch("/rooms/{room_id}/poll-types/{type_id}/options/{option_id}", response_model=PollOptionOut)
def patch_option(
    room_id: int,
    type_id: int,
    option_id: int,
    body: PollOptionPatchIn,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> PollOptionOut:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    _poll_type_or_404(room_id, type_id, db)
    o = db.get(PollOption, option_id)
    if o is None or o.type_id != type_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "选项不存在")
    if body.text is not None:
        o.text = body.text
    if body.sort_order is not None:
        o.sort_order = body.sort_order
    db.commit()
    db.refresh(o)
    return PollOptionOut.model_validate(o)


@router.delete("/rooms/{room_id}/poll-types/{type_id}/options/{option_id}")
def delete_option(
    room_id: int,
    type_id: int,
    option_id: int,
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[tuple[str | None, str | None], Depends(admin_room_creds)],
) -> dict[str, bool]:
    authorization, x_admin_token = creds
    _verify_room(room_id, db, x_admin_token, authorization)
    _poll_type_or_404(room_id, type_id, db)
    o = db.get(PollOption, option_id)
    if o is None or o.type_id != type_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "选项不存在")
    n = _option_count(type_id, db)
    if n <= 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "每题至少保留 2 个选项")
    db.delete(o)
    db.commit()
    return {"ok": True}
