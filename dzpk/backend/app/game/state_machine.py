"""游戏状态机：单桌一手牌的完整流程。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from .deck import Card, Deck
from .player import Player, PlayerStatus
from .poker import (
    Action,
    ActionType,
    BettingRound,
    IllegalActionError,
    Pot,
    compute_side_pots,
    validate_and_apply_action,
)
from .showdown import PotAward, distribute_pots


class GameStage(str, Enum):
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    REVEAL_WAIT = "reveal_wait"  # 等待玩家选择是否展示手牌
    SHOWDOWN = "showdown"
    HAND_END = "hand_end"


@dataclass
class HandResult:
    """一手牌结束的结果。"""
    awards: List[PotAward]
    community_cards: List[Card]
    player_holes: Dict[int, List[Card]]  # seat -> hole_cards（仅未弃牌且参与摊牌）


@dataclass
class GameConfig:
    """牌局配置。"""
    small_blind: int = 5
    big_blind: int = 10
    max_players: int = 9


class TableState:
    """单桌状态。

    职责：
    - 管理座位上的玩家列表
    - 驱动一手牌从 Preflop → Showdown
    - 通过 asyncio.Queue 接收玩家动作（外层 WS 投递）
    - 通过 emit 回调向外推送事件（外层订阅）
    - 通过 _system_message 回调发送系统聊天消息（外层订阅）
    """

    def __init__(
        self,
        config: GameConfig,
        emit: Optional[Callable[[str, dict], None]] = None,
        deck_seed: Optional[int] = None,
    ) -> None:
        self.config = config
        self.players: Dict[int, Player] = {}  # seat -> Player
        self.button_seat: int = -1
        self.stage: GameStage = GameStage.WAITING
        self.community_cards: List[Card] = []
        self.deck: Deck = Deck(seed=deck_seed)
        self._deck_seed = deck_seed
        self.round_state: BettingRound = BettingRound()
        self.action_queue: asyncio.Queue = asyncio.Queue()
        self._emit = emit or (lambda evt, data: None)
        self._system_message: Callable[[str], None] = lambda content: None
        self._current_actor: Optional[int] = None

    # ---------- 座位管理 ----------

    def seat_player(self, player: Player) -> None:
        if player.seat in self.players:
            raise ValueError(f"座位 {player.seat} 已有玩家")
        if len(self.players) >= self.config.max_players:
            raise ValueError("座位已满")
        self.players[player.seat] = player
        self._emit("player_join", {
            "seat": player.seat,
            "nickname": player.nickname,
            "chips": player.chips,
            "isReady": player.is_ready,
            "isOwner": player.is_owner,
        })

    def unseat_player(self, seat: int) -> None:
        if seat in self.players:
            del self.players[seat]
            self._emit("player_leave", {"seat": seat})

    def active_seats(self) -> List[int]:
        """按座位号升序返回当前未弃牌、未离座的玩家座位。"""
        return sorted(
            s for s, p in self.players.items()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
        )

    def in_hand_seats(self) -> List[int]:
        """本手牌仍可能争夺底池的玩家（未弃牌、未离座）。"""
        return sorted(
            s for s, p in self.players.items()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
        )

    def can_act_seats(self) -> List[int]:
        """仍可主动行动的玩家（排除 All-in 与已弃牌）。"""
        return sorted(
            s for s, p in self.players.items()
            if p.status == PlayerStatus.ACTIVE
        )

    # ---------- 牌局生命周期 ----------

    async def start_hand(self) -> str:
        """开始一手牌，跑完整流程。

        返回:
            "uncontested": 不战而胜（只剩一人未弃牌）
            "showdown": 需要摊牌（River 结束后多人未弃牌）
        """
        self._reset_for_new_hand()

        # 激活所有有筹码的玩家（main.py 已验证全部 ready）
        for p in self.players.values():
            if p.chips > 0:
                p.status = PlayerStatus.ACTIVE

        if len(self.in_hand_seats()) < 2:
            raise RuntimeError("人数不足无法开始牌局")

        self._move_button()
        self._post_blinds()
        self._deal_hole_cards()
        self.stage = GameStage.PREFLOP
        self._emit("state_change", {"state": self.stage.value, "dealerSeat": self.button_seat})
        self._system_message("游戏开始！")

        # Preflop：第一个行动者是大盲左手
        first_to_act = self._next_seat_after(self._big_blind_seat())
        await self._run_betting_round(first_to_act, preflop=True)

        if self._only_one_remaining():
            return "uncontested"

        # Flop
        self.community_cards.extend(self._burn_and_deal(3))
        self.stage = GameStage.FLOP
        self._emit("state_change", {"state": self.stage.value, "dealerSeat": self.button_seat})
        self._emit("community_cards", {
            "cards": [str(c) for c in self.community_cards[-3:]],
            "stage": self.stage.value,
        })
        self._reset_betting_round()
        first = self._first_to_act_postflop()
        if first is not None:
            await self._run_betting_round(first, preflop=False)

        if self._only_one_remaining():
            return "uncontested"

        # Turn
        self.community_cards.extend(self._burn_and_deal(1))
        self.stage = GameStage.TURN
        self._emit("state_change", {"state": self.stage.value, "dealerSeat": self.button_seat})
        self._emit("community_cards", {
            "cards": [str(self.community_cards[-1])],
            "stage": self.stage.value,
        })
        self._reset_betting_round()
        first = self._first_to_act_postflop()
        if first is not None:
            await self._run_betting_round(first, preflop=False)

        if self._only_one_remaining():
            return "uncontested"

        # River
        self.community_cards.extend(self._burn_and_deal(1))
        self.stage = GameStage.RIVER
        self._emit("state_change", {"state": self.stage.value, "dealerSeat": self.button_seat})
        self._emit("community_cards", {
            "cards": [str(self.community_cards[-1])],
            "stage": self.stage.value,
        })
        self._reset_betting_round()
        first = self._first_to_act_postflop()
        if first is not None:
            await self._run_betting_round(first, preflop=False)

        # River 结束后，进入展示阶段（由 main.py 处理）
        return "showdown"

    def enter_reveal_phase(self) -> List[int]:
        """进入手牌展示阶段，返回需要做出选择的玩家座位列表。

        注意：此方法只设置内部状态，不发送事件。
        事件发送由 main.py 处理。

        包含所有有手牌的玩家（包括已弃牌的），但排除：
        - SITTING_OUT（旁观）
        - WAITING（等待中）
        - 没有手牌的玩家
        """
        pending = [s for s, p in self.players.items()
                   if p.hole_cards  # 有手牌
                   and p.status not in (PlayerStatus.SITTING_OUT, PlayerStatus.WAITING)]
        self.stage = GameStage.REVEAL_WAIT
        return pending

    def apply_reveal_choice(self, seat: int, reveal: bool) -> bool:
        """应用玩家的展示选择。

        Args:
            seat: 玩家座位
            reveal: True=展示手牌, False=不展示

        Returns:
            bool: 玩家是否参与了摊牌判定（未弃牌且选择展示）

        注意：
            - 已弃牌玩家选择展示：只展示手牌，不参与结算
            - 未弃牌玩家选择不展示：视为弃牌，不参与结算
            - 未弃牌玩家选择展示：参与摊牌判定
        """
        if seat not in self.players:
            return False
        player = self.players[seat]

        was_active = player.status != PlayerStatus.FOLDED

        if not reveal:
            # 不展示，视为弃牌（仅对未弃牌玩家有影响）
            if was_active:
                player.status = PlayerStatus.FOLDED
            return False
        else:
            # 展示手牌
            # 已弃牌玩家：展示手牌但不参与结算
            # 未弃牌玩家：展示手牌并参与结算
            return was_active

    def compute_hand_result(self, reveal_choices: Dict[int, bool], uncontested: bool = False) -> HandResult:
        """展示阶段结束后计算牌局结果并发送 hand_end 事件。

        Args:
            reveal_choices: 每个玩家的展示选择（seat -> True/False）
            uncontested: 是否是不战而胜场景（由 main.py 传入）

        Returns:
            HandResult: 牌局结果
        """
        # 不战而胜场景：直接计算赢家，不进入摊牌判定
        # 但需要包含选择展示的手牌
        if uncontested:
            # 找出唯一未弃牌的玩家作为赢家
            not_folded = [s for s, p in self.players.items()
                          if p.status != PlayerStatus.FOLDED
                          and p.status not in (PlayerStatus.SITTING_OUT, PlayerStatus.WAITING)]
            winner_seat = not_folded[0] if not_folded else -1

            pots = compute_side_pots(list(self.players.values()))
            awards = distribute_pots(pots, self.players, self.community_cards, self.button_seat)

            # 收集选择展示的手牌
            revealed_hands: Dict[int, List[Card]] = {}
            for s, p in self.players.items():
                if reveal_choices.get(s, False) and p.hole_cards:
                    revealed_hands[s] = list(p.hole_cards)

            result = HandResult(
                awards=awards,
                community_cards=list(self.community_cards),
                player_holes=revealed_hands,
            )
            self.stage = GameStage.HAND_END
            # 不发送 hand_end，由 main.py 发送 showdown_result
            return result

        # 摊牌场景：检查是否只剩一人未弃牌（所有人都选择不展示）
        if self._only_one_remaining():
            result = self._end_hand_uncontested(emit_event=True)
        else:
            # 执行摊牌
            result = self._showdown()

        # 补充已弃牌但选择展示的手牌到 player_holes
        additional_revealed = {}
        for s, p in self.players.items():
            if reveal_choices.get(s, False) and p.hole_cards:
                # 只添加那些不在 result.player_holes 中的
                if s not in result.player_holes:
                    additional_revealed[s] = list(p.hole_cards)

        if additional_revealed:
            result.player_holes = {**result.player_holes, **additional_revealed}

        return result

    def finalize_showdown(self) -> HandResult:
        """所有玩家做出展示选择后，执行摊牌判定。"""
        return self._showdown()

    # ---------- 内部辅助 ----------

    def _reset_for_new_hand(self) -> None:
        for p in self.players.values():
            p.reset_for_new_hand()
        self.community_cards = []
        # 每手重新构造 deck，确保每手独立洗牌
        self.deck = Deck(seed=self._deck_seed)
        self.deck.shuffle()
        self.round_state = BettingRound()
        self._current_actor = None

    def _move_button(self) -> None:
        seats = sorted(s for s, p in self.players.items()
                       if p.status != PlayerStatus.SITTING_OUT)
        if not seats:
            return
        if self.button_seat not in seats:
            self.button_seat = seats[0]
        else:
            idx = seats.index(self.button_seat)
            self.button_seat = seats[(idx + 1) % len(seats)]

    def _post_blinds(self) -> None:
        seats = self.active_seats()
        if len(seats) == 2:
            # Heads-up：button 是小盲
            sb_seat = self.button_seat
            bb_seat = self._next_seat_after(sb_seat)
        else:
            sb_seat = self._next_seat_after(self.button_seat)
            bb_seat = self._next_seat_after(sb_seat)

        sb_player = self.players[sb_seat]
        bb_player = self.players[bb_seat]
        sb_player.post_chips(self.config.small_blind)
        bb_player.post_chips(self.config.big_blind)
        self.round_state.current_bet = self.config.big_blind
        self.round_state.last_raise_size = self.config.big_blind
        self.round_state.big_blind = self.config.big_blind
        self.round_state.aggressor_seat = bb_seat
        self._emit("blinds_posted", {
            "smallBlindSeat": sb_seat,
            "bigBlindSeat": bb_seat,
            "smallBlind": self.config.small_blind,
            "bigBlind": self.config.big_blind,
            "smallBlindTotalBet": sb_player.total_bet_this_hand,
            "bigBlindTotalBet": bb_player.total_bet_this_hand,
        })

    def _deal_hole_cards(self) -> None:
        seats = self.active_seats()
        for _ in range(2):
            for seat in seats:
                card = self.deck.deal(1)[0]
                self.players[seat].hole_cards.append(card)
        for seat in seats:
            self._emit("hole_cards", {
                "seat": seat,
                "cards": [str(c) for c in self.players[seat].hole_cards],
            })

    def _burn_and_deal(self, n: int) -> List[Card]:
        self.deck.burn(1)
        return self.deck.deal(n)

    def _next_seat_after(self, seat: int) -> int:
        """从 seat 之后找下一个还在手中（未弃牌、未离座、未 all-in）的座位。"""
        return self._next_active_seat_after(seat, only_can_act=False)

    def _next_active_seat_after(self, seat: int, only_can_act: bool = True) -> int:
        all_seats = sorted(self.players.keys())
        if not all_seats:
            return -1
        idx = all_seats.index(seat) if seat in all_seats else -1
        n = len(all_seats)
        for k in range(1, n + 1):
            cand = all_seats[(idx + k) % n]
            p = self.players[cand]
            if only_can_act:
                if p.status == PlayerStatus.ACTIVE:
                    return cand
            else:
                if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN):
                    return cand
        return -1

    def _big_blind_seat(self) -> int:
        seats = self.active_seats()
        if len(seats) == 2:
            return self._next_seat_after(self.button_seat)
        sb = self._next_seat_after(self.button_seat)
        return self._next_seat_after(sb)

    def _first_to_act_postflop(self) -> Optional[int]:
        """翻牌后第一个行动者：button 左手第一个仍可行动者。"""
        # 若可行动玩家 < 2，则跳过下注轮
        if len(self.can_act_seats()) < 2:
            return None
        return self._next_active_seat_after(self.button_seat, only_can_act=True)

    def _reset_betting_round(self) -> None:
        for p in self.players.values():
            p.reset_for_new_betting_round()
        self.round_state.reset(self.config.big_blind)

    def _only_one_remaining(self) -> bool:
        not_folded = [s for s, p in self.players.items()
                      if p.status != PlayerStatus.FOLDED
                      and p.status != PlayerStatus.SITTING_OUT
                      and p.status != PlayerStatus.WAITING]
        return len(not_folded) <= 1

    def is_only_one_remaining(self) -> bool:
        """公开方法：检查是否只剩一人未弃牌。"""
        return self._only_one_remaining()

    async def _run_betting_round(self, first_seat: int, preflop: bool) -> None:
        """运行一个下注轮，直到所有人 acted 且下注一致或仅剩一人。

        Preflop 特殊：大盲有 option（即使其他人都 call，大盲仍可 raise/check）。
        """
        if first_seat < 0:
            return

        actor = first_seat
        while True:
            if self._only_one_remaining():
                return
            if len(self.can_act_seats()) == 0:
                return  # 全部 all-in 或弃牌

            player = self.players[actor]
            if player.status != PlayerStatus.ACTIVE:
                actor = self._next_active_seat_after(actor, only_can_act=True)
                if actor < 0:
                    return
                continue

            # 检查是否结束
            if self._is_round_complete(preflop):
                return

            self._current_actor = actor
            self._emit("action_request", {
                "seat": actor,
                "toCall": self.round_state.current_bet - player.current_bet,
                "minRaise": max(self.config.big_blind, self.round_state.last_raise_size),
                "currentBet": self.round_state.current_bet,
            })

            action: Action = await self.action_queue.get()
            if action.seat != actor:
                # 非当前行动者的动作直接拒绝
                self._emit("action_rejected", {
                    "seat": action.seat,
                    "reason": "not_your_turn",
                })
                continue
            try:
                amount = validate_and_apply_action(action, player, self.round_state)
            except IllegalActionError as e:
                self._emit("action_rejected", {"seat": action.seat, "reason": str(e)})
                continue

            self._emit("player_action", {
                "seat": action.seat,
                "action": action.type.value,
                "amount": amount,
                "totalBet": player.current_bet,
                "totalBetThisHand": player.total_bet_this_hand,
                "chipsLeft": player.chips,
            })

            # 系统聊天消息
            nickname = player.nickname
            if action.type == ActionType.FOLD:
                self._system_message(f'"{nickname}" 弃牌了')
            elif action.type == ActionType.CHECK:
                self._system_message(f'"{nickname}" 过牌')
            elif action.type == ActionType.CALL:
                self._system_message(f'"{nickname}" 跟注 {player.current_bet}')
            elif action.type == ActionType.BET:
                self._system_message(f'"{nickname}" 下注 {player.current_bet}')
            elif action.type == ActionType.RAISE:
                self._system_message(f'"{nickname}" 加注到 {player.current_bet}')
            elif action.type == ActionType.ALL_IN:
                self._system_message(f'"{nickname}" 全压了！')

            # 如果是加注/下注/有效 all-in（提升了 current_bet），其他玩家需重新行动
            if action.type in (ActionType.BET, ActionType.RAISE) or (
                action.type == ActionType.ALL_IN and self.round_state.aggressor_seat == actor
            ):
                for s, p in self.players.items():
                    if s != actor and p.status == PlayerStatus.ACTIVE:
                        p.has_acted_this_round = False

            if self._is_round_complete(preflop):
                return

            actor = self._next_active_seat_after(actor, only_can_act=True)
            if actor < 0:
                return

    def _is_round_complete(self, preflop: bool) -> bool:
        """下注轮是否结束。

        条件：所有 ACTIVE 玩家都已行动过，且其 current_bet == round_state.current_bet。
        Preflop 特殊：如果大盲尚未 option（aggressor 是大盲且其他人都 call），仍需等大盲行动。
        """
        actives = [p for p in self.players.values() if p.status == PlayerStatus.ACTIVE]
        if len(actives) == 0:
            return True
        if len(actives) == 1:
            # 只剩一人能行动；若他已 call/check 完毕，则结束
            p = actives[0]
            return p.has_acted_this_round and p.current_bet == self.round_state.current_bet

        for p in actives:
            if not p.has_acted_this_round:
                return False
            if p.current_bet != self.round_state.current_bet:
                return False
        return True

    def _end_hand_uncontested(self, emit_event: bool = True) -> HandResult:
        """仅剩一名未弃牌玩家，他不战而胜。

        Args:
            emit_event: 是否发送 hand_end 事件。默认 True（保持向后兼容）。
                        不战而胜后进入展示阶段时设为 False。
        """
        self.stage = GameStage.HAND_END
        pots = compute_side_pots(list(self.players.values()))
        awards = distribute_pots(pots, self.players, self.community_cards, self.button_seat)
        result = HandResult(
            awards=awards,
            community_cards=list(self.community_cards),
            player_holes={},  # 不亮牌
        )
        if emit_event:
            self._emit("hand_end", {
                "winners": [a.winner_seats for a in awards],
                "pots": [a.pot_amount for a in awards],
                "showdown": False,
            })
        return result

    def _showdown(self) -> HandResult:
        self.stage = GameStage.SHOWDOWN
        pots = compute_side_pots(list(self.players.values()))
        awards = distribute_pots(pots, self.players, self.community_cards, self.button_seat)

        # 摊牌：仅未弃牌玩家亮牌
        revealed: Dict[int, List[Card]] = {
            s: list(p.hole_cards)
            for s, p in self.players.items()
            if p.status != PlayerStatus.FOLDED
            and p.status not in (PlayerStatus.SITTING_OUT, PlayerStatus.WAITING)
        }

        result = HandResult(
            awards=awards,
            community_cards=list(self.community_cards),
            player_holes=revealed,
        )
        self.stage = GameStage.HAND_END
        self._emit("hand_end", {
            "winners": [a.winner_seats for a in awards],
            "pots": [a.pot_amount for a in awards],
            "showdown": True,
            "revealed": {str(s): [str(c) for c in cs] for s, cs in revealed.items()},
        })
        return result

    # ---------- 外部投递动作 ----------

    async def submit_action(self, action: Action) -> None:
        await self.action_queue.put(action)
