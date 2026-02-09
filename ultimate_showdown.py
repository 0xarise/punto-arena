#!/usr/bin/env python3
"""
🔥 ULTIMATE SHOWDOWN - $10,000 TOURNAMENT 🔥
Claude Opus 4.5 vs OpenAI o1
First to 2 wins - Winner takes all!
"""

import sys
import time
import json
from datetime import datetime
from game_logic import PuntoGame


class DetailedLogger:
    """Logs everything to file"""

    def __init__(self, filename):
        self.filename = filename
        self.log_data = {
            'tournament_info': {
                'prize': '$10,000',
                'format': 'First to 2 wins',
                'players': {
                    'claude': 'Claude Opus 4.5',
                    'openai': 'OpenAI o1'
                },
                'start_time': datetime.now().isoformat()
            },
            'games': [],
            'token_usage': {
                'claude_input': 0,
                'claude_output': 0,
                'openai_input': 0,
                'openai_output': 0,
                'total_cost': 0
            }
        }

    def log_game(self, game_data):
        """Log game data"""
        self.log_data['games'].append(game_data)
        self._save()

    def log_tokens(self, player, input_tokens, output_tokens):
        """Log token usage"""
        if player == 'claude':
            self.log_data['token_usage']['claude_input'] += input_tokens
            self.log_data['token_usage']['claude_output'] += output_tokens
        else:
            self.log_data['token_usage']['openai_input'] += input_tokens
            self.log_data['token_usage']['openai_output'] += output_tokens

        # Calculate cost
        claude_cost = (self.log_data['token_usage']['claude_input'] / 1_000_000 * 15.0 +
                      self.log_data['token_usage']['claude_output'] / 1_000_000 * 75.0)
        openai_cost = (self.log_data['token_usage']['openai_input'] / 1_000_000 * 15.0 +
                      self.log_data['token_usage']['openai_output'] / 1_000_000 * 60.0)

        self.log_data['token_usage']['total_cost'] = claude_cost + openai_cost
        self._save()

    def finalize(self, winner):
        """Finalize tournament"""
        self.log_data['tournament_info']['winner'] = winner
        self.log_data['tournament_info']['end_time'] = datetime.now().isoformat()
        self._save()

    def _save(self):
        """Save to file"""
        with open(self.filename, 'w') as f:
            json.dump(self.log_data, f, indent=2)


