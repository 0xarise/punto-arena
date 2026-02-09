#!/usr/bin/env python3
"""
Punto AI - CLI Client for Terminal Play
Connect via Socket.io and play from command line
"""

import socketio
import time
import sys

sio = socketio.Client()

# Game state
game = {
    'room_id': None,
    'player_name': None,
    'my_cards': [],
    'board': [[None]*6 for _ in range(6)],
    'my_turn': False,
    'role': None
}

# ============================================================================
# SOCKET.IO EVENT HANDLERS
# ============================================================================

@sio.on('connect')
def on_connect():
    print('✅ Connected to server')
    print(f'   Socket ID: {sio.sid}\n')

    # AUTO-REJOIN after reconnect
    if game['room_id'] and game['player_name']:
        print('🔄 Reconnected! Rejoining room...')
        sio.emit('join_wagered_room', {
            'room_id': game['room_id'],
            'name': game['player_name'],
            'address': '0xBeru000000000000000000000000000000000000'
        })

@sio.on('player_joined')
def on_player_joined(data):
    print(f'👤 Player joined: {data["name"]} ({data["role"]})')
    print(f'   Players in room: {data["players_count"]}/2\n')

@sio.on('game_start')
def on_game_start(data):
    print('\n' + '='*50)
    print('🎮 GAME STARTED!')
    print('='*50)

    print(f'\n🔵 Player 1: {data["player1"]["name"]}')
    print(f'🔴 Player 2: {data["player2"]["name"]}\n')

    # Set my cards
    if game['role'] == 'player1':
        game['my_cards'] = data['player1']['cards']
    else:
        game['my_cards'] = data['player2']['cards']

    game['my_turn'] = (data['current_turn'] == game['role'])

    print_board(data['board'])
    print_my_cards()

    if game['my_turn']:
        # ALERT: Your turn!
        print('\a')  # Terminal bell
        print('\n' + '='*50)
        print('🔔 ' + '🟢 YOUR TURN!' + ' 🔔')
        print('='*50)

        # Try system notification (macOS)
        try:
            import subprocess
            subprocess.run([
                'osascript', '-e',
                'display notification "Your turn to play!" with title "🎮 Punto AI"'
            ], capture_output=True)
        except:
            pass

        prompt_move()
    else:
        print('\n🔴 Waiting for opponent...')

@sio.on('move_made')
def on_move_made(data):
    player = '🔵' if data['player'] == 'player1' else '🔴'
    print(f'\n{player} Move: Card {data["card"]} → ({data["position"][0]}, {data["position"][1]})')

    # Update state
    game['board'] = data['board']

    if game['role'] == 'player1':
        game['my_cards'] = data['player1_cards']
    else:
        game['my_cards'] = data['player2_cards']

    game['my_turn'] = (data['next_turn'] == game['role'])

    print_board(data['board'])

    if data.get('winner'):
        winner = '🔵 Player 1' if data['winner'] == 'player1' else '🔴 Player 2'
        print(f'\n🏆 GAME OVER! Winner: {winner}\n')
        sys.exit(0)

    if game['my_turn']:
        print_my_cards()

        # ALERT: Your turn!
        print('\a')  # Terminal bell
        print('\n' + '='*50)
        print('🔔 ' + '🟢 YOUR TURN!' + ' 🔔')
        print('='*50)

        # Try system notification (macOS)
        try:
            import subprocess
            subprocess.run([
                'osascript', '-e',
                'display notification "Your turn to play!" with title "🎮 Punto AI"'
            ], capture_output=True)
        except:
            pass

        prompt_move()
    else:
        print('\n🔴 Waiting for opponent...')

@sio.on('game_end')
def on_game_end(data):
    winner = '🔵 Player 1' if data['winner'] == 'player1' else '🔴 Player 2'
    print(f'\n' + '='*50)
    print(f'🏆 GAME OVER!')
    print(f'Winner: {winner}')
    if data.get('payout', 0) > 0:
        print(f'💰 Payout: ${data["payout"]}')
    print('='*50 + '\n')

