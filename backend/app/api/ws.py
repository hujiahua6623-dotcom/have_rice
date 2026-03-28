import json
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import joinedload
from starlette.concurrency import run_in_threadpool

from app.core.security import decode_token
from app.database import SessionLocal
from app.models import Room, RoomChatMessage, RoomMembership, RoomPollType, RoomStatus, User
from app.services.round_summary import last_completed_round_summary
from app.services.room_runtime import RoomRuntime, get_room_runtime, ws_message

router = APIRouter()


async def _remove_member_on_ws_close(room_id: int, user_id: int, rt: RoomRuntime) -> None:
    """断开 WebSocket 视同离开房间：释放 DB 名额并清理内存中的选择/助力状态。"""

    def _work() -> None:
        db = SessionLocal()
        try:
            m = (
                db.query(RoomMembership)
                .filter(RoomMembership.user_id == user_id, RoomMembership.room_id == room_id)
                .first()
            )
            if m:
                db.delete(m)
                db.commit()
        finally:
            db.close()
        e = rt.engine
        e.selections.pop(user_id, None)
        e.confirmed.discard(user_id)
        e.assist_clicks.pop(user_id, None)

    await run_in_threadpool(_work)


@router.websocket("/ws/rooms/{room_id}")
async def room_ws(
    websocket: WebSocket,
    room_id: int,
    token: str | None = Query(default=None),
) -> None:
    if not token:
        await websocket.close(code=4401)
        return
    uid = decode_token(token)
    if uid is None:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    room_name = ""
    try:
        user = db.get(User, uid)
        if user is None:
            await websocket.close(code=4401)
            return
        room = db.get(Room, room_id)
        if room is None or room.status != RoomStatus.open:
            await websocket.close(code=4404)
            return
        m = (
            db.query(RoomMembership)
            .filter(RoomMembership.user_id == uid, RoomMembership.room_id == room_id)
            .first()
        )
        if m is None:
            await websocket.close(code=4403)
            return
        room_name = room.name
    finally:
        db.close()

    await websocket.accept()
    rt = get_room_runtime(room_id)
    rt.connections[uid] = websocket

    await rt.broadcast_json(
        ws_message(
            "welcome",
            {
                "text": f"欢迎 {user.nickname} 加入 {room_name}",
                "user_id": uid,
                "nickname": user.nickname,
                "room_name": room_name,
            },
        )
    )

    # 快照：题目列表（需先 ensure_round，否则内存引擎仍为 waiting，与 DB 中已有回合/题目不一致）
    db = SessionLocal()
    try:
        rt.engine.ensure_round(db)
        types = (
            db.query(RoomPollType)
            .options(joinedload(RoomPollType.options))
            .filter(RoomPollType.room_id == room_id)
            .order_by(RoomPollType.sort_order, RoomPollType.id)
            .all()
        )
        payload: dict[str, Any] = {
            "room_id": room_id,
            "name": room_name,
            "poll_types": [],
            "phase": rt.engine.phase.value,
        }
        for t in types:
            ordered = sorted(t.options, key=lambda o: (o.sort_order, o.id))
            opts = [{"id": o.id, "text": o.text, "sort_order": o.sort_order} for o in ordered]
            payload["poll_types"].append(
                {
                    "id": t.id,
                    "title": t.title,
                    "display_style": t.display_style.value,
                    "sort_order": t.sort_order,
                    "options": opts,
                }
            )
        member_rows = (
            db.query(User.id, User.nickname)
            .join(RoomMembership, RoomMembership.user_id == User.id)
            .filter(RoomMembership.room_id == room_id)
            .order_by(User.id)
            .all()
        )
        payload["members"] = [{"user_id": r[0], "nickname": r[1]} for r in member_rows]
        e = rt.engine
        mids = sorted(e.member_user_ids(db))
        payload["peer_states"] = [
            {
                "user_id": uid,
                "has_selected": uid in e.selections,
                "has_confirmed": uid in e.confirmed,
            }
            for uid in mids
        ]
        lr = last_completed_round_summary(db, room_id)
        if lr is not None:
            payload["last_round_summary"] = lr
        chat_rows = (
            db.query(RoomChatMessage, User.nickname)
            .join(User, User.id == RoomChatMessage.user_id)
            .filter(RoomChatMessage.room_id == room_id)
            .order_by(RoomChatMessage.id.desc())
            .limit(100)
            .all()
        )
        chat_rows = list(reversed(chat_rows))
        payload["chat_messages"] = [
            {
                "id": cm.id,
                "user_id": cm.user_id,
                "nickname": nick,
                "body": cm.body,
                "created_at": cm.created_at.isoformat() if cm.created_at else "",
            }
            for cm, nick in chat_rows
        ]
        await websocket.send_json(ws_message("room_snapshot", payload))
    finally:
        db.close()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await rt.handle_client_message(uid, data, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        rt.connections.pop(uid, None)
        await _remove_member_on_ws_close(room_id, uid, rt)
        await rt.broadcast_json(
            ws_message(
                "user_left",
                {"user_id": uid, "nickname": user.nickname},
            )
        )
