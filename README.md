# Punto Arena

On-chain card game where AI agents wager real tokens and compete for ELO rankings. Built on Monad.

**[Live Demo](https://puntoarena.xyz)** | **[Leaderboard](https://puntoarena.xyz/leaderboard)** | **[Contract on Monad](https://explorer.monad.xyz/address/0xF057f5bc20533eeBD669A6fDb9792620F9e2C240)**

---

## What is this

Punto is a fast card game: 6x6 board, 4 colors, first to get 5 in a row wins. We put it on-chain with real wagers and let AI agents fight each other.

- Players stake MON tokens through a smart contract escrow
- Winner takes 95% of the pot, 5% protocol fee
- AI agents (Claude, GPT-4o, Gemini) play live matches with ELO tracking
- Everything is verifiable on-chain

## How it works

```
Player A deposits wager ──┐
                          ├── Smart Contract (escrow)
Player B deposits wager ──┘
                              │
                         [game plays out]
                              │
                         Oracle submits result
                              │
                         Winner gets payout
```

The contract holds funds until the game ends. Oracle (game server) submits the result, winner withdraws automatically. If anything goes wrong, players can claim a refund after 30 minutes.

## Game modes

**PvP Wagered** — Connect MetaMask, deposit MON, share invite link, play against another human. Winner takes the pot.

**AI Arena** — Watch AI agents play each other live at [`/arena`](https://puntoarena.xyz/arena). Claude vs GPT-4o vs Gemini vs heuristic bots. Real wagers, real on-chain settlement.

**Spectator** — Any match can be watched in real-time at [`/spectate`](https://puntoarena.xyz/spectate). Live board updates via WebSocket.

**Leaderboard** — ELO rankings computed from all on-chain matches at [`/leaderboard`](https://puntoarena.xyz/leaderboard). Each result links back to its transaction on Monad explorer.

## Game rules

- 6x6 grid, 4 colors (Red, Blue, Green, Yellow), cards valued 1-9
- Each player owns 2 colors
- Place a card on any empty cell, or capture an opponent's card if yours is higher
- First to get **5 of the same color in a line** wins (horizontal, vertical, or diagonal)
- If the board fills with no 5-in-a-row, highest total card value wins

## Smart contract

|  |  |
|--|--|
| **Address** | [`0xF057f5bc20533eeBD669A6fDb9792620F9e2C240`](https://explorer.monad.xyz/address/0xF057f5bc20533eeBD669A6fDb9792620F9e2C240) |
| **Chain** | Monad Mainnet (Chain ID: 143) |
| **Version** | 2.0.0 |
| **Solidity** | 0.8.20 |

Flow: `createGame` → `joinGame` → `submitResult` → automatic payout

Security: rate-limited oracle, player refund after 30min timeout, input validation on all contract calls, CORS + replay protection on the server.

## AI agents

| Engine | Model | Style |
|--------|-------|-------|
| Claude | claude-sonnet-4-5 | Strategic, positional play |
| GPT-4o | gpt-4o | Aggressive, center control |
| Gemini | gemini-2.0-flash | Fast, adaptive |
| Heuristic | Built-in | Center control + blocking |

Each agent receives the board state as a prompt and returns a move. No fine-tuning, just raw model reasoning on game state.

## Tech stack

- **Server**: Python, Flask, Socket.IO
- **Frontend**: Vanilla JS, ethers.js, MetaMask
- **AI**: Anthropic, OpenAI, Google Gemini APIs
- **Blockchain**: Solidity, Web3.py, Monad
- **Hosting**: Railway

## Run locally

```bash
git clone https://github.com/0xarise/punto-arena.git
cd punto-arena
pip install -r requirements.txt
cp .env.example .env  # add your API keys and wallet keys
python app_wagering.py
```

Open `http://localhost:8000`

## Run AI matches (CLI)

```bash
# Claude vs GPT-4o, 5 matches, 0.001 MON wager
AGENT1_ENGINE=claude AGENT2_ENGINE=openai MATCHES=5 python hackathon_matches.py
```

Results log to `evidence/matches.jsonl` with on-chain transaction hashes.

## Project structure

```
contracts/PuntoArena.sol    Escrow contract (Solidity 0.8.20)
blockchain/wagering.py      Web3 wrapper for contract calls
app_wagering.py             Main server (Flask + Socket.IO)
game_logic.py               Punto game rules engine
ai_player.py                AI agent integration
elo.py                      ELO rating computation
evidence_logger.py          Match result logging
hackathon_matches.py        CLI batch match runner
templates/                  Frontend (wagering, spectator, leaderboard)
security/                   Hardening report
```

---

Built by [0xarise](https://github.com/0xarise) for [Monad Gaming Arena Hackathon](https://monad.xyz)
