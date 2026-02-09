# Punto Arena - Submission Checklist

**Last Updated:** 2026-02-07 20:31 CET

---

## PROMPT FOR OPUS 4.6

```
Jesteś Principal Engineer + Delivery Lead dla projektu Punto Arena. Masz pełny dostęp do kontraktów, backendu i frontendu.
Twoim celem jest maksymalizacja szans na wygraną hackathonu (duża stawka), a nie ślepe odhaczanie listy.

Kontekst i źródła prawdy:
- SUBMISSION_CHECKLIST.md (ten plik)
- CONTEXT.md / CONTEXT_2026-02-07.md
- hackathon_matches.py
- app_wagering.py / app_multiplayer.py / app.py
- contracts/PuntoArena.sol
- ai_player.py
- game_logic.py

Tryb pracy:
1. Najpierw szybko audytujesz stan repo i identyfikujesz największe luki do „submit-ready".
2. Możesz odejść od checklisty, jeśli masz lepszy plan. Warunek: pokaż dlaczego plan jest lepszy dla end goal.
3. Wdrażasz zmiany end-to-end (kod + testy + evidence + docs), nie kończysz na samych rekomendacjach.
4. Priorytetyzujesz impact/ryzyko/czas. Jeśli coś jest overengineeringiem, tnij i dawaj wersję pragmatic MVP.
5. Każdą decyzję uzasadniasz krótko i konkretnie.

Nienegocjowalne wymagania (must pass):
- Brak sekretów/hardcoded keys.
- Oficjalne mecze muszą pokazywać decyzje LLM (nie czysty if/then jako główny silnik).
- Spójny on-chain flow: createGame -> joinGame -> submitResult -> verify payout/state.
- Publiczny dowód: pełne tx hash + linki explorer.
- Evidence artifacts: JSONL/CSV + winrate/summary.
- Submission docs spójne z realnym stanem kodu.

Twoja autonomia:
- Możesz proponować i wdrażać lepszą architekturę, jeśli zwiększa szansę wygranej.
- Możesz dodać leaderboard/ELO, hardening tests, chaos tests, contract tests jeśli ROI jest wysokie.
- Jeśli napotkasz blocker, przedstaw 2-3 realne opcje i rekomenduj jedną.

Format raportowania (po każdej większej iteracji):
- Co zrobiłeś.
- Jakie pliki zmieniłeś.
- Jakie testy odpaliłeś i wyniki.
- Jakie ryzyka zostały.
- Następne 3 kroki.

Definicja zakończenia:
- Wszystkie P0 z checklisty są spełnione i udokumentowane dowodami.
- Repo jest „judge-ready": reproducible demo, czytelne docs, twarde evidence.
```

---

## 🎮 DOCELOWA ARCHITEKTURA: 3 TRYBY

### Mode 1: Single Player (Human vs AI)
- **File:** `app.py`
- **Flow:** Human plays against AI locally
- **Wagering:** None (practice mode)
- **Status:** ✅ Working

### Mode 2: Multiplayer Wagered (Human vs Human)
- **File:** `app_wagering.py`
- **Flow:** Human vs Human with on-chain wagers
- **Wagering:** Yes (MON tokens via smart contract)
- **Status:** ✅ Working

### Mode 3: AI Arena (AI vs AI Wagered) ⭐ HACKATHON FOCUS
- **File:** `hackathon_matches.py`
- **Flow:** AI agents compete with real wagers
- **Wagering:** Yes (on-chain)
- **Spectator Mode:** 🔴 TODO - add live view/replay
- **Status:** ⚠️ Functional, needs polish

---

## 📁 PROJECT STRUCTURE

