"""
ELO rating system for Punto Arena AI agents.

Reads evidence/matches.jsonl, computes ELO per agent engine.
Starting ELO: 1200, K-factor: 32.
"""

import json
from pathlib import Path
from collections import defaultdict

EVIDENCE_DIR = Path(__file__).parent / "evidence"
MATCHES_FILE = EVIDENCE_DIR / "matches.jsonl"

STARTING_ELO = 1200
K_FACTOR = 32


def _read_matches() -> list[dict]:
    """Read all matches from JSONL."""
    if not MATCHES_FILE.exists():
        return []
    matches = []
    with open(MATCHES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                matches.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return matches


def _expected_score(rating_a: float, rating_b: float) -> float:
    """ELO expected score for player A vs player B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def _agent_label(agent: dict) -> str:
    """Build display label: 'engine' or 'engine (model)' for non-default models."""
    engine = agent.get("engine", "unknown")
    model = agent.get("model", "default")
    if model and model != "default":
        # Shorten common model prefixes
        short = model.replace("claude-", "").replace("models/", "")
        return f"{engine} ({short})"
    return engine


def compute_rankings() -> list[dict]:
    """
    Compute ELO rankings from match history.

    Returns list of dicts sorted by ELO descending:
    [{rank, engine, elo, wins, losses, winrate, matches, proof_links}]
    """
    matches = _read_matches()

    elos = defaultdict(lambda: STARTING_ELO)
    wins = defaultdict(int)
    losses = defaultdict(int)
    total = defaultdict(int)
    proof_links = defaultdict(list)

    explorer_base = "https://monad.socialscan.io/tx/"

    for m in matches:
        engine1 = _agent_label(m.get("agent1", {}))
        engine2 = _agent_label(m.get("agent2", {}))
        winner = m.get("winner", "")
        tx_result = m.get("tx_result", "")
        base = m.get("explorer_base", explorer_base)

        total[engine1] += 1
        total[engine2] += 1

        # Collect proof links
        if tx_result:
            link = f"{base}{tx_result}"
            proof_links[engine1].append(link)
            proof_links[engine2].append(link)

        # Determine winner/loser engines
        if winner == "agent1":
            winner_engine = engine1
            loser_engine = engine2
        elif winner == "agent2":
            winner_engine = engine2
            loser_engine = engine1
        else:
            continue  # skip draws/unknown

        wins[winner_engine] += 1
        losses[loser_engine] += 1

        # Update ELO ratings
        expected_w = _expected_score(elos[winner_engine], elos[loser_engine])
        expected_l = _expected_score(elos[loser_engine], elos[winner_engine])

        elos[winner_engine] += K_FACTOR * (1.0 - expected_w)
        elos[loser_engine] += K_FACTOR * (0.0 - expected_l)

    # Build ranked list
    rankings = []
    for engine in sorted(total.keys()):
        w = wins[engine]
        l = losses[engine]
        m_count = total[engine]
        winrate = (w / m_count * 100) if m_count > 0 else 0

        rankings.append({
            "engine": engine,
            "elo": round(elos[engine]),
            "wins": w,
            "losses": l,
            "winrate": round(winrate, 1),
            "matches": m_count,
            "proof_links": proof_links[engine][:10],  # Cap at 10 links
        })

    # Sort by ELO descending
    rankings.sort(key=lambda r: r["elo"], reverse=True)

    # Assign ranks
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    return rankings


if __name__ == "__main__":
    rankings = compute_rankings()
    print("\n🏆 PUNTO ARENA - ELO RANKINGS")
    print("=" * 60)
    for r in rankings:
        print(f"  #{r['rank']} {r['engine']:12s}  ELO: {r['elo']:4d}  "
              f"W/L: {r['wins']}/{r['losses']}  "
              f"Winrate: {r['winrate']}%  "
              f"Matches: {r['matches']}")
