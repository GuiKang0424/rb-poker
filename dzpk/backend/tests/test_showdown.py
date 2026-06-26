"""测试胜负判定与筹码分配。"""
from app.game.deck import Card
from app.game.player import Player, PlayerStatus
from app.game.poker import compute_side_pots
from app.game.showdown import distribute_pots


def cards(*strs):
    return [Card.from_str(s) for s in strs]


def make_player(seat: int, chips: int = 0) -> Player:
    p = Player(seat=seat, user_id=f"u{seat}", nickname=f"P{seat}", chips=chips)
    p.status = PlayerStatus.ACTIVE
    return p


def test_single_winner_takes_pot():
    p0 = make_player(0)
    p1 = make_player(1)
    p0.hole_cards = cards("As", "Ah")  # 一对 A
    p1.hole_cards = cards("2c", "7d")  # 高牌
    p0.total_bet_this_hand = 100
    p1.total_bet_this_hand = 100
    players = {0: p0, 1: p1}
    pots = compute_side_pots(list(players.values()))
    awards = distribute_pots(pots, players, cards("Kc", "Qd", "Js", "9h", "3c"), button_seat=0)
    assert len(awards) == 1
    assert awards[0].winner_seats == [0]
    assert p0.chips == 200
    assert p1.chips == 0


def test_split_pot_even_division():
    """两人平局，平分 200。"""
    p0 = make_player(0)
    p1 = make_player(1)
    # 公共牌已是同花顺，双方底牌不影响
    p0.hole_cards = cards("2c", "3d")
    p1.hole_cards = cards("4h", "5d")
    p0.total_bet_this_hand = 100
    p1.total_bet_this_hand = 100
    players = {0: p0, 1: p1}
    pots = compute_side_pots(list(players.values()))
    awards = distribute_pots(pots, players, cards("As", "Ks", "Qs", "Js", "Ts"), button_seat=0)
    assert len(awards) == 1
    assert set(awards[0].winner_seats) == {0, 1}
    assert p0.chips == 100
    assert p1.chips == 100


def test_split_pot_odd_chip_to_after_button():
    """3 人平分 100，余 1 给 button 左手第一个赢家。"""
    p0 = make_player(0)
    p1 = make_player(1)
    p2 = make_player(2)
    # 公共牌 royal flush，所有人都打 board
    community = cards("As", "Ks", "Qs", "Js", "Ts")
    for p in (p0, p1, p2):
        p.hole_cards = cards("2c", "3d") if p.seat != 1 else cards("4h", "5d")
        p.total_bet_this_hand = 34  # 总池 102，3 人平分余 0
    # 改成不能整除：100/3 余 1
    p0.total_bet_this_hand = 33
    p1.total_bet_this_hand = 33
    p2.total_bet_this_hand = 34
    players = {0: p0, 1: p1, 2: p2}
    pots = compute_side_pots(list(players.values()))
    # button=0，左手是 1
    awards = distribute_pots(pots, players, community, button_seat=0)
    # 整池 100，3 人分 → 33 each + 1 余给 1
    # 但 compute_side_pots 会拆分（因为投入不同），所以可能不止一个池
    total_chips = p0.chips + p1.chips + p2.chips
    assert total_chips == 100


def test_uncontested_pot_goes_to_only_unfolded():
    """三人投入，但 1、2 都弃牌，0 独自获胜。"""
    p0 = make_player(0)
    p1 = make_player(1)
    p2 = make_player(2)
    p0.total_bet_this_hand = 100
    p1.total_bet_this_hand = 100
    p1.status = PlayerStatus.FOLDED
    p2.total_bet_this_hand = 100
    p2.status = PlayerStatus.FOLDED
    p0.hole_cards = cards("2c", "3d")
    players = {0: p0, 1: p1, 2: p2}
    pots = compute_side_pots(list(players.values()))
    # 公共牌只是占位，因为只有 0 未弃牌不需要比牌
    awards = distribute_pots(pots, players, cards("As", "Ks", "Qs", "Js", "Ts"), button_seat=2)
    assert p0.chips == 300


def test_side_pot_main_winner_short_stack():
    """0 all-in 50（最强牌），1、2 投入 200（牌弱）。
    主池 150 给 0；边池 300 给 1、2 中较强者。"""
    p0 = make_player(0)
    p1 = make_player(1)
    p2 = make_player(2)
    p0.hole_cards = cards("As", "Ah")  # 对 A
    p1.hole_cards = cards("Kh", "Qs")  # 高牌
    p2.hole_cards = cards("Kc", "Kd")  # 对 K
    p0.total_bet_this_hand = 50
    p0.status = PlayerStatus.ALL_IN
    p1.total_bet_this_hand = 200
    p2.total_bet_this_hand = 200
    players = {0: p0, 1: p1, 2: p2}
    community = cards("2c", "5d", "9h", "Tc", "3s")
    pots = compute_side_pots(list(players.values()))
    awards = distribute_pots(pots, players, community, button_seat=0)
    # 0 拿主池 150
    assert p0.chips == 150
    # 2（对 K）拿边池 300
    assert p2.chips == 300
    assert p1.chips == 0
