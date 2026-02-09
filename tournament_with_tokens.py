#!/usr/bin/env python3
"""
Tournament with Token Tracking - Precise measurement of API usage
"""

import sys
import time
from game_logic import PuntoGame
from tournament_with_memory import AIPlayerWithMemory


class TokenTracker:
    """Tracks token usage across tournament"""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.claude_input = 0
        self.claude_output = 0
        self.openai_input = 0
        self.openai_output = 0
        self.api_calls = 0

    def add_usage(self, player_name: str, input_tokens: int, output_tokens: int):
        """Add token usage for a player"""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls += 1

        if player_name == "claude":
            self.claude_input += input_tokens
            self.claude_output += output_tokens
        else:
            self.openai_input += input_tokens
            self.openai_output += output_tokens

    def get_cost(self):
        """Calculate estimated cost"""
        # Claude Sonnet 4.5 pricing
        claude_cost = (self.claude_input / 1_000_000 * 3.0 +
                      self.claude_output / 1_000_000 * 15.0)

        # GPT-4o pricing
        openai_cost = (self.openai_input / 1_000_000 * 2.5 +
                      self.openai_output / 1_000_000 * 10.0)

        return claude_cost + openai_cost

    def display_stats(self):
        """Display token usage statistics"""
        total = self.total_input_tokens + self.total_output_tokens

        print(f"\n{'='*70}")
        print(f"📊 STATYSTYKI TOKENÓW")
        print(f"{'='*70}")

        print(f"\n🔵 Claude:")
        print(f"   Input:  {self.claude_input:,} tokenów")
        print(f"   Output: {self.claude_output:,} tokenów")
        print(f"   Razem:  {self.claude_input + self.claude_output:,} tokenów")

        print(f"\n🔴 OpenAI:")
        print(f"   Input:  {self.openai_input:,} tokenów")
        print(f"   Output: {self.openai_output:,} tokenów")
        print(f"   Razem:  {self.openai_input + self.openai_output:,} tokenów")

        print(f"\n📈 TOTAL:")
        print(f"   Input:  {self.total_input_tokens:,} tokenów")
        print(f"   Output: {self.total_output_tokens:,} tokenów")
        print(f"   RAZEM:  {total:,} tokenów")
        print(f"   API calls: {self.api_calls}")
        print(f"   Średnia tokens/call: {total/self.api_calls:,.0f}")

        cost = self.get_cost()
        print(f"\n💰 KOSZT:")
        print(f"   Claude:  ${self.claude_input/1_000_000*3 + self.claude_output/1_000_000*15:.4f}")
        print(f"   OpenAI:  ${self.openai_input/1_000_000*2.5 + self.openai_output/1_000_000*10:.4f}")
        print(f"   TOTAL:   ${cost:.4f}")


class AIPlayerWithTokens(AIPlayerWithMemory):
    """AI Player that tracks token usage"""

    def __init__(self, player_name: str, api_type: str, tracker: TokenTracker):
        super().__init__(player_name, api_type)
        self.tracker = tracker

    def get_move(self, board, hand, opponent_hand_size, current_game_num, total_tournament_games):
        """Get move and track tokens"""
        prompt = self._create_tournament_aware_prompt(
            board, hand, opponent_hand_size,
            current_game_num, total_tournament_games
        )

        try:
            if self.api_type == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    messages=[{"role": "user", "content": prompt}]
                )

                # Track Claude tokens
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.tracker.add_usage("claude", input_tokens, output_tokens)

                move_text = response.content[0].text

            else:  # OpenAI
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )

                # Track OpenAI tokens
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                self.tracker.add_usage("openai", input_tokens, output_tokens)

                move_text = response.choices[0].message.content

            move = self._parse_move(move_text)
            return move

        except Exception as e:
            print(f"   ⚠️ Błąd AI: {e}")
            return self._random_fallback_move(board, hand)