@sio.on('game_state_restored')
def on_game_state_restored(data):
    """Handle rejoining mid-game"""
    print('\n' + '='*50)
    print('🔄 GAME STATE RESTORED!')
    print('='*50)

    # Restore game state
    game['board'] = data['board']
    game['my_cards'] = data['your_cards']
    game['role'] = data['your_role']
    game['my_turn'] = (data['current_turn'] == game['role'])

    print(f'\n✅ Reconnected as {game["role"]}')
    print_board(data['board'])
    print_my_cards()

    if game['my_turn']:
        # ALERT: Your turn!
        print('\a')  # Terminal bell
        print('\n' + '='*50)
        print('🔔 ' + '🟢 YOUR TURN!' + ' 🔔')
        print('='*50)

        # Try system notification (macOS)
        try:
            import subprocess
            subprocess.run([
                'osascript', '-e',
                'display notification "Your turn to play!" with title "🎮 Punto AI"'
            ], capture_output=True)
        except:
            pass

        prompt_move()
    else:
        print('\n🔴 Waiting for opponent...')

@sio.on('error')
def on_error(data):
    print(f'❌ Error: {data["message"]}')

# ============================================================================
# GAME FUNCTIONS
# ============================================================================

def print_board(board):
    print('\n  0  1  2  3  4  5')
    print('  ┌──┬──┬──┬──┬──┬──┐')
    for row in range(6):
        print(f'{row} │', end='')
        for col in range(6):
            cell = board[row][col]
            if cell is None:
                print('· │', end='')
            elif cell['player'] == 'player1':
                print(f'\033[94m{cell["card"]}\033[0m│', end='')  # Blue
            else:
                print(f'\033[91m{cell["card"]}\033[0m│', end='')  # Red
        print()
        if row < 5:
            print('  ├──┼──┼──┼──┼──┼──┤')
    print('  └──┴──┴──┴──┴──┴──┘')

def print_my_cards():
    print(f'\n🃏 Your cards: {game["my_cards"]}')

def prompt_move():
    while True:
        try:
            print('\nEnter move (format: card row col):')
            print('Example: 7 2 3  (play card 7 at row 2, col 3)')

            inp = input('> ').strip().split()

            if len(inp) != 3:
                print('❌ Invalid format. Use: card row col')
                continue

            card = int(inp[0])
            row = int(inp[1])
            col = int(inp[2])

            if card not in game['my_cards']:
                print(f'❌ You don\'t have card {card}')
                continue

            if not (0 <= row <= 5 and 0 <= col <= 5):
                print('❌ Invalid position. Row and col must be 0-5')
                continue

            # Send move
            sio.emit('make_move', {
                'card': card,
                'row': row,
                'col': col
            })

            game['my_turn'] = False
            print('\n⏳ Sending move...')
            break

        except ValueError:
            print('❌ Invalid input. Use numbers only.')
        except KeyboardInterrupt:
            print('\n\n👋 Goodbye!')
            sys.exit(0)

def join_room(room_id, player_name):
    game['room_id'] = room_id
    game['player_name'] = player_name

    print(f'🔗 Joining room: {room_id}')
    print(f'👤 Player name: {player_name}\n')

    sio.emit('join_wagered_room', {
        'room_id': room_id,
        'name': player_name
    })

    # Determine role (rough guess, server will confirm)
    game['role'] = 'player2'  # Usually second to join

# ============================================================================
# MAIN
# ============================================================================

def main():
    print('='*50)
    print('🎮 PUNTO AI - CLI CLIENT')
    print('='*50)

    if len(sys.argv) < 3:
        print('\nUsage:')
        print('  python cli_client.py <room_id> <your_name>')
        print('\nExample:')
        print('  python cli_client.py DqVCC_3AO5s Beru')
        sys.exit(1)

    room_id = sys.argv[1]
    player_name = sys.argv[2]

    # Connect
    print('\n⏳ Connecting to server...')
    server_url = sys.argv[3] if len(sys.argv) > 3 else 'http://127.0.0.1:8000'
    sio.connect(server_url)

    # Join room
    time.sleep(0.5)
    join_room(room_id, player_name)

    # Keep running
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print('\n\n👋 Goodbye!')
        sio.disconnect()

if __name__ == '__main__':
    main()
