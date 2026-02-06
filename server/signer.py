"""
Oracle Signer - Signs game results for contract verification
"""

import os
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3


class OracleSigner:
    """Signs game results matching the contract's verification logic."""
    
    def __init__(self, private_key: str | None = None):
        """
        Initialize signer with private key.
        
        Args:
            private_key: Hex private key (with or without 0x prefix)
                        Falls back to ORACLE_PRIVATE_KEY env var
        """
        key = private_key or os.getenv("ORACLE_PRIVATE_KEY")
        if not key:
            raise ValueError("No private key provided. Set ORACLE_PRIVATE_KEY env var")
        
        # Normalize key format
        if not key.startswith("0x"):
            key = f"0x{key}"
        
        self.account = Account.from_key(key)
        self.address = self.account.address
    
    def sign_game_result(
        self,
        game_id: int,
        winner: str,
        chain_id: int
    ) -> dict:
        """
        Sign a game result for contract verification.
        
        Contract expects: keccak256(abi.encodePacked(gameId, winner, block.chainid))
        
        Args:
            game_id: On-chain game ID
            winner: Winner's wallet address
            chain_id: Target blockchain chain ID
            
        Returns:
            Dict with signature components
        """
        # Validate winner address
        if not Web3.is_address(winner):
            raise ValueError(f"Invalid winner address: {winner}")
        
        winner = Web3.to_checksum_address(winner)
        
        # Create message hash matching contract's abi.encodePacked
        # encodePacked: uint256 + address + uint256
        message_hash = Web3.solidity_keccak(
            ["uint256", "address", "uint256"], [game_id, winner, chain_id]
        )
        
        # Sign as eth_sign does (adds "\x19Ethereum Signed Message:\n32" prefix)
        signable = encode_defunct(message_hash)
        signed = self.account.sign_message(signable)
        
        return {
            "game_id": game_id,
            "winner": winner,
            "chain_id": chain_id,
            "signature": f"0x{signed.signature.hex()}",
            "v": signed.v,
            "r": hex(signed.r),
            "s": hex(signed.s),
            "signer": self.address
        }
    
    def get_address(self) -> str:
        """Return the oracle's signing address."""
        return self.address


# Singleton for easy import
_signer: OracleSigner | None = None


def get_signer() -> OracleSigner:
    """Get or create the global signer instance."""
    global _signer
    if _signer is None:
        _signer = OracleSigner()
    return _signer