```
/Users/beru/arise/projects/punto-ai-game/
├── .env                    # MAIN CONFIG (Monad mainnet + API keys)
├── .env.example            # Template
├── .env.monad              # Testnet (blanked)
│
├── contracts/
│   └── PuntoArena.sol      # Smart contract
│
├── blockchain/
│   ├── deploy.js           # Testnet deploy
│   ├── deploy_mainnet.js   # Mainnet deploy
│   └── wagering.py         # Python wrapper
│
├── game_logic.py           # Core Punto game rules
├── ai_player.py            # LLM integration (Claude/OpenAI)
│
├── app.py                  # Mode 1: Single Player
├── app_multiplayer.py      # Mode 2 (no wager)
├── app_wagering.py         # Mode 2: Multiplayer Wagered
├── hackathon_matches.py    # Mode 3: AI Arena
│
├── static/
│   ├── game.js
│   ├── multiplayer.js
│   ├── wagering.js
│   └── style.css
│
├── templates/
│   ├── index.html
│   ├── multiplayer.html
│   └── wagering.html
│
├── evidence/               # 🔴 TODO: Create for submission
│   ├── matches.jsonl
│   └── summary.csv
│
└── SUBMISSION_CHECKLIST.md # This file
```

---

## 🔐 ENVIRONMENT CONFIGURATION

### Main `.env` (Template - DO NOT commit real keys!)
```bash
# Network
MONAD_RPC_URL=https://rpc.monad.xyz
CHAIN_ID=143

# Contract (DEPLOYED!)
CONTRACT_ADDRESS=0xF057f5bc20533eeBD669A6fDb9792620F9e2C240

# Wallets
ORACLE_ADDRESS=0xAA7417EAB05B656756B0125663D30d9d8de0b6A6
ORACLE_PRIVATE_KEY=<REDACTED - set in .env>
WALLET1_PRIVATE_KEY=<REDACTED - set in .env>
WALLET2_PRIVATE_KEY=<REDACTED - set in .env>

# Match Config
MATCH_WAGER_MON=0.01
MATCH_COUNT=5
MATCH_DELAY_SEC=2

# Agent Engines: heuristic | claude | openai
AGENT1_ENGINE=heuristic
AGENT2_ENGINE=heuristic
AGENT1_MODEL=
AGENT2_MODEL=

# AI API Keys
ANTHROPIC_API_KEY=<REDACTED - set in .env>
OPENAI_API_KEY=<REDACTED - set in .env>
GEMINI_API_KEY=<REDACTED - set in .env>

# Server
PORT=8000
```

---

## 📜 SMART CONTRACT

| Field | Value |
|-------|-------|
| **Address** | `0xF057f5bc20533eeBD669A6fDb9792620F9e2C240` |
| **Chain** | Monad Mainnet (Chain ID: 143) |
| **RPC** | `https://rpc.monad.xyz` |
| **Explorer** | https://monad.socialscan.io/address/0xF057f5bc20533eeBD669A6fDb9792620F9e2C240 |
| **Oracle** | `0xAA7417EAB05B656756B0125663D30d9d8de0b6A6` (BERU HOT) |
| **Protocol Fee** | 5% (500 bps) |
| **Refund Delay** | 30 minutes |

### Contract Functions
```solidity
createGame(string roomId) payable → uint256 gameId
joinGame(uint256 gameId) payable
submitResult(uint256 gameId, address winner) // Oracle only
refund(uint256 gameId) // After timeout
```

### Contract Events
```solidity
GameCreated(gameId, player1, wager, roomId)
GameJoined(gameId, player2)
GameFinished(gameId, winner, payout, fee)
GameCancelled(gameId, reason)
GameRefunded(gameId, player1, player2, refundAmount)
```

---

## 💰 WALLETS

| Name | Address | Balance | Role |
|------|---------|---------|------|
| **BERU HOT** | `0xAA7417EAB05B656756B0125663D30d9d8de0b6A6` | ~497 MON | Oracle + Player1 |
| **trytoexploit** | `0xb69Ba2De95da9a529fD055297d25dC8cBe6a16f8` | ~0.27 MON | Player2 |

---

## 🤖 AI ENGINES

