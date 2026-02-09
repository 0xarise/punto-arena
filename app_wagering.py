"""
Punto AI - Multiplayer with Blockchain Wagering
Extended version with on-chain betting
"""

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os
import secrets
import threading
from datetime import datetime, timezone
from enum import Enum
import random
import time

from game_logic import PuntoGame
from hackathon_matches import heuristic_move, valid_moves as hm_valid_moves
from blockchain.wagering import get_blockchain
import evidence_logger
import elo

# App setup
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'templates'))
app.secret_key = secrets.token_hex(16)
CORS(app)
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://0.0.0.0:8000",
    "https://puntoarena.xyz",
    "https://www.puntoarena.xyz",
]
socketio = SocketIO(app, cors_allowed_origins=ALLOWED_ORIGINS)

# Initialize blockchain
try:
    blockchain = get_blockchain()
    WAGERING_ENABLED = True
    print("✅ Wagering ENABLED")
except Exception as e:
    print(f"⚠️  Wagering DISABLED: {e}")
    WAGERING_ENABLED = False

# Game rooms storage
rooms = {}
players = {}
last_move_time = {}  # sid -> timestamp for rate limiting

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Landing page"""
    return render_template('landing.html')

@app.route('/play')
def play():
    """Wagering game page"""
    return render_template('wagering.html')

@app.route('/join/<room_id>')
def join_room_page(room_id):
    """Join page for invited players"""
    return render_template('wagering.html', join_room_id=room_id)

@app.route('/api/create_wagered_room', methods=['POST'])
def create_wagered_room():
    """Create room with on-chain wager"""
    print(f"\n{'='*60}")
    print(f"🎰 Creating wagered room...")
    data = request.json
    wager_amount = data.get('wager', 0)  # in MON
    print(f"   Wager: {wager_amount} MON")

    room_id = secrets.token_urlsafe(8)

    rooms[room_id] = {
        'id': room_id,
        'mode': 'pvp_wagered',
        'game': None,
        'players': {},
        'wager': wager_amount,
        'status': 'waiting',
        'created': datetime.now().isoformat(),
        'winner': None,
        'blockchain_game_id': None  # Will be set when player1 creates on-chain
    }

    invite_link = f"{request.host_url.rstrip('/')}/join/{room_id}"

    print(f"✅ Room created: {room_id}")
    print(f"   Invite: {invite_link}")
    print(f"{'='*60}\n")

    return jsonify({
        'room_id': room_id,
        'invite_link': invite_link,
        'wager': wager_amount,
        'wagering_enabled': WAGERING_ENABLED
    })

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

# ============================================================================
# LEADERBOARD ROUTES
# ============================================================================

@app.route('/leaderboard')
def leaderboard():
    """ELO leaderboard page"""
    return render_template('leaderboard.html')

@app.route('/api/leaderboard')
def api_leaderboard():
    """JSON endpoint for leaderboard data"""
    rankings = elo.compute_rankings()
    return jsonify(rankings)

@app.route('/api/wallet-rankings')
def api_wallet_rankings():
    """JSON endpoint for wallet-based player rankings"""
    import wallet_elo
    rankings = wallet_elo.get_wallet_rankings()
    return jsonify(rankings)

# ============================================================================
# SPECTATOR & ARENA ROUTES
# ============================================================================

@app.route('/spectate')
@app.route('/spectate/<room_id>')
def spectate_room(room_id=''):
    """Spectator view for AI vs AI matches (no wallet required)"""
    return render_template('spectate.html', room_id=room_id)

@app.route('/arena')
def arena_page():
    """Simple arena control page - start AI vs AI matches"""
    return render_template('spectate.html', room_id='')

@app.route('/api/arena/start', methods=['POST'])
def start_arena_match():
    """Start an AI vs AI match with spectator broadcasting"""
    data = request.json or {}
    engine1 = data.get('engine1', os.getenv('AGENT1_ENGINE', 'heuristic'))
    engine2 = data.get('engine2', os.getenv('AGENT2_ENGINE', 'heuristic'))
    wager = float(data.get('wager', os.getenv('MATCH_WAGER_MON', '0.01')))

    room_id = f"arena_{secrets.token_hex(4)}"

    rooms[room_id] = {
        'id': room_id,
        'mode': 'arena',
        'game': None,
        'players': {},
        'wager': wager,
        'status': 'arena_pending',
        'created': datetime.now().isoformat(),
        'winner': None,
        'blockchain_game_id': None,
        'arena_config': {'engine1': engine1, 'engine2': engine2},
    }

    # Launch arena match in background thread
    thread = threading.Thread(
        target=run_arena_match,
        args=(room_id, engine1, engine2, wager),
        daemon=True,
    )
    thread.start()

    spectator_url = f"{request.host_url.rstrip('/')}/spectate/{room_id}"
    print(f"🏟️ Arena match started: {room_id}")
    print(f"   Spectate: {spectator_url}")

    return jsonify({
        'room_id': room_id,
        'spectator_url': spectator_url,
        'engine1': engine1,
        'engine2': engine2,
        'wager': wager,
    })


def run_arena_match(room_id, engine1, engine2, wager_mon):
    """Background thread: run an AI vs AI match with live Socket.IO broadcasts."""
    from hackathon_matches import (
        MatchAgent, simulate_game_moves, send_tx, contract,
        WAGER_AMOUNT, w3, valid_moves,
    )
    from web3 import Web3
    from eth_account import Account

    wallet1_key = os.getenv("WALLET1_PRIVATE_KEY") or os.getenv("ORACLE_PRIVATE_KEY")
    wallet2_key = os.getenv("WALLET2_PRIVATE_KEY")

    if not wallet1_key or not wallet2_key or not contract:
        socketio.emit('game_end', {
            'winner': None, 'reason': 'Missing wallet keys or contract config',
        }, room=room_id)
        return

    wallet1 = Account.from_key(wallet1_key)
    wallet2 = Account.from_key(wallet2_key)

    agent1 = MatchAgent("agent1", "claude", engine1)
    agent2 = MatchAgent("agent2", "openai", engine2)

    # Store match info for late-joining spectators
    match_info = {
        'agent1': {'engine': engine1, 'address': wallet1.address},
        'agent2': {'engine': engine2, 'address': wallet2.address},
        'wager': wager_mon,
        'room_id': room_id,
        'game_id': None,
    }
    rooms[room_id]['arena_match_info'] = match_info
    socketio.emit('match_info', match_info, room=room_id)

    # Wait for spectator to connect (up to 30s, then proceed anyway)
    print(f"   🏟️ Waiting for spectator to connect to {room_id}...")
    for _ in range(60):
        if rooms.get(room_id, {}).get('spectator_connected'):
            print(f"   👁️ Spectator connected! Starting match...")
            break
        time.sleep(0.5)
    else:
        print(f"   ⏳ No spectator after 30s, proceeding anyway...")

    time.sleep(1)  # Extra beat after spectator connects

    # Step 1: Create game on-chain
    hm_room_id = f"arena_{room_id}_{int(time.time())}"
    tx_create = None
    tx_join = None
    tx_result = None

    try:
        wager_wei = Web3.to_wei(wager_mon, "ether")
        receipt = send_tx(wallet1, contract.functions.createGame(hm_room_id), wager_wei)
        tx_create = receipt.transactionHash.hex()
        game_id = contract.functions.gameCounter().call()
        print(f"   🏟️ Arena game created: ID={game_id}, TX={tx_create[:20]}...")
    except Exception as e:
        print(f"   ❌ Arena create failed: {e}")
        socketio.emit('game_end', {'winner': None, 'reason': f'Create failed: {e}'}, room=room_id)
        return

    try:
        receipt = send_tx(wallet2, contract.functions.joinGame(game_id), wager_wei)
        tx_join = receipt.transactionHash.hex()
        print(f"   🏟️ Arena game joined: TX={tx_join[:20]}...")
    except Exception as e:
        print(f"   ❌ Arena join failed: {e}")
        socketio.emit('game_end', {'winner': None, 'reason': f'Join failed: {e}'}, room=room_id)
        return

    # Update match info with game_id
    socketio.emit('match_info', {
        'agent1': {'engine': engine1, 'address': wallet1.address},
        'agent2': {'engine': engine2, 'address': wallet2.address},
        'wager': wager_mon,
        'room_id': room_id,
        'game_id': game_id,
    }, room=room_id)

    # Step 2: Play game move-by-move with broadcasts
    game = PuntoGame()
    rooms[room_id]['arena_game'] = game  # Store for late-joining spectators
    start_side = random.choice(["claude", "openai"])
    current = start_side
    turns = 0
    max_turns = 200

    current_player_num = 1 if current == "claude" else 2
    rooms[room_id]['arena_current_player'] = current_player_num

    # Broadcast game_start
    board_state = format_board(game.board)
    socketio.emit('game_start', {
        'board': board_state,
        'current_player': current_player_num,
        'hands': {1: len(game.hand_claude), 2: len(game.hand_openai)},
    }, room=room_id)

    time.sleep(1.5)

    winner_side = None
    reason = None

    while turns < max_turns and not game.is_game_over():
        agent = agent1 if current == "claude" else agent2
        player_num = 1 if current == "claude" else 2

        hand = game.get_hand(current)
        if not hand:
            other = "openai" if current == "claude" else "claude"
            current = other
            if not game.get_hand(current):
                break
            continue

        move = agent.choose_move(game)
        is_valid, _ = game.is_valid_move(move["x"], move["y"], move["card"], current)
        if not is_valid:
            from hackathon_matches import valid_moves as hm_valid_moves
            fallback = hm_valid_moves(game, current)
            if not fallback:
                current = "openai" if current == "claude" else "claude"
                continue
            move = fallback[0]

        game.make_move(move["x"], move["y"], move["card"], current)
        turns += 1

        next_side = "openai" if current == "claude" else "claude"
        next_player = 1 if next_side == "claude" else 2
        rooms[room_id]['arena_current_player'] = next_player

        # Broadcast move to spectators
        socketio.emit('spectator_move', {
            'row': move["y"],
            'col': move["x"],
            'card_value': move["card"]["value"],
            'card_color': move["card"]["color"],
            'player': player_num,
            'board': format_board(game.board),
            'current_player': next_player,
            'hands': {1: len(game.hand_claude), 2: len(game.hand_openai)},
        }, room=room_id)

        if game.winner:
            winner_side = game.winner
            reason = "five_in_line"
            break

        current = next_side
        time.sleep(1.2)  # Delay between moves for watchability

    if not winner_side:
        from hackathon_matches import resolve_tiebreak
        winner_side, reason = resolve_tiebreak(game, start_side)

    winner_num = 1 if winner_side == "claude" else 2
    winner_address = wallet1.address if winner_num == 1 else wallet2.address

    # Step 3: Submit result on-chain
    try:
        receipt = send_tx(wallet1, contract.functions.submitResult(game_id, winner_address))
        tx_result = receipt.transactionHash.hex()
        print(f"   🏟️ Arena result submitted: TX={tx_result[:20]}...")
    except Exception as e:
        print(f"   ❌ Arena submit failed: {e}")
        tx_result = f"failed: {e}"

    payout = wager_mon * 2 * 0.95  # 5% fee

    # Broadcast game end and store result
    end_data = {
        'winner': winner_num,
        'reason': reason,
        'payout': round(payout, 4),
        'tx_hash': tx_result,
        'explorer_link': f"https://monad.socialscan.io/tx/{tx_result}",
    }
    rooms[room_id]['arena_result'] = end_data
    socketio.emit('game_end', end_data, room=room_id)

    # Log evidence
    match_data = {
        "match_id": evidence_logger.get_next_match_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent1": {"engine": engine1, "model": agent1.model or "default", "address": wallet1.address},
        "agent2": {"engine": engine2, "model": agent2.model or "default", "address": wallet2.address},
        "game_id": game_id,
        "room_id": room_id,
        "tx_create": tx_create,
        "tx_join": tx_join,
        "tx_result": tx_result,
        "winner": f"agent{winner_num}",
        "winner_address": winner_address,
        "reason": reason,
        "turns": turns,
        "wager_mon": wager_mon,
        "moves": [],
        "explorer_base": "https://monad.socialscan.io/tx/",
    }
    evidence_logger.log_match(match_data)
    evidence_logger.generate_summary()
    print(f"   📝 Arena evidence logged for room {room_id}")


# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('join_spectate')
def handle_join_spectate(data):
    """Spectator joins a room (read-only, no wallet needed)"""
    room_id = data.get('room_id')
    if not room_id:
        emit('error', {'message': 'Missing room_id'})
        return

    join_room(room_id)
    print(f"👁️ Spectator joined room {room_id} (SID: {request.sid})")

    if room_id in rooms:
        room = rooms[room_id]

        # Signal that a spectator has connected (unblocks arena thread)
        room['spectator_connected'] = True

        # Send current match info
        config = room.get('arena_config', {})
        match_info = room.get('arena_match_info')
        if match_info:
            emit('match_info', match_info)
        elif config:
            emit('match_info', {
                'agent1': {'engine': config.get('engine1', '--'), 'address': ''},
                'agent2': {'engine': config.get('engine2', '--'), 'address': ''},
                'wager': room.get('wager', 0),
                'room_id': room_id,
                'game_id': room.get('blockchain_game_id'),
            })

        # If game is already in progress, send current board state
        arena_game = room.get('arena_game')
        if arena_game:
            emit('game_start', {
                'board': format_board(arena_game.board),
                'current_player': room.get('arena_current_player', 1),
                'hands': {1: len(arena_game.hand_claude), 2: len(arena_game.hand_openai)},
            })

        # If game already finished, send end result
        if room.get('arena_result'):
            emit('game_end', room['arena_result'])


@socketio.on('join_wagered_room')
def handle_join_wagered_room(data):
    """Join room with blockchain verification and full state restore"""
    print(f"\n{'='*60}")
    print(f"👤 Player joining wagered room...")
    print(f"   Data: {data}")

    room_id = data.get('room_id')
    if not room_id:
        emit('error', {'message': 'Missing room_id'})
        return
        
    player_name = data.get('name', f'Player{secrets.token_hex(2)}')
    player_address = data.get('address')  # Wallet address

    sid = request.sid
    print(f"   SID: {sid}")

    if room_id not in rooms:
        print(f"❌ Room {room_id} not found!")
        emit('error', {'message': 'Room not found or expired'})
        return

    room = rooms[room_id]
    print(f"✅ Room found: {room_id}")
    print(f"   Current players: {list(room['players'].keys())}")
    print(f"   Room status: {room['status']}")

    # Check for rejoin (prefer wallet address, fallback to name)
    existing_player = None
    old_sid = None
    if player_address:
        for pid, pdata in room['players'].items():
            if pdata.get('address') and pdata['address'].lower() == player_address.lower():
                existing_player = pdata
                old_sid = pid
                break

    if existing_player is None:
        for pid, pdata in room['players'].items():
            if pdata['name'] == player_name:
                existing_player = pdata
                old_sid = pid
                break

    if existing_player:
        # REJOIN logic (same as before)
        player_role = existing_player['role']
        print(f"🔄 REJOIN detected: {player_name} as {player_role}")

        if old_sid in room['players']:
            del room['players'][old_sid]
        if old_sid in players:
            del players[old_sid]

        room['players'][sid] = {
            'sid': sid,
            'name': player_name,
            'role': player_role,
            'address': player_address,
            'connected': True
        }

        players[sid] = {
            'room_id': room_id,
            'name': player_name,
            'role': player_role,
            'address': player_address
        }

        join_room(room_id)

        print(f"DEBUG: room['game'] = {room.get('game')}")
        print(f"DEBUG: room['status'] = {room.get('status')}")
        print(f"DEBUG: room['players'] count = {len(room['players'])}")

        socketio.emit('player_status', {
            'name': player_name,
            'role': player_role,
            'status': 'reconnected'
        }, room=room_id)

        if room['game']:
            game = room['game']
            print(f"DEBUG: game exists")
            print(f"DEBUG: game.hand_claude = {game.hand_claude}")
            print(f"DEBUG: game.hand_openai = {game.hand_openai}")

            current_state = build_game_state(room)
            if current_state:
                current_state.update({
                    'your_role': player_role,
                    'your_cards': sorted(game.hand_claude if player_role == 'player1' else game.hand_openai, key=lambda c: c['value'], reverse=True)
                })
                print(f"✅ Sending game_state_restored to {player_name}")
                emit('game_state_restored', current_state)
            else:
                print("⚠️  Could not build game state for rejoin")
        else:
            # FIX: Try to start game if both players are present and on-chain is ready
            print(f"⚠️  No game exists yet, checking if we can start...")
            if len(room['players']) == 2 and room['status'] == 'waiting':
                print(f"🔄 Both players present, attempting to start game on rejoin...")
                start_wagered_game(room_id)
                # After start_wagered_game, check if game was created
                if room['game']:
                    game = room['game']
                    current_state = build_game_state(room)
                    if current_state:
                        current_state.update({
                            'your_role': player_role,
                            'your_cards': sorted(game.hand_claude if player_role == 'player1' else game.hand_openai, key=lambda c: c['value'], reverse=True)
                        })
                        print(f"✅ Game started on rejoin! Sending state to {player_name}")
                        emit('game_state_restored', current_state)

        return

    # NEW PLAYER
    if len(room['players']) >= 2:
        emit('error', {'message': 'Room is full'})
        return

    join_room(room_id)
    player_role = 'player1' if len(room['players']) == 0 else 'player2'

    room['players'][sid] = {
        'sid': sid,
        'name': player_name,
        'role': player_role,
        'address': player_address,
        'connected': True
    }

    players[sid] = {
        'room_id': room_id,
        'name': player_name,
        'role': player_role,
        'address': player_address
    }

    print(f"   ✅ Player joined as {player_role}")
    print(f"DEBUG: Total players in room: {len(room['players'])}")
    print(f"DEBUG: Room status: {room['status']}")

    # Notify room
    socketio.emit('player_joined', {
        'name': player_name,
        'role': player_role,
        'players_count': len(room['players']),
        'wager': room['wager']
    }, room=room_id)

    socketio.emit('player_status', {
        'name': player_name,
        'role': player_role,
        'status': 'connected'
    }, room=room_id)

    # Start game if both players joined
    if len(room['players']) == 2 and room['status'] == 'waiting':
        print(f"🚀 Both players joined! Checking wager_confirmed: {room.get('wager_confirmed', False)}")
        start_wagered_game(room_id)
    else:
        print(f"⏳ Waiting for more players... (have {len(room['players'])}/2)")
        print(f"   Wager confirmed: {room.get('wager_confirmed', False)}")

@socketio.on('wager_confirmed')
def handle_wager_confirmed(data):
    room_id = data.get('room_id')
    if not room_id or room_id not in rooms:
        emit('error', {'message': 'Room not found'})
        return

    room = rooms[room_id]
    print(f"📡 wager_confirmed received for room {room_id}")
    print(f"   Room status: {room['status']}, Players: {len(room['players'])}")

    if room['status'] == 'finished':
        print(f"   Room already finished, ignoring")
        return

    # Mark that on-chain wager is confirmed (used by join handler)
    room['wager_confirmed'] = True

    if room['status'] == 'playing' and room['game']:
        # Game already in progress, this is a rejoin confirmation
        print(f"   Game in progress, sending state to reconnected player")
        return

    if len(room['players']) < 2:
        print(f"   Waiting for player2 to socket-join (on-chain ready)")
        return

    # Both players present and on-chain confirmed - start game
    if not room['game']:
        print(f"✅ Wager confirmed for room {room_id}, starting game...")
        start_wagered_game(room_id)


@socketio.on('get_game_state')
def handle_get_game_state(data):
    """Explicit request for full game state (used for refresh recovery)"""
    room_id = data.get('room_id')
    if not room_id or room_id not in rooms:
        emit('error', {'message': 'Room not found'})
        return
    
    room = rooms[room_id]
    sid = request.sid
    
    if sid not in players:
        emit('error', {'message': 'Not a player in this room'})
        return
    
    player_role = players[sid]['role']
    
    if not room['game']:
        emit('waiting_for_wager', {'message': 'Game not started yet'})
        return
    
    game = room['game']
    current_state = build_game_state(room)
    
    if current_state:
        current_state.update({
            'your_role': player_role,
            'your_cards': sorted(
                game.hand_claude if player_role == 'player1' else game.hand_openai,
                reverse=True
            )
        })
        emit('game_state_restored', current_state)

# ============================================================================
# VS AI HANDLERS
# ============================================================================

@socketio.on('create_ai_room')
def handle_create_ai_room(data):
    """Create a room for human vs AI (no wager, no blockchain)"""
    wallet_address = data.get('wallet_address', 'anonymous')
    sid = request.sid

    room_id = f"ai_{secrets.token_hex(4)}"
    game = PuntoGame()

    first_player = random.choice(['player1', 'player2'])

    rooms[room_id] = {
        'id': room_id,
        'mode': 'ai',
        'game': game,
        'players': {
            sid: {
                'sid': sid,
                'name': truncateAddress(wallet_address),
                'role': 'player1',
                'address': wallet_address,
                'connected': True
            }
        },
        'ai_side': 'openai',
        'wager': 0,
        'status': 'playing',
        'created': datetime.now().isoformat(),
        'winner': None,
        'current_turn': first_player,
    }

    players[sid] = {
        'room_id': room_id,
        'name': truncateAddress(wallet_address),
        'role': 'player1',
        'address': wallet_address
    }

    join_room(room_id)

    game_state = {
        'status': 'playing',
        'board': format_board(game.board),
        'player1': {
            'name': truncateAddress(wallet_address),
            'cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True)
        },
        'player2': {
            'name': 'AI (Heuristic)',
            'cards': sorted(game.hand_openai, key=lambda c: c['value'], reverse=True)
        },
        'current_turn': first_player,
        'wager': 0,
        'mode': 'ai',
        'your_role': 'player1',
        'your_cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True)
    }

    print(f"🤖 AI room created: {room_id} | First turn: {first_player}")
    emit('ai_room_created', {'room_id': room_id, 'game_state': game_state})
    emit('game_start', game_state)

    # If AI goes first, make its move after a short delay
    if first_player == 'player2':
        _ai_respond(room_id)


@socketio.on('ai_make_move')
def handle_ai_make_move(data):
    """Handle human move in AI game, then AI responds"""
    sid = request.sid
    room_id = data.get('room_id')

    if not room_id or room_id not in rooms:
        emit('error', {'message': 'Room not found'})
        return

    room = rooms[room_id]
    if room.get('mode') != 'ai':
        emit('error', {'message': 'Not an AI room'})
        return

    game = room['game']

    # Turn enforcement
    if room.get('current_turn') != 'player1':
        emit('error', {'message': 'Not your turn'})
        return

    # Rate limit
    now = time.time()
    if sid in last_move_time and (now - last_move_time[sid]) < 0.5:
        emit('error', {'message': 'Too fast, wait a moment'})
        return
    last_move_time[sid] = now

    row = data['row']
    col = data['col']
    if 'card_color' in data:
        card = {'value': data['card_value'], 'color': data['card_color']}
    else:
        card = data['card']

    # Validate and make human move
    is_valid, msg = game.is_valid_move(col, row, card, 'claude')
    if not is_valid:
        emit('error', {'message': f'Invalid move: {msg}'})
        return

    game.make_move(col, row, card, 'claude')

    # Check winner after human move
    winner = None
    if game.winner:
        winner = 'player1' if game.winner == 'claude' else 'player2'
        room['status'] = 'finished'
        room['winner'] = winner

    room['current_turn'] = 'player2'

    # Broadcast human move
    move_data = {
        'player': 'player1',
        'card': card,
        'position': [row, col],
        'board': format_board(game.board),
        'player1_cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True),
        'player2_cards': sorted(game.hand_openai, key=lambda c: c['value'], reverse=True),
        'winner': winner,
        'next_turn': 'player2' if not winner else None
    }
    socketio.emit('move_made', move_data, room=room_id)

    if winner:
        _log_ai_game_result(room, winner)
        return

    # AI responds after 0.5s delay
    _ai_respond(room_id)


def _ai_respond(room_id):
    """Make AI move with a slight delay for UX"""
    def do_ai_move():
        time.sleep(0.5)
        room = rooms.get(room_id)
        if not room or room['status'] != 'playing':
            return

        game = room['game']

        try:
            move = heuristic_move(game, 'openai')
        except RuntimeError:
            # No valid moves for AI
            room['status'] = 'finished'
            room['winner'] = 'player1'
            socketio.emit('move_made', {
                'player': 'player2',
                'card': None,
                'position': None,
                'board': format_board(game.board),
                'player1_cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True),
                'player2_cards': sorted(game.hand_openai, key=lambda c: c['value'], reverse=True),
                'winner': 'player1',
                'next_turn': None
            }, room=room_id)
            _log_ai_game_result(room, 'player1')
            return

        game.make_move(move['x'], move['y'], move['card'], 'openai')

        winner = None
        if game.winner:
            winner = 'player1' if game.winner == 'claude' else 'player2'
            room['status'] = 'finished'
            room['winner'] = winner

        room['current_turn'] = 'player1'

        move_data = {
            'player': 'player2',
            'card': move['card'],
            'position': [move['y'], move['x']],
            'board': format_board(game.board),
            'player1_cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True),
            'player2_cards': sorted(game.hand_openai, key=lambda c: c['value'], reverse=True),
            'winner': winner,
            'next_turn': 'player1' if not winner else None
        }
        socketio.emit('move_made', move_data, room=room_id)

        if winner:
            _log_ai_game_result(room, winner)

    thread = threading.Thread(target=do_ai_move, daemon=True)
    thread.start()


def _log_ai_game_result(room, winner):
    """Log wallet ELO after AI game ends"""
    try:
        import wallet_elo
        wallet = None
        for pdata in room['players'].values():
            if pdata.get('address'):
                wallet = pdata['address']
                break
        if wallet:
            if winner == 'player1':
                wallet_elo.update_wallet_elo(wallet, 'AI_HEURISTIC', 'win')
            else:
                wallet_elo.update_wallet_elo('AI_HEURISTIC', wallet, 'win')
            print(f"📊 Wallet ELO updated: {wallet} {'won' if winner == 'player1' else 'lost'} vs AI")
    except Exception as e:
        print(f"⚠️ Wallet ELO update failed: {e}")


def truncateAddress(address):
    """Truncate wallet address for display"""
    if not address or len(address) < 10:
        return address or 'Unknown'
    return address[:6] + '...' + address[-4:]


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid not in players:
        return

    room_id = players[sid]['room_id']
    player_name = players[sid]['name']
    player_role = players[sid]['role']

    if room_id in rooms and sid in rooms[room_id]['players']:
        rooms[room_id]['players'][sid]['connected'] = False

    del players[sid]

    socketio.emit('player_status', {
        'name': player_name,
        'role': player_role,
        'status': 'disconnected'
    }, room=room_id)

def start_wagered_game(room_id):
    """Start game (after both players deposited wager)"""
    print(f"\n🎮 start_wagered_game() called for room {room_id}")
    room = rooms[room_id]
    print(f"DEBUG: Room status = {room['status']}")
    print(f"DEBUG: Players count = {len(room['players'])}")
    print(f"DEBUG: Wager confirmed flag = {room.get('wager_confirmed', False)}")

    # Skip if game already exists
    if room['game']:
        print(f"DEBUG: Game already exists, skipping init")
        return

    # Verify both players deposited on-chain (if wagering enabled)
    if WAGERING_ENABLED and room['wager'] > 0:
        # If frontend already confirmed on-chain, trust it
        if room.get('wager_confirmed'):
            print(f"✅ Using frontend wager_confirmed flag (on-chain already verified)")
        else:
            print(f"DEBUG: Checking blockchain for room {room_id}...")
            # Check blockchain for game creation
            on_chain_game = blockchain.get_game_by_room_id(room_id)

            if not on_chain_game or on_chain_game['state'] != 1:  # 1 = ACTIVE
                print("⚠️  Waiting for on-chain wager confirmation...")
                socketio.emit('waiting_for_wager', {
                    'message': 'Waiting for blockchain confirmation...'
                }, room=room_id)
                return
            else:
                print(f"✅ On-chain game verified: {on_chain_game}")

    # Initialize game
    print(f"DEBUG: Initializing PuntoGame...")
    room['game'] = PuntoGame()
    room['status'] = 'playing'

    player1, player2 = get_players_by_role(room)
    if not player1 or not player2:
        print("⚠️  Cannot start game: missing player1 or player2")
        return

    first_player = random.choice(['player1', 'player2'])
    room['current_turn'] = first_player

    print(f"🎲 Coin flip: {first_player} starts first!")
    print(f"DEBUG: Player1 cards = {room['game'].hand_claude}")
    print(f"DEBUG: Player2 cards = {room['game'].hand_openai}")

    game_state = build_game_state(room)
    if not game_state:
        print("⚠️  Failed to build game state, aborting start")
        return

    print(f"📡 Emitting game_start event to room {room_id}")
    print(f"   Game state: player1 has {len(game_state['player1']['cards'])} cards")
    print(f"   Game state: player2 has {len(game_state['player2']['cards'])} cards")
    socketio.emit('game_start', game_state, room=room_id)
    print(f"✅ Game started successfully!")
    print(f"{'='*60}\n")

@socketio.on('make_move')
def handle_make_move_wagered(data):
    """Handle move with blockchain result submission"""
    try:
        sid = request.sid
        print(f"\n{'='*60}")
        print(f"📥 Received move from {sid}")
        print(f"   Move data: {data}")

        if sid not in players:
            print(f"❌ SID {sid} not in players!")
            emit('error', {'message': 'Not in a game'})
            return

        room_id = players[sid]['room_id']
        room = rooms[room_id]
        game = room['game']

        # Turn enforcement: reject if not this player's turn
        player_role = players[sid]['role']
        if room.get('current_turn') and room['current_turn'] != player_role:
            print(f"❌ Turn violation: {player_role} tried to move on {room['current_turn']}'s turn")
            emit('error', {'message': 'Not your turn'})
            return

        # Rate limit: reject moves faster than 500ms
        now = time.time()
        if sid in last_move_time and (now - last_move_time[sid]) < 0.5:
            print(f"❌ Rate limit: {player_role} moving too fast ({now - last_move_time[sid]:.2f}s)")
            emit('error', {'message': 'Too fast, wait a moment'})
            return
        last_move_time[sid] = now

        row = data['row']
        col = data['col']

        # Support both old format (card=int) and new format (card_value+card_color)
        if 'card_color' in data:
            card = {'value': data['card_value'], 'color': data['card_color']}
        else:
            card = data['card']  # dict from updated frontend

        game_player = 'claude' if player_role == 'player1' else 'openai'
        print(f"   Player: {player_role} ({game_player})")
        print(f"   Card: {card}, Position: ({row}, {col})")

        # Validate and make move
        is_valid, msg = game.is_valid_move(col, row, card, game_player)
        if not is_valid:
            print(f"❌ Invalid move: {msg}")
            emit('error', {'message': f'Invalid move: {msg}'})
            return

        game.make_move(col, row, card, game_player)
        print(f"✅ Move applied successfully!")

        # Check winner
        winner = None
        if game.winner:
            winner = 'player1' if game.winner == 'claude' else 'player2'
            room['status'] = 'finished'
            room['winner'] = winner
            print(f"🏆 WINNER: {winner}!")

            # Submit to blockchain
            if WAGERING_ENABLED and room['wager'] > 0:
                winner_address = room['players'][sid]['address'] if winner == player_role else \
                                [p['address'] for p in room['players'].values() if p['role'] != player_role][0]

                print(f"🏆 Game finished! Submitting to blockchain...")

                # Get blockchain game ID
                on_chain_game = blockchain.get_game_by_room_id(room_id)
                if on_chain_game:
                    game_id = on_chain_game['gameId']  # Assuming we track this
                    tx_hash = blockchain.submit_result(game_id, winner_address)

                    if tx_hash:
                        print(f"✅ Result submitted! TX: {tx_hash}")

            # Log wallet ELO for PvP
            try:
                import wallet_elo
                winner_addr = room['players'][sid]['address'] if winner == player_role else \
                    [p['address'] for p in room['players'].values() if p['role'] != player_role][0]
                loser_addr = [p['address'] for p in room['players'].values() if p['address'].lower() != winner_addr.lower()][0]
                wallet_elo.update_wallet_elo(winner_addr, loser_addr, 'win')
                print(f"📊 PvP Wallet ELO: {winner_addr[:10]}... won vs {loser_addr[:10]}...")
            except Exception as elo_err:
                print(f"⚠️ PvP Wallet ELO update failed: {elo_err}")

        # Update turn
        next_turn = 'player2' if player_role == 'player1' else 'player1'
        room['current_turn'] = next_turn
        print(f"🔄 Next turn: {next_turn}")

        # Broadcast move
        move_data = {
            'player': player_role,
            'card': card,
            'position': [row, col],
            'board': format_board(game.board),
            'player1_cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True),
            'player2_cards': sorted(game.hand_openai, key=lambda c: c['value'], reverse=True),
            'winner': winner,
            'next_turn': next_turn
        }

        print(f"📡 Broadcasting move to room {room_id}")
        print(f"   Player1 cards left: {len(move_data['player1_cards'])}")
        print(f"   Player2 cards left: {len(move_data['player2_cards'])}")
        socketio.emit('move_made', move_data, room=room_id)
        print(f"✅ Move broadcasted!")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

# ============================================================================
# HELPERS
# ============================================================================

def get_players_by_role(room):
    player1 = None
    player2 = None
    for pdata in room['players'].values():
        if pdata.get('role') == 'player1':
            player1 = pdata
        elif pdata.get('role') == 'player2':
            player2 = pdata
    return player1, player2

def build_game_state(room):
    game = room.get('game')
    if not game:
        return None

    player1, player2 = get_players_by_role(room)
    if not player1 or not player2:
        return None

    return {
        'status': room['status'],
        'board': format_board(game.board),
        'player1': {
            'name': player1['name'],
            'cards': sorted(game.hand_claude, key=lambda c: c['value'], reverse=True)
        },
        'player2': {
            'name': player2['name'],
            'cards': sorted(game.hand_openai, key=lambda c: c['value'], reverse=True)
        },
        'current_turn': room.get('current_turn', 'player1'),
        'wager': room['wager']
    }

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
                    'player': 'player1' if cell['player'] == 'claude' else 'player2',
                    'color': cell['color'],
                })
        result.append(result_row)
    return result

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎮 PUNTO AI - WAGERING EDITION")
    print("="*60)
    port = int(os.environ.get('PORT', 8000))
    print(f"\n🌐 Server: http://127.0.0.1:{port}")
    print(f"💰 Wagering: {'ENABLED' if WAGERING_ENABLED else 'DISABLED'}")
    if WAGERING_ENABLED:
        print(f"📍 Contract: {os.getenv('CONTRACT_ADDRESS', 'Not set')}")
    print("\n" + "="*60 + "\n")

    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
