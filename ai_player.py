"""
AI Player - integration with Claude and OpenAI API
Updated for 4-color Punto rules (5-in-a-row of same color to win).
Enhanced with board analysis and tactical prompting for stronger play.
"""

import json
import re
from typing import Dict, List, Optional, Tuple


COLOR_SYMBOLS = {'red': 'R', 'blue': 'B', 'green': 'G', 'yellow': 'Y'}
PLAYER_COLORS = {
    'claude': ['red', 'blue'],
    'openai': ['green', 'yellow'],
}

SYSTEM_PROMPT = """You are an expert Punto card game AI. You play strategically and precisely.

Key principles:
- SAME COLOR lines win. 5 cards of ONE color in a row/column/diagonal.
- You have 2 colors. Focus on building ONE color's line rather than scattering both.
- Captures are powerful: placing a higher card on an opponent's card removes their piece.
- Center control matters early game; line completion matters late game.
- ALWAYS block an opponent's 4-in-a-line — it's an instant loss otherwise.
- When you have 4-in-a-line, complete it if possible.
- Use your high-value cards (7-9) for captures and critical positions. Don't waste them on empty cells early.
- Use low-value cards (1-3) to fill empty cells and extend lines.

You must respond with ONLY a JSON object. No explanation outside the JSON."""


