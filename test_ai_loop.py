#!/usr/bin/env python3
"""
AI vs AI Test Loop for Punto Arena
Stress tests the game engine by running many automated games.
No browser required - connects directly via Socket.IO.

Usage:
    python test_ai_loop.py              # Run 10 games (default)
    python test_ai_loop.py -n 100       # Run 100 games
    python test_ai_loop.py -v           # Verbose output
    python test_ai_loop.py --parallel 4 # Run 4 games in parallel
"""

import argparse
import json
import random
import time
import threading
import statistics
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime

import socketio


@dataclass
class GameResult:
    game_id: int
    room_id: str
    winner: Optional[str]  # 'player1', 'player2', or None (draw/error)
    turns: int
    duration_ms: float
    error: Optional[str] = None


@dataclass 
class TestStats:
    total_games: int = 0
    completed: int = 0
    player1_wins: int = 0
    player2_wins: int = 0
    draws: int = 0
    errors: int = 0
    durations: List[float] = field(default_factory=list)
    turn_counts: List[int] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)


class AIPlayer:
    """Simulates a player making random valid moves via Socket.IO"""
    
    def __init__(self, server_url: str, player_id: str, verbose: bool = False):
        self.server_url = server_url
        self.player_id = player_id
        self.verbose = verbose
        self.sio = socketio.Client(reconnection=False)
        
        self.room_id: Optional[str] = None
        self.role: Optional[str] = None
        self.my_cards: List[int] = []
        self.board: List[List[Optional[dict]]] = [[None]*6 for _ in range(6)]
        self.my_turn = False
        self.game_over = False
        self.winner: Optional[str] = None
        self.turns_played = 0
        self.error: Optional[str] = None
        self.connected = False
        self.game_started = threading.Event()
        self.game_ended = threading.Event()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.sio.on('connect')
        def on_connect():
            self.connected = True
            if self.verbose:
                print(f"  [{self.player_id}] Connected")
        
        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False
            if self.verbose:
                print(f"  [{self.player_id}] Disconnected")
        
        @self.sio.on('game_start')
        def on_game_start(data):
            self.role = 'player1' if self.player_id == 'player1' else 'player2'
            if self.role == 'player1':
                self.my_cards = data['player1']['cards']
            else:
                self.my_cards = data['player2']['cards']
            self.my_turn = (data['current_turn'] == self.role)
            self._update_board(data['board'])
            self.game_started.set()
            if self.verbose:
                print(f"  [{self.player_id}] Game started. Cards: {self.my_cards}, my_turn: {self.my_turn}")
            
            if self.my_turn:
                self._make_move()
        
        @self.sio.on('game_state_restored')
        def on_state_restored(data):
            self.role = data.get('your_role', self.role)
            self.my_cards = data.get('your_cards', [])
            self.my_turn = (data.get('current_turn') == self.role)
            self._update_board(data['board'])
            self.game_started.set()
            if self.verbose:
                print(f"  [{self.player_id}] State restored. Cards: {self.my_cards}")
            
            if self.my_turn and not self.game_over:
                self._make_move()
        
        @self.sio.on('move_made')
        def on_move_made(data):
            self._update_board(data['board'])
            
            if self.role == 'player1':
                self.my_cards = data['player1_cards']
            else:
                self.my_cards = data['player2_cards']
            
            self.my_turn = (data['next_turn'] == self.role)
            
            if data.get('winner'):
                self.winner = data['winner']
                self.game_over = True
                self.game_ended.set()
                if self.verbose:
                    print(f"  [{self.player_id}] Game over! Winner: {self.winner}")
            elif self.my_turn:
                self._make_move()
        
        @self.sio.on('player_joined')
        def on_player_joined(data):
            if self.verbose:
                print(f"  [{self.player_id}] Player joined: {data.get('role')}")
        
        @self.sio.on('error')
        def on_error(data):
            self.error = data.get('message', 'Unknown error')
            if self.verbose:
                print(f"  [{self.player_id}] ERROR: {self.error}")
            # Don't end game on some recoverable errors
            if 'Invalid move' not in self.error:
                self.game_over = True
                self.game_ended.set()
    
    def _update_board(self, board_data):
        """Update internal board state from server data"""
        self.board = []
        for row in board_data:
            board_row = []
            for cell in row:
                if cell is None:
                    board_row.append(None)
                else:
                    board_row.append({'value': cell['card'], 'player': cell['player']})
            self.board.append(board_row)
    
    def _get_valid_moves(self) -> List[Tuple[int, int, int]]:
        """Returns list of (row, col, card) tuples for valid moves"""
        valid = []
        
        for card in self.my_cards:
            # Check if board is empty - can place anywhere in center
            board_empty = all(self.board[r][c] is None for r in range(6) for c in range(6))
            
            if board_empty:
                # First move - center area
                for row in range(2, 4):
                    for col in range(2, 4):
                        valid.append((row, col, card))
            else:
                # Find adjacent cells or cells we can override
                for row in range(6):
                    for col in range(6):
                        cell = self.board[row][col]
                        
                        if cell is None:
                            # Check if adjacent to an existing card
                            if self._is_adjacent_to_card(row, col):
                                valid.append((row, col, card))
                        else:
                            # Can override with higher card
                            if card > cell['value']:
                                valid.append((row, col, card))
        
        return valid
    
    def _is_adjacent_to_card(self, row: int, col: int) -> bool:
        """Check if position is adjacent to any existing card"""
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < 6 and 0 <= nc < 6:
                    if self.board[nr][nc] is not None:
                        return True
        return False
    
    def _make_move(self):
        """Select and make a random valid move"""
        if self.game_over or not self.my_cards:
            return
        
        valid_moves = self._get_valid_moves()
        
        if not valid_moves:
            if self.verbose:
                print(f"  [{self.player_id}] No valid moves available!")
            # This shouldn't happen, but handle gracefully
            self.error = "No valid moves"
            self.game_over = True
            self.game_ended.set()
            return
        
        row, col, card = random.choice(valid_moves)
        self.turns_played += 1
        
        if self.verbose:
            print(f"  [{self.player_id}] Move #{self.turns_played}: card={card} at ({row},{col})")
        
        self.sio.emit('make_move', {
            'card': card,
            'row': row,
            'col': col
        })
        
        self.my_turn = False
    
    def connect(self):
        """Connect to server"""
        self.sio.connect(self.server_url)
    
    def join_room(self, room_id: str, name: str = None):
        """Join a game room"""
        self.room_id = room_id
        self.sio.emit('join_wagered_room', {
            'room_id': room_id,
            'name': name or f'AI_{self.player_id}',
            'address': f'0xAI{self.player_id}{random.randint(1000,9999):04d}'
        })
    
    def disconnect(self):
        """Disconnect from server"""
        if self.connected:
            self.sio.disconnect()


