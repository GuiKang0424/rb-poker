"""测试牌库与洗牌。"""
from app.game.deck import Card, Deck, build_deck


def test_build_deck_has_52_unique_cards():
    deck = build_deck()
    assert len(deck) == 52
    assert len(set((c.rank, c.suit) for c in deck)) == 52


def test_card_str_roundtrip():
    c = Card.from_str("As")
    assert str(c) == "As"
    assert c.rank == "A"
    assert c.suit == "s"


def test_deck_shuffle_changes_order():
    d1 = Deck(seed=42)
    d2 = Deck(seed=42)
    d1.shuffle()
    d2.shuffle()
    cards1 = d1.deal(52)
    cards2 = d2.deal(52)
    # 同种子应得相同结果
    assert cards1 == cards2


def test_deck_shuffle_different_seeds_diverge():
    d1 = Deck(seed=1)
    d2 = Deck(seed=2)
    d1.shuffle()
    d2.shuffle()
    assert d1.deal(52) != d2.deal(52)


def test_deck_deal_advances_cursor():
    d = Deck(seed=0)
    d.shuffle()
    assert d.remaining == 52
    d.deal(2)
    assert d.remaining == 50
    d.burn(1)
    assert d.remaining == 49


def test_deck_dealt_cards_unique():
    d = Deck(seed=123)
    d.shuffle()
    cards = d.deal(52)
    assert len(set(cards)) == 52