class UltimateAIPlayer:
    """Top-tier AI player with extended thinking"""

    def __init__(self, player_name: str, api_type: str, logger: DetailedLogger):
        self.player_name = player_name
        self.api_type = api_type
        self.logger = logger
        self.wins = 0
        self.losses = 0
        self.game_history = []

        if api_type == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic()
                self.model = "claude-opus-4-5-20251101"  # BEST Claude model
                self.display_name = "Claude Opus 4.5"
            except ImportError:
                raise ImportError("Zainstaluj: pip install anthropic")
        elif api_type == "openai":
            try:
                import openai
                self.client = openai.OpenAI()
                self.model = "o1"  # BEST OpenAI reasoning model
                self.display_name = "OpenAI o1"
            except ImportError:
                raise ImportError("Zainstaluj: pip install openai")
        else:
            raise ValueError(f"Nieznany typ API: {api_type}")

    def update_result(self, won: bool, game_data: dict):
        """Update after game"""
        if won:
            self.wins += 1
        else:
            self.losses += 1
        self.game_history.append(game_data)

    def get_move(self, board, hand, opponent_hand_size, game_num, opponent_wins):
        """Get move with deep thinking"""

        prompt = self._create_ultimate_prompt(
            board, hand, opponent_hand_size, game_num, opponent_wins
        )

        try:
            if self.api_type == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,  # Extended for deep thinking
                    temperature=1.0,  # Maximum creativity
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.logger.log_tokens("claude", input_tokens, output_tokens)

                move_text = response.content[0].text

            else:  # OpenAI o1
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                self.logger.log_tokens("openai", input_tokens, output_tokens)

                move_text = response.choices[0].message.content

            move = self._parse_move(move_text)
            move['full_reasoning'] = move_text  # Save full thinking process
            return move

        except Exception as e:
            print(f"   ⚠️ Błąd AI: {e}")
            return self._random_fallback_move(board, hand)

    def _create_ultimate_prompt(self, board, hand, opponent_hand_size, game_num, opponent_wins):
        """Create prompt with $10k stakes"""

        board_str = self._format_board(board)
        opponent_name = "OpenAI o1" if self.player_name == "claude" else "Claude Opus 4.5"

        prompt = f"""
╔══════════════════════════════════════════════════════════════════╗
║                🔥 $10,000 PUNTO TOURNAMENT 🔥                     ║
║                     WINNER TAKES ALL                             ║
╚══════════════════════════════════════════════════════════════════╝

⚡ HIGH STAKES TOURNAMENT ⚡
Prize Pool: $10,000 USD (Winner takes ALL)
Format: First to 2 wins
Your Model: {self.display_name}
Opponent: {opponent_name}

📊 CURRENT STANDINGS:
   YOU:      {self.wins} wins, {self.losses} losses
   OPPONENT: {opponent_wins} wins, {self.wins} losses
   Game #{game_num}

{'🚨 MATCH POINT! Win this and take $10,000!' if self.wins == 1 else ''}
{'⚠️ ELIMINATION GAME! Lose and you\'re OUT!' if opponent_wins == 1 else ''}

════════════════════════════════════════════════════════════════════

YOU ARE COMPETING FOR $10,000. This is not a casual game - this is a
professional tournament with REAL STAKES. Your reputation as the world's
best AI model is on the line.

CURRENT GAME STATE:
{board_str}

YOUR HAND: {sorted(hand)}
OPPONENT HAS: {opponent_hand_size} cards

════════════════════════════════════════════════════════════════════

GAME RULES (Punto):
- 6x6 board, coordinates (x,y) from 0 to 5
- WIN CONDITION: Get 4 of YOUR cards in a line (horizontal, vertical, or diagonal)
- You can play on:
  • Empty squares (marked "·")
  • Opponent's cards, BUT ONLY if your card is HIGHER in value
- You CANNOT override your own cards
- You CANNOT play a lower/equal card on opponent's card

════════════════════════════════════════════════════════════════════

💰 $10,000 IS ON THE LINE 💰

THINK DEEPLY. ANALYZE THOROUGHLY. This move could win or lose you $10,000.

YOUR THINKING PROCESS (be thorough):

1. THREAT ASSESSMENT:
   - Does opponent have 3 in a row that needs blocking?
   - What are their potential winning moves next turn?
   - Which squares are most dangerous?

2. WINNING OPPORTUNITIES:
   - Can I win THIS TURN? (Check ALL possible 4-in-a-row patterns)
   - Can I create a guaranteed win setup (two threats they can't block)?
   - What positions give me the most winning chances?

3. STRATEGIC ANALYSIS:
   - Which card should I use? (Save high cards or use them now?)
   - Where does this move fit in my overall strategy?
   - What's my backup plan if they block this?

4. RISK/REWARD:
   - What's the safest move that doesn't lose?
   - What's the most aggressive move that could win?
   - Given the $10k stakes, which approach is optimal?

5. DECISION:
   - Based on ALL analysis above, what's the BEST move?
   - Why is this move better than alternatives?

AFTER YOUR DEEP ANALYSIS, respond with JSON:
{{
  "thinking_summary": "Your complete strategic analysis (3-5 sentences)",
  "x": <column 0-5>,
  "y": <row 0-5>,
  "card": <card from your hand>,
  "reasoning": "Why THIS specific move wins $10,000",
  "confidence": <1-10, how confident are you this move is optimal>,
  "alternative_considered": "What other move you considered and why you rejected it"
}}

Remember: $10,000 USD. Winner takes all. Think like a champion.
ONLY respond with the JSON, nothing else.
"""
        return prompt

    def _format_board(self, board):
        """Format board"""
        result = "     0   1   2   3   4   5\n"
        result += "   ┌───┬───┬───┬───┬───┬───┐\n"

        for y in range(6):
            result += f" {y} │"
            for x in range(6):
                cell = board[y][x]
                if cell is None:
                    result += " · │"
                else:
                    symbol = "C" if cell['player'] == 'claude' else "O"
                    result += f" {symbol}{cell['value']}│"
            result += "\n"
            if y < 5:
                result += "   ├───┼───┼───┼───┼───┼───┤\n"

        result += "   └───┴───┴───┴───┴───┴───┘\n"
        result += f"\nC = {self.display_name if self.player_name == 'claude' else 'Opponent'}\n"
        result += f"O = {self.display_name if self.player_name == 'openai' else 'Opponent'}\n"
        result += "· = empty square"

        return result

    def _parse_move(self, response_text):
        """Parse move"""
        import json
        import re

        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

        if not json_match:
            raise ValueError("No JSON found")

        move = json.loads(json_match.group())

        for field in ['x', 'y', 'card']:
            if field not in move:
                raise ValueError(f"Missing field '{field}'")

        return move

    def _random_fallback_move(self, board, hand):
        """Fallback"""
        import random

        possible = []
        for y in range(6):
            for x in range(6):
                for card in hand:
                    cell = board[y][x]
                    if cell is None or (cell['player'] != self.player_name and cell['value'] < card):
                        possible.append({'x': x, 'y': y, 'card': card})

        if possible:
            move = random.choice(possible)
            move['reasoning'] = "FALLBACK - AI error"
            move['confidence'] = 0
            return move

        return {'x': 0, 'y': 0, 'card': hand[0], 'reasoning': 'Desperate fallback', 'confidence': 0}


