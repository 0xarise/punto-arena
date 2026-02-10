#!/usr/bin/env python3
"""
Hackathon Match Simulator
Play wagered on-chain matches between two wallets with real agent-vs-agent logic.
"""

import os
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

from game_logic import PuntoGame
from ai_player import AIPlayer
import evidence_logger

load_dotenv()

# ============================================================================
# CONFIG
# ============================================================================

RPC_URL = os.getenv("MONAD_RPC_URL", "https://rpc.monad.xyz")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

# Wallet 1 signs results (oracle/deployer in current setup)
WALLET1_KEY = os.getenv("WALLET1_PRIVATE_KEY") or os.getenv("ORACLE_PRIVATE_KEY")
WALLET2_KEY = os.getenv("WALLET2_PRIVATE_KEY")

WAGER_AMOUNT_MON = float(os.getenv("MATCH_WAGER_MON", "0.01"))
WAGER_AMOUNT = Web3.to_wei(WAGER_AMOUNT_MON, "ether")

MATCH_COUNT = int(os.getenv("MATCH_COUNT", "5"))
MATCH_DELAY_SEC = float(os.getenv("MATCH_DELAY_SEC", "2"))

# Agent engine selection:
# - heuristic (no API keys required)
# - openai (requires OPENAI_API_KEY)
# - claude (requires ANTHROPIC_API_KEY)
AGENT1_ENGINE = os.getenv("AGENT1_ENGINE", "heuristic").strip().lower()
AGENT2_ENGINE = os.getenv("AGENT2_ENGINE", "heuristic").strip().lower()
AGENT1_MODEL = os.getenv("AGENT1_MODEL")
AGENT2_MODEL = os.getenv("AGENT2_MODEL")

