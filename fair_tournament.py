#!/usr/bin/env python3
"""
Fair Tournament - Players alternate who goes first
"""

import sys
import time
from game_logic import PuntoGame
from tournament_with_memory import AIPlayerWithMemory


class FairTournament:
    def __init__(self, num_games: int = 10, delay: float = 0.2, verbose: bool = True):
        self.num_games = num_games
        self.delay = delay
        self.verbose = verbose

        print("🎮 Inicjalizacja SPRAWIEDLIWEGO turnieju...")
        try:
            self.claude_player = AIPlayerWithMemory("claude", api_type="claude")
            print("✅ Claude player gotowy")
        except Exception as e:
            print(f"❌ Błąd Claude: {e}")
            sys.exit(1)

        try:
            self.openai_player = AIPlayerWithMemory("openai", api_type="openai")
            print("✅ OpenAI player gotowy")
        except Exception as e:
            print(f"❌ Błąd OpenAI: {e}")
            sys.exit(1)

    def run_tournament(self):
        """Run fair tournament with alternating first player"""
        print(f"\n{'='*70}")
        print(f"🏆 SPRAWIEDLIWY TURNIEJ - {self.num_games} GIER")
        print(f"{'='*70}")
        print(f"⚖️  ZASADA: Gracze zmieniają się co grę!")
        print(f"   Nieparzyste gry (1,3,5,7,9): Claude zaczyna")
        print(f"   Parzyste gry (2,4,6,8,10): OpenAI zaczyna")
        print(f"{'='*70}\n")

        for game_num in range(1, self.num_games + 1):
            # Determine who goes first
            first_player = "claude" if game_num % 2 == 1 else "openai"
            first_symbol = "🔵" if first_player == "claude" else "🔴"

            print(f"\n{'▼'*70}")
            print(f"GRA {game_num}/{self.num_games} | {first_symbol} {first_player.upper()} zaczyna!")
            print(f"Stan: Claude {self.claude_player.my_wins} - {self.openai_player.my_wins} OpenAI")
            print(f"{'▼'*70}")

            result = self.play_single_game(game_num, first_player)

            # Update both players' memory
            self.claude_player.update_tournament_state(result)
            self.openai_player.update_tournament_state(result)

            # Show result
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
        """Play a single game with specified first player"""
        game = PuntoGame()
        turn_count = 0
        start_time = time.time()

        # Determine player order
        if first_player == "claude":
            players = [
                (self.claude_player, "claude"),
                (self.openai_player, "openai")
            ]
        else:
            players = [
                (self.openai_player, "openai"),
                (self.claude_player, "claude")
            ]

        while not game.is_game_over() and turn_count < 100:
            turn_count += 1

            # First player's turn
            player1, name1 = players[0]
            if self.verbose and turn_count == 1:
                symbol1 = "🔵" if name1 == "claude" else "🔴"
                print(f"\n{symbol1} {name1.upper()} rozpoczyna...")

            success = self._play_turn(game, player1, name1, game_num)
            if not success or game.is_game_over():
                break

            time.sleep(self.delay)

            # Second player's turn
            player2, name2 = players[1]
            if self.verbose and turn_count == 1:
                symbol2 = "🔵" if name2 == "claude" else "🔴"
                print(f"\n{symbol2} {name2.upper()} odpowiada...")

            success = self._play_turn(game, player2, name2, game_num)
            if not success or game.is_game_over():
                break

            time.sleep(self.delay)

        duration = time.time() - start_time

        return {
            'game_num': game_num,
            'winner': game.winner if game.winner else None,
            'turns': turn_count,
            'duration': duration,
            'first_player': first_player
        }

    def _play_turn(self, game: PuntoGame, player: AIPlayerWithMemory,
                   player_name: str, game_num: int) -> bool:
        """Execute a turn"""
        hand = game.get_hand(player_name)
        opponent_name = "openai" if player_name == "claude" else "claude"
        opponent_hand_size = len(game.get_hand(opponent_name))

        if not hand:
            return False

        try:
            move = player.get_move(
                game.get_board_state(),
                hand,
                opponent_hand_size,
                game_num,
                self.num_games
            )

            if self.verbose:
                print(f"   Ruch: {move['card']} → ({move['x']}, {move['y']})")

            is_valid, _ = game.is_valid_move(move['x'], move['y'], move['card'], player_name)

            if is_valid:
                game.make_move(move['x'], move['y'], move['card'], player_name)
                return True
            else:
                return self._try_fallback_move(game, player_name, hand)

        except:
            return self._try_fallback_move(game, player_name, hand)

    def _try_fallback_move(self, game: PuntoGame, player_name: str, hand: list) -> bool:
        """Fallback move"""
        for card in hand:
            for y in range(6):
                for x in range(6):
                    is_valid, _ = game.is_valid_move(x, y, card, player_name)
                    if is_valid:
                        try:
                            game.make_move(x, y, card, player_name)
                            if self.verbose:
                                print(f"   Fallback: {card} → ({x}, {y})")
                            return True
                        except:
                            continue
        return False

    def display_final_results(self):
        """Display final results with fairness analysis"""
        print("\n" + "="*70)
        print("🏆 WYNIKI KOŃCOWE SPRAWIEDLIWEGO TURNIEJU")
        print("="*70)

        claude_wins = self.claude_player.my_wins
        openai_wins = self.openai_player.my_wins

        print(f"\n🔵 Claude:  {claude_wins} wygranych ({claude_wins/self.num_games*100:.1f}%)")
        print(f"🔴 OpenAI:  {openai_wins} wygranych ({openai_wins/self.num_games*100:.1f}%)")

        # Analyze wins by who went first
        claude_first_games = [g for g in self.claude_player.tournament_history if g['first_player'] == 'claude']
        openai_first_games = [g for g in self.openai_player.tournament_history if g['first_player'] == 'openai']

        claude_wins_when_first = sum(1 for g in claude_first_games if g['winner'] == 'claude')
        claude_wins_when_second = sum(1 for g in openai_first_games if g['winner'] == 'claude')

        openai_wins_when_first = sum(1 for g in openai_first_games if g['winner'] == 'openai')
        openai_wins_when_second = sum(1 for g in claude_first_games if g['winner'] == 'openai')

        print(f"\n⚖️  ANALIZA SPRAWIEDLIWOŚCI:")
        print(f"\n🔵 Claude:")
        print(f"   Gdy zaczynał:  {claude_wins_when_first}/{len(claude_first_games)} wygranych")
        print(f"   Gdy był drugi: {claude_wins_when_second}/{len(openai_first_games)} wygranych")

        print(f"\n🔴 OpenAI:")
        print(f"   Gdy zaczynał:  {openai_wins_when_first}/{len(openai_first_games)} wygranych")
        print(f"   Gdy był drugi: {openai_wins_when_second}/{len(claude_first_games)} wygranych")

        # First player advantage
        first_player_wins = claude_wins_when_first + openai_wins_when_first
        print(f"\n📊 Przewaga pierwszego gracza:")
        print(f"   Pierwszy gracz wygrał: {first_player_wins}/{self.num_games} gier ({first_player_wins/self.num_games*100:.0f}%)")

        print(f"\n{'='*70}")
        if claude_wins > openai_wins:
            print("🎉 MISTRZ TURNIEJU: 🔵 CLAUDE!")
        elif openai_wins > claude_wins:
            print("🎉 MISTRZ TURNIEJU: 🔴 OPENAI!")
        else:
            print("🤝 TURNIEJ ZAKOŃCZYŁ SIĘ REMISEM!")
        print(f"{'='*70}")


def main():
    import os

    print("""
╔═══════════════════════════════════════════════╗
║   FAIR PUNTO AI TOURNAMENT                    ║
║   Gracze zmieniają się! ⚖️                     ║
╚═══════════════════════════════════════════════╝
    """)

    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Brak kluczy API")
        sys.exit(1)

    try:
        tournament = FairTournament(
            num_games=10,
            delay=0.2,
            verbose=True
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
