# Punto Arena Server

FastAPI backend for Punto Arena game with WebSocket support and oracle signing.

## Setup

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure oracle key
cp .env.example .env
# Edit .env with your oracle private key
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

## API Endpoints

### REST
- `GET /health` - Health check
- `POST /match/create` - Join matchmaking queue
- `POST /match/join` - Join specific match
- `GET /match/{match_id}` - Get match state
- `POST /sign-result` - Sign game result for contract
- `GET /queue/status` - Matchmaking queue size

### WebSocket
- `WS /ws/{match_id}/{player_id}` - Real-time game play

## WebSocket Protocol

Client sends:
```json
{"type": "ready"}
{"type": "move", "row": 2, "col": 3}
{"type": "next_round"}
```

Server sends:
```json
{"type": "state", "you_are": "player1", ...}
{"type": "game_start", ...}
{"type": "move_result", "success": true, ...}
{"type": "round_start", ...}
{"type": "error", "message": "..."}
```

## Architecture

```
main.py          - FastAPI app, routes, WebSocket
matchmaking.py   - Queue-based matchmaking
game_manager.py  - Active game sessions
signer.py        - Oracle signature for contract
```
