"""
Game Manager - Manages active Punto games
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import asyncio
import time

# Add game module to path
game_path = Path(__file__).parent.parent / "game"
sys.path.insert(0, str(game_path.parent))

from game import PuntoMatch, Player, GameState


@dataclass
class GameSession:
    """Active game session with metadata."""
    match_id: str
    on_chain_id: Optional[int]  # Contract game ID (set after on-chain creation)
    wager: Optional[str]  # Wager in MON (string for display)
    match: PuntoMatch
    player_sockets: dict  # player_id -> WebSocket
    nicknames: dict  # player_id -> nickname
    created_at: float
    
    @property
    def player1_id(self) -> str:
        return self.match.player1_id
    
    @property
    def player2_id(self) -> str:
        return self.match.player2_id

    def nicknames_by_role(self) -> dict:
        return {
            "player1": self.nicknames.get(self.player1_id),
            "player2": self.nicknames.get(self.player2_id)
        }


class GameManager:
    """Manages all active game sessions."""
    
    def __init__(self):
        self.games: dict[str, GameSession] = {}  # match_id -> GameSession
        self.player_games: dict[str, str] = {}   # player_id -> match_id
        self._lock = asyncio.Lock()
    
    async def create_game(
        self,
        match_id: str,
        player1_id: str,
        player2_id: str,
        on_chain_id: Optional[int] = None,
        wager: Optional[str] = None,
        player1_name: Optional[str] = None,
        player2_name: Optional[str] = None
    ) -> GameSession:
        """
        Create a new game session.
        
        Args:
            match_id: Unique match identifier
            player1_id: First player's ID
            player2_id: Second player's ID
            on_chain_id: Contract game ID (optional, can be set later)
        """
        async with self._lock:
            match = PuntoMatch(player1_id, player2_id)
            
            session = GameSession(
                match_id=match_id,
                on_chain_id=on_chain_id,
                wager=wager,
                match=match,
                player_sockets={},
                nicknames={
                    **({player1_id: player1_name} if player1_name else {}),
                    **({player2_id: player2_name} if player2_name and player2_id != "waiting" else {})
                },
                created_at=time.time()
            )
            
            self.games[match_id] = session
            self.player_games[player1_id] = match_id
            if player2_id and player2_id != "waiting":
                self.player_games[player2_id] = match_id
            
            return session
    
    async def get_game(self, match_id: str) -> Optional[GameSession]:
        """Get game session by match ID."""
        return self.games.get(match_id)
    
    async def get_player_game(self, player_id: str) -> Optional[GameSession]:
        """Get game session for a player."""
        match_id = self.player_games.get(player_id)
        return self.games.get(match_id) if match_id else None
    
    async def start_game(self, match_id: str) -> dict:
        """Start a game (both players connected)."""
        session = self.games.get(match_id)
        if not session:
            return {"error": "Game not found"}
        
        session.match.start()
        return {"success": True, **session.match.get_state()}
    
    async def make_move(
        self,
        match_id: str,
        player_id: str,
        row: int,
        col: int,
        card_index: int
    ) -> dict:
        """
        Process a player's move.
        
        Returns result dict from PuntoMatch.make_move()
        """
        session = self.games.get(match_id)
        if not session:
            return {"success": False, "error": "Game not found"}
        
        # Determine which player
        if player_id == session.player1_id:
            player = Player.ONE
        elif player_id == session.player2_id:
            player = Player.TWO
        else:
            return {"success": False, "error": "Not a player in this game"}
        
        return session.match.make_move(player, row, col, card_index)
    
    async def next_round(self, match_id: str) -> dict:
        """Start next round after round_end."""
        session = self.games.get(match_id)
        if not session:
            return {"success": False, "error": "Game not found"}
        
        return session.match.start_next_round()
    
    async def get_state(self, match_id: str) -> dict:
        """Get current game state."""
        session = self.games.get(match_id)
        if not session:
            return {"error": "Game not found"}
        
        return session.match.get_state()
    
    async def set_on_chain_id(self, match_id: str, on_chain_id: int):
        """Link match to on-chain game ID."""
        session = self.games.get(match_id)
        if session:
            session.on_chain_id = on_chain_id

    async def set_wager(self, match_id: str, wager: str):
        """Store wager amount for display/joins."""
        session = self.games.get(match_id)
        if session:
            session.wager = wager

    async def set_nickname(self, match_id: str, player_id: str, nickname: Optional[str]):
        """Store a nickname for a player."""
        if not nickname:
            return
        session = self.games.get(match_id)
        if session:
            session.nicknames[player_id] = nickname
    
    async def remove_game(self, match_id: str):
        """Remove completed game from active games."""
        async with self._lock:
            session = self.games.pop(match_id, None)
            if session:
                self.player_games.pop(session.player1_id, None)
                self.player_games.pop(session.player2_id, None)
    
    async def register_socket(self, match_id: str, player_id: str, websocket):
        """Register a WebSocket connection for a player."""
        session = self.games.get(match_id)
        if session:
            session.player_sockets[player_id] = websocket
    
    async def unregister_socket(self, match_id: str, player_id: str):
        """Unregister a WebSocket connection."""
        session = self.games.get(match_id)
        if session:
            session.player_sockets.pop(player_id, None)
    
    async def broadcast(self, match_id: str, message: dict, exclude: str = None):
        """Broadcast message to all players in a game."""
        session = self.games.get(match_id)
        if not session:
            return
        
        import json
        msg = json.dumps(message)
        
        for pid, ws in list(session.player_sockets.items()):
            if pid != exclude:
                try:
                    await ws.send_text(msg)
                except Exception:
                    pass  # Socket might be closed


# Global instance
game_manager = GameManager()
