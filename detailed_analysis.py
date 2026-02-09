#!/usr/bin/env python3
"""
Detailed analysis - runs games with full move logging and analysis
"""

import sys
import json
from game_logic import PuntoGame
from ai_player import AIPlayer


class DetailedGameAnalyzer:
    def __init__(self):
        print("🎮 Inicjalizacja graczy AI...")
        try:
            self.claude_player = AIPlayer("claude", api_type="claude")
            self.openai_player = AIPlayer("openai", api_type="openai")
            print("✅ Gracze gotowi\n")
        except Exception as e:
            print(f"❌ Błąd: {e}")
            sys.exit(1)

    def analyze_game(self, game_num: int):
        """Play a single game with detailed logging"""
        print(f"{'='*70}")
        print(f"GRA {game_num} - SZCZEGÓŁOWA ANALIZA")
        print(f"{'='*70}\n")

        game = PuntoGame()

        # Log initial hands
        print(f"🎴 POCZĄTKOWE KARTY:")
        print(f"   Claude:  {sorted(game.hand_claude)}")
        print(f"   OpenAI:  {sorted(game.hand_openai)}\n")

        moves_log = []
        turn = 0

        while not game.is_game_over() and turn < 50:
            turn += 1

            # Claude's turn
            print(f"{'─'*70}")
            print(f"TURA {turn}A - 🔵 CLAUDE")
            print(f"{'─'*70}")

            move_data = self._play_and_log_turn(game, self.claude_player, "claude", turn, 'A')
            if move_data:
                moves_log.append(move_data)

            if game.is_game_over():
                break

            # OpenAI's turn
            print(f"{'─'*70}")
            print(f"TURA {turn}B - 🔴 OPENAI")
            print(f"{'─'*70}")

            move_data = self._play_and_log_turn(game, self.openai_player, "openai", turn, 'B')
            if move_data:
                moves_log.append(move_data)

            if game.is_game_over():
                break

        # Final results
        print(f"\n{'='*70}")
        print(f"KONIEC GRY {game_num}")
        print(f"{'='*70}\n")
        print(game.format_board())

        if game.winner:
            winner_symbol = "🔵" if game.winner == "claude" else "🔴"
            print(f"\n{winner_symbol} ZWYCIĘZCA: {game.winner.upper()} po {turn} turach\n")
        else:
            print(f"\n🤝 REMIS\n")

        # Analysis
        self._analyze_moves(moves_log, game.winner)

        return {
            'game_num': game_num,
            'winner': game.winner,
            'turns': turn,
            'moves': moves_log
        }

    def _play_and_log_turn(self, game: PuntoGame, player: AIPlayer, player_name: str, turn: int, subturn: str):
        """Execute and log a single turn"""
        hand = game.get_hand(player_name)
        opponent_name = "openai" if player_name == "claude" else "claude"
        opponent_hand_size = len(game.get_hand(opponent_name))

        if not hand:
            return None

        print(f"Karty na ręku: {sorted(hand)}")

        try:
            move = player.get_move(
                game.get_board_state(),
                hand,
                opponent_hand_size
            )

            # Check if it's a valid move
            is_valid, message = game.is_valid_move(move['x'], move['y'], move['card'], player_name)

            if is_valid:
                print(f"✅ Ruch: karta {move['card']} → ({move['x']}, {move['y']})")
                print(f"💭 Reasoning: {move.get('reasoning', 'brak')}")

                game.make_move(move['x'], move['y'], move['card'], player_name)

                return {
                    'turn': f"{turn}{subturn}",
                    'player': player_name,
                    'card': move['card'],
                    'position': (move['x'], move['y']),
                    'reasoning': move.get('reasoning', ''),
                    'was_fallback': False,
                    'hand_before': hand.copy()
                }
            else:
                print(f"❌ NIEPRAWIDŁOWY RUCH: {message}")
                print(f"   Próbowano: {move['card']} na ({move['x']}, {move['y']})")
                print(f"   Reasoning AI: {move.get('reasoning', 'brak')}")

                # Fallback
                fallback = self._try_fallback(game, player_name, hand)
                return fallback

        except Exception as e:
            print(f"❌ BŁĄD: {e}")
            fallback = self._try_fallback(game, player_name, hand)
            return fallback

    def _try_fallback(self, game: PuntoGame, player_name: str, hand: list):
        """Try fallback move"""
        for card in sorted(hand, reverse=True):  # Try highest cards first
            for y in range(6):
                for x in range(6):
                    is_valid, _ = game.is_valid_move(x, y, card, player_name)
                    if is_valid:
                        game.make_move(x, y, card, player_name)
                        print(f"🔄 FALLBACK: {card} → ({x}, {y})")
                        return {
                            'player': player_name,
                            'card': card,
                            'position': (x, y),
                            'reasoning': 'FALLBACK - AI error',
                            'was_fallback': True,
                            'hand_before': hand.copy()
                        }
        return None

    def _analyze_moves(self, moves_log: list, winner: str):
        """Analyze move patterns"""
        print(f"{'='*70}")
        print(f"📊 ANALIZA RUCHÓW")
        print(f"{'='*70}\n")

        claude_moves = [m for m in moves_log if m['player'] == 'claude']
        openai_moves = [m for m in moves_log if m['player'] == 'openai']

        print(f"🔵 Claude:")
        print(f"   Ruchy: {len(claude_moves)}")
        print(f"   Fallbacki: {sum(1 for m in claude_moves if m.get('was_fallback', False))}")
        if claude_moves:
            avg_card = sum(m['card'] for m in claude_moves) / len(claude_moves)
            print(f"   Średnia wartość karty: {avg_card:.1f}")

        print(f"\n🔴 OpenAI:")
        print(f"   Ruchy: {len(openai_moves)}")
        print(f"   Fallbacki: {sum(1 for m in openai_moves if m.get('was_fallback', False))}")
        if openai_moves:
            avg_card = sum(m['card'] for m in openai_moves) / len(openai_moves)
            print(f"   Średnia wartość karty: {avg_card:.1f}")

        # Strategy patterns
        print(f"\n📍 STRATEGIA POZYCJI:")
        for player_name in ['claude', 'openai']:
            moves = [m for m in moves_log if m['player'] == player_name]
            if moves:
                positions = [m['position'] for m in moves]
                center_moves = sum(1 for x, y in positions if 2 <= x <= 3 and 2 <= y <= 3)
                edge_moves = sum(1 for x, y in positions if x in [0, 5] or y in [0, 5])

                symbol = "🔵" if player_name == "claude" else "🔴"
                print(f"   {symbol} {player_name.capitalize()}:")
                print(f"      Środek planszy (2-3, 2-3): {center_moves}/{len(moves)} ({center_moves/len(moves)*100:.0f}%)")
                print(f"      Krawędzie (0,5): {edge_moves}/{len(moves)} ({edge_moves/len(moves)*100:.0f}%)")

        # Key moments
        print(f"\n🎯 KLUCZOWE MOMENTY:")
        for i, move in enumerate(moves_log[-5:]):  # Last 5 moves
            symbol = "🔵" if move['player'] == "claude" else "🔴"
            fallback = " [FALLBACK]" if move.get('was_fallback') else ""
            print(f"   Ruch {i+1}: {symbol} {move['card']} → {move['position']}{fallback}")


def main():
    import os

    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Brak kluczy API")
        sys.exit(1)

    analyzer = DetailedGameAnalyzer()

    # Play 3 games with detailed analysis
    print(f"""
╔═══════════════════════════════════════════════╗
║   SZCZEGÓŁOWA ANALIZA - 3 GRY                 ║
╚═══════════════════════════════════════════════╝
    """)

    results = []
    for i in range(1, 4):
        result = analyzer.analyze_game(i)
        results.append(result)
        print("\n" + "▼"*70 + "\n")
        input("Naciśnij ENTER aby kontynuować do następnej gry...")
        print("\n")

    # Summary
    print(f"\n{'='*70}")
    print(f"PODSUMOWANIE 3 GIER")
    print(f"{'='*70}\n")

    claude_wins = sum(1 for r in results if r['winner'] == 'claude')
    openai_wins = sum(1 for r in results if r['winner'] == 'openai')

    print(f"🔵 Claude: {claude_wins} wygrane")
    print(f"🔴 OpenAI: {openai_wins} wygrane")


if __name__ == "__main__":
    main()
