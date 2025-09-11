# app.py (Final version with all correct response parsing)

import os
import base58
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

# --- Solana Imports for version 0.28.0 ---
from solana.publickey import PublicKey
from solana.keypair import Keypair
from solana.rpc.api import Client
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import create_associated_token_account, transfer, TransferParams

# --- Load Secret Environment Variables ---
load_dotenv()
app = Flask(__name__)

# --- CONFIGURATION ---
RPC_URL = "https://snowy-sleek-moon.solana-mainnet.quiknode.pro/b782686111aa4eac5d9df855722fc24d95c7cc98/"
SECRET_KEY_STRING = os.getenv("SECRET_KEY")
if not SECRET_KEY_STRING:
    raise ValueError("SECRET_KEY not found in .env file!")
FAUCET_KEYPAIR = Keypair.from_secret_key(base58.b58decode(SECRET_KEY_STRING))
TOKEN_MINT_ADDRESS = PublicKey("5FMU7DUgkD8cA8hBXc4QSsLA7PzJGSfYEtZBYA1hoCf2")
AMOUNT_TO_SEND = 100 * (10 ** 6)

# --- Cooldown Settings ---
claim_records = {}
COOLDOWN_PERIOD = timedelta(seconds=60)


# --- HELPER FUNCTION TO SEND TOKEN ---
def send_spl_token(recipient_pubkey: PublicKey, amount: int):
    try:
        client = Client(RPC_URL)

        source_token_account, _ = PublicKey.find_program_address(
            [bytes(FAUCET_KEYPAIR.public_key), bytes(TOKEN_PROGRAM_ID), bytes(TOKEN_MINT_ADDRESS)],
            ASSOCIATED_TOKEN_PROGRAM_ID
        )
        dest_token_account, _ = PublicKey.find_program_address(
            [bytes(recipient_pubkey), bytes(TOKEN_PROGRAM_ID), bytes(TOKEN_MINT_ADDRESS)], ASSOCIATED_TOKEN_PROGRAM_ID
        )

        txn = Transaction()

        # --- THIS IS THE CORRECTED LINE ---
        account_info = client.get_account_info(dest_token_account)
        if not account_info.value:
            print("Recipient token account not found, adding create instruction to transaction...")
            create_ix = create_associated_token_account(
                payer=FAUCET_KEYPAIR.public_key,
                owner=recipient_pubkey,
                mint=TOKEN_MINT_ADDRESS
            )
            txn.add(create_ix)
        # --- END OF CORRECTION ---

        transfer_ix = transfer(
            params=TransferParams(
                source=source_token_account,
                dest=dest_token_account,
                owner=FAUCET_KEYPAIR.public_key,
                amount=amount,
                program_id=TOKEN_PROGRAM_ID
            )
        )
        txn.add(transfer_ix)

        tx_sig = client.send_transaction(txn, FAUCET_KEYPAIR)

        print(f"Transaction successful! Signature: {tx_sig.value}")
        return str(tx_sig.value)

    except Exception as e:
        import traceback
        print(f"An error occurred in send_spl_token:")
        traceback.print_exc()
        return None


# --- CLAIM ENDPOINT (No changes) ---
@app.route("/claim", methods=['POST'])
def claim_tokens():
    # ... (code is correct and unchanged)
    data = request.get_json()
    if not data or 'wallet_address' not in data:
        return jsonify({"error": "Wallet address is missing!"}), 400
    wallet_address_str = data['wallet_address']

    last_claim_time = claim_records.get(wallet_address_str)
    current_time = datetime.now()
    if last_claim_time and (current_time < last_claim_time + COOLDOWN_PERIOD):
        time_remaining = (last_claim_time + COOLDOWN_PERIOD) - current_time
        return jsonify({"error": "Cooldown!", "time_remaining": round(time_remaining.total_seconds())}), 429

    try:
        recipient_pubkey = PublicKey(wallet_address_str)
        tx_signature = send_spl_token(recipient_pubkey, AMOUNT_TO_SEND)

        if tx_signature:
            claim_records[wallet_address_str] = current_time
            token_amount_display = AMOUNT_TO_SEND / (10 ** 6)
            return jsonify({
                "success": True,
                "message": f"{token_amount_display} tokens sent!",
                "transaction_signature": tx_signature
            })
        else:
            return jsonify({"error": "Failed to send tokens."}), 500

    except Exception:
        return jsonify({"error": "Invalid Solana wallet address."}), 400


# --- Main Server Run ---
if __name__ == "__main__":
    app.run(debug=True)