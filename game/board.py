"""
Punto Game Board - 6x6 grid with stacking
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from .cards import Card, Color


@dataclass
class Cell:
    card: Optional[Card] = None
    
    def is_empty(self) -> bool:
        return self.card is None
    
    def can_place(self, new_card: Card) -> bool:
        """Check if new card can be placed here."""
        if self.is_empty():
            return True
        return new_card.beats(self.card)
    
    def place(self, card: Card) -> bool:
        """Place card if valid. Returns success."""
        if self.can_place(card):
            self.card = card
            return True
        return False


class Board:
    """6x6 Punto board with boundary tracking."""
    
    SIZE = 6
    
    def __init__(self):
        self.grid: List[List[Cell]] = [
            [Cell() for _ in range(self.SIZE)] 
            for _ in range(self.SIZE)
        ]
        self.min_row = self.SIZE
        self.max_row = -1
        self.min_col = self.SIZE
        self.max_col = -1
        self.move_count = 0
    
    def is_valid_position(self, row: int, col: int) -> bool:
        """Check if position is within grid."""
        return 0 <= row < self.SIZE and 0 <= col < self.SIZE
    
    def is_adjacent_to_existing(self, row: int, col: int) -> bool:
        """Check if position is adjacent to any existing card."""
        if self.move_count == 0:
            return True  # First move can be anywhere
        
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if self.is_valid_position(nr, nc):
                    if not self.grid[nr][nc].is_empty():
                        return True
        return False
    
    def would_exceed_bounds(self, row: int, col: int) -> bool:
        """Check if placing here would exceed 6x6 bounds."""
        if self.move_count == 0:
            return False
        
        new_min_row = min(self.min_row, row)
        new_max_row = max(self.max_row, row)
        new_min_col = min(self.min_col, col)
        new_max_col = max(self.max_col, col)
        
        return (new_max_row - new_min_row >= self.SIZE or 
                new_max_col - new_min_col >= self.SIZE)
    
    def can_place(self, row: int, col: int, card: Card) -> bool:
        """Full validation for placing a card."""
        if not self.is_valid_position(row, col):
            return False
        if not self.is_adjacent_to_existing(row, col):
            return False
        if self.would_exceed_bounds(row, col):
            return False
        return self.grid[row][col].can_place(card)
    
    def place(self, row: int, col: int, card: Card) -> bool:
        """Place card on board. Returns success."""
        if not self.can_place(row, col, card):
            return False
        
        self.grid[row][col].place(card)
        self._update_bounds(row, col)
        self.move_count += 1
        return True
    
    def _update_bounds(self, row: int, col: int):
        """Update tracked boundaries."""
        self.min_row = min(self.min_row, row)
        self.max_row = max(self.max_row, row)
        self.min_col = min(self.min_col, col)
        self.max_col = max(self.max_col, col)
    
    def get_card(self, row: int, col: int) -> Optional[Card]:
        """Get card at position."""
        if self.is_valid_position(row, col):
            return self.grid[row][col].card
        return None
    
    def get_valid_moves(self, card: Card) -> List[Tuple[int, int]]:
        """Get all valid positions for a card."""
        moves = []
        for row in range(self.SIZE):
            for col in range(self.SIZE):
                if self.can_place(row, col, card):
                    moves.append((row, col))
        return moves
    
    def __str__(self) -> str:
        """ASCII representation of board."""
        lines = []
        lines.append("  " + " ".join(str(i) for i in range(self.SIZE)))
        for row in range(self.SIZE):
            cells = []
            for col in range(self.SIZE):
                card = self.grid[row][col].card
                cells.append(str(card) if card else "..")
            lines.append(f"{row} " + " ".join(cells))
        return "\n".join(lines)
