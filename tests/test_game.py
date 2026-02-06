"""
Test Punto Game Logic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import (
    Card, Color, Deck, PlayerHand, create_two_player_hands,
    Board, WinChecker, PuntoMatch, Player, GameState
)


def test_cards():
    """Test card creation and comparison."""
    print("Testing cards...")
    
    card1 = Card(Color.RED, 5)
    card2 = Card(Color.BLUE, 3)
    card3 = Card(Color.RED, 7)
    
    assert str(card1) == "R5"
    assert card1.beats(card2)  # 5 > 3
    assert card3.beats(card1)  # 7 > 5
    assert not card2.beats(card1)  # 3 < 5
    
    print("✓ Cards work!")


def test_deck():
    """Test deck creation."""
    print("Testing deck...")
    
    deck = Deck()
    assert len(deck) == 72  # 4 colors × 9 values × 2 copies
    
    deck.shuffle()
    card = deck.draw()
    assert card is not None
    assert len(deck) == 71
    
    print("✓ Deck works!")


def test_player_hands():
    """Test 2-player hand creation."""
    print("Testing player hands...")
    
    hand1, hand2 = create_two_player_hands()
    
    # Each player gets 2 colors × 9 values × 2 copies = 36 cards
    assert len(hand1) == 36
    assert len(hand2) == 36
    
    # Colors should be different
    assert set(hand1.colors) != set(hand2.colors)
    
    print("✓ Player hands work!")


def test_board():
    """Test board placement and validation."""
    print("Testing board...")
    
    board = Board()
    card1 = Card(Color.RED, 5)
    card2 = Card(Color.BLUE, 3)
    card3 = Card(Color.GREEN, 7)
    
    # First move can be anywhere
    assert board.place(3, 3, card1)
    
    # Must be adjacent
    assert not board.can_place(0, 0, card2)  # Not adjacent
    assert board.place(3, 4, card2)  # Adjacent, ok
    
    # Can stack with higher value
    assert board.place(3, 3, card3)  # 7 > 5, ok
    
    print(board)
    print("✓ Board works!")


def test_win_checker():
    """Test win condition detection."""
    print("Testing win checker...")
    
    board = Board()
    checker = WinChecker(win_length=5)
    
    # Place 5 red cards in a row
    for i in range(5):
        board.place(2, i, Card(Color.RED, 5 + i % 3))
    
    winner = checker.check_win(board)
    assert winner == Color.RED
    
    print("✓ Win checker works!")


def test_match_flow():
    """Test basic match flow."""
    print("Testing match flow...")
    
    match = PuntoMatch("player1", "player2")
    assert match.state == GameState.WAITING
    
    match.start()
    assert match.state == GameState.ACTIVE
    
    # Get current card and make a move
    current = match.get_current_card()
    assert current is not None
    
    result = match.make_move(Player.ONE, 3, 3, 0)
    assert result["success"]
    
    print(f"State: {match.get_state()}")
    print("✓ Match flow works!")


def test_full_round():
    """Test playing until someone wins a round."""
    print("Testing full round...")
    
    match = PuntoMatch("alice", "bob")
    match.start()
    
    moves = 0
    max_moves = 100  # Safety limit
    
    while match.state == GameState.ACTIVE and moves < max_moves:
        player = match.current_player
        hand = match.get_hand(player)
        card = hand[0] if hand else None
        
        if not card:
            break
        
        # Find a valid move
        valid_moves = match.board.get_valid_moves(card)
        if not valid_moves:
            break
        
        row, col = valid_moves[0]
        result = match.make_move(player, row, col, 0)
        moves += 1
        
        if result.get("round_end") or result.get("match_end"):
            print(f"Round ended after {moves} moves!")
            print(f"Result: {result}")
            break
    
    print(f"Played {moves} moves")
    print("✓ Full round works!")


if __name__ == "__main__":
    test_cards()
    test_deck()
    test_player_hands()
    test_board()
    test_win_checker()
    test_match_flow()
    test_full_round()
    
    print("\n" + "=" * 40)
    print("All tests passed! 🐜")
