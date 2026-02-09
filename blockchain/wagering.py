"""
Blockchain Integration for Punto Arena
Handles contract interaction and oracle signing
"""

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
import os
import json
from typing import Optional, Dict

class PuntoBlockchain:
    """Handles all blockchain interactions for wagering"""

    def __init__(self):
        # Load environment variables
        self.rpc_url = os.getenv('MONAD_RPC_URL', 'http://localhost:8545')
        self.contract_address = os.getenv('CONTRACT_ADDRESS')
        self.oracle_private_key = os.getenv('ORACLE_PRIVATE_KEY')

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        # Load contract ABI
        with open('blockchain/PuntoArena_ABI.json', 'r') as f:
            self.contract_abi = json.load(f)

        # Contract instance
        if self.contract_address:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.contract_abi
            )

        # Oracle account
        if self.oracle_private_key:
            self.oracle_account = Account.from_key(self.oracle_private_key)

        print(f"✅ Blockchain initialized")
        print(f"   RPC: {self.rpc_url}")
        print(f"   Contract: {self.contract_address}")
        print(f"   Oracle: {self.oracle_account.address if self.oracle_private_key else 'Not set'}")

    def get_game_by_room_id(self, room_id: str) -> Optional[Dict]:
        """Get on-chain game data by room ID"""
        try:
            # First get the game ID
            game_id = self.contract.functions.roomIdToGameId(room_id).call()
            
            game = self.contract.functions.getGameByRoomId(room_id).call()

            return {
                'gameId': game_id,
                'player1': game[0],
                'player2': game[1],
                'wager': game[2],
                'state': game[3],  # 0=PENDING, 1=ACTIVE, 2=FINISHED, 3=CANCELLED
                'winner': game[4],
                'createdAt': game[5],
                'roomId': game[6]
            }
        except Exception as e:
            print(f"❌ Error fetching game: {e}")
            return None

    def submit_result(self, game_id: int, winner_address: str) -> str:
        """
        Submit game result to contract (oracle only)
        Returns transaction hash
        """
        try:
            print(f"\n🔐 Submitting result to blockchain...")
            print(f"   Game ID: {game_id}")
            print(f"   Winner: {winner_address}")

            # Build transaction
            tx = self.contract.functions.submitResult(
                game_id,
                Web3.to_checksum_address(winner_address)
            ).build_transaction({
                'from': self.oracle_account.address,
                'nonce': self.w3.eth.get_transaction_count(self.oracle_account.address),
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price
            })

            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.oracle_private_key)

            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            print(f"   📤 Transaction sent: {tx_hash.hex()}")

            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt['status'] == 1:
                print(f"   ✅ Result submitted successfully!")
                return tx_hash.hex()
            else:
                print(f"   ❌ Transaction failed")
                return None

        except Exception as e:
            print(f"❌ Error submitting result: {e}")
            import traceback
            traceback.print_exc()
            return None

    def calculate_payout(self, wager_wei: int) -> Dict[str, int]:
        """Calculate payout and fee for a given wager"""
        try:
            result = self.contract.functions.calculatePayout(wager_wei).call()
            return {
                'payout': result[0],
                'fee': result[1],
                'payout_eth': self.w3.from_wei(result[0], 'ether'),
                'fee_eth': self.w3.from_wei(result[1], 'ether')
            }
        except Exception as e:
            print(f"❌ Error calculating payout: {e}")
            return None

    def listen_for_events(self, callback):
        """
        Listen for contract events in real-time
        Callback receives: event_name, event_data
        """
        print("👂 Listening for blockchain events...")

        event_filter = self.contract.events.GameCreated.create_filter(fromBlock='latest')

        while True:
            for event in event_filter.get_new_entries():
                callback('GameCreated', event)

# Singleton instance
blockchain = None

def get_blockchain() -> PuntoBlockchain:
    """Get or create blockchain instance"""
    global blockchain
    if blockchain is None:
        blockchain = PuntoBlockchain()
    return blockchain