# Contract ABI (minimal)
CONTRACT_ABI = [
    {
        "inputs": [{"name": "roomId", "type": "string"}],
        "name": "createGame",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"name": "gameId", "type": "uint256"}],
        "name": "joinGame",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "gameId", "type": "uint256"},
            {"name": "winner", "type": "address"},
        ],
        "name": "submitResult",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "roomId", "type": "string"}],
        "name": "getGameByRoomId",
        "outputs": [
            {
                "components": [
                    {"name": "player1", "type": "address"},
                    {"name": "player2", "type": "address"},
                    {"name": "wager", "type": "uint256"},
                    {"name": "state", "type": "uint8"},
                    {"name": "winner", "type": "address"},
                    {"name": "createdAt", "type": "uint256"},
                    {"name": "roomId", "type": "string"},
                ],
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "gameCounter",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ============================================================================
# BLOCKCHAIN
# ============================================================================

w3 = Web3(Web3.HTTPProvider(RPC_URL))
contract = (
    w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
    if CONTRACT_ADDRESS
    else None
)


def send_tx(account, tx_func, value=0):
    """Build, sign, and send transaction"""
    tx = tx_func.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "value": value,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    return receipt


# ============================================================================
# AGENT ENGINES
# ============================================================================


def other_player(player: str) -> str:
    return "openai" if player == "claude" else "claude"


def valid_moves(game: PuntoGame, player: str) -> List[Dict]:
    hand = sorted(game.get_hand(player), key=lambda c: c['value'], reverse=True)
    moves: List[Dict] = []
    for card in hand:
        for y in range(6):
            for x in range(6):
                is_valid, _ = game.is_valid_move(x, y, card, player)
                if is_valid:
                    moves.append({"x": x, "y": y, "card": card})
    return moves


def immediate_winning_move(game: PuntoGame, player: str, moves: List[Dict]) -> Optional[Dict]:
    for move in moves:
        sim = PuntoGame()
        sim.board = [[None if c is None else dict(c) for c in row] for row in game.board]
        sim.current_turn = game.current_turn
        sim.winner = game.winner
        sim.deck_claude = [dict(c) for c in game.deck_claude]
        sim.deck_openai = [dict(c) for c in game.deck_openai]
        sim.hand_claude = [dict(c) for c in game.hand_claude]
        sim.hand_openai = [dict(c) for c in game.hand_openai]

        sim.make_move(move["x"], move["y"], move["card"], player)
        if sim.winner == player:
            return move
    return None


def count_line_length(board, x, y, color, dx, dy) -> int:
    """Count consecutive same-color cells in one direction from (x,y), not counting (x,y) itself."""
    count = 0
    cx, cy = x + dx, y + dy
    while 0 <= cx < 6 and 0 <= cy < 6:
        cell = board[cy][cx]
        if cell is not None and cell["color"] == color:
            count += 1
            cx += dx
            cy += dy
        else:
            break
    return count


def heuristic_score(game: PuntoGame, player: str, move: Dict) -> float:
    x = move["x"]
    y = move["y"]
    card = move["card"]
    cell = game.board[y][x]
    color = card["color"]

    # Center control (mild bonus)
    center_bonus = 3.0 - (abs(x - 2.5) + abs(y - 2.5)) * 0.5

    # Prefer captures of opponent cards
    capture_bonus = 0.0
    if cell is not None and cell["player"] != player:
        capture_bonus = 3.0
    elif cell is not None and cell["player"] == player and cell["color"] != color:
        capture_bonus = -1.0  # Replacing own card with different color is usually bad

    # Line length scoring: count how long a line this move creates in each direction
    # Directions: horizontal, vertical, diag-DR, diag-UR
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    best_line = 0
    line_score = 0.0

    for dx, dy in directions:
        fwd = count_line_length(game.board, x, y, color, dx, dy)
        bwd = count_line_length(game.board, x, y, color, -dx, -dy)
        total = fwd + bwd + 1  # +1 for the card we're placing

        if total > best_line:
            best_line = total

        # Exponential bonuses for longer lines
        if total >= 4:
            line_score += 50.0  # One step from winning
        elif total == 3:
            line_score += 15.0
        elif total == 2:
            line_score += 4.0

    # Card economy: prefer using low cards for non-critical moves
    card_penalty = 0.0
    if best_line < 3 and card["value"] >= 7:
        card_penalty = -2.0  # Don't waste high cards on weak positions

    return center_bonus + capture_bonus + line_score + card_penalty


def heuristic_move(game: PuntoGame, player: str) -> Dict[str, int]:
    moves = valid_moves(game, player)
    if not moves:
        raise RuntimeError(f"No valid moves for {player}")

    # 1) Win immediately if possible
    win_now = immediate_winning_move(game, player, moves)
    if win_now:
        return win_now

    # 2) Block opponent immediate win
    opponent = other_player(player)
    opp_moves = valid_moves(game, opponent)
    threat_cells = set()
    for opp_move in opp_moves:
        sim = PuntoGame()
        sim.board = [[None if c is None else dict(c) for c in row] for row in game.board]
        sim.current_turn = game.current_turn
        sim.winner = game.winner
        sim.deck_claude = [dict(c) for c in game.deck_claude]
        sim.deck_openai = [dict(c) for c in game.deck_openai]
        sim.hand_claude = [dict(c) for c in game.hand_claude]
        sim.hand_openai = [dict(c) for c in game.hand_openai]
        sim.make_move(opp_move["x"], opp_move["y"], opp_move["card"], opponent)
        if sim.winner == opponent:
            threat_cells.add((opp_move["x"], opp_move["y"]))

    if threat_cells:
        blockers = [m for m in moves if (m["x"], m["y"]) in threat_cells]
        if blockers:
            return max(blockers, key=lambda m: (m["card"]["value"], heuristic_score(game, player, m)))

    # 3) Best heuristic move
    return max(moves, key=lambda m: heuristic_score(game, player, m))


class MatchAgent:
    def __init__(self, label: str, side: str, engine: str, model: Optional[str] = None):
        self.label = label
        self.side = side  # "claude" or "openai"
        self.engine = engine
        self.model = model
        self.llm_player: Optional[AIPlayer] = None

        if engine in {"openai", "claude", "gemini"}:
            try:
                self.llm_player = AIPlayer(side, api_type=engine, model=model)
            except Exception as exc:
                print(f"⚠️  {label}: failed to init {engine} engine ({exc}), falling back to heuristic")
                self.engine = "heuristic"
                self.llm_player = None

    def choose_move(self, game: PuntoGame) -> Dict[str, int]:
        if self.llm_player is not None:
            hand = game.get_hand(self.side)
            opponent_hand_size = len(game.get_hand(other_player(self.side)))
            try:
                move = self.llm_player.get_move(game.get_board_state(), hand, opponent_hand_size)
                is_valid, _ = game.is_valid_move(move["x"], move["y"], move["card"], self.side)
                if is_valid:
                    return {"x": move["x"], "y": move["y"], "card": move["card"]}
                print(f"⚠️  {self.label}: LLM proposed invalid move, fallback to heuristic")
            except Exception as exc:
                print(f"⚠️  {self.label}: LLM move failed ({exc}), fallback to heuristic")

        return heuristic_move(game, self.side)


@dataclass
class SimulationResult:
    winner_side: str  # "claude" for player1, "openai" for player2
    turns: int
    start_side: str
    reason: str


def resolve_tiebreak(game: PuntoGame, start_side: str) -> Tuple[str, str]:
    score = {"claude": 0, "openai": 0}
    count = {"claude": 0, "openai": 0}

    for row in game.board:
        for cell in row:
            if cell is None:
                continue
            p = cell["player"]
            score[p] += int(cell["value"])
            count[p] += 1

    if score["claude"] > score["openai"]:
        return "claude", "tiebreak_total_card_value"
    if score["openai"] > score["claude"]:
        return "openai", "tiebreak_total_card_value"

    if count["claude"] > count["openai"]:
        return "claude", "tiebreak_piece_count"
    if count["openai"] > count["claude"]:
        return "openai", "tiebreak_piece_count"

    # Deterministic final tie-breaker
    return start_side, "tiebreak_starting_player"


def simulate_game_moves(agent1: MatchAgent, agent2: MatchAgent) -> SimulationResult:
    game = PuntoGame()
    start_side = random.choice(["claude", "openai"])
    current = start_side
    turns = 0
    max_turns = 200

    while turns < max_turns and not game.is_game_over():
        agent = agent1 if current == "claude" else agent2

        hand = game.get_hand(current)
        if not hand:
            # No cards available on this side; switch turns.
            current = other_player(current)
            if not game.get_hand(current):
                break
            continue

        move = agent.choose_move(game)
        is_valid, _ = game.is_valid_move(move["x"], move["y"], move["card"], current)
        if not is_valid:
            # Safety fallback: pick first valid move deterministically.
            fallback_moves = valid_moves(game, current)
            if not fallback_moves:
                current = other_player(current)
                continue
            move = fallback_moves[0]

        game.make_move(move["x"], move["y"], move["card"], current)
        turns += 1

        if game.winner:
            return SimulationResult(
                winner_side=game.winner,
                turns=turns,
                start_side=start_side,
                reason="five_in_line",
            )

        current = other_player(current)

    winner, reason = resolve_tiebreak(game, start_side)
    return SimulationResult(winner_side=winner, turns=turns, start_side=start_side, reason=reason)


# ============================================================================
# MATCH EXECUTION
# ============================================================================

def play_match(match_num, wallet1, wallet2, agent1: MatchAgent, agent2: MatchAgent):
    """Play a single wagered match. Returns match_data dict on success, None on failure."""
    from datetime import datetime, timezone

    print(f"\n{'='*60}")
    print(f"🎮 MATCH {match_num}")
    print(f"{'='*60}")

    room_id = f"hackathon_match_{match_num}_{int(time.time())}"
    tx_create = None
    tx_join = None
    tx_result = None

    # Step 1: Player 1 creates game on-chain
    print(f"\n1️⃣ Player 1 ({wallet1.address[:10]}...) creating game...")
    try:
        receipt = send_tx(wallet1, contract.functions.createGame(room_id), WAGER_AMOUNT)
        tx_create = receipt.transactionHash.hex()
        print(f"   ✅ Game created! TX: {tx_create[:20]}...")
        print(f"   Gas used: {receipt.gasUsed}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

    # Get game ID
    game_id = contract.functions.gameCounter().call()
    print(f"   Game ID: {game_id}")

    # Step 2: Player 2 joins game
    print(f"\n2️⃣ Player 2 ({wallet2.address[:10]}...) joining game...")
    try:
        receipt = send_tx(wallet2, contract.functions.joinGame(game_id), WAGER_AMOUNT)
        tx_join = receipt.transactionHash.hex()
        print(f"   ✅ Joined! TX: {tx_join[:20]}...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

    # Step 3: Agent-vs-agent gameplay
    print("\n3️⃣ Playing agent-vs-agent game...")
    result = simulate_game_moves(agent1, agent2)
    winner_num = 1 if result.winner_side == "claude" else 2
    winner_address = wallet1.address if winner_num == 1 else wallet2.address
    print(
        f"   🧠 Winner: Player {winner_num} ({winner_address[:10]}...)"
        f" | reason={result.reason} | turns={result.turns} | start={result.start_side}"
    )

    # Step 4: Oracle submits result (wallet1 is oracle)
    print("\n4️⃣ Oracle submitting result...")
    try:
        receipt = send_tx(wallet1, contract.functions.submitResult(game_id, winner_address))
        tx_result = receipt.transactionHash.hex()
        print(f"   ✅ Result submitted! TX: {tx_result[:20]}...")
        print("   💰 Payout sent to winner!")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

    # Verify game state
    game_data = contract.functions.getGameByRoomId(room_id).call()
    print("\n📊 Final game state:")
    print(f"   State: {['PENDING', 'ACTIVE', 'FINISHED', 'CANCELLED'][game_data[3]]}")
    print(f"   Winner: {game_data[4][:10]}...")

    # Build match data for evidence logging
    match_data = {
        "match_id": evidence_logger.get_next_match_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent1": {
            "engine": agent1.engine,
            "model": agent1.model or "default",
            "address": wallet1.address,
        },
        "agent2": {
            "engine": agent2.engine,
            "model": agent2.model or "default",
            "address": wallet2.address,
        },
        "game_id": game_id,
        "room_id": room_id,
        "tx_create": tx_create,
        "tx_join": tx_join,
        "tx_result": tx_result,
        "winner": "agent1" if winner_num == 1 else "agent2",
        "winner_address": winner_address,
        "reason": result.reason,
        "turns": result.turns,
        "wager_mon": WAGER_AMOUNT_MON,
        "moves": [],
        "explorer_base": "https://monad.socialscan.io/tx/",
    }

    evidence_logger.log_match(match_data)
    print(f"   📝 Evidence logged to evidence/matches.jsonl")

    return match_data


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("🏆 PUNTO ARENA - HACKATHON MATCH SIMULATOR")
    print("=" * 60)
    print(f"\n📍 Contract: {CONTRACT_ADDRESS}")
    print(f"🌐 RPC: {RPC_URL}")
    print(f"🎰 Wager per game: {WAGER_AMOUNT_MON} MON")

    if not CONTRACT_ADDRESS:
        print("\n❌ Missing CONTRACT_ADDRESS")
        print("   Set CONTRACT_ADDRESS in your .env")
        return

    if not WALLET1_KEY:
        print("\n❌ Missing WALLET1_PRIVATE_KEY (or ORACLE_PRIVATE_KEY)")
        print("   Set WALLET1_PRIVATE_KEY in your .env")
        return

    if not WALLET2_KEY:
        print("\n❌ Missing WALLET2_PRIVATE_KEY")
        print("   Set WALLET2_PRIVATE_KEY in your .env")
        return

    # Load wallets
    wallet1 = Account.from_key(WALLET1_KEY)
    wallet2 = Account.from_key(WALLET2_KEY)

    # Configure agents
    agent1 = MatchAgent("agent1", "claude", AGENT1_ENGINE, AGENT1_MODEL)
    agent2 = MatchAgent("agent2", "openai", AGENT2_ENGINE, AGENT2_MODEL)

    print(f"\n🤖 Agent1 (player1): engine={agent1.engine}, model={agent1.model or 'default'}")
    print(f"🤖 Agent2 (player2): engine={agent2.engine}, model={agent2.model or 'default'}")

    print(f"\n💰 Wallet 1: {wallet1.address}")
    print(f"   Balance: {w3.from_wei(w3.eth.get_balance(wallet1.address), 'ether')} MON")
    print(f"\n💰 Wallet 2: {wallet2.address}")
    print(f"   Balance: {w3.from_wei(w3.eth.get_balance(wallet2.address), 'ether')} MON")

    # Play matches
    successful = 0
    for i in range(1, MATCH_COUNT + 1):
        match_data = play_match(i, wallet1, wallet2, agent1, agent2)
        if match_data is not None:
            successful += 1
        time.sleep(MATCH_DELAY_SEC)

    # Generate evidence summary
    print(f"\n📊 Generating evidence reports...")
    evidence_logger.generate_summary()
    print(f"   ✅ evidence/summary.csv")
    print(f"   ✅ evidence/tx_links.md")
    print(f"   ✅ evidence/winrate_report.md")

    print(f"\n{'='*60}")
    print("🏁 HACKATHON COMPLETE!")
    print(f"{'='*60}")
    print(f"   Matches played: {successful}/{MATCH_COUNT}")
    print(f"   Contract: {CONTRACT_ADDRESS}")
    print(f"   Evidence: evidence/matches.jsonl ({successful} records)")
    print("   Ready for submission! ✅")


if __name__ == "__main__":
    main()
