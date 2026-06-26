"""玩家、座位领域模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .deck import Card


class PlayerStatus(str, Enum):
    """玩家在当前牌局中的状态。"""
    WAITING = "waiting"          # 等待下一局
    ACTIVE = "active"            # 在手牌中
    FOLDED = "folded"            # 已弃牌
    ALL_IN = "all_in"            # 已 All-in
    SITTING_OUT = "sitting_out"  # 暂时离座


@dataclass
class Player:
    """玩家。

    seat: 座位号（0-based）
    user_id: 唯一身份（游客模式下为前端生成的临时 id）
    nickname: 昵称
    chips: 当前剩余筹码
    is_ai: 是否 AI
    ai_style: AI 策略风格（仅 AI）
    """
    seat: int
    user_id: str
    nickname: str
    chips: int
    is_ai: bool = False
    ai_style: Optional[str] = None

    # 房间管理
    is_ready: bool = False      # 是否已准备
    is_owner: bool = False      # 是否为房主

    # 当前牌局状态
    status: PlayerStatus = PlayerStatus.WAITING
    hole_cards: List[Card] = field(default_factory=list)
    # 当前下注轮已投入的筹码（每轮重置）
    current_bet: int = 0
    # 本手牌已投入的总筹码（用于分池）
    total_bet_this_hand: int = 0
    # 是否已在本下注轮行动过
    has_acted_this_round: bool = False

    def reset_for_new_hand(self) -> None:
        self.hole_cards = []
        self.current_bet = 0
        self.total_bet_this_hand = 0
        self.has_acted_this_round = False
        self.is_ready = False
        if self.chips > 0:
            self.status = PlayerStatus.WAITING
        else:
            self.status = PlayerStatus.SITTING_OUT

    def reset_for_new_betting_round(self) -> None:
        self.current_bet = 0
        self.has_acted_this_round = False

    def post_chips(self, amount: int) -> int:
        """投注 amount 筹码（不超过 chips），返回实际投入。

        若 amount >= chips，则全部投入并标记 All-in。
        """
        actual = min(amount, self.chips)
        self.chips -= actual
        self.current_bet += actual
        self.total_bet_this_hand += actual
        if self.chips == 0 and self.status == PlayerStatus.ACTIVE:
            self.status = PlayerStatus.ALL_IN
        return actual

    def can_act(self) -> bool:
        return self.status == PlayerStatus.ACTIVE
