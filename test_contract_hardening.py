#!/usr/bin/env python3
"""
Contract Security Hardening Tests for PuntoArena
Runs on-chain tests against the deployed contract to verify access control,
input validation, state machine guards, and payout accounting.
"""

import os
import time
from typing import Dict

import pytest
from web3 import Web3
from web3.exceptions import ContractLogicError
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# This file is an on-chain integration suite (not a fast unit-test module).
# Run manually with: python test_contract_hardening.py
pytestmark = pytest.mark.skip(reason="On-chain integration suite; run manually as script")

# ============================================================================
# CONFIG
# ============================================================================

RPC_URL = os.getenv("MONAD_RPC_URL", "https://rpc.monad.xyz")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

WALLET1_KEY = os.getenv("WALLET1_PRIVATE_KEY") or os.getenv("ORACLE_PRIVATE_KEY")
WALLET2_KEY = os.getenv("WALLET2_PRIVATE_KEY")

WAGER_AMOUNT = Web3.to_wei(0.01, "ether")

# Contract ABI (minimal - includes all functions needed for security tests)
CONTRACT_ABI = [
    {
        "inputs": [{"name": "roomId", "type": "string"}],
        "name": "createGame",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"name": "gameId", "type": "uint256"}],
        "name": "joinGame",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "gameId", "type": "uint256"},
            {"name": "winner", "type": "address"},
        ],
        "name": "submitResult",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "roomId", "type": "string"}],
        "name": "getGameByRoomId",
        "outputs": [
            {
                "components": [
                    {"name": "player1", "type": "address"},
                    {"name": "player2", "type": "address"},
                    {"name": "wager", "type": "uint256"},
                    {"name": "state", "type": "uint8"},
                    {"name": "winner", "type": "address"},
                    {"name": "createdAt", "type": "uint256"},
                    {"name": "roomId", "type": "string"},
                ],
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "gameCounter",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "gameId", "type": "uint256"}],
        "name": "claimRefund",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "wager", "type": "uint256"}],
        "name": "calculatePayout",
        "outputs": [
            {"name": "payout", "type": "uint256"},
            {"name": "fee", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "minimumWager",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ============================================================================
# BLOCKCHAIN SETUP
# ============================================================================

w3 = Web3(Web3.HTTPProvider(RPC_URL))
contract = (
    w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
    if CONTRACT_ADDRESS
    else None
)


def send_tx(account, tx_func, value=0):
    """Build, sign, and send transaction. Raises on revert (status=0)."""
    tx = tx_func.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "value": value,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 0:
        raise ContractLogicError(f"Transaction reverted (status=0, tx={tx_hash.hex()[:20]}...)")
    return receipt


def make_room_id(test_name: str) -> str:
    """Generate a unique room ID for each test run."""
    return f"hardening_test_{test_name}_{int(time.time())}"


def create_and_join_game(wallet1, wallet2, room_id: str, wager=WAGER_AMOUNT):
    """Helper: create a game with wallet1, join with wallet2, return game_id."""
    send_tx(wallet1, contract.functions.createGame(room_id), wager)
    game_id = contract.functions.gameCounter().call()
    send_tx(wallet2, contract.functions.joinGame(game_id), wager)
    return game_id


# ============================================================================
# TESTS
# ============================================================================


def test_unauthorized_submit_result(wallet1, wallet2) -> Dict:
    """
    Security: Only the oracle should be able to submit results.
    Create a game, join it, then try submitResult from WALLET2 (non-oracle).
    Expected: revert with "Only oracle".
    """
    test_name = "unauthorized_submit_result"
    room_id = make_room_id(test_name)
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    try:
        # Setup: create and join a game
        print("  Setting up game...")
        game_id = create_and_join_game(wallet1, wallet2, room_id)
        print(f"  Game {game_id} created and joined (room: {room_id})")

        # Attack: wallet2 (non-oracle) tries to submit result
        print("  Attempting submitResult from non-oracle wallet2...")
        send_tx(wallet2, contract.functions.submitResult(game_id, wallet2.address))

        # If we get here, the tx succeeded - that means the guard is missing
        print(f"  FAIL: submitResult succeeded from non-oracle wallet!")
        return {"test": test_name, "passed": False, "reason": "No revert - oracle check missing"}

    except (ContractLogicError, Exception) as e:
        error_msg = str(e)
        if "Only oracle" in error_msg or "revert" in error_msg.lower():
            print(f"  PASS: Reverted as expected")
            print(f"  Error: {error_msg[:120]}")
            return {"test": test_name, "passed": True, "reason": f"Reverted: {error_msg[:120]}"}
        else:
            print(f"  FAIL: Unexpected error: {error_msg[:200]}")
            return {"test": test_name, "passed": False, "reason": f"Unexpected error: {error_msg[:200]}"}


def test_join_wrong_wager(wallet1, wallet2) -> Dict:
    """
    Validation: Joining a game must match the creator's wager amount.
    Create a game with 0.01 MON, try to join with 0.005 MON.
    Expected: revert with "Wrong wager amount".
    """
    test_name = "join_wrong_wager"
    room_id = make_room_id(test_name)
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    try:
        # Setup: create a game with 0.01 MON
        print("  Creating game with 0.01 MON wager...")
        send_tx(wallet1, contract.functions.createGame(room_id), WAGER_AMOUNT)
        game_id = contract.functions.gameCounter().call()
        print(f"  Game {game_id} created (room: {room_id})")

        # Attack: join with half the wager (0.005 MON)
        wrong_wager = Web3.to_wei(0.005, "ether")
        print(f"  Attempting joinGame with 0.005 MON (should require 0.01)...")
        send_tx(wallet2, contract.functions.joinGame(game_id), wrong_wager)

        print(f"  FAIL: joinGame succeeded with wrong wager!")
        return {"test": test_name, "passed": False, "reason": "No revert - wager check missing"}

    except (ContractLogicError, Exception) as e:
        error_msg = str(e)
        if "Wrong wager" in error_msg or "wager" in error_msg.lower() or "revert" in error_msg.lower():
            print(f"  PASS: Reverted as expected")
            print(f"  Error: {error_msg[:120]}")
            return {"test": test_name, "passed": True, "reason": f"Reverted: {error_msg[:120]}"}
        else:
            print(f"  FAIL: Unexpected error: {error_msg[:200]}")
            return {"test": test_name, "passed": False, "reason": f"Unexpected error: {error_msg[:200]}"}


def test_double_submit_result(wallet1, wallet2) -> Dict:
    """
    State machine: A game result can only be submitted once.
    Create game, join, submit result (success), then submit again.
    Expected: second submitResult reverts with "Game not active".
    """
    test_name = "double_submit_result"
    room_id = make_room_id(test_name)
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    try:
        # Setup: create, join, and submit result once
        print("  Setting up game...")
        game_id = create_and_join_game(wallet1, wallet2, room_id)
        print(f"  Game {game_id} created and joined (room: {room_id})")

        print("  Submitting result (first time - should succeed)...")
        send_tx(wallet1, contract.functions.submitResult(game_id, wallet1.address))
        print("  First submitResult succeeded")

        # Attack: submit result again on the same finished game
        print("  Attempting submitResult again (second time)...")
        send_tx(wallet1, contract.functions.submitResult(game_id, wallet2.address))

        print(f"  FAIL: Second submitResult succeeded!")
        return {"test": test_name, "passed": False, "reason": "No revert - double submit allowed"}

    except (ContractLogicError, Exception) as e:
        error_msg = str(e)
        if "not active" in error_msg.lower() or "Game not active" in error_msg or "revert" in error_msg.lower():
            print(f"  PASS: Reverted as expected")
            print(f"  Error: {error_msg[:120]}")
            return {"test": test_name, "passed": True, "reason": f"Reverted: {error_msg[:120]}"}
        else:
            print(f"  FAIL: Unexpected error: {error_msg[:200]}")
            return {"test": test_name, "passed": False, "reason": f"Unexpected error: {error_msg[:200]}"}


def test_claim_refund_before_timeout(wallet1, wallet2) -> Dict:
    """
    Timing: claimRefund should only work after the 30-minute timeout.
    Create a game, immediately try claimRefund.
    Expected: revert with "Refund not available yet".
    """
    test_name = "claim_refund_before_timeout"
    room_id = make_room_id(test_name)
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    try:
        # Setup: create a game (don't join - refund is for stuck games)
        print("  Creating game with 0.01 MON wager...")
        send_tx(wallet1, contract.functions.createGame(room_id), WAGER_AMOUNT)
        game_id = contract.functions.gameCounter().call()
        print(f"  Game {game_id} created (room: {room_id})")

        # Attack: immediately try to claim refund (timeout is 30 min)
        print("  Attempting claimRefund immediately (timeout is 30 min)...")
        send_tx(wallet1, contract.functions.claimRefund(game_id))

        print(f"  FAIL: claimRefund succeeded before timeout!")
        return {"test": test_name, "passed": False, "reason": "No revert - timeout check missing"}

    except (ContractLogicError, Exception) as e:
        error_msg = str(e)
        if "not available" in error_msg.lower() or "Refund" in error_msg or "timeout" in error_msg.lower() or "revert" in error_msg.lower():
            print(f"  PASS: Reverted as expected")
            print(f"  Error: {error_msg[:120]}")
            return {"test": test_name, "passed": True, "reason": f"Reverted: {error_msg[:120]}"}
        else:
            print(f"  FAIL: Unexpected error: {error_msg[:200]}")
            return {"test": test_name, "passed": False, "reason": f"Unexpected error: {error_msg[:200]}"}


def test_payout_accounting(wallet1, wallet2) -> Dict:
    """
    Accounting: Verify payout + fee == total pot, and fee is 5% of total pot.
    Call calculatePayout(0.01 ether) and check the math.
    This is a pure view call - no gas spent.
    """
    test_name = "payout_accounting"
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    try:
        wager = Web3.to_wei(0.01, "ether")
        total_pot = wager * 2  # Both players wager

        print(f"  Calling calculatePayout({Web3.from_wei(wager, 'ether')} ether)...")
        payout, fee = contract.functions.calculatePayout(wager).call()

        print(f"  Wager:     {Web3.from_wei(wager, 'ether')} MON")
        print(f"  Total pot: {Web3.from_wei(total_pot, 'ether')} MON")
        print(f"  Payout:    {Web3.from_wei(payout, 'ether')} MON")
        print(f"  Fee:       {Web3.from_wei(fee, 'ether')} MON")

        # Check 1: payout + fee == total pot
        sum_check = payout + fee == total_pot
        print(f"  payout + fee == total_pot? {sum_check}  ({Web3.from_wei(payout + fee, 'ether')} == {Web3.from_wei(total_pot, 'ether')})")

        # Check 2: fee is 5% of total pot
        expected_fee = total_pot * 5 // 100
        fee_check = fee == expected_fee
        print(f"  fee == 5% of total_pot?   {fee_check}  ({Web3.from_wei(fee, 'ether')} == {Web3.from_wei(expected_fee, 'ether')})")

        if sum_check and fee_check:
            print(f"  PASS: Payout accounting is correct")
            return {"test": test_name, "passed": True, "reason": f"payout={payout}, fee={fee}, total={total_pot}"}
        else:
            reasons = []
            if not sum_check:
                reasons.append(f"payout+fee={payout+fee} != total_pot={total_pot}")
            if not fee_check:
                reasons.append(f"fee={fee} != expected 5%={expected_fee}")
            reason = "; ".join(reasons)
            print(f"  FAIL: {reason}")
            return {"test": test_name, "passed": False, "reason": reason}

    except Exception as e:
        error_msg = str(e)
        print(f"  FAIL: Exception during view call: {error_msg[:200]}")
        return {"test": test_name, "passed": False, "reason": f"Exception: {error_msg[:200]}"}


# ============================================================================
# MAIN
# ============================================================================


def main() -> Dict:
    """Run all hardening tests and return results summary."""
    print("=" * 60)
    print("CONTRACT SECURITY HARDENING TESTS")
    print("=" * 60)
    print(f"Contract: {CONTRACT_ADDRESS}")
    print(f"RPC:      {RPC_URL}")
    print(f"Wager:    0.01 MON per test game")

    if not CONTRACT_ADDRESS:
        print("\nMissing CONTRACT_ADDRESS in .env")
        return {"tests": [], "passed": 0, "failed": 0, "total": 0}

    if not WALLET1_KEY:
        print("\nMissing WALLET1_PRIVATE_KEY or ORACLE_PRIVATE_KEY in .env")
        return {"tests": [], "passed": 0, "failed": 0, "total": 0}

    if not WALLET2_KEY:
        print("\nMissing WALLET2_PRIVATE_KEY in .env")
        return {"tests": [], "passed": 0, "failed": 0, "total": 0}

    wallet1 = Account.from_key(WALLET1_KEY)
    wallet2 = Account.from_key(WALLET2_KEY)

    print(f"\nOracle (wallet1): {wallet1.address}")
    print(f"  Balance: {w3.from_wei(w3.eth.get_balance(wallet1.address), 'ether')} MON")
    print(f"Player (wallet2): {wallet2.address}")
    print(f"  Balance: {w3.from_wei(w3.eth.get_balance(wallet2.address), 'ether')} MON")

    # Run all tests
    results = []

    results.append(test_unauthorized_submit_result(wallet1, wallet2))
    results.append(test_join_wrong_wager(wallet1, wallet2))
    results.append(test_double_submit_result(wallet1, wallet2))
    results.append(test_claim_refund_before_timeout(wallet1, wallet2))
    results.append(test_payout_accounting(wallet1, wallet2))

    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    print(f"\n{'='*60}")
    print("HARDENING TEST SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['test']}: {r['reason'][:80]}")

    print(f"\n  Total: {total}  Passed: {passed}  Failed: {failed}")

    if failed == 0:
        print("  All security tests passed!")
    else:
        print(f"  WARNING: {failed} security test(s) failed!")

    print(f"{'='*60}\n")

    return {
        "tests": results,
        "passed": passed,
        "failed": failed,
        "total": total,
    }


if __name__ == "__main__":
    main()
