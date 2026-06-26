"""FastAPI 入口，WebSocket 路由与房间管理。"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api.websocket import ConnectionManager, parse_client_action
from .api.auth import router as auth_router, verify_token, get_current_user
from .db.models import User
from .db.session import SessionLocal, init_db
from .game.player import Player
from .game.room import RoomManager
from .game.state_machine import GameStage
from .schemas.game import (
    CreateRoomRequest,
    CreateRoomResponse,
    RoomListItem,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dzpk")

app = FastAPI(title="德州扑克后端", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

room_manager = RoomManager()
conn_manager = ConnectionManager()


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    logger.info("服务启动完成")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/rooms", response_model=CreateRoomResponse)
async def create_room(req: CreateRoomRequest) -> CreateRoomResponse:
    if not (5 <= req.max_players <= 10):
        raise HTTPException(400, "max_players 必须在 5-10 之间")
    if req.big_blind < 2 or req.small_blind < 1 or req.small_blind >= req.big_blind:
        raise HTTPException(400, "盲注配置非法")
    room = await room_manager.create_room(
        owner_user_id=req.userId or req.nickname,
        small_blind=req.small_blind,
        big_blind=req.big_blind,
        max_players=req.max_players,
    )
    # 把发射回调挂到房间上，向当前房间所有连接广播
    room.table._emit = _make_emitter(room.room_id)
    room.table._system_message = _make_system_message_emitter(room.room_id)
    return CreateRoomResponse(room_id=room.room_id)


@app.get("/rooms", response_model=list[RoomListItem])
async def list_rooms() -> list[RoomListItem]:
    return [RoomListItem(**r) for r in room_manager.list_rooms()]


def _make_emitter(room_id: str):
    """生成事件发射器：丢到事件循环里广播。"""
    def _emit(event: str, data: dict) -> None:
        try:
            asyncio.get_event_loop().create_task(
                conn_manager.broadcast(room_id, event, data)
            )
        except RuntimeError:
            # 无 loop 时静默（如测试场景）
            pass
    return _emit


def _make_system_message_emitter(room_id: str):
    """生成系统聊天消息发射器。"""
    def _emit_system(content: str) -> None:
        try:
            asyncio.get_event_loop().create_task(
                conn_manager.broadcast_chat_system(room_id, content)
            )
        except RuntimeError:
            pass
    return _emit_system


@app.websocket("/ws/{room_id}")
async def ws_endpoint(ws: WebSocket, room_id: str) -> None:
    """WebSocket 入口。

    协议：
    - 认证（可选）: {action: 'auth', data: {token}}
    - 加入房间: {action: 'join_room', data: {nickname, userId}}
    - 准备: {action: 'ready', data: {chips?: number}}
    - 取消准备: {action: 'unready', data: {}}
    - 房主开始游戏: {action: 'start_game', data: {}}
    - 游戏动作: {action: 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in', data: {amount?}}
    """
    room = room_manager.get(room_id)
    if room is None:
        await ws.close(code=4404)
        return

    await conn_manager.connect(ws, room_id, "")
    user_id = ""
    nickname = ""
    seat: int | None = None
    authenticated_db_user_id: str | None = None  # JWT 认证后的 users.id

    async def _broadcast_waiting() -> None:
        await conn_manager.broadcast(room_id, "waiting_update", {
            "players": [{"userId": wp.user_id, "nickname": wp.nickname} for wp in room.waiting],
        })

    try:
        # 首条消息：可以是 auth（可选）或 join_room（必须）
        raw = await ws.receive_text()
        msg = json.loads(raw)

        # 处理可选的 auth 消息
        if msg.get("action") == "auth":
            adata = msg.get("data") or {}
            token = adata.get("token") or ""
            db_user_id = verify_token(token)
            if db_user_id is None:
                await ws.send_text(json.dumps({"type": "auth_failed", "data": {"reason": "invalid_token"}}))
                await ws.close(code=4401)
                return
            # 验证用户是否存在
            async with SessionLocal() as db:
                result = await db.execute(select(User).where(User.id == db_user_id))
                db_user = result.scalar_one_or_none()
            if db_user is None:
                await ws.send_text(json.dumps({"type": "auth_failed", "data": {"reason": "user_not_found"}}))
                await ws.close(code=4401)
                return
            authenticated_db_user_id = db_user_id
            conn_manager.authenticate(ws, db_user_id)
            await ws.send_text(json.dumps({"type": "auth_success", "data": {
                "userId": db_user_id,
                "username": db_user.username,
                "chips": db_user.chips,
                "isAnonymous": db_user.is_anonymous,
            }}))

            # auth 成功后等待 join_room
            raw = await ws.receive_text()
            msg = json.loads(raw)

        if msg.get("action") != "join_room":
            await ws.close(code=4400)
            return
        data = msg.get("data") or {}
        # 如果已认证，使用 DB 用户 ID；否则使用前端生成的 userId
        user_id = authenticated_db_user_id or data.get("userId") or ""
        nickname = data.get("nickname") or "游客"

        # 更新 connection 元数据
        conn_manager._meta[ws] = (room_id, user_id)

        is_owner = room.is_owner(user_id)

        if is_owner:
            # 房主自动入座座位0 + 自动准备
            seat = 0
            player = Player(
                seat=0, user_id=user_id, nickname=nickname, chips=1000,
                is_ready=True, is_owner=True,
            )
            room.table.seat_player(player)
            await ws.send_text(json.dumps({"type": "joined", "data": {"seat": seat, "isOwner": True}}))
            asyncio.create_task(conn_manager.broadcast_chat_system(room_id, f'"{nickname}" 加入了房间'))
            asyncio.create_task(conn_manager.broadcast_chat_system(room_id, f'"{nickname}" 坐上了 {seat}号位'))
        else:
            # 加入等待区
            room.add_to_waiting(user_id, nickname)
            await ws.send_text(json.dumps({"type": "joined", "data": {"seat": None, "isOwner": False}}))
            await _broadcast_waiting()
            asyncio.create_task(conn_manager.broadcast_chat_system(room_id, f'"{nickname}" 加入了房间'))

        # 向新加入玩家发送当前所有已入座玩家的信息
        for sp in room.table.players.values():
            if sp.user_id == user_id:
                continue  # 不给自己发自己的 player_join
            await ws.send_text(json.dumps({"type": "player_join", "data": {
                "seat": sp.seat,
                "nickname": sp.nickname,
                "chips": sp.chips,
                "isReady": sp.is_ready,
                "isOwner": sp.is_owner,
            }}))

        # 向新玩家发送聊天历史
        chat_history = conn_manager.get_chat_history(room_id)
        if chat_history:
            await ws.send_text(json.dumps({"type": "chat_history", "data": {"messages": chat_history}}))

        # 主循环
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            action_str = msg.get("action")
            adata = msg.get("data") or {}

            # 检测是否被牌局结束后的清理踢回等待区
            if seat is not None and seat not in room.table.players:
                seat = None

            if action_str in ("fold", "check", "call", "bet", "raise", "all_in"):
                if seat is None:
                    await ws.send_text(json.dumps({"type": "error", "data": {"reason": "未入座，无法操作"}}))
                    continue
                try:
                    action = parse_client_action(msg, seat)
                    await room.table.submit_action(action)
                except ValueError as e:
                    await ws.send_text(json.dumps({"type": "error", "data": {"reason": str(e)}}))

            elif action_str == "ready":
                # 已入座玩家准备下一局
                if seat is not None:
                    # 校验：游戏不能正在进行中
                    if room.table.stage not in (GameStage.WAITING, GameStage.HAND_END):
                        await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": "游戏进行中，请等待结束"}}))
                        continue
                    player = room.table.players.get(seat)
                    if player is None:
                        await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": "玩家不存在"}}))
                        continue
                    # 设置准备状态
                    player.is_ready = True
                    await conn_manager.broadcast(room_id, "player_ready", {
                        "seat": seat, "isReady": True, "chips": player.chips,
                    })
                    continue

                # 以下为等待区玩家准备入座逻辑
                # 校验：必须在等待区列表中
                in_waiting = any(wp.user_id == user_id for wp in room.waiting)
                if not in_waiting:
                    await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": "不在等待区"}}))
                    continue
                # 校验：游戏不能正在进行中
                if room.table.stage not in (GameStage.WAITING, GameStage.HAND_END):
                    await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": "游戏进行中，请等待结束"}}))
                    continue
                # 校验筹码
                chips = int(adata.get("chips") or 1000)
                if chips < 100 or chips > 10000:
                    await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": "筹码必须在 100-10000 之间"}}))
                    continue
                # 校验筹码不能超过账号余额
                if authenticated_db_user_id:
                    async with SessionLocal() as db:
                        result = await db.execute(select(User).where(User.id == authenticated_db_user_id))
                        db_user = result.scalar_one_or_none()
                    if db_user and chips > db_user.chips:
                        await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": f"带入筹码不能超过账号余额({db_user.chips})"}}))
                        continue
                # 找空座位（非房主跳过0号位）
                available = room.find_available_seat(is_owner=is_owner)
                if available is None:
                    await ws.send_text(json.dumps({"type": "ready_rejected", "data": {"reason": "座位已满"}}))
                    continue
                # 入座
                seat = available
                room.remove_from_waiting(user_id)
                player = Player(
                    seat=seat, user_id=user_id, nickname=nickname, chips=chips,
                    is_ready=True, is_owner=is_owner,
                )
                room.table.seat_player(player)
                # 发送座位确认给当前玩家（设置 mySeat）
                await ws.send_text(json.dumps({"type": "joined", "data": {"seat": seat, "isOwner": is_owner}}))
                await conn_manager.broadcast(room_id, "player_ready", {
                    "seat": seat, "isReady": True, "chips": chips,
                })
                await _broadcast_waiting()
                asyncio.create_task(conn_manager.broadcast_chat_system(room_id, f'"{nickname}" 坐上了 {seat}号位'))

            elif action_str == "unready":
                # 校验：必须已入座且 is_ready=True
                if seat is None:
                    await ws.send_text(json.dumps({"type": "error", "data": {"reason": "未入座"}}))
                    continue
                # 校验：游戏不能正在进行中
                if room.table.stage not in (GameStage.WAITING, GameStage.HAND_END):
                    await ws.send_text(json.dumps({"type": "error", "data": {"reason": "游戏进行中，无法取消准备"}}))
                    continue
                player = room.table.players.get(seat)
                if player is None or not player.is_ready:
                    await ws.send_text(json.dumps({"type": "error", "data": {"reason": "未准备状态"}}))
                    continue
                # 踢回等待区
                del room.table.players[seat]
                room.table._emit("player_leave", {"seat": seat})
                room.add_to_waiting(user_id, nickname)
                old_seat = seat
                seat = None
                await _broadcast_waiting()
                asyncio.create_task(conn_manager.broadcast_chat_system(room_id, f'"{nickname}" 离开了 {old_seat}号位'))

            elif action_str == "start_game":
                # 校验：必须是房主
                if not is_owner:
                    await ws.send_text(json.dumps({"type": "start_game_rejected", "data": {"reason": "只有房主可以开始游戏"}}))
                    continue
                # 校验：游戏不能正在进行中
                if room.table.stage not in (GameStage.WAITING, GameStage.HAND_END):
                    await ws.send_text(json.dumps({"type": "start_game_rejected", "data": {"reason": "游戏已在进行中"}}))
                    continue
                # 校验：入座人数 >= 2
                if len(room.table.players) < 2:
                    await ws.send_text(json.dumps({"type": "start_game_rejected", "data": {"reason": "至少需要 2 名玩家入座"}}))
                    continue
                # 校验：所有入座玩家 is_ready == True
                not_ready = [s for s, p in room.table.players.items() if not p.is_ready]
                if not_ready:
                    await ws.send_text(json.dumps({"type": "start_game_rejected", "data": {"reason": "还有玩家未准备"}}))
                    continue

                # 开始游戏（后台任务，不阻塞 WS 消息循环）
                async def _run_game():
                    async with room.lock:
                        # 开始前踢出筹码不足者
                        to_kick_before = []
                        for s, p in list(room.table.players.items()):
                            if p.chips < 100:
                                to_kick_before.append(s)
                        for s in to_kick_before:
                            p = room.table.players.pop(s)
                            room.table._emit("player_leave", {"seat": s})
                            room.add_to_waiting(p.user_id, p.nickname)
                        if to_kick_before:
                            await _broadcast_waiting()

                        # 重新检查人数
                        if len(room.table.players) < 2:
                            return

                        # 重置展示阶段状态
                        room.reveal_pending.clear()
                        room.reveal_choices.clear()

                        # 重置 stage 为 WAITING（允许从 hand_end 开始新游戏）
                        room.table.stage = GameStage.WAITING

                        # 记录各玩家初始筹码（用于牌局结束后计算 profit）
                        room.hand_initial_chips = {
                            s: p.chips for s, p in room.table.players.items()
                        }

                        try:
                            result_type = await room.table.start_hand()
                        except RuntimeError as e:
                            logger.error("游戏异常: %s", e)
                            return

                        # 处理牌局结束：无论是不战而胜还是摊牌，都进入展示阶段
                        pending = room.table.enter_reveal_phase()
                        room.reveal_pending = set(pending)
                        room.reveal_choices = {}
                        room.uncontested = (result_type == "uncontested")  # 标记是否不战而胜

                        await conn_manager.broadcast(room_id, "reveal_phase_start", {
                            "pendingPlayers": pending,
                            "uncontested": result_type == "uncontested",  # 告知前端是否不战而胜
                        })

                asyncio.create_task(_run_game())

            elif action_str == "leave":
                # 显式离开：清理玩家状态并退出主循环
                if seat is not None and seat in room.table.players:
                    room.table.unseat_player(seat)
                    seat = None
                room.remove_from_waiting(user_id)
                await _broadcast_waiting()
                asyncio.create_task(conn_manager.broadcast_chat_system(room_id, f'"{nickname}" 离开了房间'))
                break

            elif action_str == "reveal_choice":
                # 展示阶段：玩家选择是否展示手牌
                choice = adata.get("choice", False)

                if seat is None or seat not in room.reveal_pending:
                    await ws.send_text(json.dumps({"type": "error", "data": {"reason": "无需做出选择"}}))
                    continue

                player = room.table.players[seat]
                room.reveal_choices[seat] = choice
                room.reveal_pending.discard(seat)

                # 应用选择（不展示 = 弃牌，但已弃牌玩家不受影响）
                room.table.apply_reveal_choice(seat, choice)

                # 广播玩家的选择
                await conn_manager.broadcast(room_id, "player_revealed", {
                    "seat": seat,
                    "revealed": choice,
                    "cards": [str(c) for c in player.hole_cards] if choice else None,
                    "nickname": player.nickname,
                })

                # 检查是否所有人都做出了选择
                if not room.reveal_pending:
                    # 计算结果（包含已弃牌但选择展示的手牌）
                    result = room.table.compute_hand_result(room.reveal_choices, room.uncontested)

                    # 广播最终结果
                    await conn_manager.broadcast(room_id, "showdown_result", {
                        "winners": [a.winner_seats for a in result.awards],
                        "pots": [a.pot_amount for a in result.awards],
                        "showdown": not room.uncontested,
                        "revealedHands": {str(s): [str(c) for c in cs] for s, cs in result.player_holes.items()},
                    })

                    # 系统消息：牌局结束
                    asyncio.create_task(conn_manager.broadcast_chat_system(room_id, "牌局结束"))

                    # 重置玩家 ready 状态，等待下一局
                    for s, p in room.table.players.items():
                        room.table._emit("player_ready", {"seat": s, "isReady": False, "chips": p.chips})

                    # 持久化：更新数据库中的用户筹码和战绩
                    winner_seats: set[int] = set()
                    for award in result.awards:
                        winner_seats.update(award.winner_seats)
                    async with SessionLocal() as db:
                        for s, p in room.table.players.items():
                            if not p.user_id:
                                continue
                            db_user = await db.get(User, p.user_id)
                            if db_user is None:
                                continue
                            initial = room.hand_initial_chips.get(s, p.chips)
                            db_user.chips += (p.chips - initial)
                            db_user.total_hands += 1
                            if s in winner_seats:
                                db_user.total_wins += 1
                            db_user.total_profit += (p.chips - initial)
                        await db.commit()

            elif action_str == "ack":
                pass  # 占位

            elif action_str == "chat":
                chat_type = adata.get("type", "text")
                # seat: -1 表示等待区，None 也表示等待区
                chat_seat = seat if seat is not None else -1
                if chat_type == "text":
                    content = str(adata.get("content", ""))
                    await conn_manager.broadcast_chat_message(
                        room_id, seat=chat_seat, user_id=user_id,
                        nickname=nickname, msg_type="text", content=content,
                    )
                elif chat_type == "quick":
                    phrase_id = str(adata.get("phrase_id", 0))
                    await conn_manager.broadcast_chat_message(
                        room_id, seat=chat_seat, user_id=user_id,
                        nickname=nickname, msg_type="quick", content=phrase_id,
                    )

            else:
                await ws.send_text(json.dumps({"type": "error", "data": {"reason": "未知动作"}}))

    except WebSocketDisconnect:
        logger.info("WS 断开: room=%s user=%s seat=%s", room_id, user_id, seat)
    except Exception as e:
        logger.exception("WS 处理异常: %s", e)
    finally:
        # 清理：从等待区移除
        room.remove_from_waiting(user_id)
        # 清理：离座
        if seat is not None and seat in room.table.players:
            room.table.unseat_player(seat)
        conn_manager.disconnect(ws)
        # 广播等待区更新
        try:
            await _broadcast_waiting()
        except Exception:
            pass
