"""WebSocket 连接管理。"""
from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..game.poker import Action, ActionType
from ..game.player import Player
from ..game.room import RoomManager

# 聊天历史最大条数
MAX_CHAT_HISTORY = 100


class ChatHistory:
    """房间聊天记录，固定大小内存缓存。"""

    def __init__(self, max_size: int = MAX_CHAT_HISTORY) -> None:
        self._messages: deque[dict] = deque(maxlen=max_size)

    def append(self, message: dict) -> None:
        self._messages.append(message)

    def get_all(self) -> list[dict]:
        return list(self._messages)


class ConnectionManager:
    """房间内 WebSocket 连接管理：广播事件、路由动作。"""

    def __init__(self) -> None:
        # room_id -> set of WebSocket
        self._connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> (room_id, user_id)
        self._meta: Dict[WebSocket, tuple] = {}
        # WebSocket -> auth_user_id (JWT 认证后的 users.id)
        self._auth: Dict[WebSocket, str] = {}
        # room_id -> ChatHistory
        self._chat_histories: Dict[str, ChatHistory] = {}

    def get_or_create_chat_history(self, room_id: str) -> ChatHistory:
        if room_id not in self._chat_histories:
            self._chat_histories[room_id] = ChatHistory()
        return self._chat_histories[room_id]

    def get_chat_history(self, room_id: str) -> list[dict]:
        ch = self._chat_histories.get(room_id)
        return ch.get_all() if ch else []

    async def broadcast_chat_message(
        self, room_id: str, seat: int, user_id: str,
        nickname: str, msg_type: str, content: str,
    ) -> None:
        """广播一条聊天消息到房间，同时存入历史。"""
        data = {
            "seat": seat,
            "userId": user_id,
            "nickname": nickname,
            "type": msg_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self.get_or_create_chat_history(room_id).append(data)
        await self.broadcast(room_id, "chat_message", data)

    async def broadcast_chat_system(self, room_id: str, content: str) -> None:
        """广播一条系统聊天消息。"""
        await self.broadcast_chat_message(
            room_id, seat=-1, user_id="", nickname="",
            msg_type="system", content=content,
        )

    async def connect(self, ws: WebSocket, room_id: str, user_id: str) -> None:
        await ws.accept()
        self._connections.setdefault(room_id, set()).add(ws)
        self._meta[ws] = (room_id, user_id)

    def disconnect(self, ws: WebSocket) -> None:
        meta = self._meta.pop(ws, None)
        self._auth.pop(ws, None)
        if meta:
            room_id, _ = meta
            conns = self._connections.get(room_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    del self._connections[room_id]

    def authenticate(self, ws: WebSocket, db_user_id: str) -> None:
        """将 WebSocket 连接与数据库用户绑定。"""
        self._auth[ws] = db_user_id

    def get_auth_user_id(self, ws: WebSocket) -> Optional[str]:
        """获取连接绑定的数据库用户 ID，未认证返回 None。"""
        return self._auth.get(ws)

    async def broadcast(self, room_id: str, event: str, data: dict) -> None:
        conns = list(self._connections.get(room_id, ()))
        if not conns:
            return
        msg = json.dumps({"type": event, "data": data})
        await asyncio.gather(*(ws.send_text(msg) for ws in conns), return_exceptions=True)


def parse_client_action(payload: dict, seat: int) -> Action:
    """将客户端 JSON 动作解析为 Action 对象。"""
    action_str = payload.get("action")
    data = payload.get("data") or {}
    type_map = {
        "fold": ActionType.FOLD,
        "check": ActionType.CHECK,
        "call": ActionType.CALL,
        "bet": ActionType.BET,
        "raise": ActionType.RAISE,
        "all_in": ActionType.ALL_IN,
    }
    if action_str not in type_map:
        raise ValueError(f"未知动作: {action_str}")
    return Action(
        type=type_map[action_str],
        seat=seat,
        amount=int(data.get("amount", 0)),
    )
