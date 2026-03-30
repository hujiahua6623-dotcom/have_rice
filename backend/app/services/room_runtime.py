"""房间内 WebSocket 连接与游戏状态（内存 + DB 持久化回合）。"""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import SessionLocal
from app.models import (
    GamePhase,
    PollOption,
    RoomChatMessage,
    RoomMembership,
    RoomPollType,
    RoundAssist,
    RoundVote,
    User,
    VoteRound,
)
from app.services.marquee import build_marquee_steps, sample_weighted_option
from app.services.round_summary import assist_ranking_for_round


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ws_message(msg_type: str, payload: dict[str, Any] | None = None, v: int = 1) -> dict[str, Any]:
    return {
        "v": v,
        "msg_type": msg_type,
        "payload": payload or {},
        "server_ts_ms": int(_now().timestamp() * 1000),
    }


class GameEngine:
    """同步逻辑；由 RoomRuntime 在 threadpool 中调用。"""

    def __init__(self, room_id: int) -> None:
        self.room_id = room_id
        self.phase: GamePhase = GamePhase.waiting
        self.round_id: int | None = None
        self.type_id: int | None = None
        self.selections: dict[int, int] = {}
        self.confirmed: set[int] = set()
        self.assist_clicks: dict[int, int] = {}
        self.winning_option_id: int | None = None
        self.marquee_steps: list[dict[str, Any]] = []
        self.cancel_generation = 0

    def _first_poll_type_id(self, db: Session) -> int | None:
        t = (
            db.query(RoomPollType)
            .filter(RoomPollType.room_id == self.room_id)
            .order_by(RoomPollType.sort_order, RoomPollType.id)
            .first()
        )
        return t.id if t else None

    def ensure_round(self, db: Session) -> None:
        tid = self._first_poll_type_id(db)
        if not tid:
            self.phase = GamePhase.waiting
            return
        if self.round_id:
            vr = db.get(VoteRound, self.round_id)
            if vr:
                self.phase = vr.phase
                self.type_id = vr.type_id
                return
        vr = (
            db.query(VoteRound)
            .filter(VoteRound.room_id == self.room_id)
            .order_by(VoteRound.id.desc())
            .first()
        )
        if vr:
            self.round_id = vr.id
            self.type_id = vr.type_id
            self.phase = vr.phase
            self.selections = {}
            self.confirmed = set()
            for rv in db.query(RoundVote).filter(RoundVote.round_id == vr.id):
                self.selections[rv.user_id] = rv.option_id
            return
        vr = VoteRound(
            room_id=self.room_id,
            type_id=tid,
            phase=GamePhase.selecting,
            phase_started_at=_now(),
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        self.round_id = vr.id
        self.type_id = tid
        self.phase = GamePhase.selecting

    def member_user_ids(self, db: Session) -> list[int]:
        rows = db.query(RoomMembership.user_id).filter(RoomMembership.room_id == self.room_id).all()
        return [r[0] for r in rows]

    def round_voter_user_ids(self, db: Session) -> list[int]:
        """本回合已在 DB 中落票的用户。倒计时/助力期间新进房者尚未有 RoundVote，不应参与本轮结算。"""
        if not self.round_id:
            return []
        rows = db.query(RoundVote.user_id).filter(RoundVote.round_id == self.round_id).all()
        return sorted(r[0] for r in rows)

    def _persist_phase(self, db: Session) -> None:
        if not self.round_id:
            return
        vr = db.get(VoteRound, self.round_id)
        if vr:
            vr.phase = self.phase
            vr.phase_started_at = _now()
            if self.winning_option_id:
                vr.winning_option_id = self.winning_option_id
            db.commit()

    def set_phase(self, db: Session, phase: GamePhase) -> None:
        self.phase = phase
        self._persist_phase(db)

    def handle_select(self, db: Session, user_id: int, option_id: int) -> str | None:
        self.ensure_round(db)
        if self.phase == GamePhase.waiting:
            return "暂无投票题目"
        if self.phase != GamePhase.selecting:
            return "当前阶段不可选"
        opts = (
            db.query(PollOption.id)
            .filter(PollOption.type_id == self.type_id, PollOption.id == option_id)
            .first()
        )
        if not opts:
            return "无效选项"
        self.selections[user_id] = option_id
        if user_id in self.confirmed:
            self.confirmed.discard(user_id)
        rv = (
            db.query(RoundVote)
            .filter(RoundVote.round_id == self.round_id, RoundVote.user_id == user_id)
            .first()
        )
        if rv:
            rv.option_id = option_id
        else:
            db.add(RoundVote(round_id=self.round_id, user_id=user_id, option_id=option_id))
        db.commit()
        return None

    def handle_confirm(self, db: Session, user_id: int) -> str | None:
        if self.phase != GamePhase.selecting:
            return "当前不可确认"
        if user_id not in self.selections:
            return "请先选择选项"
        self.confirmed.add(user_id)
        return None

    def handle_cancel(self, db: Session, user_id: int) -> str | None:
        if self.phase == GamePhase.countdown_5s:
            self.confirmed.discard(user_id)
            self.phase = GamePhase.selecting
            self._persist_phase(db)
            return None
        if self.phase == GamePhase.selecting:
            self.confirmed.discard(user_id)
            return None
        return "当前不可取消"

    def all_ready(self, db: Session) -> bool:
        mids = self.member_user_ids(db)
        if not mids:
            return False
        for uid in mids:
            if uid not in self.selections or uid not in self.confirmed:
                return False
        return True

    def reset_round_after_result(self, db: Session) -> None:
        """结果展示后开启新一轮（同一题目类型）。"""
        tid = self.type_id or self._first_poll_type_id(db)
        if not tid:
            self.phase = GamePhase.waiting
            return
        self.selections.clear()
        self.confirmed.clear()
        self.assist_clicks.clear()
        self.winning_option_id = None
        self.marquee_steps = []
        vr = VoteRound(
            room_id=self.room_id,
            type_id=tid,
            phase=GamePhase.selecting,
            phase_started_at=_now(),
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        self.round_id = vr.id
        self.type_id = tid
        self.phase = GamePhase.selecting
        self._persist_phase(db)

    def run_computing(self, db: Session) -> str | None:
        mids = self.round_voter_user_ids(db)
        weights: dict[int, float] = {}
        for uid in mids:
            oid = self.selections.get(uid)
            if oid is None:
                return "有玩家未选择"
            raw = self.assist_clicks.get(uid, 0)
            effective = 1 if raw == 0 else min(raw, settings.assist_cap_per_user)
            weights[oid] = weights.get(oid, 0.0) + float(effective)

        if not weights:
            return "权重为空"

        win = sample_weighted_option(weights)
        self.winning_option_id = win

        ordered = (
            db.query(PollOption)
            .filter(PollOption.type_id == self.type_id)
            .order_by(PollOption.sort_order, PollOption.id)
            .all()
        )
        chosen_ids = {self.selections[u] for u in mids}
        filtered = [o for o in ordered if o.id in chosen_ids]
        if not filtered:
            return "无有效选项"
        index_list = [o.id for o in filtered]
        if self.winning_option_id not in index_list:
            sub_w = {k: weights[k] for k in index_list if k in weights}
            self.winning_option_id = sample_weighted_option(sub_w)
        win_idx = index_list.index(self.winning_option_id)
        total_assist = sum(
            (1 if self.assist_clicks.get(u, 0) == 0 else min(self.assist_clicks[u], settings.assist_cap_per_user))
            for u in mids
        )
        n_sec = min(10, max(1, total_assist))
        steps = build_marquee_steps(len(index_list), win_idx, float(n_sec), total_assist)
        self.marquee_steps = steps

        for uid in mids:
            raw = self.assist_clicks.get(uid, 0)
            cnt = 1 if raw == 0 else min(raw, settings.assist_cap_per_user)
            ra = (
                db.query(RoundAssist)
                .filter(RoundAssist.round_id == self.round_id, RoundAssist.user_id == uid)
                .first()
            )
            if ra:
                ra.click_count = cnt
            else:
                db.add(RoundAssist(round_id=self.round_id, user_id=uid, click_count=cnt))
        db.commit()
        return None


def build_round_result_payload(db: Session, engine: GameEngine) -> dict[str, Any]:
    """本轮结果：胜出选项、各选项得票人数、胜方昵称（与 DB 回合一致）。"""
    tid = engine.type_id
    win = engine.winning_option_id
    mids = engine.round_voter_user_ids(db)
    counts: Counter[int] = Counter()
    for uid in mids:
        oid = engine.selections.get(uid)
        if oid is not None:
            counts[oid] += 1
    pt = db.get(RoomPollType, tid) if tid else None
    poll_title = pt.title if pt else ""
    options_out: list[dict[str, Any]] = []
    if tid:
        for o in (
            db.query(PollOption)
            .filter(PollOption.type_id == tid)
            .order_by(PollOption.sort_order, PollOption.id)
            .all()
        ):
            options_out.append({"option_id": o.id, "text": o.text, "count": counts.get(o.id, 0)})
    names: list[str] = []
    for uid in mids:
        if engine.selections.get(uid) == win:
            u = db.get(User, uid)
            if u:
                names.append(u.nickname)
    return {
        "round_id": engine.round_id,
        "poll_title": poll_title,
        "winning_option_id": win,
        "winner_nicknames": names,
        "options": options_out,
        "assist_ranking": assist_ranking_for_round(db, engine.round_id) if engine.round_id else [],
    }


class RoomRuntime:
    def __init__(self, room_id: int) -> None:
        self.room_id = room_id
        self.connections: dict[int, WebSocket] = {}
        self.engine = GameEngine(room_id)
        self.lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[Any]] = []
        self._countdown_gen = 0
        self._assist_commit_open = False

    async def broadcast_json(self, message: dict[str, Any]) -> None:
        dead: list[int] = []
        for uid, ws in list(self.connections.items()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.connections.pop(uid, None)

    def schedule(self, coro: Any) -> None:
        t = asyncio.create_task(coro)
        self._tasks.append(t)

    async def _run_countdown_5s(self) -> None:
        gen = self._countdown_gen
        engine = self.engine
        for sec in range(5, 0, -1):
            if gen != self._countdown_gen:
                return
            await self.broadcast_json(ws_message("countdown", {"phase": "countdown_5s", "seconds": sec}))
            await asyncio.sleep(1.0)
        if gen != self._countdown_gen:
            return

        def _go_assist_preview() -> None:
            db = SessionLocal()
            try:
                if engine.phase != GamePhase.countdown_5s:
                    return
                engine.set_phase(db, GamePhase.assist_preview)
            finally:
                db.close()

        await run_in_threadpool(_go_assist_preview)
        await self.broadcast_json(
            ws_message("phase_changed", {"phase": GamePhase.assist_preview.value})
        )
        await self._run_assist_preview()

    async def _run_assist_preview(self) -> None:
        for sec in range(5, 0, -1):
            await self.broadcast_json(ws_message("countdown", {"phase": "assist_preview", "seconds": sec}))
            await asyncio.sleep(1.0)
        await self._start_assist_go()

    async def _start_assist_go(self) -> None:

        def _set_go() -> None:
            db = SessionLocal()
            try:
                self.engine.set_phase(db, GamePhase.assist_go)
                self.engine.assist_clicks.clear()
            finally:
                db.close()

        await run_in_threadpool(_set_go)
        await self.broadcast_json(ws_message("phase_changed", {"phase": GamePhase.assist_go.value}))
        for sec in range(10, 0, -1):
            await self.broadcast_json(ws_message("countdown", {"phase": "assist_go", "seconds": sec}))
            await asyncio.sleep(1.0)
        grace = float(settings.assist_grace_seconds)
        grace_ms = max(0, int(round(grace * 1000)))
        await self.broadcast_json(
            ws_message(
                "assist_submit_window",
                {"grace_ms": grace_ms, "grace_sec": grace},
            )
        )
        self._assist_commit_open = True
        try:
            await asyncio.sleep(grace)
        finally:
            self._assist_commit_open = False
        await self._run_computing_and_marquee()

    async def _run_computing_and_marquee(self) -> None:

        def _compute() -> tuple[str | None, list[dict[str, Any]], int | None, float]:
            db = SessionLocal()
            try:
                e = self.engine
                err = e.run_computing(db)
                if err:
                    return err, [], None, 0.0
                e.set_phase(db, GamePhase.computing)
                steps = e.marquee_steps
                win = e.winning_option_id
                n_sec = min(
                    10,
                    max(
                        1,
                        sum(
                            (
                                1
                                if e.assist_clicks.get(u, 0) == 0
                                else min(e.assist_clicks[u], settings.assist_cap_per_user)
                            )
                            for u in e.round_voter_user_ids(db)
                        ),
                    ),
                )
                return None, steps, win, float(n_sec)
            finally:
                db.close()

        err, steps, win_id, n_sec = await run_in_threadpool(_compute)
        if err:
            await self.broadcast_json(ws_message("error", {"message": err}))
            return

        def _set_marquee() -> None:
            db = SessionLocal()
            try:
                self.engine.set_phase(db, GamePhase.marquee)
            finally:
                db.close()

        await run_in_threadpool(_set_marquee)
        def _ordered_ids() -> list[int]:
            db = SessionLocal()
            try:
                e = self.engine
                ordered = (
                    db.query(PollOption)
                    .filter(PollOption.type_id == e.type_id)
                    .order_by(PollOption.sort_order, PollOption.id)
                    .all()
                )
                mids = e.round_voter_user_ids(db)
                chosen = {e.selections[u] for u in mids}
                return [o.id for o in ordered if o.id in chosen]
            finally:
                db.close()

        ordered_ids = await run_in_threadpool(_ordered_ids)
        await self.broadcast_json(
            ws_message(
                "marquee_start",
                {
                    "steps": steps,
                    "ordered_option_ids": ordered_ids,
                    "winning_option_id": win_id,
                    "duration_sec": n_sec,
                },
            )
        )
        await asyncio.sleep(n_sec)

        def _set_result() -> dict[str, Any]:
            db = SessionLocal()
            try:
                e = self.engine
                e.set_phase(db, GamePhase.result)
                return build_round_result_payload(db, e)
            finally:
                db.close()

        result_payload = await run_in_threadpool(_set_result)
        await self.broadcast_json(ws_message("round_result", result_payload))
        await asyncio.sleep(5.0)

        def _next_round() -> None:
            db = SessionLocal()
            try:
                self.engine.reset_round_after_result(db)
            finally:
                db.close()

        await run_in_threadpool(_next_round)
        await self.broadcast_json(
            ws_message("phase_changed", {"phase": GamePhase.selecting.value, "new_round": True})
        )

    async def maybe_start_countdown(self) -> None:
        async with self.lock:

            def _check() -> bool:
                db = SessionLocal()
                try:
                    self.engine.ensure_round(db)
                    if self.engine.phase != GamePhase.selecting:
                        return False
                    return self.engine.all_ready(db)
                finally:
                    db.close()

            ok = await run_in_threadpool(_check)
            if not ok:
                return

            def _set_cd() -> None:
                db = SessionLocal()
                try:
                    if self.engine.phase != GamePhase.selecting:
                        return
                    self.engine.set_phase(db, GamePhase.countdown_5s)
                finally:
                    db.close()

            await run_in_threadpool(_set_cd)
            self._countdown_gen += 1
            await self.broadcast_json(
                ws_message("phase_changed", {"phase": GamePhase.countdown_5s.value})
            )
            self.schedule(self._run_countdown_5s())

    async def _handle_chat_message(
        self, user_id: int, data: dict[str, Any], sender_ws: WebSocket | None
    ) -> None:
        raw = data.get("body")
        if raw is None:
            raw = data.get("text", "")
        if not isinstance(raw, str):
            raw = str(raw)
        body = raw.strip()
        if not body:
            if sender_ws:
                try:
                    await sender_ws.send_json(
                        ws_message("error", {"message": "消息不能为空", "scope": "chat"})
                    )
                except Exception:
                    pass
            return
        if len(body) > 512:
            body = body[:512]

        def _work() -> tuple[str | None, dict[str, Any] | None]:
            db = SessionLocal()
            try:
                mship = (
                    db.query(RoomMembership)
                    .filter(RoomMembership.user_id == user_id, RoomMembership.room_id == self.room_id)
                    .first()
                )
                if not mship:
                    return "不在房间内", None
                u = db.get(User, user_id)
                if not u:
                    return "用户不存在", None
                row = RoomChatMessage(room_id=self.room_id, user_id=user_id, body=body)
                db.add(row)
                db.commit()
                db.refresh(row)
                ts = row.created_at.isoformat() if row.created_at else ""
                payload = {
                    "id": row.id,
                    "user_id": user_id,
                    "nickname": u.nickname,
                    "body": body,
                    "created_at": ts,
                }
                return None, payload
            finally:
                db.close()

        err, payload = await run_in_threadpool(_work)
        if err or not payload:
            if sender_ws:
                try:
                    await sender_ws.send_json(
                        ws_message("error", {"message": err or "发送失败", "scope": "chat"})
                    )
                except Exception:
                    pass
            return
        await self.broadcast_json(ws_message("chat_message", payload))

    async def handle_client_message(
        self, user_id: int, data: dict[str, Any], sender_ws: WebSocket | None
    ) -> None:
        m = data.get("msg_type")
        if m == "heartbeat":
            return
        if m == "chat_message":
            await self._handle_chat_message(user_id, data, sender_ws)
            return
        if m == "assist_commit":
            if not self._assist_commit_open:
                if sender_ws:
                    try:
                        await sender_ws.send_json(ws_message("error", {"message": "不在提交窗口"}))
                    except Exception:
                        pass
                return

            def _assist_commit() -> str | None:
                db = SessionLocal()
                try:
                    e = self.engine
                    e.ensure_round(db)
                    if e.phase != GamePhase.assist_go:
                        return "非助力阶段"
                    raw = data.get("count", 0)
                    try:
                        c = int(raw)
                    except (TypeError, ValueError):
                        c = 0
                    c = max(0, min(c, settings.assist_cap_per_user))
                    e.assist_clicks[user_id] = c
                    return None
                finally:
                    db.close()

            err = await run_in_threadpool(_assist_commit)
            if err and sender_ws:
                try:
                    await sender_ws.send_json(ws_message("error", {"message": err}))
                except Exception:
                    pass
            return

        def _work() -> tuple[str | None, bool, bool, str | None]:
            db = SessionLocal()
            try:
                e = self.engine
                e.ensure_round(db)
                err: str | None = None
                need_countdown = False
                private_select = False
                cancel_mode: str | None = None
                if m == "select_option":
                    oid = data.get("option_id")
                    if oid is None:
                        err = "缺少 option_id"
                    else:
                        err = e.handle_select(db, user_id, int(oid))
                        private_select = err is None
                elif m == "confirm":
                    err = e.handle_confirm(db, user_id)
                    if not err:
                        need_countdown = e.all_ready(db)
                elif m == "cancel":
                    ph_before = e.phase
                    err = e.handle_cancel(db, user_id)
                    if not err:
                        if ph_before == GamePhase.countdown_5s:
                            cancel_mode = "countdown"
                        elif ph_before == GamePhase.selecting:
                            cancel_mode = "selecting"
                elif m == "assist_click":
                    if e.phase != GamePhase.assist_go:
                        err = "非助力阶段"
                    # assist_go：由客户端本地累计，在 assist_submit_window 内一次性 assist_commit
                else:
                    err = f"未知消息: {m}"
                return err, need_countdown, private_select, cancel_mode
            finally:
                db.close()

        err, need_countdown, private_select, cancel_mode = await run_in_threadpool(_work)
        if err:
            if sender_ws:
                try:
                    await sender_ws.send_json(ws_message("error", {"message": err}))
                except Exception:
                    pass
            return
        if private_select and sender_ws:
            oid = data.get("option_id")
            try:
                await sender_ws.send_json(
                    ws_message("select_ack", {"option_id": int(oid) if oid is not None else None})
                )
            except Exception:
                pass
            await self.broadcast_json(
                ws_message(
                    "peer_state",
                    {"user_id": user_id, "has_selected": True, "has_confirmed": False},
                )
            )
        elif m == "confirm":
            await self.broadcast_json(
                ws_message(
                    "peer_state",
                    {"user_id": user_id, "has_confirmed": True},
                )
            )
        elif m == "cancel":
            if cancel_mode == "countdown":
                self._countdown_gen += 1
                await self.broadcast_json(
                    ws_message(
                        "phase_changed",
                        {"phase": GamePhase.selecting.value, "cancelled_by": user_id},
                    )
                )
            elif cancel_mode == "selecting":
                await self.broadcast_json(
                    ws_message(
                        "peer_state",
                        {"user_id": user_id, "has_confirmed": False},
                    )
                )
        if need_countdown:
            await self.maybe_start_countdown()


_room_runtimes: dict[int, RoomRuntime] = {}


def get_room_runtime(room_id: int) -> RoomRuntime:
    if room_id not in _room_runtimes:
        _room_runtimes[room_id] = RoomRuntime(room_id)
    return _room_runtimes[room_id]


def drop_room_runtime(room_id: int) -> None:
    _room_runtimes.pop(room_id, None)


def online_count(room_id: int) -> int:
    return len(get_room_runtime(room_id).connections)
