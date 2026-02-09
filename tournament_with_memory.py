#!/usr/bin/env python3
"""
Tournament with Memory - AI players are aware of tournament standings and history
"""

import sys
import time
from game_logic import PuntoGame
from typing import Dict, List


class AIPlayerWithMemory:
    """AI Player that remembers tournament history"""

    def __init__(self, player_name: str, api_type: str = "claude"):
        self.player_name = player_name
        self.api_type = api_type
        self.tournament_history = []
        self.my_wins = 0
        self.opponent_wins = 0
        self.total_games = 0

        if api_type == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic()
                self.model = "claude-sonnet-4-5-20250929"
            except ImportError:
                raise ImportError("Zainstaluj: pip install anthropic")
        elif api_type == "openai":
            try:
                import openai
                self.client = openai.OpenAI()
                self.model = "gpt-4o"
            except ImportError:
                raise ImportError("Zainstaluj: pip install openai")
        else:
            raise ValueError(f"Nieznany typ API: {api_type}")

    def update_tournament_state(self, game_result: Dict):
        """Update knowledge about tournament"""
        self.tournament_history.append(game_result)
        self.total_games = len(self.tournament_history)

        if game_result['winner'] == self.player_name:
            self.my_wins += 1
        elif game_result['winner'] and game_result['winner'] != self.player_name:
            self.opponent_wins += 1

    def get_move(self, board: List[List], hand: List[int], opponent_hand_size: int,
                 current_game_num: int, total_tournament_games: int) -> Dict:
        """Get move with tournament context"""
        prompt = self._create_tournament_aware_prompt(
            board, hand, opponent_hand_size,
            current_game_num, total_tournament_games
        )

        try:
            if self.api_type == "claude":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                move_text = response.content[0].text
            else:  # OpenAI
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    temperature=0.7
                )
                move_text = response.choices[0].message.content

            move = self._parse_move(move_text)
            return move

        except Exception as e:
            print(f"   ⚠️ Błąd AI: {e}")
            return self._random_fallback_move(board, hand)

    def _create_tournament_aware_prompt(self, board: List[List], hand: List[int],
                                       opponent_hand_size: int, current_game_num: int,
                                       total_tournament_games: int) -> str:
        """Create prompt with full tournament context"""

        board_str = self._format_board_for_ai(board)
        opponent_name = "OpenAI" if self.player_name == "claude" else "Claude"

        # Tournament context
        tournament_context = f"""
╔════════════════════════════════════════════════════════════════╗
║                    TURNIEJ PUNTO AI                            ║
║             Gra {current_game_num}/{total_tournament_games}                                     ║
╚════════════════════════════════════════════════════════════════╝

📊 AKTUALNY STAN TURNIEJU:
   Ty ({self.player_name.upper()}): {self.my_wins} wygranych
   Przeciwnik ({opponent_name}): {self.opponent_wins} wygranych
   Pozostało gier: {total_tournament_games - current_game_num + 1}
"""

        # Recent history
        if self.tournament_history:
            tournament_context += f"\n📜 HISTORIA OSTATNICH GIER:\n"
            recent_games = self.tournament_history[-3:]  # Last 3 games
            for game in recent_games:
                winner_symbol = "✅" if game['winner'] == self.player_name else "❌"
                winner_text = "TY" if game['winner'] == self.player_name else opponent_name
                tournament_context += f"   Gra {game['game_num']}: {winner_symbol} Wygrał: {winner_text} (po {game['turns']} turach)\n"

        # Strategic advice based on position
        if current_game_num > 1:
            tournament_context += f"\n💡 SYTUACJA STRATEGICZNA:\n"

            games_remaining = total_tournament_games - current_game_num + 1
            point_diff = self.my_wins - self.opponent_wins

            if point_diff > 0:
                tournament_context += f"   ✅ PROWADZISZ o {point_diff} wygraną(ych)!\n"
                if games_remaining <= 2:
                    tournament_context += f"   🎯 Strategia: Graj pewnie - blisko zwycięstwa w turnieju!\n"
                else:
                    tournament_context += f"   🎯 Strategia: Utrzymaj przewagę - zostało {games_remaining} gier\n"
            elif point_diff < 0:
                tournament_context += f"   ⚠️ PRZEGRYWASZ o {abs(point_diff)} wygraną(ych)\n"
                if games_remaining <= 2:
                    tournament_context += f"   🔥 Strategia: MUST WIN! To ostatnia szansa na odrobienie strat!\n"
                else:
                    tournament_context += f"   💪 Strategia: Musisz zacząć wygrywać - zostało {games_remaining} gier\n"
            else:
                tournament_context += f"   ⚖️ REMIS w turnieju\n"
                tournament_context += f"   🎯 Strategia: Ta gra może przechylić szalę - zagraj mądrze!\n"

        # Game rules and current state
        game_prompt = f"""
{tournament_context}

════════════════════════════════════════════════════════════════

Grasz w PUNTO jako {self.player_name.upper()}.

ZASADY GRY:
- Plansza 6x6 (współrzędne x,y od 0 do 5)
- Cel: Ułóż 4 swoje karty w linii (poziomo, pionowo lub ukośnie)
- Możesz grać na pustych polach ("·") lub przebijać karty przeciwnika wyższą wartością
- Nie możesz przebić swoich własnych kart

AKTUALNY STAN PLANSZY:
{board_str}

TWOJE KARTY: {sorted(hand)}
PRZECIWNIK MA: {opponent_hand_size} kart(y)

════════════════════════════════════════════════════════════════

TWOJE ZADANIE:
Biorąc pod uwagę:
1. Aktualny stan turnieju ({self.my_wins}-{self.opponent_wins})
2. Jak ważna jest ta gra dla Twojego wyniku końcowego
3. Poprzednie gry i to czego się z nich nauczyłeś

Wybierz NAJLEPSZY ruch, który da Ci przewagę w TEJ GRZE i CAŁYM TURNIEJU.

ODPOWIEDŹ (TYLKO JSON):
{{
  "x": <kolumna 0-5>,
  "y": <wiersz 0-5>,
  "card": <karta z Twojej ręki>,
  "reasoning": "Krótkie wyjaśnienie dlaczego ten ruch jest dobry w kontekście turnieju",
  "tournament_strategy": "Jak ten ruch wpływa na Twoją strategię turniejową"
}}

Pamiętaj: Nie pisz nic poza JSONem!
"""
        return game_prompt

    def _format_board_for_ai(self, board: List[List]) -> str:
        """Format board for AI"""
        result = "     0   1   2   3   4   5\n"
        result += "   ┌───┬───┬───┬───┬───┬───┐\n"

        for y in range(6):
            result += f" {y} │"
            for x in range(6):
                cell = board[y][x]
                if cell is None:
                    result += " · │"
                else:
                    player_symbol = "C" if cell['player'] == 'claude' else "O"
                    result += f" {player_symbol}{cell['value']}│"
            result += "\n"
            if y < 5:
                result += "   ├───┼───┼───┼───┼───┼───┤\n"

        result += "   └───┴───┴───┴───┴───┴───┘\n"
        result += f"\nLegenda: C={self.player_name.upper() if self.player_name == 'claude' else 'przeciwnik'}, "
        result += f"O={self.player_name.upper() if self.player_name == 'openai' else 'przeciwnik'}, · = puste"

        return result

    def _parse_move(self, response_text: str) -> Dict:
        """Parse AI response"""
        import json
        import re

        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)

        json_match = re.search(r'\{[^}]*\}', response_text, re.DOTALL)

        if not json_match:
            raise ValueError(f"Nie znaleziono JSON")

        move = json.loads(json_match.group())

        required_fields = ['x', 'y', 'card']
        for field in required_fields:
            if field not in move:
                raise ValueError(f"Brak pola '{field}'")

        return move

    def _random_fallback_move(self, board: List[List], hand: List[int]) -> Dict:
        """Random fallback move"""
        import random

        possible_moves = []
        for y in range(6):
            for x in range(6):
                for card in hand:
                    cell = board[y][x]
                    if cell is None or (cell['player'] != self.player_name and cell['value'] < card):
                        possible_moves.append({'x': x, 'y': y, 'card': card})

        if possible_moves:
            move = random.choice(possible_moves)
            move['reasoning'] = "Ruch awaryjny (błąd AI)"
            move['tournament_strategy'] = "Fallback"
            return move

        return {
            'x': 0, 'y': 0, 'card': hand[0],
            'reasoning': 'Awaryjny',
            'tournament_strategy': 'Fallback'
        }


