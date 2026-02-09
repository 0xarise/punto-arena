"""
AI Player - integration with Claude and OpenAI API
Updated for 4-color Punto rules (5-in-a-row of same color to win).
"""

import json
import re
from typing import Dict, List, Optional


COLOR_SYMBOLS = {'red': 'R', 'blue': 'B', 'green': 'G', 'yellow': 'Y'}


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
        """
        Get move from AI.
        hand: list of {'value': int, 'color': str}
        Returns: {"x": int, "y": int, "card": {'value': int, 'color': str}, "reasoning": str}
        """
        prompt = self._create_prompt(board, hand, opponent_hand_size)

        try:
            if self.api_type == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                move_text = response.content[0].text
            elif self.api_type == "gemini":
                response = self.client.generate_content(prompt)
                move_text = response.text
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                move_text = response.choices[0].message.content

            move = self._parse_move(move_text, hand)
            self.move_history.append(move)
            return move

        except Exception as e:
            print(f"AI Error ({self.api_type}): {e}")
            return self._random_fallback_move(board, hand)

    def _create_prompt(self, board: List[List], hand: List[Dict], opponent_hand_size: int) -> str:
        board_str = self._format_board_for_ai(board)

        # Format hand for display
        hand_str = ", ".join(f"{COLOR_SYMBOLS[c['color']]}{c['value']}" for c in hand)

        if self.player_name == "claude":
            my_colors = "RED (R) and BLUE (B)"
            opp_colors = "GREEN (G) and YELLOW (Y)"
        else:
            my_colors = "GREEN (G) and YELLOW (Y)"
            opp_colors = "RED (R) and BLUE (B)"

        prompt = f"""You are playing PUNTO as player "{self.player_name}".

RULES:
- 6x6 board (coordinates x,y from 0 to 5)
- Each player has 2 COLORS. Your colors: {my_colors}. Opponent: {opp_colors}.
- WIN: Place 5 cards of the SAME COLOR in a line (horizontal, vertical, or diagonal)
- You can play on:
  * Empty cells (shown as ".")
  * ANY occupied cell, but ONLY if your card has a STRICTLY HIGHER value
- You CAN capture your own cards too (if higher value)

BOARD:
{board_str}

YOUR HAND: [{hand_str}]
OPPONENT HAND SIZE: {opponent_hand_size}

STRATEGY:
1. Priority: Check if you can win (5 same-color in a line)
2. Block opponent if they have 4 same-color in a line
3. Build same-color lines (aim for 3-4 in a row of one color)
4. Capture weak opponent cards strategically

RESPOND WITH ONLY JSON:
{{
  "x": <column 0-5>,
  "y": <row 0-5>,
  "card_value": <value from your hand>,
  "card_color": "<color from your hand: red/blue/green/yellow>",
  "reasoning": "brief strategy (1-2 sentences)"
}}

IMPORTANT:
- You MUST play a card from your hand
- Coordinates must be 0-5
- Output ONLY the JSON, nothing else
"""
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
        result += "\nLegend: R=Red, B=Blue (Player claude), G=Green, Y=Yellow (Player openai), .=empty"
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
                # Fallback: old format (just int) - pick first hand card with that value
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