def create_test_room(server_url: str) -> Optional[str]:
    """Create a new room via HTTP API"""
    import requests
    try:
        resp = requests.post(
            f"{server_url}/api/create_wagered_room",
            json={'wager': 0},  # No wager for tests
            timeout=5
        )
        data = resp.json()
        return data.get('room_id')
    except Exception as e:
        print(f"Failed to create room: {e}")
        return None


def run_single_game(game_id: int, server_url: str, verbose: bool = False) -> GameResult:
    """Run a single AI vs AI game"""
    start_time = time.time()
    
    # Create room
    room_id = create_test_room(server_url)
    if not room_id:
        return GameResult(
            game_id=game_id,
            room_id='',
            winner=None,
            turns=0,
            duration_ms=0,
            error="Failed to create room"
        )
    
    if verbose:
        print(f"\n[Game {game_id}] Room: {room_id}")
    
    # Create AI players
    p1 = AIPlayer(server_url, 'player1', verbose)
    p2 = AIPlayer(server_url, 'player2', verbose)
    
    try:
        # Connect both players
        p1.connect()
        time.sleep(0.1)  # Small delay for stability
        p2.connect()
        time.sleep(0.1)
        
        # Join room
        p1.join_room(room_id, 'AI_Player1')
        time.sleep(0.1)
        p2.join_room(room_id, 'AI_Player2')
        
        # Emit wager_confirmed for both (since wager=0, no on-chain needed)
        time.sleep(0.1)
        p1.sio.emit('wager_confirmed', {'room_id': room_id})
        time.sleep(0.1)
        p2.sio.emit('wager_confirmed', {'room_id': room_id})
        
        # Wait for game to start
        started = p1.game_started.wait(timeout=10)
        if not started:
            raise TimeoutError("Game did not start within 10s")
        
        # Wait for game to end
        ended = p1.game_ended.wait(timeout=60)  # Max 60s per game
        if not ended:
            raise TimeoutError("Game did not end within 60s")
        
        duration_ms = (time.time() - start_time) * 1000
        total_turns = p1.turns_played + p2.turns_played
        
        error = p1.error or p2.error
        
        return GameResult(
            game_id=game_id,
            room_id=room_id,
            winner=p1.winner,
            turns=total_turns,
            duration_ms=duration_ms,
            error=error
        )
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return GameResult(
            game_id=game_id,
            room_id=room_id,
            winner=None,
            turns=p1.turns_played + p2.turns_played,
            duration_ms=duration_ms,
            error=str(e)
        )
    finally:
        p1.disconnect()
        p2.disconnect()


