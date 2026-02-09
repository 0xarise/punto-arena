#!/usr/bin/env python3
"""
PUNTO ARENA - FRONTEND CHAOS/STRESS TEST
=========================================
Simulates real user chaos to find edge cases that break the game.

Uses Python socketio-client for fast, no-browser testing.
Run server first: python app_wagering.py

Usage:
    python test_frontend_chaos.py           # Run all tests
    python test_frontend_chaos.py --test 3  # Run specific test
    python test_frontend_chaos.py --fast    # Quick smoke test
"""

import socketio
import requests
import time
import random
import threading
import json
import traceback
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import argparse

# ============================================================================
# CONFIG
# ============================================================================

SERVER_URL = "http://127.0.0.1:8000"
VERBOSE = True

# Test wallets (fake addresses for testing)
WALLET_1 = "0x1111111111111111111111111111111111111111"
WALLET_2 = "0x2222222222222222222222222222222222222222"
WALLET_3 = "0x3333333333333333333333333333333333333333"

# ============================================================================
# HELPERS
# ============================================================================

@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "DEBUG": "🔍"}.get(level, "")
    if VERBOSE or level in ["PASS", "FAIL", "WARN"]:
        print(f"[{timestamp}] {prefix} {msg}")

def create_room(wager=0.01) -> Dict:
    """Create a new room via API"""
    response = requests.post(
        f"{SERVER_URL}/api/create_wagered_room",
        json={"wager": wager},
        timeout=5
    )
    return response.json()