| Engine | Implementation | API Required | Cost |
|--------|----------------|--------------|------|
| `heuristic` | Inline in hackathon_matches.py | None | Free |
| `claude` | ai_player.py | ANTHROPIC_API_KEY | ~$0.01/move |
| `openai` | ai_player.py | OPENAI_API_KEY | ~$0.01/move |

**For Hackathon Submission:**
```bash
# Use LLM engines to show "strategic AI decisions"
AGENT1_ENGINE=claude
AGENT2_ENGINE=openai
```

---

## ✅ STATUS (2026-02-07)

### Completed
- [x] Security cleanup: hardcoded secrets removed
- [x] Agent-vs-agent mode in hackathon_matches.py
- [x] Non-random strategy (heuristic engine)
- [x] On-chain flow working (create → join → submit → payout)
- [x] 1 test match successful (TX verified)

### P0 Must-Have (Remaining)
- [ ] 5+ matches vs different opponents with evidence
- [ ] Winrate report (neutral/positive over 10+ matches)
- [ ] Submission docs clean and consistent
- [ ] **Spectator mode for AI Arena** ⭐

### P1 Recommended
- [ ] Opponent adaptation (pattern detection)
- [ ] Bankroll management
- [ ] Evidence logger (JSONL/CSV export)
- [ ] Demo video (2-3 min)

### P2 Bonus
- [ ] Second game type
- [ ] Tournament/ranking mode
- [ ] Psychological tactics

---

## 🚀 RUN COMMANDS

```bash
cd /Users/beru/arise/projects/punto-ai-game

# Mode 1: Single Player (Human vs AI)
python app.py
# → http://localhost:5000

# Mode 2: Multiplayer Wagered (Human vs Human)
python app_wagering.py
# → http://localhost:8000

# Mode 3: AI Arena (AI vs AI)
python hackathon_matches.py
# Runs MATCH_COUNT matches, outputs to terminal

# Quick test (1 match)
MATCH_COUNT=1 python hackathon_matches.py

# With LLM engines
AGENT1_ENGINE=claude AGENT2_ENGINE=openai python hackathon_matches.py
```

---

## 📊 EVIDENCE NEEDED FOR SUBMISSION

```
evidence/
├── matches.jsonl          # One JSON per line, each match
├── summary.csv            # Aggregated stats
└── tx_links.md            # Explorer links for verification
```

### Match Record Format
```json
{
  "match_id": 1,
  "timestamp": "2026-02-07T19:50:00Z",
  "agent1": {"engine": "claude", "model": "claude-sonnet-4-5-20250929"},
  "agent2": {"engine": "openai", "model": "gpt-4o"},
  "tx_create": "0x82d2c7d56d6512a5ef0d...",
  "tx_join": "0x6f7fcafe398ee03e9762...",
  "tx_result": "0xd7b23c0763f50cf6cc87...",
  "winner": "agent1",
  "reason": "four_in_line",
  "turns": 15,
  "wager_mon": 0.01,
  "explorer_link": "https://monad.socialscan.io/tx/0x..."
}
```

---

## 🎯 NEXT STEPS (Priority Order)

1. **Add Spectator Mode** — WebSocket broadcast of AI vs AI moves for live viewing
2. **Add Evidence Logger** — Auto-save match results to evidence/
3. **Run 5+ Official Matches** — With Claude vs OpenAI engines
4. **Generate Winrate Report** — Summary stats for submission
5. **Record Demo Video** — 2-3 min showing all 3 modes
6. **Clean Submission Docs** — README + HACKATHON_SUBMISSION.md

---

## 🔗 LINKS

- **Contract Explorer:** https://monad.socialscan.io/address/0xF057f5bc20533eeBD669A6fDb9792620F9e2C240
- **Monad RPC:** https://rpc.monad.xyz
- **Hackathon Deadline:** 2026-02-15

---

*Prepared by Baru 🐜 | Ready for Opus 4.6*