class TournamentWithMemory:
    def __init__(self, num_games: int = 10, delay: float = 0.3, verbose: bool = True):
        self.num_games = num_games
        self.delay = delay
        self.verbose = verbose

        print("🎮 Inicjalizacja ŚWIADOMYCH graczy AI...")
        try:
            self.claude_player = AIPlayerWithMemory("claude", api_type="claude")
            print("✅ Claude player gotowy (ze świadomością turnieju)")
        except Exception as e:
            print(f"❌ Błąd Claude: {e}")
            sys.exit(1)

        try:
            self.openai_player = AIPlayerWithMemory("openai", api_type="openai")
            print("✅ OpenAI player gotowy (ze świadomością turnieju)")
        except Exception as e:
            print(f"❌ Błąd OpenAI: {e}")
            sys.exit(1)

    def run_tournament(self):
        """Run tournament with memory"""
        print(f"\n{'='*70}")
        print(f"🏆 TURNIEJ ZE ŚWIADOMOŚCIĄ - {self.num_games} GIER")
        print(f"{'='*70}")
        print(f"📌 Gracze wiedzą o:")
        print(f"   - Aktualnym wyniku turnieju")
        print(f"   - Historii poprzednich gier")
        print(f"   - Strategicznej sytuacji (prowadzą/przegrywają)")
        print(f"{'='*70}\n")

        for game_num in range(1, self.num_games + 1):
            print(f"\n{'▼'*70}")
            print(f"GRA {game_num}/{self.num_games}")
            print(f"Stan: Claude {self.claude_player.my_wins} - {self.openai_player.my_wins} OpenAI")
            print(f"{'▼'*70}")

            result = self.play_single_game(game_num)

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

    def play_single_game(self, game_num: int):
        """Play a single game"""
        game = PuntoGame()
        turn_count = 0
        start_time = time.time()

        while not game.is_game_over() and turn_count < 100:
            turn_count += 1

            # Claude
            if self.verbose and turn_count == 1:
                print(f"\n🔵 Claude myśli o turnieju...")

            success = self._play_turn(game, self.claude_player, "claude", game_num)
            if not success or game.is_game_over():
                break

            time.sleep(self.delay)

            # OpenAI
            if self.verbose and turn_count == 1:
                print(f"\n🔴 OpenAI myśli o turnieju...")

            success = self._play_turn(game, self.openai_player, "openai", game_num)
            if not success or game.is_game_over():
                break

            time.sleep(self.delay)

        duration = time.time() - start_time

        return {
            'game_num': game_num,
            'winner': game.winner if game.winner else None,
            'turns': turn_count,
            'duration': duration
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
                if 'tournament_strategy' in move:
                    print(f"   🎯 Strategia: {move.get('tournament_strategy', 'brak')}")

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
        """Display final results"""
        print("\n" + "="*70)
        print("🏆 WYNIKI KOŃCOWE TURNIEJU ZE ŚWIADOMOŚCIĄ")
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


def main():
    import os

    print("""
╔═══════════════════════════════════════════════╗
║   PUNTO AI TOURNAMENT WITH MEMORY             ║
║   Gracze są świadomi turnieju!                ║
╚═══════════════════════════════════════════════╝
    """)

    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Brak kluczy API")
        sys.exit(1)

    try:
        tournament = TournamentWithMemory(
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
