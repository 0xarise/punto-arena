"""
Evidence logger for Punto Arena hackathon matches.

Logs match results to JSONL, generates CSV summaries,
transaction link pages, and winrate reports.
"""

import json
import csv
import io
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

EVIDENCE_DIR = Path(__file__).parent / "evidence"
MATCHES_FILE = EVIDENCE_DIR / "matches.jsonl"


def _ensure_dir():
    EVIDENCE_DIR.mkdir(exist_ok=True)


def get_next_match_id() -> int:
    """Return next sequential match ID based on existing JSONL entries."""
    if not MATCHES_FILE.exists():
        return 1
    max_id = 0
    with open(MATCHES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                mid = entry.get("match_id", 0)
                if mid > max_id:
                    max_id = mid
            except json.JSONDecodeError:
                continue
    return max_id + 1


def log_match(match_data: dict):
    """Append one JSON line to evidence/matches.jsonl."""
    _ensure_dir()
    with open(MATCHES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(match_data, ensure_ascii=False) + "\n")


def _read_matches() -> list[dict]:
    """Read all matches from JSONL. Returns empty list if file missing."""
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


def generate_summary():
    """Generate summary.csv, tx_links.md, and winrate_report.md from matches.jsonl."""
    _ensure_dir()
    matches = _read_matches()

    _write_summary_csv(matches)
    _write_tx_links(matches)
    _write_winrate_report(matches)


def _write_summary_csv(matches: list[dict]):
    """Write evidence/summary.csv with key match columns."""
    path = EVIDENCE_DIR / "summary.csv"
    fieldnames = [
        "match_id", "timestamp", "agent1_engine", "agent2_engine",
        "winner", "turns", "wager_mon", "tx_result",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in matches:
            writer.writerow({
                "match_id": m.get("match_id", ""),
                "timestamp": m.get("timestamp", ""),
                "agent1_engine": m.get("agent1", {}).get("engine", ""),
                "agent2_engine": m.get("agent2", {}).get("engine", ""),
                "winner": m.get("winner", ""),
                "turns": m.get("turns", ""),
                "wager_mon": m.get("wager_mon", ""),
                "tx_result": m.get("tx_result", ""),
            })


def _write_tx_links(matches: list[dict]):
    """Write evidence/tx_links.md with explorer links for each match."""
    path = EVIDENCE_DIR / "tx_links.md"
    lines = ["# Transaction Links\n"]

    if not matches:
        lines.append("No matches recorded yet.\n")
    else:
        for m in matches:
            mid = m.get("match_id", "?")
            base = m.get("explorer_base", "https://monad.socialscan.io/tx/")
            lines.append(f"## Match {mid}\n")

            for tx_key, label in [
                ("tx_create", "Create"),
                ("tx_join", "Join"),
                ("tx_result", "Result"),
            ]:
                tx = m.get(tx_key, "")
                if tx:
                    lines.append(f"- **{label}**: [{tx}]({base}{tx})")
                else:
                    lines.append(f"- **{label}**: n/a")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_winrate_report(matches: list[dict]):
    """Write evidence/winrate_report.md with per-engine stats."""
    path = EVIDENCE_DIR / "winrate_report.md"

    total = len(matches)
    if total == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Winrate Report\n\nNo matches recorded yet.\n")
        return

    # Collect stats per engine
    engine_wins = defaultdict(int)
    engine_appearances = defaultdict(int)
    all_turns = []

    for m in matches:
        a1_engine = m.get("agent1", {}).get("engine", "unknown")
        a2_engine = m.get("agent2", {}).get("engine", "unknown")
        winner = m.get("winner", "")
        turns = m.get("turns", 0)

        engine_appearances[a1_engine] += 1
        engine_appearances[a2_engine] += 1

        if winner == "agent1":
            engine_wins[a1_engine] += 1
        elif winner == "agent2":
            engine_wins[a2_engine] += 1

        if isinstance(turns, (int, float)) and turns > 0:
            all_turns.append(turns)

    avg_turns = sum(all_turns) / len(all_turns) if all_turns else 0

    lines = [
        "# Winrate Report\n",
        f"**Total matches**: {total}  ",
        f"**Average turns per match**: {avg_turns:.1f}\n",
        "## Per-Engine Stats\n",
        "| Engine | Appearances | Wins | Winrate |",
        "|--------|------------|------|---------|",
    ]

    for engine in sorted(engine_appearances.keys()):
        apps = engine_appearances[engine]
        wins = engine_wins.get(engine, 0)
        rate = (wins / apps * 100) if apps > 0 else 0
        lines.append(f"| {engine} | {apps} | {wins} | {rate:.1f}% |")

    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