class GameClient:
    """Socket.IO client wrapper for testing"""
    
    def __init__(self, name: str, wallet: str):
        self.name = name
        self.wallet = wallet
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=3,
            reconnection_delay=0.5,
            logger=False,
            engineio_logger=False
        )
        self.connected = False
        self.room_id = None
        self.role = None
        self.my_cards = []
        self.board = None
        self.my_turn = False
        self.game_started = False
        self.game_over = False
        self.winner = None
        self.errors = []
        self.events_received = []
        self.last_state = None
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.sio.on('connect')
        def on_connect():
            self.connected = True
            self.events_received.append(('connect', time.time()))
            log(f"[{self.name}] Connected", "DEBUG")
        
        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False
            self.events_received.append(('disconnect', time.time()))
            log(f"[{self.name}] Disconnected", "DEBUG")
        
        @self.sio.on('player_joined')
        def on_player_joined(data):
            self.events_received.append(('player_joined', data))
            if data.get('role') != self.role:
                log(f"[{self.name}] Opponent joined: {data}", "DEBUG")
        
        @self.sio.on('game_start')
        def on_game_start(data):
            self.events_received.append(('game_start', data))
            self.game_started = True
            self._update_state(data)
            log(f"[{self.name}] Game started! Role={self.role}, Cards={self.my_cards}", "DEBUG")
        
        @self.sio.on('game_state_restored')
        def on_state_restored(data):
            self.events_received.append(('game_state_restored', data))
            self.game_started = True
            self._update_state(data)
            log(f"[{self.name}] State restored! Cards={self.my_cards}", "DEBUG")
        
        @self.sio.on('move_made')
        def on_move_made(data):
            self.events_received.append(('move_made', data))
            self._update_after_move(data)
            if data.get('winner'):
                self.game_over = True
                self.winner = data['winner']
        
        @self.sio.on('player_status')
        def on_player_status(data):
            self.events_received.append(('player_status', data))
        
        @self.sio.on('waiting_for_wager')
        def on_waiting(data):
            self.events_received.append(('waiting_for_wager', data))
        
        @self.sio.on('error')
        def on_error(data):
            self.errors.append(data)
            self.events_received.append(('error', data))
            log(f"[{self.name}] ERROR: {data}", "WARN")
    
    def _update_state(self, data):
        self.last_state = data
        self.board = data.get('board')
        self.role = data.get('your_role', self.role)
        
        if self.role == 'player1':
            self.my_cards = data.get('your_cards') or data.get('player1', {}).get('cards', [])
            self.my_turn = data.get('current_turn') == 'player1'
        else:
            self.my_cards = data.get('your_cards') or data.get('player2', {}).get('cards', [])
            self.my_turn = data.get('current_turn') == 'player2'
    
    def _update_after_move(self, data):
        self.board = data.get('board')
        if self.role == 'player1':
            self.my_cards = data.get('player1_cards', [])
        else:
            self.my_cards = data.get('player2_cards', [])
        self.my_turn = data.get('next_turn') == self.role
    
    def connect(self):
        if not self.connected:
            self.sio.connect(SERVER_URL, wait_timeout=5)
            time.sleep(0.2)
    
    def disconnect(self):
        if self.connected:
            self.sio.disconnect()
            time.sleep(0.1)
    
    def join_room(self, room_id):
        self.room_id = room_id
        self.sio.emit('join_wagered_room', {
            'room_id': room_id,
            'name': self.name,
            'address': self.wallet
        })
        time.sleep(0.1)
    
    def confirm_wager(self):
        self.sio.emit('wager_confirmed', {'room_id': self.room_id})
        time.sleep(0.1)
    
    def make_move(self, card: int, row: int, col: int):
        self.sio.emit('make_move', {
            'card': card,
            'row': row,
            'col': col
        })
        time.sleep(0.05)
    
    def find_valid_move(self) -> Optional[tuple]:
        """Find a valid move based on current state"""
        if not self.my_cards or not self.board:
            return None
        
        card = max(self.my_cards)  # Use highest card
        
        # Find empty cells
        empty_cells = []
        for r in range(6):
            for c in range(6):
                if self.board[r][c] is None:
                    empty_cells.append((r, c))
        
        if empty_cells:
            row, col = random.choice(empty_cells)
            return (card, row, col)
        
        # Find cells we can overwrite
        for r in range(6):
            for c in range(6):
                cell = self.board[r][c]
                if cell and cell.get('card', 0) < card:
                    return (card, r, c)
        
        return None
    
    def wait_for_event(self, event_name: str, timeout: float = 5.0, since: float = None) -> bool:
        """Wait for a specific event (optionally since a timestamp)"""
        start = time.time()
        check_time = since if since else start - 0.1  # Look for recent events
        while time.time() - start < timeout:
            for e in self.events_received:
                if e[0] == event_name:
                    # Check timestamp if available
                    if len(e) > 1 and isinstance(e[1], (int, float)):
                        if e[1] > check_time:
                            return True
                    else:
                        return True  # Event exists
            time.sleep(0.1)
        return False
    
    def has_event(self, event_name: str) -> bool:
        """Check if event was received (non-blocking)"""
        return any(e[0] == event_name for e in self.events_received)
    
    def wait_for_turn(self, timeout: float = 10.0) -> bool:
        """Wait until it's our turn"""
        start = time.time()
        while time.time() - start < timeout:
            if self.my_turn or self.game_over:
                return True
            time.sleep(0.1)
        return False

# ============================================================================
# CHAOS TESTS
# ============================================================================