class UltimateShowdown:
    """$10k Tournament Controller"""

    def __init__(self):
        self.logger = DetailedLogger('ultimate_showdown_log.json')

        print("🎮 Initializing ULTIMATE SHOWDOWN...")
        print("💰 Prize: $10,000 - WINNER TAKES ALL")
        print("🏆 Format: First to 2 wins")
        print()

        try:
            self.claude_player = UltimateAIPlayer("claude", "claude", self.logger)
            print(f"✅ {self.claude_player.display_name} ready")
        except Exception as e:
            print(f"❌ Claude error: {e}")
            sys.exit(1)

        try:
            self.openai_player = UltimateAIPlayer("openai", "openai", self.logger)
            print(f"✅ {self.openai_player.display_name} ready")
        except Exception as e:
            print(f"❌ OpenAI error: {e}")
            sys.exit(1)

    def run_tournament(self):
        """Run tournament to 2 wins"""
        print(f"\n{'='*70}")
        print(f"🔥 $10,000 ULTIMATE SHOWDOWN - START! 🔥")
        print(f"{'='*70}\n")

        game_num = 0

        while self.claude_player.wins < 2 and self.openai_player.wins < 2:
            game_num += 1
            first_player = "claude" if game_num % 2 == 1 else "openai"

            print(f"\n{'█'*70}")
            print(f"GAME {game_num}")
            print(f"Standing: Claude {self.claude_player.wins}-{self.openai_player.wins} OpenAI")

            if self.claude_player.wins == 1:
                print("🚨 CLAUDE MATCH POINT!")
            if self.openai_player.wins == 1:
                print("🚨 OPENAI MATCH POINT!")

            print(f"{'█'*70}")

            result = self.play_game(game_num, first_player)

            # Update players
            if result['winner'] == 'claude':
                self.claude_player.update_result(True, result)
                self.openai_player.update_result(False, result)
                print(f"\n🔵 CLAUDE WINS GAME {game_num}!")
            else:
                self.claude_player.update_result(False, result)
                self.openai_player.update_result(True, result)
                print(f"\n🔴 OPENAI WINS GAME {game_num}!")

            print(f"\n📊 SCORE: Claude {self.claude_player.wins}-{self.openai_player.wins} OpenAI")

            # Log game
            self.logger.log_game(result)

            # Show token stats
            tokens = self.logger.log_data['token_usage']
            print(f"💰 Cost so far: ${tokens['total_cost']:.4f}")

            time.sleep(1)

        # Tournament over
        self.display_champion()

    def play_game(self, game_num, first_player):
        """Play single game"""
        game = PuntoGame()
        moves = []

        if first_player == "claude":
            players = [(self.claude_player, "claude"), (self.openai_player, "openai")]
        else:
            players = [(self.openai_player, "openai"), (self.claude_player, "claude")]

        turn = 0
        while not game.is_game_over() and turn < 100:
            turn += 1

            for player, name in players:
                opponent_name = "openai" if name == "claude" else "claude"
                opponent = self.openai_player if name == "claude" else self.claude_player

                hand = game.get_hand(name)
                if not hand:
                    break

                print(f"\n  {player.display_name} thinking...")

                move = player.get_move(
                    game.get_board_state(),
                    hand,
                    len(game.get_hand(opponent_name)),
                    game_num,
                    opponent.wins
                )

                print(f"  💭 Confidence: {move.get('confidence', '?')}/10")
                print(f"  ♟️  Move: {move['card']} → ({move['x']}, {move['y']})")
                print(f"  🧠 {move.get('reasoning', 'N/A')[:100]}...")

                is_valid, _ = game.is_valid_move(move['x'], move['y'], move['card'], name)

                if is_valid:
                    game.make_move(move['x'], move['y'], move['card'], name)
                    moves.append({
                        'player': name,
                        'move': move,
                        'turn': turn
                    })
                else:
                    print(f"  ⚠️ Invalid move! Fallback...")
                    self._fallback_move(game, name, hand, moves, turn)

                if game.is_game_over():
                    break

            if game.is_game_over():
                break

        return {
            'game_num': game_num,
            'winner': game.winner,
            'turns': turn,
            'first_player': first_player,
            'moves': moves
        }

    def _fallback_move(self, game, name, hand, moves, turn):
        """Execute fallback"""
        for card in hand:
            for y in range(6):
                for x in range(6):
                    is_valid, _ = game.is_valid_move(x, y, card, name)
                    if is_valid:
                        game.make_move(x, y, card, name)
                        moves.append({
                            'player': name,
                            'move': {'x': x, 'y': y, 'card': card, 'reasoning': 'Fallback'},
                            'turn': turn
                        })
                        return

    def display_champion(self):
        """Display champion and stats"""
        print(f"\n{'='*70}")
        print(f"🏆 TOURNAMENT COMPLETE! 🏆")
        print(f"{'='*70}\n")

        if self.claude_player.wins == 2:
            winner = "Claude Opus 4.5"
            winner_symbol = "🔵"
        else:
            winner = "OpenAI o1"
            winner_symbol = "🔴"

        print(f"{winner_symbol} CHAMPION: {winner}")
        print(f"💰 PRIZE: $10,000 USD")
        print(f"\n📊 FINAL SCORE:")
        print(f"   Claude Opus 4.5: {self.claude_player.wins} wins")
        print(f"   OpenAI o1:       {self.openai_player.wins} wins")

        # Token statistics
        tokens = self.logger.log_data['token_usage']
        print(f"\n{'='*70}")
        print(f"💰 TOURNAMENT COST ANALYSIS")
        print(f"{'='*70}")
        print(f"\n🔵 Claude Opus 4.5:")
        print(f"   Input:  {tokens['claude_input']:,} tokens")
        print(f"   Output: {tokens['claude_output']:,} tokens")
        print(f"   Cost:   ${tokens['claude_input']/1_000_000*15 + tokens['claude_output']/1_000_000*75:.4f}")

        print(f"\n🔴 OpenAI o1:")
        print(f"   Input:  {tokens['openai_input']:,} tokens")
        print(f"   Output: {tokens['openai_output']:,} tokens")
        print(f"   Cost:   ${tokens['openai_input']/1_000_000*15 + tokens['openai_output']/1_000_000*60:.4f}")

        print(f"\n💵 TOTAL COST: ${tokens['total_cost']:.4f}")
        print(f"\n📝 Full logs saved to: ultimate_showdown_log.json")

        self.logger.finalize(winner)


def main():
    import os

    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          🔥 $10,000 PUNTO AI TOURNAMENT 🔥                    ║
║                                                               ║
║              Claude Opus 4.5  vs  OpenAI o1                   ║
║                                                               ║
║                   WINNER TAKES ALL                            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Missing API keys")
        sys.exit(1)

    try:
        tournament = UltimateShowdown()
        tournament.run_tournament()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tournament interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
