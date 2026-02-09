# PUNTO ARENA - Debug Context

## Shared Agent Rule
- Before starting and after finishing work, read/update `/Users/beru/Desktop/AGENT_SCRATCHPAD.md` (append-only, no secrets).

## 🎯 Cel
Gra karciana Punto z **on-chain wagering** na Monad blockchain dla hackathonu.
Gracze deponują MON → grają → zwycięzca dostaje 95% puli automatycznie.

## 📁 Struktura

```
punto-ai-game/
├── app_wagering.py        # ⭐ GŁÓWNY SERWER (Flask + Socket.IO + Web3)
├── game_logic.py          # Logika gry Punto (PuntoGame class)
├── blockchain/
│   ├── wagering.py        # Web3 integration, oracle functions
│   └── PuntoArena_ABI.json
├── contracts/
│   └── PuntoArena.sol     # Smart contract (deployed)
├── static/
│   ├── wagering.js        # ⭐ FRONTEND JS (MetaMask + Socket.IO)
│   └── style.css
├── templates/
│   └── wagering.html
└── .env                   # Config (RPC, contract address, oracle key)
```

## 🔗 Flow gry

```
1. Player1 (browser) → Create Room → MetaMask deposit → createGame() on-chain
2. Player2 (browser) → Join via link → MetaMask deposit → joinGame() on-chain
3. Server detects both deposits → start_wagered_game() → deal cards
4. Players take turns via Socket.IO
5. Winner determined → Oracle calls submitResult() → auto payout
```

## 🐛 AKTUALNY PROBLEM

**Symptom:** Player2 dołącza, ale ma puste karty (`your_cards: []`)

**Gdzie szukać:**

### 1. `app_wagering.py` - join handler (~linia 85-170)
```python
@socketio.on('join_wagered_room')
def handle_join_wagered_room(data):
    # ... 
    # REJOIN PATH (gdy gracz reconnectuje):
    if existing_player:
        # Wysyła game_state_restored z your_cards
        'your_cards': sorted(game.hand_claude if player_role == 'player1' else game.hand_openai)
        # ^^^ PROBLEM: game.hand_openai może być puste!
```

### 2. `app_wagering.py` - start game (~linia 180-220)
```python
def start_wagered_game(room_id):
    # Sprawdza on-chain state
    if WAGERING_ENABLED and room['wager'] > 0:
        on_chain_game = blockchain.get_game_by_room_id(room_id)
        if not on_chain_game or on_chain_game['state'] != 1:  # 1 = ACTIVE
            # Czeka - NIE startuje gry!
            return
    
    # Inicjalizuje grę i rozdaje karty
    room['game'] = PuntoGame()
    # hand_claude = player1 cards
    # hand_openai = player2 cards
```

### 3. `game_logic.py` - PuntoGame class
```python
class PuntoGame:
    def __init__(self):
        self.hand_claude = [...]  # 18 kart dla player1
        self.hand_openai = [...]  # 18 kart dla player2
```

## 🔍 Debug checklist

1. **Czy `start_wagered_game()` jest wywoływane?**
   - Szukaj w logach: `🎲 Coin flip`
   - Jeśli NIE → problem z on-chain verification

2. **Czy `room['game']` istnieje gdy player2 joinuje?**
   - Dodaj: `print(f"DEBUG game exists: {room.get('game') is not None}")`

3. **Czy karty są rozdane?**
   - Dodaj: `print(f"DEBUG hand_openai: {game.hand_openai if game else 'NO GAME'}")`

4. **Timing issue?**
   - Player2 może dołączyć przez socket PRZED on-chain confirmation
   - Server nie wie że gracz zdeponował → nie startuje gry

## 🔧 Potencjalny fix

W `handle_join_wagered_room`, po dołączeniu player2, sprawdź on-chain i wymuś start:

```python
# Po dodaniu player2 do room:
if len(room['players']) == 2 and room['status'] == 'waiting':
    # Force check on-chain status
    on_chain = blockchain.get_game_by_room_id(room_id)
    if on_chain and on_chain['state'] == 1:  # ACTIVE on-chain
        start_wagered_game(room_id)
```

## 📍 Contract Info

- **Address:** `0xF057f5bc20533eeBD669A6fDb9792620F9e2C240` (v2.0)
- **Old Address:** `0x8B55cAB0051b542cB56D46d06E65CE8C0eFe48A5` (v1.0, deprecated)
- **Chain:** Monad Mainnet (143)
- **RPC:** `https://rpc.monad.xyz`

### v2.0 New Features:
- `claimRefund(gameId)` - gracze mogą sami refundować po 30min timeout
- `getGameIdByRoomId(roomId)` - helper do identyfikacji gry po roomId
- `canClaimRefund(gameId)` - sprawdza czy refund dostępny
- `GameRefunded` event - backend może nasłuchiwać

## 🧪 Test commands

