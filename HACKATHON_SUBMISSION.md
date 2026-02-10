# PUNTO ARENA - Monad Gaming Arena Submission

## Overview
**Punto Arena** is an on-chain wagering platform for the classic card game Punto, deployed on Monad mainnet. Features AI vs AI arena with ELO rankings, human PvP wagering, and live spectator mode.

## Key Features
- **On-chain wagering** - Escrow-based betting with automatic payouts (95% to winner, 5% protocol fee)
- **AI Arena** - Multiple AI engines compete: Claude, GPT-4o, Gemini, Heuristic — auto-loop runs matches continuously
- **vs AI Single Player** - Play against Claude, GPT-4o, or heuristic bot with tactical board analysis
- **ELO Leaderboard** - Dual rankings: AI agent ELO + player wallet ELO
- **Live Spectator Lobby** - Browse active matches, watch AI vs AI live, one-click "Next Match" chaining
- **Human PvP** - MetaMask-powered wagering between human players
- **VICTORY / REKT** - GTA-style game over screens with animations and sound effects
- **5-in-a-row rules** - 4-color Punto variant (same color, 5 in a line to win)
- **Security hardened** - Turn enforcement, CORS restriction, rate limiting, contract tests

## Technical Stack
- **Smart Contract:** Solidity 0.8.20, PuntoArena v2.0
- **Backend:** Python Flask + Socket.IO
- **Frontend:** Vanilla JS + ethers.js + MetaMask
- **AI:** Anthropic Claude, OpenAI GPT-4o, Google Gemini, Heuristic engine
- **Chain:** Monad Mainnet (Chain ID: 143)

## Contract Details
| Field | Value |
|-------|-------|
| **Address** | `0xF057f5bc20533eeBD669A6fDb9792620F9e2C240` |
| **Version** | v2.0 (with player refund mechanism) |
| **Chain** | Monad Mainnet (Chain ID: 143) |
| **Oracle** | `0xAA7417EAB05B656756B0125663D30d9d8de0b6A6` |
| **Protocol Fee** | 5% (500 bps) |
| **Explorer** | [View on SocialScan](https://monad.socialscan.io/address/0xF057f5bc20533eeBD669A6fDb9792620F9e2C240) |

## AI Agent ELO Rankings

| Rank | Engine | ELO | W/L | Winrate | Matches |
|------|--------|-----|-----|---------|---------|
| 1 | Claude (Sonnet 4.5) | 1244 | 3/0 | 100% | 3 |
| 2 | OpenAI (GPT-4o) | 1220 | 3/1 | 75% | 4 |
| 3 | Gemini (2.0 Flash) | 1201 | 1/1 | 50% | 2 |
| 4 | Claude (Haiku 4.5) | 1195 | 2/2 | 50% | 4 |
| 5 | Heuristic | 1141 | 8/13 | 38% | 21 |

**400+ completed matches** across 5 engine/model combinations, all on-chain verified.

## Evidence Artifacts
```
evidence/
  matches.jsonl     # 400+ match records with full tx hashes
  summary.csv       # Aggregated stats
  tx_links.md       # Explorer links for all transactions
  winrate_report.md # Per-engine winrate analysis
```

## Security Hardening
- 5/5 contract hardening tests pass (see `security/HARDENING_REPORT.md`)
- Server-side turn enforcement + move rate limiting
- CORS restricted to localhost
- Credentials sanitized from all docs
- Frontend chaos test suite (10 stress tests)

## Gaming Arena Bounty Criteria

| Requirement | Status |
|-------------|--------|
| Game implementation | Punto card game (5-in-a-row, 4 colors) |
| Wagering system | On-chain escrow with auto payouts |
| Strategic AI decisions | Claude, GPT-4o, Gemini, Heuristic engines |
| Win/loss handling | Automatic payouts via oracle |
| Match coordination | WebSocket + invite links |
| 5+ completed matches | 400+ matches on mainnet |
| Proper wager handling | Escrow + 95% winner payout |
| Leaderboard | ELO rankings with on-chain proof |
| Security | Contract tests + server hardening |

## Three Game Modes

### Mode 1: Single Player (Human vs AI)
```bash
python app.py  # http://localhost:5000
```

### Mode 2: Multiplayer Wagered (Human vs Human)
```bash
python app_wagering.py  # http://localhost:8000
```

### Mode 3: AI Arena (AI vs AI + Spectator)
```bash
python app_wagering.py  # Start server
# Open http://localhost:8000/arena to launch matches
# Open http://localhost:8000/leaderboard for rankings
```

## Files Structure
```
punto-ai-game/
  contracts/PuntoArena.sol      # Smart contract v2.0
  blockchain/wagering.py        # Web3 integration
  app_wagering.py               # Flask server (wagering + arena + leaderboard)
  hackathon_matches.py          # AI vs AI match simulator
  game_logic.py                 # Punto game rules (5-in-a-row)
  ai_player.py                  # Claude/GPT-4o/Gemini integration
  elo.py                        # ELO ranking computation
  evidence_logger.py            # Match evidence logging
  test_contract_hardening.py    # Contract security tests
  test_frontend_chaos.py        # Frontend stress tests (10 tests)
  security/HARDENING_REPORT.md  # Security audit report
  templates/
    wagering.html               # PvP wagering UI
    spectate.html               # Live spectator mode
    leaderboard.html            # ELO rankings page
  static/wagering.js            # MetaMask frontend
  evidence/                     # Match evidence (JSONL, CSV, MD)
```

## Run Locally
```bash
pip install -r requirements_wagering.txt
cp .env.example .env  # Configure keys
python app_wagering.py
# Open http://127.0.0.1:8000
```

## Run AI Matches
```bash
# Heuristic vs Heuristic (free)
AGENT1_ENGINE=heuristic AGENT2_ENGINE=heuristic python hackathon_matches.py

# Claude vs OpenAI
AGENT1_ENGINE=claude AGENT2_ENGINE=openai python hackathon_matches.py

# Gemini vs Claude Haiku
AGENT1_ENGINE=gemini AGENT2_ENGINE=claude AGENT2_MODEL=claude-haiku-4-5-20251001 python hackathon_matches.py
```

## Team
- **Beru** (@0xtrytoexploit) - AI Agent Developer

---

*Target: $10,000 Gaming Arena Bounty*
*Contract: 0xF057f5bc20533eeBD669A6fDb9792620F9e2C240 (Monad Mainnet)*
*Submitted: February 2026*
