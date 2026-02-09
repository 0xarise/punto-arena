#!/usr/bin/env python3
"""
Demo script - testuje pojedyncze komponenty bez uruchamiania pełnej gry
"""

from game_logic import PuntoGame
from ai_player import AIPlayer
import os


def test_game_logic():
    """Test podstawowej logiki gry"""
    print("🧪 Test 1: Game Logic")
    print("-" * 50)

    game = PuntoGame()
    print("✅ Gra zainicjalizowana")
    print(f"   Claude hand: {game.hand_claude}")
    print(f"   OpenAI hand: {game.hand_openai}")
    print(game.format_board())

    # Test ruchu
    card = game.hand_claude[0]
    game.make_move(2, 2, card, "claude")
    print(f"✅ Claude zagrał {card} na (2,2)")
    print(game.format_board())

    print()


def test_ai_prompt():
    """Test generowania promptu dla AI (bez faktycznego wywołania API)"""
    print("🧪 Test 2: AI Prompt Generation")
    print("-" * 50)

    # Sprawdź czy klucze są ustawione
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    print(f"ANTHROPIC_API_KEY: {'✅ ustawiony' if has_anthropic else '❌ brak'}")
    print(f"OPENAI_API_KEY: {'✅ ustawiony' if has_openai else '❌ brak'}")

    if has_anthropic:
        try:
            player = AIPlayer("claude", api_type="claude")
            print("✅ Claude player zainicjalizowany")

            # Przykładowa plansza
            board = [[None]*6 for _ in range(6)]
            board[2][2] = {'player': 'claude', 'value': 5}
            board[3][3] = {'player': 'openai', 'value': 3}

            prompt = player._create_prompt(board, [7, 9], 2)
            print("\n📝 Przykładowy prompt dla Claude:")
            print("-" * 50)
            print(prompt[:500] + "...")

        except Exception as e:
            print(f"❌ Błąd inicjalizacji: {e}")

    print()


def test_ai_single_move():
    """Test pojedynczego ruchu AI (wymaga kluczy API)"""
    print("🧪 Test 3: Single AI Move")
    print("-" * 50)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Pominięto - brak ANTHROPIC_API_KEY")
        print("   Ustaw klucz aby przetestować: export ANTHROPIC_API_KEY='...'")
        return

    try:
        player = AIPlayer("claude", api_type="claude")
        game = PuntoGame()

        print("🤔 Claude myśli...")

        move = player.get_move(
            game.get_board_state(),
            game.get_hand("claude"),
            len(game.get_hand("openai"))
        )

        print(f"✅ Claude wybrał ruch:")
        print(f"   Karta: {move['card']}")
        print(f"   Pozycja: ({move['x']}, {move['y']})")
        print(f"   Reasoning: {move.get('reasoning', 'brak')}")

    except Exception as e:
        print(f"❌ Błąd: {e}")

    print()


def test_full_quick_game():
    """Test pełnej gry (3 tury każdego gracza)"""
    print("🧪 Test 4: Quick Game (6 tur)")
    print("-" * 50)

    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Pominięto - brak kluczy API")
        return

    try:
        from main import GameController

        # Krótka gra z szybkimi turami
        controller = GameController(delay=0.5, verbose=False)

        # Zagraj tylko kilka tur
        for i in range(3):
            print(f"\n--- Tura {i+1} ---")

            # Claude
            controller._play_turn(controller.claude_player, "claude")
            controller._display_game_state()

            if controller.game.is_game_over():
                break

            # OpenAI
            controller._play_turn(controller.openai_player, "openai")
            controller._display_game_state()

            if controller.game.is_game_over():
                break

        print("\n✅ Test zakończony (gra może być nieukończona)")

    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()

    print()


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════╗
║       PUNTO AI - DEMO & TESTS                 ║
╚═══════════════════════════════════════════════╝
    """)

    test_game_logic()
    test_ai_prompt()

    # Te testy wymagają kluczy API
    print("\n" + "=" * 60)
    print("TESTY WYMAGAJĄCE API (opcjonalne)")
    print("=" * 60 + "\n")

    test_ai_single_move()
    # test_full_quick_game()  # Odkomentuj aby przetestować krótką grę

    print("\n✅ Wszystkie testy zakończone!")
    print("\nAby uruchomić pełną grę: python main.py")