```bash
# Run server (see stdout logs):
cd /Users/beru/punto-ai-game
source venv/bin/activate
python app_wagering.py

# Check on-chain game state:
python -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://rpc.monad.xyz'))
# ... check game state
"
```

## ✅ Co działa

- Contract deployment ✅
- On-chain deposits ✅
- Player1 UI (create room, see board) ✅
- 5 automated matches completed ✅

## ✅ FIXED (2026-02-05)

### Bug: Player2 gets empty cards on rejoin

**Root Cause:** Timing issue between `wager_confirmed` and `join_wagered_room` socket events.

Frontend emits in this order:
1. `wager_confirmed` (after on-chain tx confirms)
2. `join_wagered_room` (socket join)

But the server's `wager_confirmed` handler checked `len(room['players']) < 2` and returned early before player2 joined via socket. Then when player2 did join, `start_wagered_game()` would check on-chain state directly (potentially failing due to RPC timing). On rejoin, if `room['game']` was None, the rejoin path just logged a warning and returned without cards.

**Fix (3 changes in app_wagering.py):**

1. **wager_confirmed handler:** Now sets `room['wager_confirmed'] = True` flag before returning early. This flag signals that on-chain is verified.

2. **start_wagered_game():** Added early return if `room['game']` exists. If `room['wager_confirmed']` is True, skips on-chain check (frontend already verified).

3. **REJOIN path:** If `room['game']` is None but 2 players present, calls `start_wagered_game()` and sends `game_state_restored` if successful.

**New flow:**
1. `wager_confirmed` arrives → sets flag → returns (player not yet socket-joined)
2. `join_wagered_room` arrives → player joins → `start_wagered_game()` called
3. `start_wagered_game()` sees `wager_confirmed=True` → skips RPC check → starts game
4. `game_start` emitted to both players ✅

## ❌ Remaining issues

- None known for multiplayer flow

---

## 🚀 UX OVERHAUL (2026-02-05)

### New Features Added:

#### 1. AI vs AI Test Loop (`test_ai_loop.py`)
```bash
cd /Users/beru/punto-ai-game
source venv/bin/activate

# Run 10 games (default)
python test_ai_loop.py

# Run 100 games with verbose output
python test_ai_loop.py -n 100 -v

# Run 4 games in parallel
python test_ai_loop.py -n 20 --parallel 4
```
- Stress tests game engine with automated AI players
- Logs wins, timing, turn counts, errors
- Runs headless (no browser needed)
- Uses Socket.IO client directly

#### 2. Refresh Resilience
- Auto-reconnect MetaMask on page load
- Session persisted in localStorage (room_id, role, wager)
- Auto-rejoin room on socket reconnect
- Full board state restoration on refresh
- Session expires after 1 hour

#### 3. Turn Indicator
- Pulsing glow animation when it's your turn
- "Opponent's turn..." with pulse on their name
- Visual shake feedback when selecting card out of turn
- Clear text indicator: "🟢 YOUR TURN!" / "🔴 Waiting for opponent..."

#### 4. Wager Flow UX
- Loading spinner overlay during transactions
- Step-by-step status messages
- "Wager confirmed! Waiting for opponent..." message
- Opponent wallet address shown when they join

#### 5. Wallet-Only Login
- Removed nickname input field
- Uses truncated wallet address (0x1234...5678) as player name
- Simplified join flow

### Files Modified:
- `static/wagering.js` - State persistence, reconnect, indicators
- `templates/wagering.html` - UI simplification, removed nickname
- `static/style.css` - Pulse animations, loading spinner, visual feedback
- `app_wagering.py` - Better rejoin handling, get_game_state event
- NEW: `test_ai_loop.py` - AI vs AI stress test script

## 🎯 TODO (from playtesting 2026-02-05)

### Rematch Feature
- [ ] "Rematch" button after game ends
- [ ] Same room, same players, new game
- [ ] Keep session/connection alive

### Win Counter
- [ ] Track wins per wallet address in room
- [ ] Display: "0x8bcd...2Ce5: 1 | Beru: 2"
- [ ] Persist during session (reset on room close)

### Tested & Working ✅
- Multiplayer via Cloudflare tunnel
- Wager=0 bypasses blockchain
- CLI client can play
- Reconnect restores game state
- Game logic correct (diagonal win detected)

## 🔧 Fixes Applied (2026-02-05 ~02:50)

### Bug Fixes:
1. ✅ **Card colors in hand** - Now match player role (player1=blue, player2=red)
2. ✅ **Player names swapped** - Now shows "🎮 You (name)" and "👤 Opponent"

### New Features:
3. ✅ **Rematch button** - After game over, both players can request rematch
   - First player to click sees "Waiting for opponent..."
   - When both click, new game starts in same room
   - No page reload needed

### Still TODO:
4. ⏳ **Win counter** - Track wins per session (deferred)

### Cache Busting:
- JS version bumped to v=3


---

## Update 2026-02-07 (Security + Agent Track Plan)

# Punto Arena Context (2026-02-07)

