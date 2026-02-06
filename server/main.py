"""
Punto Arena - FastAPI Server
"""

import os
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from matchmaking import matchmaking_queue
from game_manager import game_manager
from signer import get_signer

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup."""
    # Verify signer is configured
    try:
        signer = get_signer()
        print(f"Oracle address: {signer.get_address()}")
    except ValueError as e:
        print(f"Warning: {e}")
    yield


app = FastAPI(title="Punto Arena", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Models ============

class CreateMatchRequest(BaseModel):
    player_id: str
    wallet: str
    on_chain_id: Optional[int] = None
    wager: Optional[str] = None
    nickname: Optional[str] = None

class JoinMatchRequest(BaseModel):
    player_id: str
    wallet: str
    match_id: str
    on_chain_id: Optional[int] = None
    wager: Optional[str] = None
    nickname: Optional[str] = None

class SignResultRequest(BaseModel):
    match_id: str
    on_chain_id: int
    chain_id: int

class ChainIdRequest(BaseModel):
    on_chain_id: int
    wager: Optional[str] = None


# ============ REST Endpoints ============

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/match/create")
async def create_match(req: CreateMatchRequest):
    """
    Join matchmaking queue. Returns match if opponent found.
    """
    pairing = await matchmaking_queue.join(
        req.player_id,
        req.wallet,
        on_chain_id=req.on_chain_id,
        wager=req.wager,
        nickname=req.nickname
    )
    
    if pairing:
        # Match found - create game session
        session = await game_manager.get_game(pairing.match_id)
        if not session:
            session = await game_manager.create_game(
                match_id=pairing.match_id,
                player1_id=pairing.player1_id,
                player2_id=pairing.player2_id,
                on_chain_id=pairing.on_chain_id,
                wager=pairing.wager,
                player1_name=pairing.player1_nickname,
                player2_name=pairing.player2_nickname
            )
        else:
            if pairing.on_chain_id:
                session.on_chain_id = pairing.on_chain_id
            if pairing.wager:
                session.wager = pairing.wager
            if pairing.player1_nickname:
                await game_manager.set_nickname(pairing.match_id, pairing.player1_id, pairing.player1_nickname)
            if pairing.player2_nickname:
                await game_manager.set_nickname(pairing.match_id, pairing.player2_id, pairing.player2_nickname)

        you_are = "player1" if req.player_id == pairing.player1_id else "player2"
        opponent_id = pairing.player2_id if you_are == "player1" else pairing.player1_id
        return {
            "matched": True,
            "match_id": pairing.match_id,
            "opponent_id": opponent_id,
            "you_are": you_are,
            "on_chain_id": pairing.on_chain_id,
            "wager": pairing.wager,
            "nicknames": session.nicknames_by_role()
        }
    
    return {
        "matched": False,
        "message": "Waiting for opponent",
        "queue_position": await matchmaking_queue.get_position(req.player_id)
    }


@app.post("/match/join")
async def join_match(req: JoinMatchRequest):
    """
    Join a specific match (for direct invites).
    Creates game if it doesn't exist (first joiner becomes player1).
    """
    session = await game_manager.get_game(req.match_id)
    
    if not session:
        # Create game with this player as player1, player2 TBD
        session = await game_manager.create_game(
            match_id=req.match_id,
            player1_id=req.player_id,
            player2_id="waiting",  # Placeholder
            on_chain_id=req.on_chain_id,
            wager=req.wager,
            player1_name=req.nickname
        )
        return {
            "match_id": req.match_id,
            "you_are": "player1",
            "waiting": True,
            "message": "Game created, waiting for opponent",
            "on_chain_id": session.on_chain_id,
            "wager": session.wager,
            "nicknames": session.nicknames_by_role()
        }
    
    if req.player_id == session.player1_id:
        if req.nickname:
            await game_manager.set_nickname(req.match_id, req.player_id, req.nickname)
        return {
            "match_id": req.match_id,
            "you_are": "player1",
            "player1": session.player1_id,
            "player2": session.player2_id,
            "on_chain_id": session.on_chain_id,
            "wager": session.wager,
            "state": session.match.get_state(),
            "nicknames": session.nicknames_by_role()
        }

    # Game exists - add second player if needed
    if session.player2_id == "waiting":
        if req.player_id == session.player1_id:
            return {
                "match_id": req.match_id,
                "you_are": "player1",
                "waiting": True,
                "message": "Waiting for opponent",
                "on_chain_id": session.on_chain_id,
                "wager": session.wager
            }

        session.match.player2_id = req.player_id
        game_manager.player_games[req.player_id] = req.match_id
        if req.on_chain_id and not session.on_chain_id:
            session.on_chain_id = req.on_chain_id
        if req.wager and not session.wager:
            session.wager = req.wager
        if req.nickname:
            await game_manager.set_nickname(req.match_id, req.player_id, req.nickname)
    
    if req.player_id not in [session.player1_id, session.player2_id]:
        raise HTTPException(403, "Match full")
    
    return {
        "match_id": req.match_id,
        "you_are": "player2" if req.player_id == session.player2_id else "player1",
        "player1": session.player1_id,
        "player2": session.player2_id,
        "on_chain_id": session.on_chain_id,
        "wager": session.wager,
        "state": session.match.get_state(),
        "nicknames": session.nicknames_by_role()
    }


@app.get("/match/{match_id}")
async def get_match(match_id: str):
    """Get match state."""
    session = await game_manager.get_game(match_id)
    if not session:
        raise HTTPException(404, "Match not found")
    
    return {
        "match_id": match_id,
        "on_chain_id": session.on_chain_id,
        "wager": session.wager,
        "state": session.match.get_state(),
        "nicknames": session.nicknames_by_role()
    }


@app.post("/match/{match_id}/chain-id")
async def set_chain_id(match_id: str, req: ChainIdRequest):
    """Link match to on-chain game ID."""
    await game_manager.set_on_chain_id(match_id, req.on_chain_id)
    if req.wager:
        await game_manager.set_wager(match_id, req.wager)
    return {"success": True}


@app.post("/sign-result")
async def sign_result(req: SignResultRequest):
    """
    Sign game result for contract submission.
    """
    session = await game_manager.get_game(req.match_id)
    if not session:
        raise HTTPException(404, "Match not found")
    
    result = session.match.get_result_for_contract()
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    # Get winner's wallet (need to track this - for now use player_id as wallet)
    # In production, map player_id to wallet address
    winner_id = result["winner_id"]
    
    # For hackathon: assume player_id is wallet address
    # In production: look up wallet from player registry
    winner_wallet = winner_id
    
    signer = get_signer()
    signature_data = signer.sign_game_result(
        game_id=req.on_chain_id,
        winner=winner_wallet,
        chain_id=req.chain_id
    )
    
    return {
        "result": result,
        "signature": signature_data.get("signature"),
        "signature_data": signature_data
    }


@app.get("/queue/status")
async def queue_status():
    """Get matchmaking queue status."""
    return {"queue_size": await matchmaking_queue.get_queue_size()}


# ============ WebSocket ============

@app.websocket("/ws/{match_id}/{player_id}")
async def websocket_game(websocket: WebSocket, match_id: str, player_id: str):
    """
    WebSocket endpoint for real-time game play.
    
    Messages:
        Client -> Server:
            {"type": "move", "row": int, "col": int}
            {"type": "ready"}
            {"type": "next_round"}
        
        Server -> Client:
            {"type": "state", ...}
            {"type": "move_result", ...}
            {"type": "error", "message": str}
    """
    await websocket.accept()
    
    session = await game_manager.get_game(match_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Match not found"})
        await websocket.close()
        return

    def nicknames_payload():
        return {"nicknames": session.nicknames_by_role()}
    
    # Verify player (or add as player2 if slot is open)
    if player_id not in [session.player1_id, session.player2_id]:
        if session.player2_id == "waiting":
            # Join as player2
            session.match.player2_id = player_id
            game_manager.player_games[player_id] = match_id
        else:
            await websocket.send_json({"type": "error", "message": "Not a player"})
            await websocket.close()
            return
    
    # Register socket
    await game_manager.register_socket(match_id, player_id, websocket)
    
    # Send current state
    await websocket.send_json({
        "type": "state",
        "you_are": "player1" if player_id == session.player1_id else "player2",
        "on_chain_id": session.on_chain_id,
        "wager": session.wager,
        **nicknames_payload(),
        **session.match.get_state()
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ready":
                # Check if both players connected AND game not already started
                if len(session.player_sockets) == 2:
                    state = session.match.get_state()
                    if state.get("state") == "waiting":
                        result = await game_manager.start_game(match_id)
                        result["on_chain_id"] = session.on_chain_id
                        result["wager"] = session.wager
                        await game_manager.broadcast(match_id, {"type": "game_start", **nicknames_payload(), **result})
            
            elif msg_type == "move":
                row, col = data.get("row"), data.get("col")
                card_index = data.get("card_index")
                if row is None or col is None:
                    await websocket.send_json({"type": "error", "message": "Missing row/col"})
                    continue
                if card_index is None:
                    await websocket.send_json({"type": "error", "message": "Missing card_index"})
                    continue
                
                result = await game_manager.make_move(match_id, player_id, row, col, card_index)
                
                if result.get("success"):
                    await game_manager.broadcast(match_id, {
                        "type": "move_result",
                        "on_chain_id": session.on_chain_id,
                        "wager": session.wager,
                        **nicknames_payload(),
                        **result,
                        **session.match.get_state()
                    })
                    if result.get("round_end") and not result.get("match_end"):
                        async def auto_next_round():
                            await asyncio.sleep(1.2)
                            next_result = await game_manager.next_round(match_id)
                            if next_result.get("success"):
                                await game_manager.broadcast(match_id, {
                                    "type": "round_start",
                                    "on_chain_id": session.on_chain_id,
                                    "wager": session.wager,
                                    **nicknames_payload(),
                                    **next_result,
                                    **session.match.get_state()
                                })
                        asyncio.create_task(auto_next_round())
                else:
                    await websocket.send_json({"type": "error", "message": result.get("error")})
            
            elif msg_type == "next_round":
                result = await game_manager.next_round(match_id)
                await game_manager.broadcast(match_id, {
                    "type": "round_start",
                    "on_chain_id": session.on_chain_id,
                    "wager": session.wager,
                    **nicknames_payload(),
                    **result,
                    **session.match.get_state()
                })
    
    except WebSocketDisconnect:
        await game_manager.unregister_socket(match_id, player_id)
        await game_manager.broadcast(match_id, {
            "type": "player_disconnected",
            "player_id": player_id
        }, exclude=player_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
