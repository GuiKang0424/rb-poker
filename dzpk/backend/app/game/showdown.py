"""分配池子筹码到获胜者。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .deck import Card
from .evaluator import compare_hands
from .player import Player, PlayerStatus
from .poker import Pot


@dataclass
class PotAward:
    """池子分配结果。"""
    pot_amount: int
    eligible_seats: List[int]
    winner_seats: List[int]
    per_winner: int  # 每名赢家获得的金额
    odd_chip_to: int | None  # 余数筹码归属（None 表示无余数）


def distribute_pots(
    pots: List[Pot],
    players: Dict[int, Player],
    community_cards: List[Card],
    button_seat: int,
) -> List[PotAward]:
    """按主池/边池分配筹码到玩家。

    规则：
    - 每个池子由其 eligible 中"未弃牌"玩家比拼。
    - 平局均分；除不尽的余数（odd chip）按惯例给到 button 之后第一个未弃牌赢家。
    - 若仅一名 eligible 未弃牌（其他都弃牌），他不战而胜整个池。
    """
    awards: List[PotAward] = []

    for pot in pots:
        active_eligible = [
            s for s in pot.eligible_seats
            if players[s].status != PlayerStatus.FOLDED
        ]
        if not active_eligible:
            # 罕见：所有 eligible 弃牌，理论不应发生。把池给最后一个 eligible。
            target = pot.eligible_seats[-1] if pot.eligible_seats else None
            if target is not None:
                players[target].chips += pot.amount
                awards.append(PotAward(
                    pot_amount=pot.amount,
                    eligible_seats=list(pot.eligible_seats),
                    winner_seats=[target],
                    per_winner=pot.amount,
                    odd_chip_to=None,
                ))
            continue

        if len(active_eligible) == 1:
            winner = active_eligible[0]
            players[winner].chips += pot.amount
            awards.append(PotAward(
                pot_amount=pot.amount,
                eligible_seats=list(pot.eligible_seats),
                winner_seats=[winner],
                per_winner=pot.amount,
                odd_chip_to=None,
            ))
            continue

        # 比牌
        candidates = [(s, players[s].hole_cards) for s in active_eligible]
        groups = compare_hands(candidates, community_cards)
        winners = groups[0]  # 同分赢家组

        per = pot.amount // len(winners)
        remainder = pot.amount - per * len(winners)
        for s in winners:
            players[s].chips += per

        odd_chip_to = None
        if remainder > 0:
            # 余数按位置惯例：button 左手第一个赢家
            ordered = _ordered_after_button(button_seat, list(players.keys()))
            for s in ordered:
                if s in winners:
                    players[s].chips += remainder
                    odd_chip_to = s
                    break

        awards.append(PotAward(
            pot_amount=pot.amount,
            eligible_seats=list(pot.eligible_seats),
            winner_seats=winners,
            per_winner=per,
            odd_chip_to=odd_chip_to,
        ))

    return awards


def _ordered_after_button(button_seat: int, all_seats: List[int]) -> List[int]:
    """返回从 button 左手开始的座位顺序。"""
    seats = sorted(all_seats)
    if button_seat not in seats:
        return seats
    idx = seats.index(button_seat)
    return seats[idx + 1 :] + seats[: idx + 1]
