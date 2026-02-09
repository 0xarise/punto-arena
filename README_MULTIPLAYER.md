# 🎮 PUNTO AI - MULTIPLAYER

Real-time multiplayer Punto game with WebSocket, invite links, and betting hooks.

## 🚀 Quick Start

```bash
cd /Users/beru/punto-ai-game

# Set API keys
export ANTHROPIC_API_KEY='your-key'
export OPENAI_API_KEY='your-key'

# Run multiplayer server
./run_multiplayer.sh
```

Open: **http://127.0.0.1:8000**

## 🎯 Game Modes

| Mode | Description |
|------|-------------|
| **PvP** | Human vs Human (with invite links) |
| **PvE** | Human vs AI (Sonnet, GPT-4o, Opus) |
| **Spectate** | Watch games (coming soon) |

## 🔗 How to Challenge Someone

### Option 1: Direct Invite
1. Click "Challenge Friend"
2. Enter your name
3. Click "Create Room"
4. **Copy and send invite link** to opponent
5. They click link and join
6. Game starts automatically!

### Option 2: Room Code (coming soon)
- Enter short room code instead of full URL

## 💰 Wager Betting (Hook Ready)

### Current Status: **DISABLED**

Betting infrastructure is built but disabled. To enable:

```python
# In app_multiplayer.py
BETTING_ENABLED = True

BETTING_CONFIG = {
    'min_wager': 1.0,      # Min bet
    'max_wager': 1000.0,   # Max bet
    'currency': 'USD',
    'escrow_wallet': 'YOUR_WALLET_ADDRESS'
}
```

### Required Integrations (TODO):
- [ ] Payment processor (Stripe, PayPal, crypto)
- [ ] Escrow smart contract
- [ ] KYC/AML compliance
- [ ] Dispute resolution system

### How It Would Work:
1. Player 1 creates room with wager ($10)
2. Player 2 joins and matches wager
3. Funds go to escrow
4. Winner gets 2x wager ($20)
5. Platform takes fee (optional)

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│  Frontend (WebSocket Client)       │
│  - multiplayer.html                 │
│  - multiplayer.js                   │
└──────────────┬──────────────────────┘
               │ Socket.IO
┌──────────────▼──────────────────────┐
│  Backend (Flask + SocketIO)         │
│  - app_multiplayer.py               │
│  - Room management                  │
│  - Game state sync                  │
│  - Betting hooks (disabled)         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Game Logic                         │
│  - game_logic.py (Punto rules)      │
│  - ai_player.py (AI opponents)      │
└─────────────────────────────────────┘
```

## 📡 WebSocket Events

### Client → Server
- `join_room` - Join a game room
- `make_move` - Make a move
- `rematch` - Request rematch

### Server → Client
- `player_joined` - Someone joined
- `game_start` - Game beginning
- `move_made` - Move was made
- `game_end` - Game finished

## 🔒 Security Notes

- Rooms auto-cleanup when empty
- Move validation on server side
- No client-side cheating possible
- Betting escrow prevents fraud (when enabled)

## 🎨 Code Quality

- **Clean**: Minimal lines, max readability
- **Modular**: Separate concerns (game logic, networking, UI)
- **Extensible**: Easy to add features
- **Documented**: Clear comments

## 🐛 Known Issues

- [ ] GPT-4o AI not working (fix in progress)
- [ ] No spectator mode yet
- [ ] No game history/replay
- [ ] No ELO/ranking system

## 📊 Comparison: Single vs Multiplayer

| Feature | Single Player | Multiplayer |
|---------|---------------|-------------|
| Opponent | AI only | Human or AI |
| Setup | Instant | Wait for join |
| Cost | API tokens | Free (PvP) |
| Fun | 😐 | 🔥 |
| Betting | ❌ | ✅ (hook ready) |

## 🚢 Deployment

### Local Testing
```bash
./run_multiplayer.sh
```

### Production (TODO)
- Use Gunicorn + Nginx
- Add Redis for room persistence
- Enable HTTPS/WSS
- Scale with load balancer

## 📝 License

Same as main project.

---

**Built with ❤️ by Claude Code**
