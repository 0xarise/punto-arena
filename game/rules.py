"""
Punto Win Conditions - Check for lines of same color
"""

from typing import Optional, List, Tuple
from .board import Board
from .cards import Color


class WinChecker:
    """Check for winning lines on the board."""
    
    # Directions: (row_delta, col_delta)
    DIRECTIONS = [
        (0, 1),   # Horizontal
        (1, 0),   # Vertical
        (1, 1),   # Diagonal down-right
        (1, -1),  # Diagonal down-left
    ]
    
    def __init__(self, win_length: int = 5):
        """
        Args:
            win_length: Cards needed in a row to win (5 for 2p, 4 for 3-4p)
        """
        self.win_length = win_length
    
    def check_win(self, board: Board) -> Optional[Color]:
        """
        Check if any color has won.
        Returns winning color or None.
        """
        for row in range(board.SIZE):
            for col in range(board.SIZE):
                card = board.get_card(row, col)
                if card is None:
                    continue
                
                for dr, dc in self.DIRECTIONS:
                    if self._check_line(board, row, col, dr, dc, card.color):
                        return card.color
        
        return None
    
    def _check_line(
        self, 
        board: Board, 
        start_row: int, 
        start_col: int,
        dr: int, 
        dc: int, 
        color: Color
    ) -> bool:
        """Check if there's a winning line starting from position."""
        count = 0
        row, col = start_row, start_col
        
        while board.is_valid_position(row, col):
            card = board.get_card(row, col)
            if card and card.color == color:
                count += 1
                if count >= self.win_length:
                    return True
            else:
                break
            row += dr
            col += dc
        
        return False
    
    def get_winning_line(
        self, 
        board: Board
    ) -> Optional[Tuple[Color, List[Tuple[int, int]]]]:
        """
        Get the winning color and the positions forming the line.
        Returns (color, [(row, col), ...]) or None.
        """
        for row in range(board.SIZE):
            for col in range(board.SIZE):
                card = board.get_card(row, col)
                if card is None:
                    continue
                
                for dr, dc in self.DIRECTIONS:
                    line = self._get_line(board, row, col, dr, dc, card.color)
                    if len(line) >= self.win_length:
                        return (card.color, line)
        
        return None
    
    def _get_line(
        self,
        board: Board,
        start_row: int,
        start_col: int,
        dr: int,
        dc: int,
        color: Color
    ) -> List[Tuple[int, int]]:
        """Get all positions in a line of same color."""
        positions = []
        row, col = start_row, start_col
        
        while board.is_valid_position(row, col):
            card = board.get_card(row, col)
            if card and card.color == color:
                positions.append((row, col))
            else:
                break
            row += dr
            col += dc
        
        return positions


def check_draw(board: Board, p1_cards_left: int, p2_cards_left: int) -> bool:
    """
    Check if game is a draw (no valid moves possible).
    """
    if p1_cards_left == 0 and p2_cards_left == 0:
        return True
    # Could add more complex draw detection here
    return False