class TournamentWithTokenTracking:
    """Tournament with detailed token tracking"""

    def __init__(self, num_games: int = 10, delay: float = 0.2, verbose: bool = True):
        self.num_games = num_games
        self.delay = delay
        self.verbose = verbose
        self.tracker = TokenTracker()

        print("🎮 Inicjalizacja turnieju z licznikiem tokenów...")
        try:
            self.claude_player = AIPlayerWithTokens("claude", "claude", self.tracker)
            print("✅ Claude player gotowy")
        except Exception as e:
            print(f"❌ Błąd Claude: {e}")
            sys.exit(1)

        try:
            self.openai_player = AIPlayerWithTokens("openai", "openai", self.tracker)
            print("✅ OpenAI player gotowy")
        except Exception as e:
            print(f"❌ Błąd OpenAI: {e}")
            sys.exit(1)

    def run_tournament(self):
        """Run tournament with token tracking"""
        print(f"\n{'='*70}")
        print(f"🏆 TURNIEJ Z LICZNIKIEM TOKENÓW - {self.num_games} GIER")
        print(f"{'='*70}\n")

        for game_num in range(1, self.num_games + 1):
            first_player = "claude" if game_num % 2 == 1 else "openai"
            first_symbol = "🔵" if first_player == "claude" else "🔴"

            print(f"\n{'▼'*70}")
            print(f"GRA {game_num}/{self.num_games} | {first_symbol} {first_player.upper()} zaczyna!")
            print(f"Stan: Claude {self.claude_player.my_wins} - {self.openai_player.my_wins} OpenAI")

            # Show token stats so far
            if game_num > 1:
                total = self.tracker.total_input_tokens + self.tracker.total_output_tokens
                print(f"💰 Tokeny dotąd: {total:,} (${self.tracker.get_cost():.3f})")

            print(f"{'▼'*70}")

            result = self.play_single_game(game_num, first_player)

            self.claude_player.update_tournament_state(result)
            self.openai_player.update_tournament_state(result)

            if result['winner']:
                winner_symbol = "🔵" if result['winner'] == "claude" else "🔴"
                print(f"\n{winner_symbol} ZWYCIĘZCA: {result['winner'].upper()}")
            else:
                print(f"\n🤝 REMIS")

            print(f"\n📊 Stan turnieju po {game_num} grach:")
            print(f"   🔵 Claude:  {self.claude_player.my_wins}")
            print(f"   🔴 OpenAI:  {self.openai_player.my_wins}")

            time.sleep(0.5)

        self.display_final_results()

    def play_single_game(self, game_num: int, first_player: str):
        """Play single game"""
        game = PuntoGame()
        turn_count = 0
        start_time = time.time()

        if first_player == "claude":
            players = [(self.claude_player, "claude"), (self.openai_player, "openai")]
        else:
            players = [(self.openai_player, "openai"), (self.claude_player, "claude")]

        while not game.is_game_over() and turn_count < 100:
            turn_count += 1

            for player, name in players:
                success = self._play_turn(game, player, name, game_num)
                if not success or game.is_game_over():
                    break
                time.sleep(self.delay)

            if game.is_game_over():
                break

        duration = time.time() - start_time

        return {
            'game_num': game_num,
            'winner': game.winner if game.winner else None,
            'turns': turn_count,
            'duration': duration,
            'first_player': first_player
        }

    def _play_turn(self, game, player, player_name, game_num):
        """Execute turn"""
        hand = game.get_hand(player_name)
        opponent_name = "openai" if player_name == "claude" else "claude"
        opponent_hand_size = len(game.get_hand(opponent_name))

        if not hand:
            return False

        try:
            move = player.get_move(
                game.get_board_state(), hand, opponent_hand_size,
                game_num, self.num_games
            )

            is_valid, _ = game.is_valid_move(move['x'], move['y'], move['card'], player_name)

            if is_valid:
                game.make_move(move['x'], move['y'], move['card'], player_name)
                return True
            else:
                return self._try_fallback_move(game, player_name, hand)
        except:
            return self._try_fallback_move(game, player_name, hand)

    def _try_fallback_move(self, game, player_name, hand):
        """Fallback move"""
        for card in hand:
            for y in range(6):
                for x in range(6):
                    is_valid, _ = game.is_valid_move(x, y, card, player_name)
                    if is_valid:
                        try:
                            game.make_move(x, y, card, player_name)
                            return True
                        except:
                            continue
        return False

    def display_final_results(self):
        """Display results with token stats"""
        print("\n" + "="*70)
        print("🏆 WYNIKI KOŃCOWE")
        print("="*70)

        claude_wins = self.claude_player.my_wins
        openai_wins = self.openai_player.my_wins

        print(f"\n🔵 Claude:  {claude_wins} wygranych ({claude_wins/self.num_games*100:.1f}%)")
        print(f"🔴 OpenAI:  {openai_wins} wygranych ({openai_wins/self.num_games*100:.1f}%)")

        print(f"\n{'='*70}")
        if claude_wins > openai_wins:
            print("🎉 MISTRZ TURNIEJU: 🔵 CLAUDE!")
        elif openai_wins > claude_wins:
            print("🎉 MISTRZ TURNIEJU: 🔴 OPENAI!")
        else:
            print("🤝 TURNIEJ ZAKOŃCZYŁ SIĘ REMISEM!")
        print(f"{'='*70}")

        # Display token statistics
        self.tracker.display_stats()


def main():
    import os

    print("""
╔═══════════════════════════════════════════════╗
║   PUNTO AI - TOKEN TRACKING                   ║
║   Dokładny pomiar zużycia tokenów             ║
╚═══════════════════════════════════════════════╝
    """)

    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Brak kluczy API")
        sys.exit(1)

    try:
        tournament = TournamentWithTokenTracking(
            num_games=10,
            delay=0.2,
            verbose=False
        )
        tournament.run_tournament()
    except KeyboardInterrupt:
        print("\n\n⚠️  Turniej przerwany")
        print("\nStatystyki do momentu przerwania:")
        tournament.tracker.display_stats()
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
