"""手牌强度评估，封装 deuces 库。"""
from __future__ import annotations

from typing import Iterable, List, Tuple

from .deck import Card


# deuces 用 Treys 风格的字符串：rank 大写 + suit 小写。我们的 Card 已对齐。

def _to_deuces_int(card: Card):
    from deuces import Card as DCard
    return DCard.new(f"{card.rank}{card.suit}")


def evaluate_hand(hole_cards: Iterable[Card], community_cards: Iterable[Card]) -> int:
    """返回 deuces 评分（数值越小越强）。

    参数：
        hole_cards: 玩家底牌（2 张）
        community_cards: 公共牌（3-5 张）
    返回：
        deuces 整数评分。1 = 皇家同花顺，7462 = 最差高牌。
    """
    from deuces import Evaluator

    holes = [_to_deuces_int(c) for c in hole_cards]
    boards = [_to_deuces_int(c) for c in community_cards]
    if len(holes) != 2:
        raise ValueError("底牌必须为 2 张")
    if not (3 <= len(boards) <= 5):
        raise ValueError("公共牌必须为 3-5 张")
    evaluator = Evaluator()
    return evaluator.evaluate(boards, holes)


def hand_rank_class(score: int) -> str:
    """返回手牌牌型名称（如 'Flush', 'Straight'）。"""
    from deuces import Evaluator
    evaluator = Evaluator()
    rank_class = evaluator.get_rank_class(score)
    return evaluator.class_to_string(rank_class)


def compare_hands(
    candidates: List[Tuple[int, List[Card]]],
    community_cards: List[Card],
) -> List[List[int]]:
    """比较多名玩家手牌，返回名次分组。

    参数：
        candidates: [(seat, hole_cards), ...]
        community_cards: 公共牌
    返回：
        [[最强 seat 列表], [次强 seat 列表], ...]
        同分玩家在同一组内（用于均分边池）。
    """
    scored = [(seat, evaluate_hand(holes, community_cards)) for seat, holes in candidates]
    # 按分数升序（小=强）
    scored.sort(key=lambda x: x[1])
    groups: List[List[int]] = []
    cur_score = None
    for seat, score in scored:
        if score != cur_score:
            groups.append([seat])
            cur_score = score
        else:
            groups[-1].append(seat)
    return groups
