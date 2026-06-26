"""下注系统、动作类型与边池计算。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .player import Player, PlayerStatus


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class Action:
    """玩家动作。"""
    type: ActionType
    seat: int
    amount: int = 0  # 该动作总下注金额（绝对值，非增量）


class IllegalActionError(Exception):
    """非法动作。"""


@dataclass
class Pot:
    """一个池子（主池或边池）。

    amount: 池中筹码总量
    eligible_seats: 有资格争夺该池的座位（投入筹码达到该 cap 的玩家）
    cap: 该池由每名 eligible 玩家最多投入到这个金额（用于计算）
    """
    amount: int
    eligible_seats: List[int]
    cap: int = 0


def compute_side_pots(players: List[Player]) -> List[Pot]:
    """根据每个玩家本手牌的总投入计算主池与边池。

    算法：
    1. 收集所有非弃牌玩家的 total_bet_this_hand（含弃牌玩家投入也要算入池中，但他们不参与分池）。
    2. 按投入金额从小到大分层：每层 = (本层金额 - 上层金额) * 当前仍≥本层金额的玩家数。
    3. 每层池子由"投入≥本层 cap 且未弃牌"的玩家争夺。

    弃牌玩家的筹码：照常计入池子总量，但不参与争夺。
    """
    # 所有玩家本手牌投入，包括弃牌
    contributors = [p for p in players if p.total_bet_this_hand > 0]
    if not contributors:
        return []

    # 按投入金额升序的唯一阈值
    levels = sorted({p.total_bet_this_hand for p in contributors})

    pots: List[Pot] = []
    prev_level = 0
    for level in levels:
        delta = level - prev_level
        # 所有投入 >= level 的人都在该层投入了 delta（含弃牌）
        layer_amount = sum(
            min(delta, max(0, p.total_bet_this_hand - prev_level))
            for p in contributors
        )
        if layer_amount <= 0:
            prev_level = level
            continue
        # 有资格争夺该层池的：投入 >= level 且未弃牌
        eligible = [
            p.seat for p in contributors
            if p.total_bet_this_hand >= level and p.status != PlayerStatus.FOLDED
        ]
        if eligible:
            pots.append(Pot(amount=layer_amount, eligible_seats=eligible, cap=level))
        else:
            # 全部弃牌，归入上一池或单独池（理论上不会发生，因为最后至少一人未弃牌赢了池）
            if pots:
                pots[-1].amount += layer_amount
            else:
                pots.append(Pot(amount=layer_amount, eligible_seats=[], cap=level))
        prev_level = level

    # 合并相邻"eligible_seats 完全相同"的池（视觉上合一池更直观，计算上等价）
    merged: List[Pot] = []
    for pot in pots:
        if merged and merged[-1].eligible_seats == pot.eligible_seats:
            merged[-1].amount += pot.amount
            merged[-1].cap = pot.cap
        else:
            merged.append(pot)
    return merged


@dataclass
class BettingRound:
    """下注轮状态。

    current_bet: 本轮当前最高下注额（玩家需 call 到此值）
    last_raise_size: 上一次加注的"加注幅度"，用于约束最小加注
    big_blind: 大盲金额（最小加注下限）
    """
    current_bet: int = 0
    last_raise_size: int = 0
    big_blind: int = 0
    # 本轮已经发生过加注/下注的玩家座位（用于决定 check 是否合法）
    aggressor_seat: Optional[int] = None

    def reset(self, big_blind: int) -> None:
        self.current_bet = 0
        self.last_raise_size = big_blind
        self.big_blind = big_blind
        self.aggressor_seat = None


def validate_and_apply_action(
    action: Action,
    player: Player,
    round_state: BettingRound,
) -> int:
    """校验并执行玩家动作，返回该动作实际投入的筹码（增量）。

    注意：此函数仅处理"单玩家本次动作"的合法性与状态变更，
    不处理"下注轮是否结束"等外层判定。
    """
    if not player.can_act():
        raise IllegalActionError(f"玩家 seat={player.seat} 当前不可行动 (status={player.status})")

    to_call = round_state.current_bet - player.current_bet

    if action.type == ActionType.FOLD:
        player.status = PlayerStatus.FOLDED
        player.has_acted_this_round = True
        return 0

    if action.type == ActionType.CHECK:
        if to_call != 0:
            raise IllegalActionError("当前需跟注，不能 check")
        player.has_acted_this_round = True
        return 0

    if action.type == ActionType.CALL:
        if to_call <= 0:
            raise IllegalActionError("无需跟注（应使用 check）")
        actual = player.post_chips(to_call)
        player.has_acted_this_round = True
        return actual

    if action.type == ActionType.BET:
        if round_state.current_bet > 0:
            raise IllegalActionError("当前已有下注，应使用 raise")
        if action.amount < round_state.big_blind:
            raise IllegalActionError(f"下注不能少于大盲 {round_state.big_blind}")
        if action.amount > player.chips:
            raise IllegalActionError("下注超过剩余筹码")
        actual = player.post_chips(action.amount)
        round_state.current_bet = player.current_bet
        round_state.last_raise_size = action.amount
        round_state.aggressor_seat = player.seat
        player.has_acted_this_round = True
        # 触发其他玩家重新行动（外层处理）
        return actual

    if action.type == ActionType.RAISE:
        if round_state.current_bet == 0:
            raise IllegalActionError("当前无下注，应使用 bet")
        # action.amount 解释为"加注后的总下注额"
        target_bet = action.amount
        raise_size = target_bet - round_state.current_bet
        # 最小加注额 = max(大盲, 上一次加注幅度)
        min_raise = max(round_state.big_blind, round_state.last_raise_size)
        if raise_size < min_raise:
            # 例外：如果是 All-in 且不足，外层应使用 ALL_IN 而非 RAISE
            raise IllegalActionError(f"加注幅度不足，最小 {min_raise}")
        need = target_bet - player.current_bet
        if need > player.chips:
            raise IllegalActionError("加注超过剩余筹码（请使用 all_in）")
        actual = player.post_chips(need)
        round_state.current_bet = player.current_bet
        round_state.last_raise_size = raise_size
        round_state.aggressor_seat = player.seat
        player.has_acted_this_round = True
        return actual

    if action.type == ActionType.ALL_IN:
        if player.chips <= 0:
            raise IllegalActionError("无筹码可 all-in")
        actual = player.post_chips(player.chips)
        # All-in 投入后的新 current_bet
        if player.current_bet > round_state.current_bet:
            new_raise_size = player.current_bet - round_state.current_bet
            round_state.current_bet = player.current_bet
            # 不足最小加注的 All-in 不增加 last_raise_size，但仍设为 aggressor
            if new_raise_size >= max(round_state.big_blind, round_state.last_raise_size):
                round_state.last_raise_size = new_raise_size
                round_state.aggressor_seat = player.seat
            else:
                # 短 all-in：不重新打开下注轮
                pass
        player.has_acted_this_round = True
        return actual

    raise IllegalActionError(f"未知动作类型: {action.type}")
