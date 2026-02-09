"""
Punto Game Logic
Full rules: 4 colors (2 per player), 5-in-a-row of SAME COLOR to win.
"""

import random

# Player 1 (claude) uses RED + BLUE, Player 2 (openai) uses GREEN + YELLOW
PLAYER_COLORS = {
    'claude': ['red', 'blue'],
    'openai': ['green', 'yellow'],
}

COLOR_SYMBOLS = {'red': 'R', 'blue': 'B', 'green': 'G', 'yellow': 'Y'}


def _color_to_player(color):
    """Return which player owns a given color."""
    for player, colors in PLAYER_COLORS.items():
        if color in colors:
            return player
    return None


class PuntoGame:
    def __init__(self):
        self.board = [[None for _ in range(6)] for _ in range(6)]
        self.current_turn = 0
        self.winner = None

        # Deck: 9 cards per color (values 1-9), 2 colors per player = 18 cards each
        self.deck_claude = [{'value': v, 'color': c}
                           for c in PLAYER_COLORS['claude'] for v in range(1, 10)]
        self.deck_openai = [{'value': v, 'color': c}
                           for c in PLAYER_COLORS['openai'] for v in range(1, 10)]

        # Current hand (2 cards each)
        self.hand_claude = []
        self.hand_openai = []

        self._deal_initial_cards()

    def _deal_initial_cards(self):
        """Deal 2 cards to each player."""
        random.shuffle(self.deck_claude)
        random.shuffle(self.deck_openai)

        self.hand_claude = [self.deck_claude.pop(), self.deck_claude.pop()]
        self.hand_openai = [self.deck_openai.pop(), self.deck_openai.pop()]

    def is_valid_move(self, x, y, card, player):
        """Check if move is valid. card is a dict {value, color}."""
        if not (0 <= x < 6 and 0 <= y < 6):
            return False, "Coordinates out of bounds"

        hand = self.hand_claude if player == "claude" else self.hand_openai
        if card not in hand:
            return False, f"You don't have card {card} in hand"

        cell = self.board[y][x]

        if cell is None:
            return True, "OK"

        # Can capture any card (own or opponent) with strictly higher value
        if cell['value'] < card['value']:
            return True, "OK - capture"

        return False, f"Cannot play {card['value']} on cell with {cell['value']}"

    def make_move(self, x, y, card, player):
        """Execute a move."""
        is_valid, message = self.is_valid_move(x, y, card, player)

        if not is_valid:
            raise ValueError(f"Invalid move: {message}")

        hand = self.hand_claude if player == "claude" else self.hand_openai
        hand.remove(card)

        self.board[y][x] = {
            'player': player,
            'value': card['value'],
            'color': card['color'],
        }

        deck = self.deck_claude if player == "claude" else self.deck_openai
        if deck:
            hand.append(deck.pop())

        self.current_turn += 1
        self._check_winner()
        return True

    def _check_winner(self):
        """Check for 5 cards of the SAME COLOR in a line."""
        for color in ['red', 'blue', 'green', 'yellow']:
            # Horizontal
            for y in range(6):
                for x in range(2):  # 6-5+1 = 2 starting positions
                    if self._check_line_color(x, y, 1, 0, 5, color):
                        player = _color_to_player(color)
                        print(f"  WIN: {player} ({color}) - Horizontal at row={y}, col={x}")
                        self.winner = player
                        return

            # Vertical
            for x in range(6):
                for y in range(2):
                    if self._check_line_color(x, y, 0, 1, 5, color):
                        player = _color_to_player(color)
                        print(f"  WIN: {player} ({color}) - Vertical at col={x}, row={y}")
                        self.winner = player
                        return

            # Diagonal down-right
            for x in range(2):
                for y in range(2):
                    if self._check_line_color(x, y, 1, 1, 5, color):
                        player = _color_to_player(color)
                        print(f"  WIN: {player} ({color}) - Diagonal DR at ({x},{y})")
                        self.winner = player
                        return

            # Diagonal down-left
            for x in range(4, 6):
                for y in range(2):
                    if self._check_line_color(x, y, -1, 1, 5, color):
                        player = _color_to_player(color)
                        print(f"  WIN: {player} ({color}) - Diagonal DL at ({x},{y})")
                        self.winner = player
                        return

    def _check_line_color(self, start_x, start_y, dx, dy, length, color):
        """Check if there is a line of `length` cells of the given color."""
        for i in range(length):
            x = start_x + i * dx
            y = start_y + i * dy

            if not (0 <= x < 6 and 0 <= y < 6):
                return False

            cell = self.board[y][x]
            if cell is None or cell['color'] != color:
                return False

        return True

    def is_game_over(self):
        """Check if game is over."""
        if self.winner:
            return True

        if not self.hand_claude and not self.deck_claude:
            if not self.hand_openai and not self.deck_openai:
                return True

        return False

    def get_board_state(self):
        """Return current board state."""
        return self.board

    def get_hand(self, player):
        """Return player's hand."""
        if player == "claude":
            return self.hand_claude.copy()
        else:
            return self.hand_openai.copy()

    def format_board(self):
        """Format board for CLI display with color symbols."""
        result = "\n  0  1  2  3  4  5\n"
        for y in range(6):
            result += f"{y} "
            for x in range(6):
                cell = self.board[y][x]
                if cell is None:
                    result += "..  "
                else:
                    sym = COLOR_SYMBOLS.get(cell['color'], '?')
                    result += f"{sym}{cell['value']} "
            result += "\n"
        return result
