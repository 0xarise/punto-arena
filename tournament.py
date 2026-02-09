#!/usr/bin/env python3
"""
Tournament mode - runs multiple games and collects statistics
"""

import sys
import time
from game_logic import PuntoGame
from ai_player import AIPlayer


class TournamentController:
    def __init__(self, num_games: int = 10, delay: float = 0.2, verbose: bool = False):
        self.num_games = num_games
        self.delay = delay
        self.verbose = verbose
        self.results = {
            'claude_wins': 0,
            'openai_wins': 0,
            'draws': 0,
            'games': []
        }

        # Initialize AI players once
        print("🎮 Inicjalizacja graczy AI dla turnieju...")
        try:
            self.claude_player = AIPlayer("claude", api_type="claude")
            print("✅ Claude player gotowy")
        except Exception as e:
            print(f"❌ Błąd inicjalizacji Claude: {e}")
            sys.exit(1)

        try:
            self.openai_player = AIPlayer("openai", api_type="openai")
            print("✅ OpenAI player gotowy")
        except Exception as e:
            print(f"❌ Błąd inicjalizacji OpenAI: {e}")
            sys.exit(1)

    def run_tournament(self):
        """Run the tournament"""
        print(f"\n{'='*60}")
        print(f"🏆 TURNIEJ: {self.num_games} GIER")
        print(f"{'='*60}\n")

        for game_num in range(1, self.num_games + 1):
            print(f"\n{'▼'*60}")
            print(f"GRA {game_num}/{self.num_games}")
            print(f"{'▼'*60}")

            result = self.play_single_game(game_num)
            self.results['games'].append(result)

            # Update counters
            if result['winner'] == 'claude':
                self.results['claude_wins'] += 1
            elif result['winner'] == 'openai':
                self.results['openai_wins'] += 1
            else:
                self.results['draws'] += 1

            # Show current standings
            print(f"\n📊 Stan po {game_num} grach:")
            print(f"   🔵 Claude: {self.results['claude_wins']} wygranych")
            print(f"   🔴 OpenAI: {self.results['openai_wins']} wygranych")
            print(f"   🤝 Remisy: {self.results['draws']}")

            time.sleep(0.5)

        # Final results
        self.display_final_results()

    def play_single_game(self, game_num: int):
        """Play a single game and return result"""
        game = PuntoGame()
        turn_count = 0
        start_time = time.time()

        while not game.is_game_over() and turn_count < 100:  # Max 100 turns to prevent infinite loops
            turn_count += 1

            # Claude's turn
            if self.verbose:
                print(f"\nTura {turn_count}A - Claude")

            success = self._play_turn(game, self.claude_player, "claude")
            if not success or game.is_game_over():
                break

            time.sleep(self.delay)

            # OpenAI's turn
            if self.verbose:
                print(f"\nTura {turn_count}B - OpenAI")

            success = self._play_turn(game, self.openai_player, "openai")
            if not success or game.is_game_over():
                break

            time.sleep(self.delay)

        end_time = time.time()
        duration = end_time - start_time

        result = {
            'game_num': game_num,
            'winner': game.winner if game.winner else 'draw',
            'turns': turn_count,
            'duration': duration
        }

        if game.winner:
            winner_symbol = "🔵" if game.winner == "claude" else "🔴"
            print(f"\n{winner_symbol} Zwycięzca: {game.winner.upper()} (po {turn_count} turach, {duration:.1f}s)")
        else:
            print(f"\n🤝 Remis (po {turn_count} turach, {duration:.1f}s)")

        if self.verbose:
            print(game.format_board())

        return result

    def _play_turn(self, game: PuntoGame, player: AIPlayer, player_name: str) -> bool:
        """Execute a single turn"""
        hand = game.get_hand(player_name)
        opponent_name = "openai" if player_name == "claude" else "claude"
        opponent_hand_size = len(game.get_hand(opponent_name))

        if not hand:
            return False

        try:
            move = player.get_move(
                game.get_board_state(),
                hand,
                opponent_hand_size
            )

            if self.verbose:
                print(f"   {player_name}: {move['card']} na ({move['x']}, {move['y']})")

            game.make_move(move['x'], move['y'], move['card'], player_name)
            return True

        except ValueError:
            # Try fallback move
            return self._try_fallback_move(game, player_name, hand)
        except Exception as e:
            if self.verbose:
                print(f"   Błąd {player_name}: {e}")
            return self._try_fallback_move(game, player_name, hand)

    def _try_fallback_move(self, game: PuntoGame, player_name: str, hand: list) -> bool:
        """Try to make a fallback move"""
        for card in hand:
            for y in range(6):
                for x in range(6):
                    is_valid, _ = game.is_valid_move(x, y, card, player_name)
                    if is_valid:
                        try:
                            game.make_move(x, y, card, player_name)
                            if self.verbose:
                                print(f"   {player_name} (fallback): {card} na ({x}, {y})")
                            return True
                        except:
                            continue
        return False

    def display_final_results(self):
        """Display final tournament results"""
        print("\n" + "="*60)
        print("🏆 WYNIKI KOŃCOWE TURNIEJU")
        print("="*60)

        total_games = len(self.results['games'])
        claude_wins = self.results['claude_wins']
        openai_wins = self.results['openai_wins']
        draws = self.results['draws']

        print(f"\n📊 Rozegrane gry: {total_games}")
        print(f"\n🔵 Claude: {claude_wins} wygranych ({claude_wins/total_games*100:.1f}%)")
        print(f"🔴 OpenAI: {openai_wins} wygranych ({openai_wins/total_games*100:.1f}%)")
        print(f"🤝 Remisy: {draws} ({draws/total_games*100:.1f}%)")

        # Determine overall winner
        print(f"\n{'='*60}")
        if claude_wins > openai_wins:
            print("🎉 MISTRZ TURNIEJU: 🔵 CLAUDE!")
        elif openai_wins > claude_wins:
            print("🎉 MISTRZ TURNIEJU: 🔴 OPENAI!")
        else:
            print("🤝 TURNIEJ ZAKOŃCZYŁ SIŘ REMISEM!")
        print(f"{'='*60}")

        # Statistics
        avg_turns = sum(g['turns'] for g in self.results['games']) / total_games
        avg_duration = sum(g['duration'] for g in self.results['games']) / total_games

        print(f"\n📈 Statystyki:")
        print(f"   Średnia liczba tur: {avg_turns:.1f}")
        print(f"   Średni czas gry: {avg_duration:.1f}s")
        print(f"   Całkowity czas: {sum(g['duration'] for g in self.results['games']):.1f}s")

        # Game-by-game breakdown
        print(f"\n📋 Szczegóły gier:")
        for game in self.results['games']:
            winner_symbol = {
                'claude': '🔵 C',
                'openai': '🔴 O',
                'draw': '🤝 D'
            }[game['winner']]
            print(f"   Gra {game['game_num']:2d}: {winner_symbol} | {game['turns']:2d} tur | {game['duration']:.1f}s")


def main():
    import os

    print("""
╔═══════════════════════════════════════════════╗
║       PUNTO AI TOURNAMENT                     ║
║       Claude vs OpenAI - 10 gier              ║
╚═══════════════════════════════════════════════╝
    """)

    # Check API keys
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  BRAK ANTHROPIC_API_KEY")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  BRAK OPENAI_API_KEY")
        sys.exit(1)

    try:
        tournament = TournamentController(
            num_games=10,
            delay=0.1,  # Szybsze tury
            verbose=False  # Mniej logów dla szybszości
        )
        tournament.run_tournament()
    except KeyboardInterrupt:
        print("\n\n⚠️  Turniej przerwany")
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