class AIPlayer:
    def __init__(self, player_name: str, api_type: str = "claude", model: Optional[str] = None):
        self.player_name = player_name
        self.api_type = api_type
        self.move_history = []

        if api_type == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic()
                self.model = model or "claude-sonnet-4-5-20250929"
            except ImportError:
                raise ImportError("Install: pip install anthropic")
        elif api_type == "openai":
            try:
                import openai
                self.client = openai.OpenAI()
                self.model = model or "gpt-4o"
            except ImportError:
                raise ImportError("Install: pip install openai")
        elif api_type == "gemini":
            try:
                import google.generativeai as genai
                import os
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                self.model = model or "gemini-2.0-flash"
                self.client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError("Install: pip install google-generativeai")
        else:
            raise ValueError(f"Unknown API type: {api_type}")

    def get_move(self, board: List[List], hand: List[Dict], opponent_hand_size: int) -> Dict:
        prompt = self._create_prompt(board, hand, opponent_hand_size)

        try:
            if self.api_type == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                move_text = response.content[0].text
            elif self.api_type == "gemini":
                response = self.client.generate_content(SYSTEM_PROMPT + "\n\n" + prompt)
                move_text = response.text
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3
                )
                move_text = response.choices[0].message.content

            move = self._parse_move(move_text, hand)
            self.move_history.append(move)
            return move

        except Exception as e:
            print(f"AI Error ({self.api_type}): {e}")
            return self._random_fallback_move(board, hand)

    def _analyze_lines(self, board: List[List]) -> Dict:
        """Scan board for color sequences in all directions. Returns analysis dict."""
        directions = [
            (1, 0, "horizontal"),
            (0, 1, "vertical"),
            (1, 1, "diagonal-DR"),
            (1, -1, "diagonal-UR"),
        ]

        lines = {color: [] for color in ['red', 'blue', 'green', 'yellow']}

        # Scan for sequences of same color
        for dx, dy, dir_name in directions:
            # Determine scan range
            for start_y in range(6):
                for start_x in range(6):
                    # Try to build a sequence from this starting cell
                    cell = board[start_y][start_x]
                    if cell is None:
                        continue

                    color = cell['color']
                    seq = [(start_x, start_y)]
                    x, y = start_x + dx, start_y + dy

                    while 0 <= x < 6 and 0 <= y < 6:
                        c = board[y][x]
                        if c is not None and c['color'] == color:
                            seq.append((x, y))
                            x += dx
                            y += dy
                        else:
                            break

                    if len(seq) >= 2:
                        # Find extension points (empty or capturable cells at both ends)
                        extends = []
                        # Before start
                        bx, by = start_x - dx, start_y - dy
                        if 0 <= bx < 6 and 0 <= by < 6:
                            bc = board[by][bx]
                            if bc is None:
                                extends.append((bx, by, None))
                            else:
                                extends.append((bx, by, bc['value']))
                        # After end
                        ex, ey = seq[-1][0] + dx, seq[-1][1] + dy
                        if 0 <= ex < 6 and 0 <= ey < 6:
                            ec = board[ey][ex]
                            if ec is None:
                                extends.append((ex, ey, None))
                            else:
                                extends.append((ex, ey, ec['value']))

                        # Avoid duplicate sequences (only record if start is the "smallest" point)
                        key = (color, tuple(seq), dir_name)
                        if color not in lines:
                            lines[color] = []

                        # Check we haven't already recorded a superset
                        is_subset = False
                        for existing in lines[color]:
                            if set(seq).issubset(set(existing['cells'])):
                                is_subset = True
                                break
                        if not is_subset:
                            # Remove any subsets of this new sequence
                            lines[color] = [
                                e for e in lines[color]
                                if not set(e['cells']).issubset(set(seq))
                            ]
                            lines[color].append({
                                'length': len(seq),
                                'cells': seq,
                                'direction': dir_name,
                                'extends': extends,
                            })

        return lines

    def _get_valid_moves(self, board: List[List], hand: List[Dict]) -> List[Dict]:
        """Return all valid moves with annotations. Enforces adjacency rule."""
        moves = []
        # Check if board is empty (first move — unrestricted placement)
        board_empty = all(board[r][c] is None for r in range(6) for c in range(6))

        for card in hand:
            for y in range(6):
                for x in range(6):
                    cell = board[y][x]
                    if cell is None:
                        # Adjacency check: must be next to existing card (unless first move)
                        if not board_empty and not self._is_adjacent(board, x, y):
                            continue
                        moves.append({'x': x, 'y': y, 'card': card, 'type': 'place'})
                    elif cell['value'] < card['value']:
                        owner = 'own' if cell['color'] in PLAYER_COLORS.get(self.player_name, []) else 'opponent'
                        moves.append({
                            'x': x, 'y': y, 'card': card,
                            'type': f'capture_{owner}',
                            'captures': f"{COLOR_SYMBOLS[cell['color']]}{cell['value']}"
                        })
        return moves

    @staticmethod
    def _is_adjacent(board, x, y):
        """Check if (x,y) is adjacent (8 directions) to any existing card."""
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < 6 and 0 <= ny < 6:
                    if board[ny][nx] is not None:
                        return True
        return False

    def _format_tactical_analysis(self, board: List[List], hand: List[Dict]) -> str:
        """Pre-compute tactical situation and format as text for the LLM."""
        lines = self._analyze_lines(board)
        my_colors = PLAYER_COLORS.get(self.player_name, [])
        opp_name = 'openai' if self.player_name == 'claude' else 'claude'
        opp_colors = PLAYER_COLORS.get(opp_name, [])

        analysis = []

        # My threats (lines I'm building)
        my_lines = []
        for color in my_colors:
            for line in lines.get(color, []):
                if line['length'] >= 2:
                    my_lines.append((color, line))

        if my_lines:
            analysis.append("YOUR LINES:")
            for color, line in sorted(my_lines, key=lambda x: -x[1]['length']):
                cells_str = " -> ".join(f"({x},{y})" for x, y in line['cells'])
                ext_str = ""
                if line['extends']:
                    exts = []
                    for ex, ey, val in line['extends']:
                        if val is None:
                            exts.append(f"({ex},{ey}) EMPTY")
                        else:
                            exts.append(f"({ex},{ey}) has value {val}")
                    ext_str = f" | Can extend to: {', '.join(exts)}"
                sym = COLOR_SYMBOLS[color]
                analysis.append(f"  {sym} {line['length']}-in-a-row {line['direction']}: {cells_str}{ext_str}")
                if line['length'] == 4:
                    analysis.append(f"  >>> YOU CAN WIN! Extend this {sym} line to 5! <<<")

        # Opponent threats
        opp_lines = []
        for color in opp_colors:
            for line in lines.get(color, []):
                if line['length'] >= 2:
                    opp_lines.append((color, line))

        if opp_lines:
            analysis.append("OPPONENT LINES:")
            for color, line in sorted(opp_lines, key=lambda x: -x[1]['length']):
                cells_str = " -> ".join(f"({x},{y})" for x, y in line['cells'])
                ext_str = ""
                if line['extends']:
                    exts = []
                    for ex, ey, val in line['extends']:
                        if val is None:
                            exts.append(f"({ex},{ey}) EMPTY")
                        else:
                            exts.append(f"({ex},{ey}) has value {val}")
                    ext_str = f" | Extends to: {', '.join(exts)}"
                sym = COLOR_SYMBOLS[color]
                analysis.append(f"  {sym} {line['length']}-in-a-row {line['direction']}: {cells_str}{ext_str}")
                if line['length'] == 4:
                    analysis.append(f"  >>> DANGER! Block this {sym} line or you LOSE! <<<")
                elif line['length'] == 3:
                    analysis.append(f"  ** WARNING: 3-in-a-row threat — consider blocking **")

        if not my_lines and not opp_lines:
            analysis.append("No significant lines yet. Focus on center control and starting a same-color sequence.")

        return "\n".join(analysis)

    def _format_valid_moves_compact(self, board: List[List], hand: List[Dict]) -> str:
        """Format top valid moves for the prompt (keep it concise)."""
        moves = self._get_valid_moves(board, hand)

        # Annotate moves with simple scores for guidance
        annotated = []
        for m in moves:
            note = f"({m['x']},{m['y']}) {COLOR_SYMBOLS[m['card']['color']]}{m['card']['value']}"
            if m['type'] == 'capture_opponent':
                note += f" captures {m.get('captures', '?')}"
            elif m['type'] == 'capture_own':
                note += f" replaces {m.get('captures', '?')}"
            annotated.append(note)

        # Limit to prevent token explosion (show count if truncated)
        if len(annotated) > 20:
            return f"{len(annotated)} valid moves available. Examples:\n" + "\n".join(annotated[:20])
        return f"{len(annotated)} valid moves:\n" + "\n".join(annotated)

    def _create_prompt(self, board: List[List], hand: List[Dict], opponent_hand_size: int) -> str:
        board_str = self._format_board_for_ai(board)
        hand_str = ", ".join(f"{COLOR_SYMBOLS[c['color']]}{c['value']}" for c in hand)

        if self.player_name == "claude":
            my_colors = "RED (R) and BLUE (B)"
            opp_colors = "GREEN (G) and YELLOW (Y)"
        else:
            my_colors = "GREEN (G) and YELLOW (Y)"
            opp_colors = "RED (R) and BLUE (B)"

        # Tactical analysis
        tactics = self._format_tactical_analysis(board, hand)

        # Move history context
        history_str = ""
        if self.move_history:
            recent = self.move_history[-5:]  # Last 5 moves
            hist_parts = []
            for m in recent:
                c = m.get('card', {})
                sym = COLOR_SYMBOLS.get(c.get('color', ''), '?')
                hist_parts.append(f"({m['x']},{m['y']}) {sym}{c.get('value', '?')}")
            history_str = f"\nYOUR RECENT MOVES: {', '.join(hist_parts)}"

        prompt = f"""PUNTO GAME - Your turn as "{self.player_name}"

RULES REMINDER:
- 6x6 board. Win = 5 of SAME COLOR in a line (row/col/diagonal).
- Your colors: {my_colors}. Opponent: {opp_colors}.
- Play on empty cells OR capture any card with STRICTLY higher value.

BOARD:
{board_str}

YOUR HAND: [{hand_str}]
OPPONENT HAND SIZE: {opponent_hand_size}
{history_str}

TACTICAL ANALYSIS:
{tactics}

DECISION GUIDE:
1. If you can complete a 5-in-a-row of your color → DO IT (instant win)
2. If opponent has 4-in-a-row → BLOCK IT (play on their extension point)
3. If you have 3+ in a row → extend it toward 4, then 5
4. If opponent has 3-in-a-row → consider blocking before it becomes 4
5. Otherwise → build lines of your STRONGER color near center
6. Save high cards (7-9) for captures; use low cards (1-3) for empty cells

Respond with ONLY this JSON:
{{
  "x": <column 0-5>,
  "y": <row 0-5>,
  "card_value": <value from your hand>,
  "card_color": "<color from your hand>",
  "reasoning": "1-2 sentence strategy explanation"
}}"""
        return prompt

    def _format_board_for_ai(self, board: List[List]) -> str:
        result = "     0   1   2   3   4   5\n"
        result += "   +---+---+---+---+---+---+\n"

        for y in range(6):
            result += f" {y} |"
            for x in range(6):
                cell = board[y][x]
                if cell is None:
                    result += " . |"
                else:
                    sym = COLOR_SYMBOLS.get(cell.get('color', ''), '?')
                    result += f" {sym}{cell['value']}|"
            result += "\n"
            if y < 5:
                result += "   +---+---+---+---+---+---+\n"

        result += "   +---+---+---+---+---+---+\n"
        result += "\nR=Red, B=Blue (claude) | G=Green, Y=Yellow (openai) | .=empty"
        return result

    def _parse_move(self, response_text: str, hand: List[Dict]) -> Dict:
        try:
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)

            json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)

            if not json_match:
                print(f"  No JSON found in response: {response_text[:300]}")
                raise ValueError("No JSON found in response")

            json_str = json_match.group()
            print(f"  Parsing JSON: {json_str[:200]}")

            raw = json.loads(json_str)

            # Build card dict from response
            if 'card_value' in raw and 'card_color' in raw:
                card = {'value': int(raw['card_value']), 'color': raw['card_color']}
            elif 'card' in raw:
                val = int(raw['card'])
                card = next((c for c in hand if c['value'] == val), hand[0])
            else:
                raise ValueError("Missing card_value/card_color in response")

            move = {
                'x': int(raw['x']),
                'y': int(raw['y']),
                'card': card,
                'reasoning': raw.get('reasoning', 'No reasoning provided'),
            }

            return move

        except Exception as e:
            print(f"  Parse error: {e}")
            print(f"Response text: {response_text[:500]}")
            raise

    def _random_fallback_move(self, board: List[List], hand: List[Dict]) -> Dict:
        import random

        possible_moves = []
        for y in range(6):
            for x in range(6):
                for card in hand:
                    cell = board[y][x]
                    if cell is None or cell['value'] < card['value']:
                        possible_moves.append({'x': x, 'y': y, 'card': card})

        if possible_moves:
            move = random.choice(possible_moves)
            move['reasoning'] = "Fallback move (AI error)"
            return move

        return {
            'x': 0,
            'y': 0,
            'card': hand[0],
            'reasoning': 'Emergency fallback - no options',
        }
