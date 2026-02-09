"""
Punto AI - Multiplayer Web Game
Real-time PvP with WebSocket, invite links, and betting hooks
"""

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os
import secrets
from datetime import datetime
from enum import Enum

from game_logic import PuntoGame
from ai_player import AIPlayer

# App setup
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'templates'))
app.secret_key = secrets.token_hex(16)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Game modes
class GameMode(Enum):
    PVP = "pvp"           # Human vs Human
    PVE = "pve"           # Human vs AI
    SPECTATE = "spectate" # Watch only

# Game rooms storage
rooms = {}
players = {}  # socket_id -> player_info

# Betting config (disabled for now, but structure ready)
BETTING_ENABLED = False
BETTING_CONFIG = {
    'min_wager': 1.0,
    'max_wager': 1000.0,
    'currency': 'USD',
    'escrow_wallet': None  # TODO: integrate payment system
}

# ============================================================================
# CORE ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main multiplayer page"""
    return render_template('multiplayer.html')

@app.route('/api/create_room', methods=['POST'])
def create_room():
    """Create a new game room"""
    data = request.json
    mode = data.get('mode', 'pvp')
    ai_model = data.get('ai_model', None)
    wager = data.get('wager', 0) if BETTING_ENABLED else 0

    room_id = secrets.token_urlsafe(8)

    rooms[room_id] = {
        'id': room_id,
        'mode': mode,
        'ai_model': ai_model,
        'game': None,
        'players': {},
        'spectators': [],
        'wager': wager,
        'status': 'waiting',
        'created': datetime.now().isoformat(),
        'winner': None
    }

    invite_link = f"http://127.0.0.1:8000/join/{room_id}"

    return jsonify({
        'room_id': room_id,
        'invite_link': invite_link,
        'mode': mode,
        'wager': wager
    })

@app.route('/join/<room_id>')
def join_room_page(room_id):
    """Join room via invite link"""
    if room_id not in rooms:
        return "Room not found", 404
    return render_template('multiplayer.html', room_id=room_id)

# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Player connects"""
    print(f'✅ Player connected: {request.sid}')
    emit('connected', {'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """Player disconnects"""
    sid = request.sid
    print(f'⚠️  Player disconnected: {sid}')

    # Find room but DON'T delete immediately (allow rejoin)
    for room_id, room in list(rooms.items()):
        if sid in room['players']:
            player_name = room['players'][sid]['name']
            print(f'   Player: {player_name} in room {room_id}')
            print(f'   🔄 Keeping player data for potential rejoin (30s grace period)')

            # Notify other players
            socketio.emit('player_disconnected', {
                'name': player_name,
                'message': f'{player_name} disconnected. Waiting for reconnect...'
            }, room=room_id)

            # Schedule cleanup after 30 seconds if no rejoin
            def delayed_cleanup():
                import time
                time.sleep(30)
                # Check if player rejoined
                if sid in room['players']:
                    # Still same old SID = no rejoin happened
                    print(f'   ⏰ Grace period expired for {player_name}, removing from room')
                    if sid in room['players']:
                        del room['players'][sid]
                    if sid in players:
                        del players[sid]

                    # Delete empty rooms
                    if len(room['players']) == 0:
                        print(f'   🗑️  Deleting empty room {room_id}')
                        if room_id in rooms:
                            del rooms[room_id]

            # Run cleanup in background
            from threading import Thread
            Thread(target=delayed_cleanup, daemon=True).start()
            break

@socketio.on('join_room')
def handle_join_room(data):
    """Player joins a game room"""
    print(f"\n👤 Player joining room...")
    print(f"   Data: {data}")

    room_id = data['room_id']
    player_name = data.get('name', f'Player{secrets.token_hex(2)}')
    sid = request.sid

    if room_id not in rooms:
        emit('error', {'message': 'Room not found'})
        return

    room = rooms[room_id]

    # CHECK FOR REJOIN: Player with same name already in room?
    existing_player = None
    old_sid = None
    for pid, pdata in room['players'].items():
        if pdata['name'] == player_name:
            existing_player = pdata
            old_sid = pid
            print(f"   🔄 REJOIN detected: {player_name} (old_sid={old_sid}, new_sid={sid})")
            break

    if existing_player:
        # REJOIN: Update socket ID, restore state
        player_role = existing_player['role']

        # Remove old socket ID entry
        if old_sid in room['players']:
            del room['players'][old_sid]
        if old_sid in players:
            del players[old_sid]

        # Add with new socket ID
        room['players'][sid] = {
            'sid': sid,
            'name': player_name,
            'role': player_role
        }

        players[sid] = {
            'room_id': room_id,
            'name': player_name,
            'role': player_role
        }

        join_room(room_id)

        print(f"   ✅ Player rejoined as {player_role}")

        # Send current game state
        if room['game']:
            game = room['game']
            current_state = {
                'status': room['status'],
                'board': format_board(game.board),
                'player1_cards': sorted(game.hand_claude, reverse=True),
                'player2_cards': sorted(game.hand_openai, reverse=True),
                'your_role': player_role,
                'your_cards': sorted(game.hand_claude if player_role == 'player1' else game.hand_openai, reverse=True),
                'current_turn': room.get('current_turn', 'player1')
            }
            emit('game_state_restored', current_state)
            print(f"   📤 Game state sent to rejoined player")

        return

    # NEW PLAYER: Normal join logic
    # Check if room is full
    if len(room['players']) >= 2 and room['mode'] == GameMode.PVP.value:
        emit('error', {'message': 'Room is full'})
        return

    # Add player to room
    join_room(room_id)
    player_role = 'player1' if len(room['players']) == 0 else 'player2'

    room['players'][sid] = {
        'sid': sid,
        'name': player_name,
        'role': player_role
    }

    players[sid] = {
        'room_id': room_id,
        'name': player_name,
        'role': player_role
    }

    print(f"   ✅ New player joined as {player_role}")

    # Notify room
    socketio.emit('player_joined', {
        'name': player_name,
        'role': player_role,
        'players_count': len(room['players'])
    }, room=room_id)

    # Start game if ready
    if len(room['players']) == 2 and room['status'] == 'waiting':
        start_game(room_id)

def start_game(room_id):
    """Initialize and start game"""
    import random

    room = rooms[room_id]
    room['game'] = PuntoGame()
    room['status'] = 'playing'

    # Get player names
    player_list = list(room['players'].values())

    # 🎲 RANDOMIZE who starts!
    first_player = random.choice(['player1', 'player2'])
    print(f"🎲 Coin flip: {first_player} starts first!")

    # Track current turn in room
    room['current_turn'] = first_player

    game_state = {
        'status': 'playing',
        'board': format_board(room['game'].board),
        'player1': {
            'name': player_list[0]['name'],
            'cards': sorted(room['game'].hand_claude, reverse=True)
        },
        'player2': {
            'name': player_list[1]['name'],
            'cards': sorted(room['game'].hand_openai, reverse=True)
        },
        'current_turn': first_player,  # 🎲 Random!
        'wager': room['wager']
    }

    socketio.emit('game_start', game_state, room=room_id)

@socketio.on('make_move')
def handle_make_move(data):
    """Player makes a move"""
    try:
        sid = request.sid
        print(f"\n📥 Received move from {sid}")
        print(f"   Data: {data}")

        if sid not in players:
            print(f"❌ Player {sid} not in players dict")
            emit('error', {'message': 'Not in a game'})
            return

        room_id = players[sid]['room_id']
        print(f"   Room: {room_id}")

        if room_id not in rooms:
            print(f"❌ Room {room_id} not found")
            emit('error', {'message': 'Room not found'})
            return

        room = rooms[room_id]
        game = room['game']

        if not game:
            print(f"❌ No game in room {room_id}")
            emit('error', {'message': 'Game not initialized'})
            return

        card = data['card']
        row = data['row']
        col = data['col']

        # Determine player
        player_role = players[sid]['role']
        game_player = 'claude' if player_role == 'player1' else 'openai'

        print(f"   Player: {player_role} ({game_player})")
        print(f"   Move: card={card} pos=({row},{col})")

        # Validate move
        is_valid, msg = game.is_valid_move(col, row, card, game_player)
        print(f"   Valid: {is_valid} - {msg}")

        if not is_valid:
            emit('error', {'message': f'Invalid move: {msg}'})
            return

    except Exception as e:
        print(f"❌ ERROR in handle_make_move: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Server error: {str(e)}'})
        return

    try:
        # Make move
        print(f"   Making move...")
        game.make_move(col, row, card, game_player)
        print(f"   ✅ Move executed")

        # DEBUG: Print board state
        print(f"\n🎮 Move made by {player_role}: card={card} pos=({row},{col})")
        print(f"   Player: {game_player}")
        print(f"   Game winner: {game.winner}")
        print(f"   Turn count: {game.current_turn}")
        print("\n   Current board:")
        print(game.format_board())

        # Check winner
        winner = None
        if game.winner:
            winner = 'player1' if game.winner == 'claude' else 'player2'
            room['status'] = 'finished'
            room['winner'] = winner
            print(f"🏆 WINNER DETECTED: {winner} (game.winner={game.winner})")

        # Update current turn in room state
        next_turn = 'player2' if player_role == 'player1' else 'player1'
        room['current_turn'] = next_turn

        # Broadcast move
        move_data = {
            'player': player_role,
            'card': card,
            'position': [row, col],
            'board': format_board(game.board),
            'player1_cards': sorted(game.hand_claude, reverse=True),
            'player2_cards': sorted(game.hand_openai, reverse=True),
            'winner': winner,
            'next_turn': next_turn
        }

        print(f"   📤 Broadcasting move to room {room_id}")
        socketio.emit('move_made', move_data, room=room_id)
        print(f"   ✅ Move broadcasted")

        if winner:
            handle_game_end(room_id, winner)

    except Exception as e:
        print(f"❌ ERROR executing move: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error executing move: {str(e)}'})

def handle_game_end(room_id, winner):
    """Handle game end and payout (if betting enabled)"""
    room = rooms[room_id]

    # TODO: Betting payout logic here
    if BETTING_ENABLED and room['wager'] > 0:
        payout = room['wager'] * 2
        # Escrow release, payment processing, etc.
        pass

    end_data = {
        'winner': winner,
        'wager': room['wager'],
        'payout': room['wager'] * 2 if BETTING_ENABLED else 0
    }

    socketio.emit('game_end', end_data, room=room_id)

@socketio.on('rematch')
def handle_rematch(data):
    """Request rematch"""
    sid = request.sid
    room_id = players[sid]['room_id']
    room = rooms[room_id]

    # Reset game
    start_game(room_id)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_board(board):
    """Format board for frontend"""
    result = []
    for row in board:
        result_row = []
        for cell in row:
            if cell is None:
                result_row.append(None)
            else:
                result_row.append({
                    'card': cell['value'],
                    'player': 'player1' if cell['player'] == 'claude' else 'player2'
                })
        result.append(result_row)
    return result

@app.route('/api/rooms')
def list_rooms():
    """List active rooms"""
    active_rooms = [
        {
            'id': r['id'],
            'mode': r['mode'],
            'players': len(r['players']),
            'status': r['status'],
            'wager': r['wager']
        }
        for r in rooms.values()
        if r['status'] == 'waiting'
    ]
    return jsonify({'rooms': active_rooms})

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎮 PUNTO AI - MULTIPLAYER")
    print("="*60)
    print("\n🌐 Server: http://127.0.0.1:8000")
    print("🎯 Modes: PvP, PvE, Spectate")
    print("🔗 Invite links enabled")
    print(f"💰 Betting: {'ENABLED' if BETTING_ENABLED else 'DISABLED (hook ready)'}")
    print("\n" + "="*60 + "\n")

    socketio.run(app, host='127.0.0.1', port=8000, debug=True)
