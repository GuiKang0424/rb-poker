"""测试游戏状态机端到端跑一手。"""
import asyncio
import pytest

from app.game.player import Player, PlayerStatus
from app.game.poker import Action, ActionType
from app.game.state_machine import GameConfig, GameStage, TableState


def make_player(seat: int, chips: int = 1000) -> Player:
    return Player(
        seat=seat, user_id=f"u{seat}", nickname=f"P{seat}", chips=chips,
    )


@pytest.mark.asyncio
async def test_two_player_hand_all_fold_preflop():
    """heads-up：小盲（button）开牌后弃牌，大盲不战而胜。"""
    cfg = GameConfig(small_blind=5, big_blind=10)
    table = TableState(config=cfg, deck_seed=42)
    table.seat_player(make_player(0))
    table.seat_player(make_player(1))
    for p in table.players.values():
        p.status = PlayerStatus.ACTIVE

    async def driver():
        # 等状态机进入 preflop 后，sb 弃牌
        # heads-up 时 button=sb=seat 0，第一个行动者是 sb（button）= 0
        # 但代码里 _next_seat_after(big_blind) 在 heads-up 中... 让我们看看：
        # heads-up 中 big_blind_seat = next_seat_after(button) = 1
        # first_to_act preflop = next_seat_after(bb=1) = 0（即 sb/button）
        await table.submit_action(Action(ActionType.FOLD, seat=0))

    task = asyncio.create_task(driver())
    result_type = await asyncio.wait_for(table.start_hand(), timeout=2.0)
    await task

    # 不战而胜，返回 "uncontested"
    assert result_type == "uncontested"
    # 进入展示阶段后，调用 compute_hand_result 完成筹码分配
    # 座位0弃牌，座位1赢家可选择展示或不展示
    result = table.compute_hand_result({0: False, 1: True})  # 赢家选择展示

    # bb 不战而胜：拿走小盲 5
    bb_seat = 1 if table.button_seat == 0 else 0
    assert table.players[bb_seat].chips == 1000 + cfg.small_blind
    sb_seat = table.button_seat
    assert table.players[sb_seat].chips == 1000 - cfg.small_blind


@pytest.mark.asyncio
async def test_two_player_hand_to_showdown():
    """两人 call 到河牌摊牌，应正常跑完。"""
    cfg = GameConfig(small_blind=5, big_blind=10)
    table = TableState(config=cfg, deck_seed=7)
    table.seat_player(make_player(0))
    table.seat_player(make_player(1))
    for p in table.players.values():
        p.status = PlayerStatus.ACTIVE

    actions = []

    def emit(evt, data):
        actions.append((evt, data))

    table._emit = emit

    async def driver():
        # heads-up: button=0=sb, bb=1
        # preflop: sb 先行动；call 5 补到 10
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CALL, seat=0))
        # bb option：check 结束 preflop
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=1))
        # flop：postflop 第一个行动者是 button 左手 = seat 1（即 bb）
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=1))
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=0))
        # turn
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=1))
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=0))
        # river
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=1))
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=0))

    task = asyncio.create_task(driver())
    result_type = await asyncio.wait_for(table.start_hand(), timeout=5.0)
    await task

    # River 结束后，start_hand 返回 "showdown"（进入展示阶段）
    assert result_type == "showdown"
    # 测试中调用 compute_hand_result 模拟展示阶段结束后计算结果
    result = table.compute_hand_result({0: True, 1: True})  # 两人都选择展示

    assert len(result.community_cards) == 5
    # 总筹码守恒
    total_chips = sum(p.chips for p in table.players.values())
    assert total_chips == 2000
    # 至少有一个 hand_end 事件
    end_events = [a for a in actions if a[0] == "hand_end"]
    assert len(end_events) == 1
    assert end_events[0][1]["showdown"] is True


@pytest.mark.asyncio
async def test_three_player_hand_one_folds_two_showdown():
    """3 人，UTG 弃牌，两人摊牌。"""
    cfg = GameConfig(small_blind=5, big_blind=10)
    table = TableState(config=cfg, deck_seed=11)
    for s in range(3):
        table.seat_player(make_player(s))
    for p in table.players.values():
        p.status = PlayerStatus.ACTIVE

    async def driver():
        # 3 人桌：button=0, sb=1, bb=2
        # preflop 第一个行动 = next_after(bb=2) = 0（UTG）
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.FOLD, seat=0))
        # 接下来 sb=1
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CALL, seat=1))
        # bb option
        await asyncio.sleep(0.05)
        await table.submit_action(Action(ActionType.CHECK, seat=2))
        # flop：button 左手 = 1
        for _ in range(3):  # flop, turn, river all check
            await asyncio.sleep(0.05)
            await table.submit_action(Action(ActionType.CHECK, seat=1))
            await asyncio.sleep(0.05)
            await table.submit_action(Action(ActionType.CHECK, seat=2))

    task = asyncio.create_task(driver())
    result_type = await asyncio.wait_for(table.start_hand(), timeout=5.0)
    await task

    # River 结束后，start_hand 返回 "showdown"（进入展示阶段）
    assert result_type == "showdown"
    # 测试中调用 compute_hand_result 模拟展示阶段结束后计算结果
    # 座位0已弃牌，座位1和2选择展示
    result = table.compute_hand_result({0: True, 1: True, 2: True})  # 都选择展示

    # 总筹码守恒
    total = sum(p.chips for p in table.players.values())
    assert total == 3000
    assert table.players[0].chips == 1000  # 弃牌没投入
    assert len(result.community_cards) == 5
