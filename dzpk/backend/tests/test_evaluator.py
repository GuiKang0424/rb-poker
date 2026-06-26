"""测试手牌评估。"""
import pytest

from app.game.deck import Card
from app.game.evaluator import compare_hands, evaluate_hand, hand_rank_class


def cards(*strs):
    return [Card.from_str(s) for s in strs]


def test_royal_flush_beats_straight_flush():
    royal = evaluate_hand(cards("As", "Ks"), cards("Qs", "Js", "Ts", "2c", "3d"))
    straight_flush = evaluate_hand(cards("9h", "8h"), cards("7h", "6h", "5h", "2c", "3d"))
    assert royal < straight_flush  # deuces 中分数越小越强


def test_pair_beats_high_card():
    pair = evaluate_hand(cards("As", "Ah"), cards("Kc", "Qd", "Js", "9h", "2c"))
    high = evaluate_hand(cards("Kh", "Qs"), cards("9c", "5d", "3h", "2s", "7c"))
    assert pair < high


def test_compare_hands_returns_grouped_ranking():
    # 两人都是同样牌型（同花顺平局是几乎不可能的，这里造一个 split pot 场景：双方都是 board play）
    # 公共牌：As Ks Qs Js Ts → 任何人都是同花顺到 A，但底牌可能改写
    # 双方底牌都对结果无影响 → 平分
    community = cards("As", "Ks", "Qs", "Js", "Ts")
    candidates = [
        (0, cards("2c", "3d")),
        (1, cards("4h", "5d")),
    ]
    groups = compare_hands(candidates, community)
    assert len(groups) == 1
    assert set(groups[0]) == {0, 1}


def test_compare_hands_clear_winner():
    # 公共牌避开顺子/同花组合
    community = cards("2c", "5d", "8h", "Tc", "3s")
    candidates = [
        (0, cards("As", "Ah")),  # 一对 A
        (1, cards("Kh", "Qs")),  # 高牌
    ]
    groups = compare_hands(candidates, community)
    assert groups[0] == [0]
    assert groups[1] == [1]


def test_hand_rank_class_returns_string():
    score = evaluate_hand(cards("As", "Ah"), cards("Kc", "Qd", "Js", "9h", "2c"))
    name = hand_rank_class(score)
    assert isinstance(name, str)
    assert len(name) > 0