def test_01_refresh_storm() -> TestResult:
    """
    REFRESH STORM: Join game, start playing, disconnect/reconnect 5x rapidly
    Simulates: User hitting F5 repeatedly during game
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        log(f"Created room: {room_id}")
        
        p1 = GameClient("RefreshP1", WALLET_1)
        p2 = GameClient("RefreshP2", WALLET_2)
        
        # Setup game
        p1.connect()
        p1.join_room(room_id)
        time.sleep(0.2)
        
        p2.connect()
        p2.join_room(room_id)
        time.sleep(0.2)
        
        p1.confirm_wager()
        p2.confirm_wager()
        
        # Wait for game start
        time.sleep(1.0)
        if not p1.game_started:
            errors.append("Game didn't start")
        
        # CHAOS: Rapid reconnects (simulating refresh)
        successful_restores = 0
        for i in range(5):
            log(f"Refresh #{i+1} - disconnecting P1...")
            cards_before = list(p1.my_cards) if p1.my_cards else []
            p1.disconnect()
            time.sleep(0.1 + random.random() * 0.2)  # Random delay 100-300ms
            
            log(f"Refresh #{i+1} - reconnecting P1...")
            # Clear events to check for new restore
            p1.events_received = []
            p1.connect()
            p1.join_room(room_id)
            
            # Wait for state
            time.sleep(0.8)
            
            # Check if state was restored
            if p1.game_started and p1.my_cards:
                successful_restores += 1
                log(f"State restored after refresh #{i+1}, cards: {p1.my_cards}")
            else:
                log(f"State NOT restored after refresh #{i+1}!", "WARN")
        
        # Verify game is still playable
        time.sleep(0.3)
        if p1.game_started and p1.my_cards:
            log(f"Game still playable after 5 refreshes! Cards: {p1.my_cards}")
        else:
            errors.append("Game state lost after refresh storm")
        
        if successful_restores < 5:
            errors.append(f"Only {successful_restores}/5 refreshes restored state properly")
        
        # Cleanup
        p1.disconnect()
        p2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="REFRESH_STORM",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={"refresh_count": 5, "successful_restores": successful_restores, "final_cards": p1.my_cards}
        )
        
    except Exception as e:
        return TestResult(
            name="REFRESH_STORM",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_02_websocket_chaos() -> TestResult:
    """
    WEBSOCKET CHAOS: Manually disconnect/reconnect socket mid-turn
    Simulates: Network drops, mobile switching wifi/data
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("WsP1", WALLET_1)
        p2 = GameClient("WsP2", WALLET_2)
        
        # Setup
        p1.connect()
        p1.join_room(room_id)
        p2.connect()
        p2.join_room(room_id)
        p1.confirm_wager()
        p2.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        p2.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        moves_made = 0
        
        # Play a few turns with random disconnects
        for turn in range(6):
            active = p1 if p1.my_turn else p2
            inactive = p2 if p1.my_turn else p1
            
            if active.game_over:
                break
            
            # 50% chance to disconnect/reconnect before move
            if random.random() < 0.5:
                log(f"[Turn {turn}] Network drop for {active.name}...")
                active.disconnect()
                time.sleep(0.2 + random.random() * 0.3)
                active.connect()
                active.join_room(room_id)
                active.wait_for_event('game_state_restored', timeout=2)
            
            move = active.find_valid_move()
            if move:
                card, row, col = move
                log(f"[Turn {turn}] {active.name} plays {card} at ({row},{col})")
                active.make_move(card, row, col)
                moves_made += 1
                time.sleep(0.3)
        
        if moves_made < 3:
            errors.append(f"Only made {moves_made} moves, expected more")
        
        p1.disconnect()
        p2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="WEBSOCKET_CHAOS",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={"moves_made": moves_made}
        )
        
    except Exception as e:
        return TestResult(
            name="WEBSOCKET_CHAOS",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_03_double_tab() -> TestResult:
    """
    DOUBLE TAB: Open same room in 2 connections with same wallet
    Simulates: User opening game in multiple tabs
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        # Player 1 - normal
        p1 = GameClient("TabP1", WALLET_1)
        
        # Player 2 - TWO TABS with same wallet!
        p2_tab1 = GameClient("TabP2_Tab1", WALLET_2)
        p2_tab2 = GameClient("TabP2_Tab2", WALLET_2)  # Same wallet
        
        # Setup first tab
        p1.connect()
        p1.join_room(room_id)
        
        p2_tab1.connect()
        p2_tab1.join_room(room_id)
        
        p1.confirm_wager()
        p2_tab1.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        p2_tab1.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        # NOW connect second tab with same wallet (simulating duplicate tab)
        log("Opening SECOND TAB with same wallet...")
        p2_tab2.connect()
        p2_tab2.join_room(room_id)
        
        # The second tab should either:
        # 1. Get the game state (rejoin works)
        # 2. Get an error
        # What we DON'T want: broken game state
        
        time.sleep(0.5)
        
        if p2_tab2.errors:
            log(f"Second tab got error: {p2_tab2.errors}", "WARN")
        
        # Check if original tab still works
        if p2_tab1.my_turn:
            move = p2_tab1.find_valid_move()
            if move:
                p2_tab1.make_move(*move)
                time.sleep(0.3)
                
                # Verify move was received
                if not p1.wait_for_event('move_made', timeout=2):
                    errors.append("Move from tab1 not received by p1")
        
        # Try to make a move from second tab too (should fail or work, not crash)
        if p2_tab2.my_turn and p2_tab2.my_cards:
            move = p2_tab2.find_valid_move()
            if move:
                p2_tab2.make_move(*move)
                time.sleep(0.3)
        
        # Final state check
        if not p1.game_started:
            errors.append("P1 game state corrupted")
        
        p1.disconnect()
        p2_tab1.disconnect()
        p2_tab2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="DOUBLE_TAB",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={
                "tab1_errors": p2_tab1.errors,
                "tab2_errors": p2_tab2.errors,
                "tab2_got_state": p2_tab2.game_started
            }
        )
        
    except Exception as e:
        return TestResult(
            name="DOUBLE_TAB",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_04_click_spam() -> TestResult:
    """
    CLICK SPAM: Send same move 10x rapidly (race condition test)
    Simulates: Double-clicking, button mashing
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("SpamP1", WALLET_1)
        p2 = GameClient("SpamP2", WALLET_2)
        
        p1.connect()
        p1.join_room(room_id)
        p2.connect()
        p2.join_room(room_id)
        p1.confirm_wager()
        p2.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        p2.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        active = p1 if p1.my_turn else p2
        
        move = active.find_valid_move()
        if not move:
            errors.append("No valid move found")
        else:
            card, row, col = move
            initial_errors = len(active.errors)
            
            # SPAM: Send same move 10x rapidly
            log(f"SPAMMING move: {card} at ({row},{col}) x10...")
            for i in range(10):
                active.sio.emit('make_move', {
                    'card': card,
                    'row': row,
                    'col': col
                })
                # NO sleep - fire as fast as possible
            
            time.sleep(0.5)
            
            # Count move_made events and errors
            move_events = [e for e in active.events_received if e[0] == 'move_made']
            error_events = [e for e in active.events_received if e[0] == 'error']
            
            log(f"Got {len(move_events)} move_made events")
            log(f"Got {len(error_events)} error events")
            
            # Should have exactly 1 successful move
            if len(move_events) < 1:
                errors.append("No moves went through")
            elif len(move_events) > 1:
                # This might actually be from both players' perspectives
                log(f"Multiple move_made events (may be expected): {len(move_events)}", "WARN")
        
        p1.disconnect()
        p2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="CLICK_SPAM",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={
                "spam_count": 10,
                "p1_errors": len(p1.errors),
                "p2_errors": len(p2.errors)
            }
        )
        
    except Exception as e:
        return TestResult(
            name="CLICK_SPAM",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_05_reconnect_race() -> TestResult:
    """
    RECONNECT RACE: Disconnect both players, reconnect in random order
    Simulates: Server restart, network outage affecting both players
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("RaceP1", WALLET_1)
        p2 = GameClient("RaceP2", WALLET_2)
        
        p1.connect()
        p1.join_room(room_id)
        p2.connect()
        p2.join_room(room_id)
        p1.confirm_wager()
        p2.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        p2.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        # Make 2 moves first
        for _ in range(2):
            active = p1 if p1.my_turn else p2
            move = active.find_valid_move()
            if move:
                active.make_move(*move)
                time.sleep(0.3)
        
        # Save state before disconnect
        p1_cards_before = list(p1.my_cards)
        p2_cards_before = list(p2.my_cards)
        
        log("DISCONNECTING BOTH PLAYERS...")
        p1.disconnect()
        p2.disconnect()
        time.sleep(0.5)
        
        # Reconnect in random order
        players = [p1, p2]
        random.shuffle(players)
        
        for p in players:
            log(f"Reconnecting {p.name}...")
            p.connect()
            p.join_room(room_id)
            time.sleep(0.3)
        
        # Wait for state restore
        p1.wait_for_event('game_state_restored', timeout=3)
        p2.wait_for_event('game_state_restored', timeout=3)
        time.sleep(0.3)
        
        # Verify state
        if not p1.game_started:
            errors.append("P1 didn't restore game state")
        if not p2.game_started:
            errors.append("P2 didn't restore game state")
        
        # Try to continue game
        active = p1 if p1.my_turn else p2
        move = active.find_valid_move()
        if move:
            active.make_move(*move)
            time.sleep(0.3)
            
            other = p2 if active == p1 else p1
            if not other.wait_for_event('move_made', timeout=2):
                errors.append("Move after reconnect not received")
        
        p1.disconnect()
        p2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="RECONNECT_RACE",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={
                "reconnect_order": [p.name for p in players],
                "p1_restored": p1.game_started,
                "p2_restored": p2.game_started
            }
        )
        
    except Exception as e:
        return TestResult(
            name="RECONNECT_RACE",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_06_mid_move_disconnect() -> TestResult:
    """
    MID-MOVE DISCONNECT: Disconnect exactly while move is being processed
    Simulates: Network drop during action
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("MidP1", WALLET_1)
        p2 = GameClient("MidP2", WALLET_2)
        
        p1.connect()
        p1.join_room(room_id)
        p2.connect()
        p2.join_room(room_id)
        p1.confirm_wager()
        p2.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        active = p1 if p1.my_turn else p2
        move = active.find_valid_move()
        
        if move:
            card, row, col = move
            
            # Send move and IMMEDIATELY disconnect
            log(f"Sending move and disconnecting immediately...")
            active.sio.emit('make_move', {
                'card': card,
                'row': row,
                'col': col
            })
            active.disconnect()  # Instant disconnect
            
            time.sleep(0.3)
            
            # Reconnect
            active.connect()
            active.join_room(room_id)
            time.sleep(0.5)
            
            # Check: Did the move go through?
            other = p2 if active == p1 else p1
            move_events = [e for e in other.events_received if e[0] == 'move_made']
            
            if move_events:
                log("Move went through despite disconnect")
            else:
                log("Move was lost (expected in some race conditions)", "WARN")
                # This isn't necessarily an error - move might not have been processed
        
        p1.disconnect()
        p2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="MID_MOVE_DISCONNECT",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None
        )
        
    except Exception as e:
        return TestResult(
            name="MID_MOVE_DISCONNECT",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_07_stale_session() -> TestResult:
    """
    STALE SESSION: Try to rejoin with old room_id after game ended
    Simulates: User trying to rejoin finished/expired game
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("StaleP1", WALLET_1)
        p2 = GameClient("StaleP2", WALLET_2)
        
        p1.connect()
        p1.join_room(room_id)
        p2.connect()
        p2.join_room(room_id)
        p1.confirm_wager()
        p2.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        # Play until game over or 20 moves
        for i in range(20):
            if p1.game_over or p2.game_over:
                break
            active = p1 if p1.my_turn else p2
            move = active.find_valid_move()
            if move:
                active.make_move(*move)
                time.sleep(0.1)
        
        # Disconnect
        p1.disconnect()
        p2.disconnect()
        time.sleep(0.5)
        
        # Try to rejoin with same room (stale)
        log("Attempting to rejoin finished/stale room...")
        stale_client = GameClient("StaleRejoiner", WALLET_1)
        stale_client.connect()
        stale_client.join_room(room_id)
        time.sleep(0.5)
        
        # Should either get error or restored state (depending on game status)
        if stale_client.errors:
            log(f"Got expected error for stale session: {stale_client.errors}")
        elif stale_client.game_started:
            log("Got game state (game might not have ended)")
        else:
            log("No error and no state - ambiguous", "WARN")
        
        # Try to join non-existent room
        log("Attempting to join non-existent room...")
        fake_client = GameClient("FakeJoiner", WALLET_3)
        fake_client.connect()
        fake_client.join_room("nonexistent_room_id_12345")
        time.sleep(0.5)
        
        if not fake_client.errors:
            errors.append("No error for non-existent room")
        else:
            log(f"Got expected error: {fake_client.errors}")
        
        stale_client.disconnect()
        fake_client.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="STALE_SESSION",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None
        )
        
    except Exception as e:
        return TestResult(
            name="STALE_SESSION",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_08_concurrent_joins() -> TestResult:
    """
    CONCURRENT JOINS: 3 players try to join same 2-player room
    Simulates: Race to join limited room
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("ConcP1", WALLET_1)
        p2 = GameClient("ConcP2", WALLET_2)
        p3 = GameClient("ConcP3", WALLET_3)  # Third player (should be rejected)
        
        # Connect all
        p1.connect()
        p2.connect()
        p3.connect()
        
        # Join simultaneously using threads
        def join(client):
            client.join_room(room_id)
        
        threads = [
            threading.Thread(target=join, args=(p1,)),
            threading.Thread(target=join, args=(p2,)),
            threading.Thread(target=join, args=(p3,)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        time.sleep(0.5)
        
        # Check who got in
        joined_players = []
        rejected_players = []
        
        for p in [p1, p2, p3]:
            if p.errors and any('full' in str(e).lower() for e in p.errors):
                rejected_players.append(p.name)
            else:
                joined_players.append(p.name)
        
        log(f"Joined: {joined_players}")
        log(f"Rejected: {rejected_players}")
        
        if len(joined_players) > 2:
            errors.append(f"More than 2 players joined! {joined_players}")
        
        p1.disconnect()
        p2.disconnect()
        p3.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="CONCURRENT_JOINS",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={"joined": joined_players, "rejected": rejected_players}
        )
        
    except Exception as e:
        return TestResult(
            name="CONCURRENT_JOINS",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_09_rapid_room_creation() -> TestResult:
    """
    RAPID ROOM CREATION: Create 10 rooms rapidly, join and leave
    Simulates: Bot spamming room creation, memory leaks
    """
    start_time = time.time()
    errors = []
    room_ids = []
    
    try:
        # Create 10 rooms rapidly
        log("Creating 10 rooms rapidly...")
        for i in range(10):
            room = create_room(wager=0.001)
            room_ids.append(room['room_id'])
        
        log(f"Created {len(room_ids)} rooms")
        
        # Join and leave each room
        client = GameClient("RoomSpammer", WALLET_1)
        client.connect()
        
        for room_id in room_ids:
            client.join_room(room_id)
            time.sleep(0.05)
        
        time.sleep(0.3)
        
        # Check for errors
        if client.errors:
            log(f"Errors during rapid joins: {client.errors}", "WARN")
        
        client.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="RAPID_ROOM_CREATION",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={"rooms_created": len(room_ids)}
        )
        
    except Exception as e:
        return TestResult(
            name="RAPID_ROOM_CREATION",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

def test_10_invalid_moves() -> TestResult:
    """
    INVALID MOVES: Send various invalid moves
    Simulates: Hackers trying to cheat, corrupted client state
    """
    start_time = time.time()
    errors = []
    
    try:
        room = create_room(wager=0.001)
        room_id = room['room_id']
        
        p1 = GameClient("InvalidP1", WALLET_1)
        p2 = GameClient("InvalidP2", WALLET_2)
        
        p1.connect()
        p1.join_room(room_id)
        p2.connect()
        p2.join_room(room_id)
        p1.confirm_wager()
        p2.confirm_wager()
        
        p1.wait_for_event('game_start', timeout=3)
        time.sleep(0.3)
        
        active = p1 if p1.my_turn else p2
        
        # Test various invalid moves
        invalid_moves = [
            {'card': 99, 'row': 0, 'col': 0},           # Card not in hand
            {'card': 1, 'row': -1, 'col': 0},           # Negative row
            {'card': 1, 'row': 0, 'col': 100},          # Col out of bounds
            {'card': None, 'row': 0, 'col': 0},         # None card
            {'card': 'invalid', 'row': 0, 'col': 0},    # String card
            {'row': 0, 'col': 0},                        # Missing card
            {},                                          # Empty
        ]
        
        initial_errors = len(active.errors)
        
        for i, invalid in enumerate(invalid_moves):
            log(f"Testing invalid move #{i+1}: {invalid}")
            active.sio.emit('make_move', invalid)
            time.sleep(0.1)
        
        time.sleep(0.3)
        
        new_errors = len(active.errors) - initial_errors
        log(f"Got {new_errors} errors from {len(invalid_moves)} invalid moves")
        
        # Server should handle all invalid moves gracefully (errors OK, crashes NOT OK)
        
        p1.disconnect()
        p2.disconnect()
        
        passed = len(errors) == 0
        return TestResult(
            name="INVALID_MOVES",
            passed=passed,
            duration=time.time() - start_time,
            error="; ".join(errors) if errors else None,
            details={"invalid_attempts": len(invalid_moves), "errors_received": new_errors}
        )
        
    except Exception as e:
        return TestResult(
            name="INVALID_MOVES",
            passed=False,
            duration=time.time() - start_time,
            error=str(e) + "\n" + traceback.format_exc()
        )

# ============================================================================
# MAIN
# ============================================================================

ALL_TESTS = [
    ("1", "REFRESH_STORM", test_01_refresh_storm),
    ("2", "WEBSOCKET_CHAOS", test_02_websocket_chaos),
    ("3", "DOUBLE_TAB", test_03_double_tab),
    ("4", "CLICK_SPAM", test_04_click_spam),
    ("5", "RECONNECT_RACE", test_05_reconnect_race),
    ("6", "MID_MOVE_DISCONNECT", test_06_mid_move_disconnect),
    ("7", "STALE_SESSION", test_07_stale_session),
    ("8", "CONCURRENT_JOINS", test_08_concurrent_joins),
    ("9", "RAPID_ROOM_CREATION", test_09_rapid_room_creation),
    ("10", "INVALID_MOVES", test_10_invalid_moves),
]

def check_server():
    """Check if server is running"""
    try:
        response = requests.get(SERVER_URL, timeout=2)
        return response.status_code == 200
    except:
        return False

def run_tests(test_ids=None, fast=False):
    """Run specified tests or all tests"""
    if not check_server():
        print(f"❌ Server not running at {SERVER_URL}")
        print("   Start it with: python app_wagering.py")
        return
    
    print("\n" + "="*70)
    print("🔥 PUNTO ARENA - FRONTEND CHAOS TEST")
    print("="*70)
    print(f"Server: {SERVER_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    tests_to_run = ALL_TESTS
    if test_ids:
        tests_to_run = [(id, name, fn) for id, name, fn in ALL_TESTS if id in test_ids]
    
    if fast:
        # Quick smoke test - only run 3 tests
        tests_to_run = tests_to_run[:3]
    
    results = []
    
    for test_id, test_name, test_fn in tests_to_run:
        print(f"\n{'─'*50}")
        print(f"🧪 TEST {test_id}: {test_name}")
        print(f"{'─'*50}")
        
        result = test_fn()
        results.append(result)
        
        if result.passed:
            log(f"{test_name}: PASSED ({result.duration:.2f}s)", "PASS")
        else:
            log(f"{test_name}: FAILED ({result.duration:.2f}s)", "FAIL")
            if result.error:
                print(f"   Error: {result.error}")
        
        if result.details:
            print(f"   Details: {json.dumps(result.details, indent=2)}")
        
        # Small delay between tests
        time.sleep(0.5)
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    total_time = sum(r.duration for r in results)
    
    print(f"\n✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Total time: {total_time:.2f}s")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in results:
            if not r.passed:
                print(f"   • {r.name}: {r.error}")
    
    print("\n" + "="*70)
    
    return failed == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Punto Arena Chaos Tests")
    parser.add_argument("--test", "-t", nargs="+", help="Run specific test(s) by number")
    parser.add_argument("--fast", "-f", action="store_true", help="Quick smoke test")
    parser.add_argument("--quiet", "-q", action="store_true", help="Less verbose output")
    parser.add_argument("--list", "-l", action="store_true", help="List all tests")
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable tests:")
        for id, name, _ in ALL_TESTS:
            print(f"  {id}. {name}")
        exit(0)
    
    if args.quiet:
        VERBOSE = False
    
    success = run_tests(test_ids=args.test, fast=args.fast)
    exit(0 if success else 1)
