"""
Matchmaking - Queue and pairing for Punto Arena
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from collections import deque
import time
import uuid


@dataclass
class QueueEntry:
    """Player waiting for a match."""
    player_id: str
    wallet: str
    on_chain_id: Optional[int] = None
    wager: Optional[str] = None
    nickname: Optional[str] = None
    joined_at: float = field(default_factory=time.time)
    
    def __hash__(self):
        return hash(self.player_id)


@dataclass
class MatchPairing:
    """Result of successful matchmaking."""
    match_id: str
    player1_id: str
    player1_wallet: str
    player1_nickname: Optional[str]
    player2_id: str
    player2_wallet: str
    player2_nickname: Optional[str]
    on_chain_id: Optional[int] = None
    wager: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class MatchmakingQueue:
    """Simple FIFO matchmaking queue."""
    
    TIMEOUT_SECONDS = 120  # Remove stale entries after 2 min
    
    def __init__(self):
        self.queue: deque[QueueEntry] = deque()
        self.player_map: dict[str, QueueEntry] = {}  # player_id -> entry
        self.pending_pairings: dict[str, MatchPairing] = {}  # player_id -> pairing
        self._lock = asyncio.Lock()
    
    async def join(self, player_id: str, wallet: str, on_chain_id: Optional[int] = None, wager: Optional[str] = None, nickname: Optional[str] = None) -> Optional[MatchPairing]:
        """
        Add player to queue. Returns MatchPairing if opponent found.
        
        Args:
            player_id: Unique player identifier (e.g., session ID)
            wallet: Player's wallet address for wager
            
        Returns:
            MatchPairing if matched, None if queued
        """
        async with self._lock:
            if player_id in self.pending_pairings:
                return self.pending_pairings.pop(player_id)

            # Check if already in queue
            if player_id in self.player_map:
                return None
            
            # Clean stale entries
            self._cleanup_stale()
            
            # Try to find opponent
            opponent = self._find_opponent(player_id, wallet, wager)
            
            if opponent:
                # Match found!
                self.queue.remove(opponent)
                del self.player_map[opponent.player_id]
                pairing = MatchPairing(
                    match_id=str(uuid.uuid4()),
                    player1_id=opponent.player_id,
                    player1_wallet=opponent.wallet,
                    player1_nickname=opponent.nickname,
                    player2_id=player_id,
                    player2_wallet=wallet,
                    player2_nickname=nickname,
                    on_chain_id=opponent.on_chain_id or on_chain_id,
                    wager=opponent.wager or wager
                )
                self.pending_pairings[opponent.player_id] = pairing
                self.pending_pairings[player_id] = pairing
                return pairing
            
            # No opponent - add to queue
            entry = QueueEntry(player_id=player_id, wallet=wallet, on_chain_id=on_chain_id, wager=wager, nickname=nickname)
            self.queue.append(entry)
            self.player_map[player_id] = entry
            return None
    
    async def leave(self, player_id: str) -> bool:
        """Remove player from queue. Returns True if was in queue."""
        async with self._lock:
            self.pending_pairings.pop(player_id, None)
            if player_id not in self.player_map:
                return False
            
            entry = self.player_map.pop(player_id)
            self.queue.remove(entry)
            return True
    
    async def get_position(self, player_id: str) -> Optional[int]:
        """Get player's position in queue (1-indexed). None if not in queue."""
        async with self._lock:
            if player_id not in self.player_map:
                return None
            
            for i, entry in enumerate(self.queue):
                if entry.player_id == player_id:
                    return i + 1
            return None
    
    async def get_queue_size(self) -> int:
        """Get current queue size."""
        async with self._lock:
            return len(self.queue)
    
    def _find_opponent(self, player_id: str, wallet: str, wager: Optional[str]) -> Optional[QueueEntry]:
        """Find first valid opponent in queue."""
        def normalize_wager(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            try:
                return f"{float(value):.6f}"
            except ValueError:
                return None

        for entry in self.queue:
            if entry.player_id == player_id:
                continue
            if entry.wallet and wallet and entry.wallet.lower() == wallet.lower():
                continue
            if normalize_wager(entry.wager) and normalize_wager(wager):
                if normalize_wager(entry.wager) != normalize_wager(wager):
                    continue
            return entry
        return None
    
    def _cleanup_stale(self):
        """Remove entries older than timeout."""
        now = time.time()
        cutoff = now - self.TIMEOUT_SECONDS
        
        while self.queue and self.queue[0].joined_at < cutoff:
            entry = self.queue.popleft()
            self.player_map.pop(entry.player_id, None)


# Global queue instance
matchmaking_queue = MatchmakingQueue()