## Data Stamp
- `2026-02-07 19:14:57 CET`

## What We Did Today
- Completed security cleanup for secret handling.
- Removed hardcoded private keys from:
  - `hardhat.config.js`
  - `blockchain/deploy_mainnet.js`
  - `hackathon_matches.py`
  - `fund_wallet2.py`
- Switched scripts/config to env-driven credentials.
- Sanitized local env files:
  - `.env` (blanked `ORACLE_PRIVATE_KEY`)
  - `.env.monad` (blanked deployer/oracle private keys)
- Added secure template: `.env.example`.
- Ran sanity checks successfully:
  - `python3 -m py_compile hackathon_matches.py fund_wallet2.py`
  - `node --check blockchain/deploy_mainnet.js`
  - `node --check hardhat.config.js`

## Current Status
- On-chain wagering flow exists (`app_wagering.py`) and can run with proper env setup.
- Security posture improved in codebase (no hardcoded keys in project scripts/config).
- Hackathon simulator still uses random winner logic (`hackathon_matches.py`) and is not valid proof of strategic play.
- AI gameplay exists, but not yet fully integrated into on-chain wagered agent-vs-agent mode.

## Immediate Next Steps (Priority)
1. Rotate all previously exposed keys immediately.
2. Refill `.env` using fresh keys and `.env.example` as template.
3. Implement real `agent-vs-agent` mode in wagered flow (no random winner path).
4. Add strategy + opponent adaptation + bankroll management.
5. Add evidence pipeline (match logs, tx hashes, winrate report).
6. Update submission docs to match actual implementation and evidence.

## Key Rotation Checklist
- Rotate:
  - `DEPLOYER_PRIVATE_KEY`
  - `ORACLE_PRIVATE_KEY`
  - `WALLET1_PRIVATE_KEY`
  - `WALLET2_PRIVATE_KEY`
  - `SENDER_PRIVATE_KEY`
- Replace values in secret storage / local `.env` only.
- Verify old keys have zero privileged use going forward.

## Prompt: On-Chain Operations Manager Agent
Use this as the operating prompt for an agent responsible for on-chain execution and verification.

```text
You are the On-Chain Operations Manager for Punto Arena.

Objective:
- Execute and verify all blockchain operations for wagered matches safely and deterministically.
- Produce auditable evidence for hackathon submission.

Hard Rules:
1) Never hardcode private keys or secrets in code, logs, or commits.
2) Read all credentials strictly from environment variables.
3) Before each transaction, validate: chain ID, contract address, account balance, nonce source, gas strategy.
4) On failure, stop and return a structured error report with root cause and retry guidance.
5) Do not mark a match complete without confirmed receipt and parsed on-chain state.
6) For each match, emit a machine-readable record including:
   - timestamp (UTC)
   - chain_id
   - contract_address
   - room_id
   - game_id
   - player addresses
   - wager
   - tx hashes (create/join/submit)
   - final state + winner
7) Keep idempotency: safe re-runs must not corrupt match/account state.

Execution Workflow:
A) Preflight
- Validate env vars: MONAD_RPC_URL, CONTRACT_ADDRESS, ORACLE_PRIVATE_KEY, WALLET1_PRIVATE_KEY, WALLET2_PRIVATE_KEY.
- Validate contract interface availability.
- Check balances for all signer accounts.

B) Match Lifecycle
- createGame(roomId) by player1 with wager.
- joinGame(gameId) by player2 with matching wager.
- verify ACTIVE state on-chain.
- receive winner from trusted game engine.
- submitResult(gameId, winner) as oracle.
- verify FINISHED state and payout effects.

C) Evidence Output
- Append JSONL record per match.
- Maintain CSV summary for judges.
- Keep deterministic filenames and timestamps.

Output Format:
- Always return:
  1) `status`: success|failed
  2) `summary`: one paragraph
  3) `transactions`: list with tx hash + purpose + status
  4) `evidence_paths`: generated files
  5) `next_actions`: concrete numbered steps
```


## Addendum 2026-02-07 (Implemented)
- `hackathon_matches.py` now runs real `agent-vs-agent` gameplay instead of random winner selection.
- Added default deterministic heuristic agents (no API key required).
- Added optional LLM agents (`openai` / `claude`) with fallback to heuristic if init/move fails.
- Added env config knobs in `.env.example` for engines and match runtime (`AGENT1_ENGINE`, `AGENT2_ENGINE`, `MATCH_COUNT`, `MATCH_DELAY_SEC`, etc.).

## Update 2026-02-07 (Definition of Done)

- Added submission gate checklist file: `DOD_CHECKLIST.md`.
- Checklist scope: security, strict LLM decision proof, on-chain verification, evidence artifacts, and go/no-go criteria.
- Intent: use as final acceptance gate before hackathon submission.
- Expanded checklist with:
- leaderboard/ELO transparency requirements,
- frontend chaos/hack tests,
- contract hardening tests + hardening report artifact.
