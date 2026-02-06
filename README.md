# 🎯 Punto Arena

**On-chain wagering for the classic Punto card game — built on Monad.**

[![Monad](https://img.shields.io/badge/Built%20on-Monad-purple)](https://monad.xyz)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 🎮 What is Punto?

Punto is a fast-paced card game where players race to create a line of 5 cards in their color on a shared 6×6 grid. Cards can be stacked if the new card has a higher value (dots).

**Punto Arena** brings this to web3 with:
- 💰 **Wagering** — Players stake MON tokens, winner takes the pot
- 🔒 **Escrow** — Smart contract holds funds until game ends
- ⚡ **Fast** — Built on Monad for instant finality
- 🏆 **Fair** — On-chain result verification

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+
- Monad testnet access

### Installation

```bash
# Clone
git clone https://github.com/your-repo/punto-arena
cd punto-arena

# Install contract dependencies
npm install

# Install game logic dependencies
pip install -r requirements.txt
```

### Deploy Contract

```bash
# Copy env template
cp .env.example .env
# Edit .env with your private key

# Deploy to Monad testnet
npx hardhat run scripts/deploy.js --network monad
```

### Run Game Server

```bash
cd server
python main.py
```

## 📁 Project Structure

```
punto-arena/
├── contracts/           # Solidity smart contracts
│   ├── PuntoArena.sol   # Main escrow contract
│   └── interfaces/
├── game/                # Python game logic
│   ├── cards.py         # Deck & cards (4 colors, 1-9)
│   ├── board.py         # 6×6 grid with stacking
│   ├── rules.py         # Win conditions
│   └── match.py         # Full game flow
├── server/              # FastAPI backend
├── frontend/            # React frontend
├── tests/               # Test suites
└── scripts/             # Deployment scripts
```

## 🎲 Game Rules

1. **Setup:** Each player gets 2 colors (36 cards total)
2. **Play:** Take turns placing cards on a 6×6 grid
3. **Stacking:** Higher value cards can cover lower ones
4. **Win:** First to get 5 cards of their color in a row
5. **Match:** Best of 3 rounds wins the wager

## 💰 Wagering Flow

```
Player A → deposits wager ─┐
                           ├→ Smart Contract (escrow)
Player B → deposits wager ─┘
                              │
                        [GAME PLAYS]
                              │
                              ▼
                   Winner claims: wager × 2 - 5% fee
```

## 🔧 Smart Contract

The `PuntoArena.sol` contract handles:
- Game creation with wager amount
- Player joining with matching wager
- Result submission (signed by game server)
- Winner payout with protocol fee
- Timeout refunds (24h)

## 🛠️ Tech Stack

- **Blockchain:** Monad (EVM compatible)
- **Contracts:** Solidity + Hardhat
- **Backend:** Python + FastAPI
- **Frontend:** React + ethers.js
- **Game Logic:** Pure Python (portable)

## 📜 License

MIT — see [LICENSE](LICENSE)

---

Built with 🐜 for [Monad Hackathon 2026](https://hackathon.monad.xyz)
