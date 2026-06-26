"""扑克牌库与 Fisher-Yates 洗牌算法。"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import List


SUITS = ("s", "h", "d", "c")  # 黑桃、红心、方块、梅花
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")


@dataclass(frozen=True)
class Card:
    """一张扑克牌，rank + suit。"""
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"非法 rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"非法 suit: {self.suit}")

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    @classmethod
    def from_str(cls, s: str) -> "Card":
        if len(s) != 2:
            raise ValueError(f"Card 字符串必须为 2 字符: {s}")
        return cls(rank=s[0], suit=s[1])


def build_deck() -> List[Card]:
    """生成标准 52 张牌。"""
    return [Card(rank=r, suit=s) for s in SUITS for r in RANKS]


class Deck:
    """牌库，使用 Fisher-Yates 算法洗牌。

    使用 secrets.SystemRandom 作为加密安全的随机源，避免可预测洗牌。
    """

    def __init__(self, seed: int | None = None) -> None:
        # seed 仅用于测试：传入则使用 random.Random，可复现；否则使用 SystemRandom。
        if seed is None:
            import random
            self._rng = secrets.SystemRandom()
        else:
            import random
            self._rng = random.Random(seed)
        self._cards: List[Card] = build_deck()
        self._cursor: int = 0

    def shuffle(self) -> None:
        """Fisher-Yates 洗牌：从尾到头，每次随机选 [0..i] 之一交换。"""
        cards = self._cards
        n = len(cards)
        for i in range(n - 1, 0, -1):
            j = self._rng.randint(0, i)
            cards[i], cards[j] = cards[j], cards[i]
        self._cursor = 0

    def reset(self) -> None:
        """重置牌库到 52 张未洗状态。"""
        self._cards = build_deck()
        self._cursor = 0

    def deal(self, n: int = 1) -> List[Card]:
        """发出 n 张牌；不足则抛错。"""
        if self._cursor + n > len(self._cards):
            raise RuntimeError("牌库剩余不足")
        out = self._cards[self._cursor : self._cursor + n]
        self._cursor += n
        return out

    def burn(self, n: int = 1) -> None:
        """烧牌（按真实规则发翻/转/河前各烧一张）。"""
        self.deal(n)

    @property
    def remaining(self) -> int:
        return len(self._cards) - self._cursor
