"""
Punto Card Deck - 4 colors, values 1-9
"""

from dataclasses import dataclass
from enum import Enum
from typing import List
import random


class Color(Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"


@dataclass
class Card:
    color: Color
    value: int  # 1-9 (dots)
    
    def __str__(self) -> str:
        return f"{self.color.value[0].upper()}{self.value}"
    
    def beats(self, other: "Card") -> bool:
        """Returns True if this card can stack on top of other."""
        return self.value > other.value


class Deck:
    """Standard Punto deck: 4 colors × 9 values × 2 copies = 72 cards"""
    
    def __init__(self):
        self.cards: List[Card] = []
        self._build()
    
    def _build(self):
        """Build full deck with 2 copies of each card."""
        self.cards = []
        for color in Color:
            for value in range(1, 10):  # 1-9
                # Two copies of each
                self.cards.append(Card(color, value))
                self.cards.append(Card(color, value))
    
    def shuffle(self):
        random.shuffle(self.cards)
    
    def draw(self) -> Card | None:
        """Draw top card from deck."""
        return self.cards.pop() if self.cards else None
    
    def __len__(self) -> int:
        return len(self.cards)


class PlayerHand:
    """Player's deck in 2-player mode (2 colors each)."""
    
    def __init__(self, colors: List[Color]):
        self.colors = colors
        self.cards: List[Card] = []
        self._build()
        self.shuffle()
    
    def _build(self):
        """Build player deck with assigned colors."""
        self.cards = []
        for color in self.colors:
            for value in range(1, 10):
                self.cards.append(Card(color, value))
                self.cards.append(Card(color, value))
    
    def shuffle(self):
        random.shuffle(self.cards)
    
    def draw(self) -> Card | None:
        return self.cards.pop() if self.cards else None
    
    def peek(self) -> Card | None:
        """Look at top card without drawing."""
        return self.cards[-1] if self.cards else None
    
    def __len__(self) -> int:
        return len(self.cards)


def create_two_player_hands() -> tuple[PlayerHand, PlayerHand]:
    """Create hands for 2-player game (2 colors each)."""
    colors = list(Color)
    random.shuffle(colors)
    
    p1_colors = colors[:2]
    p2_colors = colors[2:]
    
    return PlayerHand(p1_colors), PlayerHand(p2_colors)
