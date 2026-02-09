#!/usr/bin/env python3
"""
Punto AI Game - Claude vs OpenAI
Uruchom: python main.py
"""

import time
import sys
from game_logic import PuntoGame
from ai_player import AIPlayer


class GameController:
    def __init__(self, delay: float = 2.0, verbose: bool = True):
        """
        Args:
            delay: Opóźnienie między ruchami (sekundy)
            verbose: Czy pokazywać szczegóły
        """
        self.game = PuntoGame()
        self.delay = delay
        self.verbose = verbose

        # Inicjalizacja graczy AI
        print("🎮 Inicjalizacja graczy AI...")
        print("🔵 Claude (Anthropic) vs 🔴 OpenAI")
        print("-" * 50)

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

        print("-" * 50)

    def play_game(self):
        """Główna pętla gry"""
        print("\n🎲 GRA ROZPOCZĘTA!\n")
        self._display_game_state()

        turn_number = 0

        while not self.game.is_game_over():
            turn_number += 1

            # Tura Claude
            print(f"\n{'=' * 60}")
            print(f"TURA {turn_number}A - 🔵 CLAUDE")
            print(f"{'=' * 60}")

            success = self._play_turn(self.claude_player, "claude")
            if not success:
                print("⚠️ Claude nie mógł wykonać ruchu - koniec gry")
                break

            self._display_game_state()

            if self.game.is_game_over():
                break

            time.sleep(self.delay)

            # Tura OpenAI
            print(f"\n{'=' * 60}")
            print(f"TURA {turn_number}B - 🔴 OPENAI")
            print(f"{'=' * 60}")

            success = self._play_turn(self.openai_player, "openai")
            if not success:
                print("⚠️ OpenAI nie mógł wykonać ruchu - koniec gry")
                break

            self._display_game_state()

            time.sleep(self.delay)

        # Koniec gry
        self._display_results()

    def _play_turn(self, player: AIPlayer, player_name: str) -> bool:
        """
        Wykonuje pojedynczą turę gracza
        Returns: True jeśli ruch się udał
        """
        hand = self.game.get_hand(player_name)
        opponent_name = "openai" if player_name == "claude" else "claude"
        opponent_hand_size = len(self.game.get_hand(opponent_name))

        print(f"💭 {player_name.upper()} myśli...")
        print(f"   Karty na ręku: {hand}")

        if not hand:
            print(f"   ⚠️ {player_name} nie ma więcej kart!")
            return False

        try:
            # Pobierz ruch od AI
            move = player.get_move(
                self.game.get_board_state(),
                hand,
                opponent_hand_size
            )

            print(f"   Wybrany ruch: karta {move['card']} na pozycję ({move['x']}, {move['y']})")

            if self.verbose and 'reasoning' in move:
                print(f"   📝 Uzasadnienie: {move['reasoning']}")

            # Wykonaj ruch
            self.game.make_move(move['x'], move['y'], move['card'], player_name)

            print(f"   ✅ Ruch wykonany!")
            return True

        except ValueError as e:
            print(f"   ❌ Błąd walidacji: {e}")
            # Spróbuj znaleźć poprawny ruch
            return self._try_fallback_move(player, player_name, hand)

        except Exception as e:
            print(f"   ❌ Nieoczekiwany błąd: {e}")
            return self._try_fallback_move(player, player_name, hand)

    def _try_fallback_move(self, player: AIPlayer, player_name: str, hand: list) -> bool:
        """Próbuje wykonać awaryjny ruch"""
        print(f"   🔄 Próba awaryjnego ruchu...")

        # Znajdź pierwszy możliwy ruch
        for card in hand:
            for y in range(6):
                for x in range(6):
                    is_valid, _ = self.game.is_valid_move(x, y, card, player_name)
                    if is_valid:
                        try:
                            self.game.make_move(x, y, card, player_name)
                            print(f"   ✅ Awaryjny ruch: {card} na ({x}, {y})")
                            return True
                        except:
                            continue

        print(f"   ❌ Brak możliwych ruchów!")
        return False

    def _display_game_state(self):
        """Wyświetla aktualny stan gry"""
        print("\n" + self.game.format_board())

        claude_hand = self.game.get_hand("claude")
        openai_hand = self.game.get_hand("openai")

        print(f"🔵 Claude: {len(claude_hand)} kart na ręku, {len(self.game.deck_claude)} w talii")
        print(f"🔴 OpenAI: {len(openai_hand)} kart na ręku, {len(self.game.deck_openai)} w talii")

    def _display_results(self):
        """Wyświetla wyniki gry"""
        print("\n" + "=" * 60)
        print("🏁 GRA ZAKOŃCZONA!")
        print("=" * 60)

        self._display_game_state()

        if self.game.winner:
            if self.game.winner == "claude":
                print("\n🏆 ZWYCIĘZCA: 🔵 CLAUDE! 🎉")
            else:
                print("\n🏆 ZWYCIĘZCA: 🔴 OPENAI! 🎉")
        else:
            print("\n🤝 REMIS - zabrakło kart!")

        print("\n" + "=" * 60)


def main():
    """Entry point"""
    print("""
╔═══════════════════════════════════════════════╗
║       PUNTO AI GAME                           ║
║       Claude vs OpenAI                        ║
╚═══════════════════════════════════════════════╝
    """)

    # Sprawdź czy są ustawione klucze API
    import os

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  UWAGA: Brak ANTHROPIC_API_KEY w zmiennych środowiskowych")
        print("   Ustaw: export ANTHROPIC_API_KEY='twoj-klucz'")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  UWAGA: Brak OPENAI_API_KEY w zmiennych środowiskowych")
        print("   Ustaw: export OPENAI_API_KEY='twoj-klucz'")
        sys.exit(1)

    try:
        controller = GameController(delay=1.5, verbose=True)
        controller.play_game()
    except KeyboardInterrupt:
        print("\n\n⚠️  Gra przerwana przez użytkownika")
    except Exception as e:
        print(f"\n❌ Błąd krytyczny: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
