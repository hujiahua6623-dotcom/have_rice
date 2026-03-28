"""跑马灯时间表：ease-out，终点为预设 winning 选项下标。"""
from __future__ import annotations

import random


def ease_out_cubic(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - pow(1 - t, 3)


def sample_weighted_option(weights: dict[int, float]) -> int:
    """按权重随机选一个 option_id。"""
    items = [(k, v) for k, v in weights.items() if v > 0]
    if not items:
        raise ValueError("empty weights")
    total = sum(v for _, v in items)
    r = random.random() * total
    acc = 0.0
    for oid, w in items:
        acc += w
        if r <= acc:
            return oid
    return items[-1][0]


def build_marquee_steps(
    num_options: int,
    winning_index: int,
    duration_sec: float,
    total_assist: int,
) -> list[dict[str, float | int]]:
    """
    返回 steps: [{t_ms, highlight_index}]，单调 t_ms，最后一项为终点。
    highlight_index 为 0..num_options-1。
    """
    if num_options < 1:
        raise ValueError("num_options must be >= 1")
    win_idx = winning_index % num_options
    # 步数：助力越多步数略多，同 n 时跑得更快（步数多、间隔短）
    n_steps = max(24, min(360, 20 + total_assist * 4))
    total_ms = duration_sec * 1000.0
    out: list[dict[str, float | int]] = []
    for j in range(n_steps + 1):
        frac = j / n_steps if n_steps else 1.0
        t_ms = ease_out_cubic(frac) * total_ms
        # 前期快速循环，后期用 blend 靠向 win_idx
        cycle = int(j * (2.5 + total_assist * 0.02)) % num_options
        blend = frac**1.8
        idx_float = (1 - blend) * cycle + blend * win_idx
        idx = int(round(idx_float)) % num_options
        if j == n_steps:
            idx = win_idx
        out.append({"t_ms": round(t_ms, 2), "highlight_index": idx})
    return out
