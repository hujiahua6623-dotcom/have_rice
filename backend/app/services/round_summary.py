"""上一轮已结束回合的汇总（用于房间快照）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import PollOption, RoomPollType, RoundAssist, RoundVote, User, VoteRound


def assist_ranking_for_round(db: Session, round_id: int) -> list[dict[str, Any]]:
    """该回合各玩家助力次数，按次数降序。"""
    rows = (
        db.query(RoundAssist, User)
        .join(User, User.id == RoundAssist.user_id)
        .filter(RoundAssist.round_id == round_id)
        .all()
    )
    out: list[dict[str, Any]] = [
        {"user_id": u.id, "nickname": u.nickname, "assist_count": ra.click_count} for ra, u in rows
    ]
    out.sort(key=lambda x: (-int(x["assist_count"]), int(x["user_id"])))
    return out


def last_completed_round_summary(db: Session, room_id: int) -> dict[str, Any] | None:
    """最近一条已产生胜出选项的回合；若尚无则返回 None。"""
    vr = (
        db.query(VoteRound)
        .filter(VoteRound.room_id == room_id, VoteRound.winning_option_id.isnot(None))
        .order_by(VoteRound.id.desc())
        .first()
    )
    if vr is None or vr.winning_option_id is None:
        return None

    rows = (
        db.query(RoundVote.option_id, func.count(RoundVote.id))
        .filter(RoundVote.round_id == vr.id)
        .group_by(RoundVote.option_id)
        .all()
    )
    count_map = {int(r[0]): int(r[1]) for r in rows}

    pt = db.get(RoomPollType, vr.type_id)
    poll_title = pt.title if pt else ""

    opts = (
        db.query(PollOption)
        .filter(PollOption.type_id == vr.type_id)
        .order_by(PollOption.sort_order, PollOption.id)
        .all()
    )
    options_out = [{"option_id": o.id, "text": o.text, "count": count_map.get(o.id, 0)} for o in opts]

    win_id = vr.winning_option_id
    winner_uids = [
        rv.user_id
        for rv in db.query(RoundVote).filter(
            RoundVote.round_id == vr.id, RoundVote.option_id == win_id
        )
    ]
    winner_names: list[str] = []
    for uid in winner_uids:
        user = db.get(User, uid)
        if user:
            winner_names.append(user.nickname)

    return {
        "round_id": vr.id,
        "poll_title": poll_title,
        "winning_option_id": win_id,
        "winner_nicknames": winner_names,
        "options": options_out,
        "assist_ranking": assist_ranking_for_round(db, vr.id),
    }