def run_test_loop(
    num_games: int = 10,
    server_url: str = "http://127.0.0.1:8000",
    verbose: bool = False,
    parallel: int = 1
):
    """Run multiple AI vs AI games and report results"""
    print(f"\n{'='*60}")
    print(f"🤖 PUNTO ARENA - AI vs AI TEST LOOP")
    print(f"{'='*60}")
    print(f"Server: {server_url}")
    print(f"Games: {num_games}")
    print(f"Parallel: {parallel}")
    print(f"Verbose: {verbose}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    stats = TestStats(total_games=num_games)
    results: List[GameResult] = []
    
    def run_game_wrapper(game_id: int):
        result = run_single_game(game_id, server_url, verbose)
        return result
    
    if parallel > 1:
        # Parallel execution
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(run_game_wrapper, i+1): i for i in range(num_games)}
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                _process_result(result, stats, verbose)
    else:
        # Sequential execution
        for i in range(num_games):
            result = run_game_wrapper(i + 1)
            results.append(result)
            _process_result(result, stats, verbose)
    
    # Print summary
    _print_summary(stats, results)


def _process_result(result: GameResult, stats: TestStats, verbose: bool):
    """Process a single game result"""
    stats.completed += 1
    
    if result.error:
        stats.errors += 1
        stats.error_messages.append(f"Game {result.game_id}: {result.error}")
        symbol = "❌"
    elif result.winner == 'player1':
        stats.player1_wins += 1
        symbol = "🔵"
    elif result.winner == 'player2':
        stats.player2_wins += 1
        symbol = "🔴"
    else:
        stats.draws += 1
        symbol = "⚪"
    
    stats.durations.append(result.duration_ms)
    if result.turns > 0:
        stats.turn_counts.append(result.turns)
    
    # Progress indicator
    pct = (stats.completed / stats.total_games) * 100
    print(f"{symbol} Game {result.game_id:3d}/{stats.total_games} | "
          f"Turns: {result.turns:2d} | "
          f"Time: {result.duration_ms:6.0f}ms | "
          f"Winner: {result.winner or 'N/A':8s} | "
          f"Progress: {pct:5.1f}%")


def _print_summary(stats: TestStats, results: List[GameResult]):
    """Print test summary"""
    print(f"\n{'='*60}")
    print(f"📊 TEST RESULTS SUMMARY")
    print(f"{'='*60}")
    
    print(f"\nGames completed: {stats.completed}/{stats.total_games}")
    print(f"Player1 wins:   {stats.player1_wins} ({stats.player1_wins/max(stats.completed,1)*100:.1f}%)")
    print(f"Player2 wins:   {stats.player2_wins} ({stats.player2_wins/max(stats.completed,1)*100:.1f}%)")
    print(f"Draws:          {stats.draws}")
    print(f"Errors:         {stats.errors}")
    
    if stats.durations:
        print(f"\nTiming Statistics:")
        print(f"  Average: {statistics.mean(stats.durations):.0f}ms")
        print(f"  Median:  {statistics.median(stats.durations):.0f}ms")
        print(f"  Min:     {min(stats.durations):.0f}ms")
        print(f"  Max:     {max(stats.durations):.0f}ms")
        if len(stats.durations) > 1:
            print(f"  StdDev:  {statistics.stdev(stats.durations):.0f}ms")
    
    if stats.turn_counts:
        print(f"\nTurn Statistics:")
        print(f"  Average: {statistics.mean(stats.turn_counts):.1f} turns")
        print(f"  Median:  {statistics.median(stats.turn_counts):.0f} turns")
        print(f"  Min:     {min(stats.turn_counts)} turns")
        print(f"  Max:     {max(stats.turn_counts)} turns")
    
    if stats.error_messages:
        print(f"\n⚠️  Errors encountered:")
        for err in stats.error_messages[:10]:  # Show first 10
            print(f"   {err}")
        if len(stats.error_messages) > 10:
            print(f"   ... and {len(stats.error_messages) - 10} more")
    
    # Overall verdict
    print(f"\n{'='*60}")
    if stats.errors == 0:
        print(f"✅ ALL TESTS PASSED - No errors detected!")
    elif stats.errors < stats.total_games * 0.1:
        print(f"⚠️  MOSTLY PASSED - {stats.errors} errors ({stats.errors/stats.total_games*100:.1f}%)")
    else:
        print(f"❌ ISSUES DETECTED - {stats.errors} errors ({stats.errors/stats.total_games*100:.1f}%)")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Punto Arena AI vs AI Test Loop')
    parser.add_argument('-n', '--num-games', type=int, default=10,
                        help='Number of games to run (default: 10)')
    parser.add_argument('-s', '--server', type=str, default='http://127.0.0.1:8000',
                        help='Server URL (default: http://127.0.0.1:8000)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-p', '--parallel', type=int, default=1,
                        help='Number of parallel games (default: 1)')
    
    args = parser.parse_args()
    
    run_test_loop(
        num_games=args.num_games,
        server_url=args.server,
        verbose=args.verbose,
        parallel=args.parallel
    )
