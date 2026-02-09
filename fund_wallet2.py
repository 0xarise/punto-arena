#!/usr/bin/env python3
"""Send MON from BERU HOT to trytoexploit for hackathon matches"""

import os
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("MONAD_RPC_URL", "https://rpc.monad.xyz")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Sender wallet key
SENDER_KEY = os.getenv("SENDER_PRIVATE_KEY") or os.getenv("DEPLOYER_PRIVATE_KEY")
if not SENDER_KEY:
    raise ValueError("Missing SENDER_PRIVATE_KEY (or DEPLOYER_PRIVATE_KEY) in environment")
sender = Account.from_key(SENDER_KEY)

# Destination wallet
RECEIVER = os.getenv("RECEIVER_ADDRESS")
if not RECEIVER:
    raise ValueError("Missing RECEIVER_ADDRESS in environment")

# Send 0.5 MON
AMOUNT_MON = float(os.getenv("FUND_AMOUNT_MON", "0.5"))
AMOUNT = Web3.to_wei(AMOUNT_MON, 'ether')

print(f"Sender: {sender.address}")
print(f"Sender balance: {w3.from_wei(w3.eth.get_balance(sender.address), 'ether')} MON")
print(f"Receiver: {RECEIVER}")
print(f"Amount: {AMOUNT_MON} MON")

tx = {
    'from': sender.address,
    'to': Web3.to_checksum_address(RECEIVER),
    'value': AMOUNT,
    'nonce': w3.eth.get_transaction_count(sender.address),
    'gas': 21000,
    'gasPrice': w3.eth.gas_price
}

signed = w3.eth.account.sign_transaction(tx, SENDER_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX sent: {tx_hash.hex()}")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
print(f"Receiver balance: {w3.from_wei(w3.eth.get_balance(RECEIVER), 'ether')} MON")
