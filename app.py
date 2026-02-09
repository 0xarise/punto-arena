"""
Punto AI Web Game - Flask Backend
Human vs AI gameplay
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
from datetime import datetime
import secrets

# Import our existing game logic
from game_logic import PuntoGame
from ai_player import AIPlayer

# Get absolute paths
import os
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'templates'))
app.secret_key = secrets.token_hex(16)
CORS(app)

# Game sessions storage (in production, use Redis/database)
games = {}

# Cost tracking
COSTS = {
    'claude-sonnet': 0.10,  # avg per game
    'gpt-4o': 0.08,
    'claude-opus': 0.35,
    'o1': 1.50
}

# Daily limits
MAX_GAMES_PER_SESSION = 20
session_games_played = {}

@app.route('/')
def index():
    """Main game page"""
    return render_template('index.html')

@app.route('/test')
def test():
    """Test endpoint"""
    return jsonify({
        'status': 'ok',
        'static_folder': app.static_folder,
        'template_folder': app.template_folder
    })

@app.route('/api/new_game', methods=['POST'])
def new_game():
    """Start a new game"""
    data = request.json
    ai_model = data.get('ai_model', 'claude-sonnet')

    # Check daily limit
    session_id = request.remote_addr
    if session_id not in session_games_played:
        session_games_played[session_id] = 0

    if session_games_played[session_id] >= MAX_GAMES_PER_SESSION:
        return jsonify({
            'error': f'Daily limit reached ({MAX_GAMES_PER_SESSION} games)',
            'games_played': session_games_played[session_id]
        }), 429

    # Create new game
    game_id = secrets.token_urlsafe(16)
    game = PuntoGame()

    # Initialize AI player  (AI will play as "openai" player in game logic)
    if ai_model == 'claude-sonnet':
        ai = AIPlayer("AI", api_type="claude", model="claude-sonnet-4-5-20250929")
    elif ai_model == 'gpt-4o':
        ai = AIPlayer("AI", api_type="openai", model="gpt-4o")
    elif ai_model == 'claude-opus':
        ai = AIPlayer("AI", api_type="claude", model="claude-opus-4-5-20251101")
    elif ai_model == 'o1':
        ai = AIPlayer("AI", api_type="openai", model="o1")
    else:
        return jsonify({'error': 'Invalid AI model'}), 400

    # Store game state
    # Human plays as "claude", AI plays as "openai" in game logic
    games[game_id] = {
        'game': game,
        'ai': ai,
        'ai_model': ai_model,
        'started': datetime.now().isoformat(),
        'cost_estimate': COSTS[ai_model]
    }

    session_games_played[session_id] = session_games_played.get(session_id, 0) + 1

    return jsonify({
        'game_id': game_id,
        'human_cards': sorted(game.get_hand("claude"), key=lambda c: c['value'], reverse=True),
        'ai_model': ai_model,
        'cost_estimate': COSTS[ai_model],
        'games_remaining': MAX_GAMES_PER_SESSION - session_games_played[session_id]
    })

@app.route('/api/make_move', methods=['POST'])
def make_move():
    """Human makes a move, then AI responds"""
    data = request.json
    game_id = data.get('game_id')
    row = data.get('row')
    col = data.get('col')

    # Support dict card from updated frontend
    if 'card_color' in data:
        card = {'value': data['card_value'], 'color': data['card_color']}
    else:
        card = data.get('card')  # dict from frontend

    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404

    game_data = games[game_id]
    game = game_data['game']
    ai = game_data['ai']

    # Validate and make human move (human is "claude" player)
    is_valid, msg = game.is_valid_move(col, row, card, "claude")
    if not is_valid:
        return jsonify({'error': f'Invalid move: {msg}'}), 400

    game.make_move(col, row, card, "claude")

    # Check if human won
    if game.winner == "claude":
        return jsonify({
            'status': 'game_over',
            'winner': 'human',
            'board': format_board_for_frontend(game.board),
            'message': '🎉 You won!',
            'turns': game.current_turn
        })

    # Check if game over (no more moves possible)
    human_hand = game.get_hand("claude")
    ai_hand = game.get_hand("openai")

    if not ai_hand:
        return jsonify({
            'status': 'game_over',
            'winner': 'draw',
            'board': format_board_for_frontend(game.board),
            'message': 'Game ended in a draw'
        })

    # AI's turn (AI is "openai" player)
    try:
        board_state = game.get_board_state()
        print(f"🤖 AI thinking... (hand: {ai_hand})")

        ai_move = ai.get_move(board_state, ai_hand, len(human_hand))
        print(f"✅ AI move received: {ai_move}")

        # Extract move details
        ai_card = ai_move['card']
        ai_col = ai_move['x']
        ai_row = ai_move['y']
        ai_reasoning = ai_move.get('reasoning', 'No reasoning provided')

        # Make AI move
        game.make_move(ai_col, ai_row, ai_card, "openai")

        # Check if AI won
        if game.winner == "openai":
            return jsonify({
                'status': 'game_over',
                'winner': 'ai',
                'board': format_board_for_frontend(game.board),
                'ai_move': {
                    'card': ai_card,
                    'position': [ai_row, ai_col],
                    'reasoning': ai_reasoning,
                    'confidence': 8
                },
                'message': f'🤖 {game_data["ai_model"]} won!',
                'turns': game.current_turn
            })

        # Game continues
        return jsonify({
            'status': 'playing',
            'board': format_board_for_frontend(game.board),
            'ai_move': {
                'card': ai_card,
                'position': [ai_row, ai_col],
                'reasoning': ai_reasoning,
                'confidence': 8
            },
            'human_cards': sorted(game.get_hand("claude"), key=lambda c: c['value'], reverse=True),
            'ai_cards_count': len(game.get_hand("openai"))
        })

    except Exception as e:
        print(f"AI Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'AI error: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/api/game_state/<game_id>')
def game_state(game_id):
    """Get current game state"""
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404

    game_data = games[game_id]
    game = game_data['game']

    return jsonify({
        'board': format_board_for_frontend(game.board),
        'human_cards': sorted(game.get_hand("claude"), key=lambda c: c['value'], reverse=True),
        'ai_cards_count': len(game.get_hand("openai")),
        'turn': game.current_turn
    })

@app.route('/api/stats')
def stats():
    """Get usage stats"""
    session_id = request.remote_addr
    games_played = session_games_played.get(session_id, 0)

    return jsonify({
        'games_played': games_played,
        'games_remaining': MAX_GAMES_PER_SESSION - games_played,
        'active_games': len(games)
    })

def format_board_for_frontend(board):
    """Convert board format for frontend"""
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

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎮 PUNTO AI WEB GAME")
    print("="*60)
    print("\n🌐 Starting server at http://localhost:8000")
    print("🤖 AI Models available: Claude Sonnet, GPT-4o, Claude Opus")
    print(f"📊 Daily limit: {MAX_GAMES_PER_SESSION} games per session")
    print("\n" + "="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=8000)
