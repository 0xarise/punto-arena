"""
Punto Match - Full game flow with rounds
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import time

from .cards import Card, Color, PlayerHand, create_two_player_hands
from .board import Board
from .rules import WinChecker, check_draw


class GameState(Enum):
    WAITING = "waiting"      # Waiting for players
    ACTIVE = "active"        # Game in progress
    ROUND_END = "round_end"  # Round finished
    FINISHED = "finished"    # Match complete


class Player(Enum):
    ONE = 1
    TWO = 2


@dataclass
class Move:
    player: Player
    card: Card
    row: int
    col: int
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player.value,
            "card": str(self.card),
            "row": self.row,
            "col": self.col,
            "timestamp": self.timestamp
        }


@dataclass
class RoundResult:
    winner: Optional[Player]
    winning_color: Optional[Color]
    moves: int
    is_draw: bool = False


class PuntoMatch:
    """
    Full Punto match (best of 3 rounds).
    """
    
    ROUNDS_TO_WIN = 2
    WIN_LENGTH_2P = 5  # 5 in a row for 2 players
    
    def __init__(self, player1_id: str, player2_id: str):
        self.player1_id = player1_id
        self.player2_id = player2_id
        
        self.state = GameState.WAITING
        self.current_round = 0
        self.rounds_won = {Player.ONE: 0, Player.TWO: 0}
        
        self.board: Optional[Board] = None
        self.decks: Dict[Player, PlayerHand] = {}
        self.hands: Dict[Player, List[Card]] = {}
        self.current_player = Player.ONE
        self.moves: List[Move] = []
        self.round_results: List[RoundResult] = []
        
        self.win_checker = WinChecker(self.WIN_LENGTH_2P)
        self.winner: Optional[Player] = None
        
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
    
    def start(self):
        """Start the match."""
        self.state = GameState.ACTIVE
        self.started_at = time.time()
        self._start_round()
    
    def _start_round(self):
        """Initialize a new round."""
        self.current_round += 1
        self.board = Board()
        self.moves = []
        
        # Create new hands for each round
        deck1, deck2 = create_two_player_hands()
        self.decks = {Player.ONE: deck1, Player.TWO: deck2}
        self.hands = {
            Player.ONE: self._draw_cards(Player.ONE, 2),
            Player.TWO: self._draw_cards(Player.TWO, 2)
        }
        
        # Alternate who starts each round
        self.current_player = Player.ONE if self.current_round % 2 == 1 else Player.TWO
    
    def _draw_cards(self, player: Player, count: int) -> List[Card]:
        """Draw up to `count` cards from player's deck."""
        deck = self.decks.get(player)
        if not deck:
            return []
        
        cards: List[Card] = []
        for _ in range(count):
            card = deck.draw()
            if not card:
                break
            cards.append(card)
        return cards

    def get_hand(self, player: Player) -> List[Card]:
        """Get current hand (2 cards) for player."""
        return self.hands.get(player, [])

    def get_current_card(self) -> Optional[Card]:
        """Backward-compatible: return first card in current player's hand."""
        hand = self.get_hand(self.current_player)
        return hand[0] if hand else None
    
    def make_move(self, player: Player, row: int, col: int, card_index: int) -> Dict[str, Any]:
        """
        Attempt to make a move.
        Returns result dict with success, error, game_state, etc.
        """
        # Validations
        if self.state != GameState.ACTIVE:
            return {"success": False, "error": "Game not active"}
        
        if player != self.current_player:
            return {"success": False, "error": "Not your turn"}
        
        hand = self.hands.get(player, [])
        if not hand:
            return {"success": False, "error": "No cards left"}
        if card_index is None or card_index < 0 or card_index >= len(hand):
            return {"success": False, "error": "Invalid card selection"}
        
        card = hand[card_index]
        
        if not self.board.can_place(row, col, card):
            return {"success": False, "error": "Invalid move"}
        
        # Make the move
        hand.pop(card_index)
        self.board.place(row, col, card)

        # Refill hand to 2 cards if possible
        if len(hand) < 2:
            hand.extend(self._draw_cards(player, 2 - len(hand)))
        
        move = Move(player, card, row, col)
        self.moves.append(move)
        
        # Check for win
        winning_color = self.win_checker.check_win(self.board)
        if winning_color:
            return self._end_round(player, winning_color)
        
        # Check for draw
        p1_remaining = len(self.hands[Player.ONE]) + len(self.decks[Player.ONE])
        p2_remaining = len(self.hands[Player.TWO]) + len(self.decks[Player.TWO])
        if check_draw(self.board, p1_remaining, p2_remaining):
            return self._end_round(None, None, is_draw=True)
        
        # Switch turns
        self.current_player = Player.TWO if player == Player.ONE else Player.ONE
        
        return {
            "success": True,
            "move": move.to_dict(),
            "next_player": self.current_player.value,
            "state": self.state.value
        }
    
    def _end_round(
        self, 
        winner: Optional[Player], 
        winning_color: Optional[Color],
        is_draw: bool = False
    ) -> Dict[str, Any]:
        """Handle end of round."""
        result = RoundResult(
            winner=winner,
            winning_color=winning_color,
            moves=len(self.moves),
            is_draw=is_draw
        )
        self.round_results.append(result)
        
        if winner:
            self.rounds_won[winner] += 1
        
        # Check for match winner
        if self.rounds_won[Player.ONE] >= self.ROUNDS_TO_WIN:
            return self._end_match(Player.ONE)
        if self.rounds_won[Player.TWO] >= self.ROUNDS_TO_WIN:
            return self._end_match(Player.TWO)
        
        # Start next round
        self.state = GameState.ROUND_END
        
        return {
            "success": True,
            "round_end": True,
            "round_winner": winner.value if winner else None,
            "is_draw": is_draw,
            "score": {
                "player1": self.rounds_won[Player.ONE],
                "player2": self.rounds_won[Player.TWO]
            },
            "state": self.state.value
        }
    
    def start_next_round(self) -> Dict[str, Any]:
        """Start the next round after round_end."""
        if self.state != GameState.ROUND_END:
            return {"success": False, "error": "Not in round_end state"}
        
        self._start_round()
        self.state = GameState.ACTIVE
        
        return {
            "success": True,
            "round": self.current_round,
            "starting_player": self.current_player.value,
            "state": self.state.value
        }
    
    def _end_match(self, winner: Player) -> Dict[str, Any]:
        """Handle match completion."""
        self.state = GameState.FINISHED
        self.winner = winner
        self.finished_at = time.time()
        
        return {
            "success": True,
            "match_end": True,
            "winner": winner.value,
            "winner_id": self.player1_id if winner == Player.ONE else self.player2_id,
            "final_score": {
                "player1": self.rounds_won[Player.ONE],
                "player2": self.rounds_won[Player.TWO]
            },
            "total_moves": sum(r.moves for r in self.round_results),
            "duration": self.finished_at - self.started_at,
            "state": self.state.value
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get current match state for frontend."""
        def card_to_dict(card: Optional[Card]) -> Optional[Dict[str, Any]]:
            if not card:
                return None
            return {"color": card.color.value, "value": card.value}

        def grid_to_dict(board: Optional[Board]) -> Optional[List[List[Optional[Dict[str, Any]]]]]:
            if not board:
                return None
            return [
                [card_to_dict(cell.card) for cell in row]
                for row in board.grid
            ]

        current_card = self.get_current_card()
        hands = {
            "player1": [card_to_dict(card) for card in self.hands.get(Player.ONE, [])],
            "player2": [card_to_dict(card) for card in self.hands.get(Player.TWO, [])]
        }
        return {
            "state": self.state.value,
            "round": self.current_round,
            "current_player": self.current_player.value if self.state == GameState.ACTIVE else None,
            "current_card": card_to_dict(current_card),
            "current_card_str": str(current_card) if current_card else None,
            "hands": hands,
            "score": {
                "player1": self.rounds_won[Player.ONE],
                "player2": self.rounds_won[Player.TWO]
            },
            "grid": grid_to_dict(self.board),
            "board": str(self.board) if self.board else None,
            "moves_this_round": len(self.moves),
            "winner": self.winner.value if self.winner else None
        }
    
    def get_result_for_contract(self) -> Dict[str, Any]:
        """Get result formatted for smart contract submission."""
        if self.state != GameState.FINISHED:
            return {"error": "Match not finished"}
        
        return {
            "winner_id": self.player1_id if self.winner == Player.ONE else self.player2_id,
            "loser_id": self.player2_id if self.winner == Player.ONE else self.player1_id,
            "score": f"{self.rounds_won[Player.ONE]}-{self.rounds_won[Player.TWO]}",
            "total_moves": sum(r.moves for r in self.round_results),
            "duration": int(self.finished_at - self.started_at),
            "timestamp": int(self.finished_at)
        }
