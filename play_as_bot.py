#!/usr/bin/env python3
"""
Bot player that joins a Punto room via Socket.IO and plays using heuristic AI.
Usage: python3 play_as_bot.py <room_id>
"""
import sys
import time
import socketio

from game_logic import PuntoGame
from hackathon_matches import heuristic_move, valid_moves
from ai_player import AIPlayer

ROOM_ID = sys.argv[1] if len(sys.argv) > 1 else "-cO2_lcuRN8"
SERVER = "http://127.0.0.1:8000"

# Force unbuffered output
import functools
print = functools.partial(print, flush=True)

sio = socketio.Client(logger=False)

# Local game state mirror
game = None
my_role = None
my_cards = []
my_turn = False

# Opus 4.6 AI player
ai_player = AIPlayer("openai", api_type="claude", model="claude-opus-4-6")


def rebuild_game_from_board(board_data, p1_cards, p2_cards):
    """Rebuild a PuntoGame from server state for heuristic analysis."""
    g = PuntoGame()
    # Clear decks/hands - we only care about board + our hand for move selection
    g.deck_claude = []
    g.deck_openai = []
    g.hand_claude = []
    g.hand_openai = []
    g.board = [[None for _ in range(6)] for _ in range(6)]

    for y in range(6):
        for x in range(6):
            cell = board_data[y][x]
            if cell:
                g.board[y][x] = {
                    'player': 'claude' if cell['player'] == 'player1' else 'openai',
                    'value': cell['card'],
                    'color': cell.get('color', 'red'),
                }

    # Set hands based on our role
    if my_role == 'player1':
        g.hand_claude = [c if isinstance(c, dict) else {'value': c, 'color': 'red'} for c in p1_cards]
        g.hand_openai = [{'value': 1, 'color': 'green'}] * len(p2_cards) if isinstance(p2_cards, list) else []
    else:
        g.hand_openai = [c if isinstance(c, dict) else {'value': c, 'color': 'green'} for c in p2_cards]
        g.hand_claude = [{'value': 1, 'color': 'red'}] * len(p1_cards) if isinstance(p1_cards, list) else []

    return g


def pick_and_send_move(board_data, my_card_list):
    """Use Opus 4.6 AI to pick a move, with heuristic fallback."""
    global my_cards

    side = 'claude' if my_role == 'player1' else 'openai'

    # Reconstruct board for AI
    board = [[None for _ in range(6)] for _ in range(6)]
    for y in range(6):
        for x in range(6):
            cell = board_data[y][x]
            if cell:
                board[y][x] = {
                    'player': 'claude' if cell['player'] == 'player1' else 'openai',
                    'value': cell['card'],
                    'color': cell.get('color', 'red'),
                }

    cards = [c if isinstance(c, dict) else {'value': c, 'color': 'green'} for c in my_card_list]

    # Try Opus 4.6 first
    try:
        print(f"  Opus 4.6 thinking...")
        move = ai_player.get_move(board, cards, 2)
        card = move['card']
        print(f"  Opus says: {card} at ({move['x']}, {move['y']}) - {move.get('reasoning', '')}")

        # Validate the move
        g = PuntoGame()
        g.board = board
        g.deck_claude = []
        g.deck_openai = []
        if side == 'claude':
            g.hand_claude = cards
            g.hand_openai = []
        else:
            g.hand_openai = cards
            g.hand_claude = []

        is_valid, msg = g.is_valid_move(move['x'], move['y'], card, side)
        if not is_valid:
            print(f"  Opus move invalid ({msg}), falling back to heuristic")
            raise ValueError(msg)

    except Exception as e:
        print(f"  Opus fallback to heuristic: {e}")
        g = PuntoGame()
        g.board = board
        g.deck_claude = []
        g.deck_openai = []
        g.hand_claude = []
        g.hand_openai = []
        if side == 'claude':
            g.hand_claude = cards
        else:
            g.hand_openai = cards
        move = heuristic_move(g, side)
        card = move['card']
        print(f"  Heuristic: {card} at ({move['x']}, {move['y']})")

    sio.emit('make_move', {
        'row': move['y'],
        'col': move['x'],
        'card': card,
        'card_value': card['value'],
        'card_color': card['color'],
    })


@sio.event
def connect():
    print(f"  Connected to {SERVER}")
    print(f"  Joining room {ROOM_ID} as Claude's Bot...")
    sio.emit('join_wagered_room', {
        'room_id': ROOM_ID,
        'name': 'ClaudeBot',
        'address': '0x0000000000000000000000000000000000000000',
    })


@sio.on('player_joined')
def on_player_joined(data):
    global my_role
    print(f"  Player joined: {data}")
    if data.get('name') == 'ClaudeBot':
        my_role = data['role']
        print(f"  I am {my_role}")


@sio.on('game_start')
def on_game_start(data):
    global my_role, my_cards, my_turn
    print(f"\n  GAME STARTED!")
    print(f"  Current turn: {data.get('current_turn')}")

    if my_role and data.get(my_role):
        my_cards = data[my_role]['cards']
        print(f"  My cards: {my_cards}")

    my_turn = (data.get('current_turn') == my_role)
    if my_turn:
        print(f"  It's MY turn!")
        time.sleep(1)
        pick_and_send_move(data['board'], my_cards)
    else:
        print(f"  Waiting for opponent...")


@sio.on('game_state_restored')
def on_game_state_restored(data):
    global my_role, my_cards, my_turn
    my_role = data.get('your_role', my_role)
    my_cards = data.get('your_cards', [])
    print(f"  State restored. Role: {my_role}, Cards: {my_cards}")
    print(f"  Current turn: {data.get('current_turn')}")

    my_turn = (data.get('current_turn') == my_role)
    if my_turn:
        print(f"  It's MY turn!")
        time.sleep(1)
        pick_and_send_move(data['board'], my_cards)


@sio.on('move_made')
def on_move_made(data):
    global my_cards, my_turn
    print(f"\n  Move: {data.get('player')} played {data.get('card')} at {data.get('position')}")

    if data.get('winner'):
        print(f"\n  GAME OVER! Winner: {data['winner']}")
        sio.disconnect()
        return

    # Update my cards
    if my_role == 'player1' and data.get('player1_cards'):
        my_cards = data['player1_cards']
    elif my_role == 'player2' and data.get('player2_cards'):
        my_cards = data['player2_cards']

    next_turn = data.get('next_turn')
    print(f"  Next turn: {next_turn}, I am: {my_role}")

    if next_turn == my_role:
        print(f"  It's MY turn! Cards: {my_cards}")
        time.sleep(1.5)
        pick_and_send_move(data['board'], my_cards)
    else:
        print(f"  Waiting for opponent...")


@sio.on('error')
def on_error(data):
    print(f"  ERROR: {data}")


@sio.on('waiting_for_wager')
def on_waiting(data):
    print(f"  Waiting for wager: {data}")
    # Auto-confirm wager for bot
    sio.emit('wager_confirmed', {'room_id': ROOM_ID})


@sio.event
def disconnect():
    print("  Disconnected")


if __name__ == '__main__':
    print(f"{'='*50}")
    print(f"  PUNTO BOT - Joining room {ROOM_ID}")
    print(f"{'='*50}")
    try:
        sio.connect(SERVER)
        sio.wait()
    except KeyboardInterrupt:
        print("\n  Bot stopped.")
        sio.disconnect()
    except Exception as e:
        print(f"  Error: {e}")
