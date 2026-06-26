"""游戏事件 Pydantic Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class CreateRoomRequest(BaseModel):
    nickname: str
    userId: str = ""
    small_blind: int = 5
    big_blind: int = 10
    max_players: int = 9


class CreateRoomResponse(BaseModel):
    room_id: str


class RoomListItem(BaseModel):
    roomId: str
    playerCount: int
    maxPlayers: int
    smallBlind: int
    bigBlind: int


class JoinRoomPayload(BaseModel):
    roomId: str
    nickname: str
    userId: str
    seat: Optional[int] = None  # 不指定则自动分配
    chips: int = 1000
