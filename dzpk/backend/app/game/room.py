"""房间管理：单进程多房间。"""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .player import Player
from .state_machine import GameConfig, TableState


@dataclass
class WaitingPlayer:
    """等待区玩家。"""
    user_id: str
    nickname: str


@dataclass
class Room:
    """一个房间 = 一张桌子 + 配置 + 房主信息。"""
    room_id: str
    owner_user_id: str
    config: GameConfig
    table: TableState
    # 锁，避免并发开局
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # 等待区玩家（未入座）
    waiting: List[WaitingPlayer] = field(default_factory=list)
    # 展示阶段状态
    reveal_pending: Set[int] = field(default_factory=set)  # 等待做出选择的玩家座位
    reveal_choices: Dict[int, bool] = field(default_factory=dict)  # seat -> 是否展示
    # 不战而胜标记
    uncontested: bool = False
    # 一手牌开始前各玩家筹码（用于计算 profit）
    hand_initial_chips: Dict[int, int] = field(default_factory=dict)

    def add_to_waiting(self, user_id: str, nickname: str) -> None:
        """将玩家加入等待区。"""
        self.waiting.append(WaitingPlayer(user_id=user_id, nickname=nickname))

    def remove_from_waiting(self, user_id: str) -> bool:
        """从等待区移除玩家，返回是否找到并移除。"""
        for i, wp in enumerate(self.waiting):
            if wp.user_id == user_id:
                self.waiting.pop(i)
                return True
        return False

    def find_available_seat(self, is_owner: bool = False) -> int | None:
        """找到可用座位号，无可用座位返回 None。

        非房主跳过 0 号位，确保房主专座。
        """
        occupied = set(self.table.players.keys())
        for s in range(self.config.max_players):
            if s == 0 and not is_owner:
                continue
            if s not in occupied:
                return s
        return None

    def is_owner(self, user_id: str) -> bool:
        return self.owner_user_id == user_id


class RoomManager:
    """单进程内的房间注册表。"""

    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def create_room(
        self,
        owner_user_id: str,
        small_blind: int = 5,
        big_blind: int = 10,
        max_players: int = 9,
    ) -> Room:
        async with self._lock:
            room_id = self._generate_room_id()
            while room_id in self._rooms:
                room_id = self._generate_room_id()
            config = GameConfig(
                small_blind=small_blind,
                big_blind=big_blind,
                max_players=max_players,
            )
            table = TableState(config=config)
            room = Room(
                room_id=room_id,
                owner_user_id=owner_user_id,
                config=config,
                table=table,
            )
            self._rooms[room_id] = room
            return room

    def get(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id)

    def remove(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)

    def list_rooms(self) -> list:
        return [
            {
                "roomId": r.room_id,
                "playerCount": len(r.table.players) + len(r.waiting),
                "maxPlayers": r.config.max_players,
                "smallBlind": r.config.small_blind,
                "bigBlind": r.config.big_blind,
            }
            for r in self._rooms.values()
        ]

    @staticmethod
    def _generate_room_id() -> str:
        # 6 位数字房间号
        return "".join(str(secrets.randbelow(10)) for _ in range(6))
