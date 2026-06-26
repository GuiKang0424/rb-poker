"""测试下注、动作合法性与边池计算。"""
import pytest

from app.game.player import Player, PlayerStatus
from app.game.poker import (
    Action,
    ActionType,
    BettingRound,
    IllegalActionError,
    compute_side_pots,
    validate_and_apply_action,
)


def make_player(seat: int, chips: int = 1000) -> Player:
    p = Player(seat=seat, user_id=f"u{seat}", nickname=f"P{seat}", chips=chips)
    p.status = PlayerStatus.ACTIVE
    return p


def test_check_when_no_bet():
    p = make_player(0)
    rs = BettingRound(big_blind=10)
    rs.reset(big_blind=10)
    validate_and_apply_action(Action(ActionType.CHECK, seat=0), p, rs)
    assert p.has_acted_this_round


def test_check_when_bet_raises_error():
    p = make_player(0)
    rs = BettingRound()
    rs.reset(big_blind=10)
    rs.current_bet = 50  # 别人下注 50
    with pytest.raises(IllegalActionError):
        validate_and_apply_action(Action(ActionType.CHECK, seat=0), p, rs)


def test_call_deducts_to_call_amount():
    p = make_player(0, chips=1000)
    rs = BettingRound()
    rs.reset(big_blind=10)
    rs.current_bet = 50
    p.current_bet = 10  # 已投 10，需补 40
    validate_and_apply_action(Action(ActionType.CALL, seat=0), p, rs)
    assert p.chips == 960
    assert p.current_bet == 50


def test_bet_below_big_blind_rejected():
    p = make_player(0)
    rs = BettingRound()
    rs.reset(big_blind=10)
    with pytest.raises(IllegalActionError):
        validate_and_apply_action(Action(ActionType.BET, seat=0, amount=5), p, rs)


def test_raise_below_min_raise_rejected():
    p = make_player(0)
    rs = BettingRound()
    rs.reset(big_blind=10)
    rs.current_bet = 50
    rs.last_raise_size = 40
    # 加注后必须达到 50+40=90，传 80 应被拒
    with pytest.raises(IllegalActionError):
        validate_and_apply_action(Action(ActionType.RAISE, seat=0, amount=80), p, rs)


def test_raise_updates_state():
    p = make_player(0, chips=1000)
    rs = BettingRound()
    rs.reset(big_blind=10)
    rs.current_bet = 50
    rs.last_raise_size = 40
    validate_and_apply_action(Action(ActionType.RAISE, seat=0, amount=120), p, rs)
    assert rs.current_bet == 120
    assert rs.last_raise_size == 70  # 120 - 50
    assert rs.aggressor_seat == 0


def test_all_in_below_min_does_not_reopen_round():
    p = make_player(0, chips=30)  # 仅有 30
    rs = BettingRound()
    rs.reset(big_blind=10)
    rs.current_bet = 50
    rs.last_raise_size = 40
    rs.aggressor_seat = 99
    validate_and_apply_action(Action(ActionType.ALL_IN, seat=0), p, rs)
    # All-in 30，但因为之前 current_bet=50，p.current_bet=30 < 50，不会更新 current_bet
    assert rs.current_bet == 50
    assert rs.aggressor_seat == 99
    assert p.status == PlayerStatus.ALL_IN


def test_fold_marks_status():
    p = make_player(0)
    rs = BettingRound()
    rs.reset(big_blind=10)
    validate_and_apply_action(Action(ActionType.FOLD, seat=0), p, rs)
    assert p.status == PlayerStatus.FOLDED


# ---------- Side Pot 测试 ----------

def test_side_pot_simple_no_all_in():
    """3 人都投入相同 100，单池 300。"""
    players = [make_player(i) for i in range(3)]
    for p in players:
        p.total_bet_this_hand = 100
    pots = compute_side_pots(players)
    assert len(pots) == 1
    assert pots[0].amount == 300
    assert set(pots[0].eligible_seats) == {0, 1, 2}


def test_side_pot_one_all_in_short():
    """玩家 0 all-in 50，玩家 1、2 投入 200。
    主池：50*3=150，由 0/1/2 争夺；边池：(200-50)*2=300，由 1/2 争夺。"""
    players = [make_player(i) for i in range(3)]
    players[0].total_bet_this_hand = 50
    players[0].status = PlayerStatus.ALL_IN
    players[1].total_bet_this_hand = 200
    players[2].total_bet_this_hand = 200
    pots = compute_side_pots(players)
    assert len(pots) == 2
    main, side = pots[0], pots[1]
    assert main.amount == 150
    assert set(main.eligible_seats) == {0, 1, 2}
    assert side.amount == 300
    assert set(side.eligible_seats) == {1, 2}


def test_side_pot_folded_player_money_in_pot_but_not_eligible():
    """玩家 0 投 100 后弃牌，1、2 投 200。
    总池：100 + 200 + 200 = 500。
    分层：100 这一层 (100*3=300) 由"未弃牌且 ≥100"的 1、2 争夺；200 这层 (100*2=200) 由 1、2 争夺。
    合并后只有一个池 500，由 1、2 争夺（因为 eligible 列表相同）。"""
    players = [make_player(i) for i in range(3)]
    players[0].total_bet_this_hand = 100
    players[0].status = PlayerStatus.FOLDED
    players[1].total_bet_this_hand = 200
    players[2].total_bet_this_hand = 200
    pots = compute_side_pots(players)
    total = sum(p.amount for p in pots)
    assert total == 500
    # 弃牌玩家不在任何 eligible 中
    for pot in pots:
        assert 0 not in pot.eligible_seats


def test_side_pot_two_all_ins():
    """0 all-in 50，1 all-in 150，2 投 300。
    层 1: 50*3=150 由 0/1/2 争夺
    层 2: (150-50)*2=200 由 1/2 争夺
    层 3: (300-150)*1=150 由 2 独占（实际只剩他下注）"""
    players = [make_player(i) for i in range(3)]
    players[0].total_bet_this_hand = 50
    players[0].status = PlayerStatus.ALL_IN
    players[1].total_bet_this_hand = 150
    players[1].status = PlayerStatus.ALL_IN
    players[2].total_bet_this_hand = 300
    pots = compute_side_pots(players)
    total = sum(p.amount for p in pots)
    assert total == 500
    # 第一池应由所有人争夺
    assert set(pots[0].eligible_seats) == {0, 1, 2}
    assert pots[0].amount == 150
    # 最后一池只有 2
    assert pots[-1].eligible_seats == [2]
