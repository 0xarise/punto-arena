"""
Wallet ELO System
Tracks player ELO based on wallet address across PvP and AI games.
"""

import json
import os
from datetime import datetime, timezone

ELO_FILE = os.path.join(os.path.dirname(__file__), "evidence", "wallet_elo.jsonl")
DEFAULT_ELO = 1200
WIN_DELTA = 20
QUIT_PENALTY = 10


def _read_events():
    """Read all ELO events from the JSONL file."""
    if not os.path.exists(ELO_FILE):
        return []
    events = []
    with open(ELO_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def get_wallet_elo(wallet):
    """Get current ELO for a wallet address."""
    wallet = wallet.lower()
    elo = DEFAULT_ELO
    for event in _read_events():
        w = event.get("winner", "").lower()
        l = event.get("loser", "").lower()
        result = event.get("result")
        if result == "win":
            if w == wallet:
                elo += WIN_DELTA
            elif l == wallet:
                elo -= WIN_DELTA
        elif result == "quit":
            if l == wallet:
                elo -= QUIT_PENALTY
    return elo


def update_wallet_elo(winner_wallet, loser_wallet, result="win"):
    """
    Append an ELO event.
    result: 'win' | 'quit'
    win:  winner +20, loser -20
    quit: quitter (loser) -10, opponent unchanged
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "winner": winner_wallet.lower(),
        "loser": loser_wallet.lower(),
        "result": result,
    }
    os.makedirs(os.path.dirname(ELO_FILE), exist_ok=True)
    with open(ELO_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def get_wallet_rankings():
    """
    Compute rankings from all events.
    Returns sorted list: [{wallet, elo, wins, losses, quits, games_played}]
    """
    events = _read_events()
    wallets = {}

    for event in events:
        w = event.get("winner", "").lower()
        l = event.get("loser", "").lower()
        result = event.get("result")

        for addr in (w, l):
            if addr and addr not in wallets:
                wallets[addr] = {"elo": DEFAULT_ELO, "wins": 0, "losses": 0, "quits": 0, "games_played": 0}

        if result == "win":
            if w:
                wallets[w]["elo"] += WIN_DELTA
                wallets[w]["wins"] += 1
                wallets[w]["games_played"] += 1
            if l:
                wallets[l]["elo"] -= WIN_DELTA
                wallets[l]["losses"] += 1
                wallets[l]["games_played"] += 1
        elif result == "quit":
            if l:
                wallets[l]["elo"] -= QUIT_PENALTY
                wallets[l]["quits"] += 1
                wallets[l]["games_played"] += 1
            if w:
                wallets[w]["games_played"] += 1

    rankings = []
    for addr, data in wallets.items():
        rankings.append({
            "wallet": addr,
            "elo": data["elo"],
            "wins": data["wins"],
            "losses": data["losses"],
            "quits": data["quits"],
            "games_played": data["games_played"],
        })

    rankings.sort(key=lambda x: x["elo"], reverse=True)
    return rankings
