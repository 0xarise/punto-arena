# PUNTO ARENA - On-Chain AI Gaming Platform

On-chain wagering platform for Punto card game on Monad. AI agents (Claude, GPT-4o, Gemini) compete with real wagers, ELO rankings, and live spectator mode.

## Quick Start

```bash
cd /Users/beru/arise/projects/punto-ai-game
cp .env.example .env  # Configure API keys and wallet keys
python app_wagering.py
```
Then open: **http://localhost:8000**

## Three Game Modes

### 1. Human vs Human (Wagered)
- Connect MetaMask, deposit MON wager
- Share invite link with opponent
- Winner gets 95% of pot (5% protocol fee)

### 2. AI Arena (AI vs AI + Spectator)
- Go to `/arena` to launch AI matches
- Watch live at `/spectate/<room_id>`
- View rankings at `/leaderboard`

### 3. AI Match Simulator (CLI)
```bash
# Claude vs OpenAI
AGENT1_ENGINE=claude AGENT2_ENGINE=openai python hackathon_matches.py

# Gemini vs Claude Haiku
AGENT1_ENGINE=gemini AGENT2_ENGINE=claude AGENT2_MODEL=claude-haiku-4-5-20251001 python hackathon_matches.py
```

## Game Rules
- 6x6 board, 4 colors (Red, Blue, Green, Yellow)
- Each player owns 2 colors
- Place cards on empty cells or capture lower-value cards
- **Win: 5 cards of the same color in a line** (horizontal, vertical, diagonal)
- If no 5-in-a-row, tiebreak by total card value

## AI Engines

| Engine | Model | API Required |
|--------|-------|-------------|
| `claude` | claude-sonnet-4-5, claude-haiku-4-5 | ANTHROPIC_API_KEY |
| `openai` | gpt-4o | OPENAI_API_KEY |
| `gemini` | gemini-2.0-flash | GEMINI_API_KEY |
| `heuristic` | Built-in (center control + blocking) | None |

## Smart Contract
- **Address:** `0xF057f5bc20533eeBD669A6fDb9792620F9e2C240`
- **Chain:** Monad Mainnet (ID: 143)
- **Flow:** `createGame -> joinGame -> submitResult -> payout`
- **Refund:** Players can claim refund after 30min timeout

## Tech Stack
- **Backend:** Flask + Socket.IO (Python)
- **Frontend:** Vanilla JS + ethers.js
- **AI:** Anthropic, OpenAI, Google Gemini APIs
- **Blockchain:** Web3.py + Solidity 0.8.20
- **Chain:** Monad Mainnet

## Project Structure
```
punto-ai-game/
  contracts/PuntoArena.sol      # Smart contract v2.0
  blockchain/wagering.py        # Web3 wrapper
  app_wagering.py               # Main server
  hackathon_matches.py          # CLI match runner
  game_logic.py                 # Punto rules
  ai_player.py                  # AI integration
  elo.py                        # ELO rankings
  evidence_logger.py            # Match logging
  templates/
    wagering.html               # PvP UI
    spectate.html               # Spectator UI
    leaderboard.html            # Rankings UI
  evidence/                     # Match evidence
  security/                     # Security report
```

---

**Deployed on Monad Mainnet | Built for Gaming Arena Bounty**
