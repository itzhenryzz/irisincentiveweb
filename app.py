# app.py (Now with a real database!)

import os
import base58
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy  # New import

# --- Load Secret Environment Variables ---
load_dotenv()

# --- App & Database Setup ---
app = Flask(__name__)
# Load the database URL from our .env file
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)  # Initialize the database connection

# --- Solana Imports for version 0.28.0 ---
from solana.publickey import PublicKey
from solana.keypair import Keypair
from solana.rpc.api import Client
from solana.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import create_associated_token_account, transfer, TransferParams

# --- CONFIGURATION ---
RPC_URL = "https://snowy-sleek-moon.solana-mainnet.quiknode.pro/b782686111aa4eac5d9df855722fc24d95c7cc98/"
SECRET_KEY_STRING = os.getenv("SECRET_KEY")
if not SECRET_KEY_STRING:
    raise ValueError("SECRET_KEY not found in .env file!")
FAUCET_KEYPAIR = Keypair.from_secret_key(base58.b58decode(SECRET_KEY_STRING))
TOKEN_MINT_ADDRESS = PublicKey("5FMU7DUgkD8cA8hBXc4QSsLA7PzJGSfYEtZBYA1hoCf2")
AMOUNT_TO_SEND = 100 * (10 ** 6)
COOLDOWN_PERIOD = timedelta(hours=24)  # Changed to 24 hours


# --- Database Model (The Blueprint for our table) ---
class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(44), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    last_claim_time = db.Column(db.DateTime, nullable=False)


# --- Create the table if it doesn't exist ---
with app.app_context():
    db.create_all()


# --- HELPER FUNCTION TO SEND TOKEN (No changes here) ---
def send_spl_token(recipient_pubkey: PublicKey, amount: int):
    # ... (This function is the same as our last working version)
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
        account_info = client.get_account_info(dest_token_account)
        if not account_info.value:
            create_ix = create_associated_token_account(
                payer=FAUCET_KEYPAIR.public_key,
                owner=recipient_pubkey,
                mint=TOKEN_MINT_ADDRESS
            )
            txn.add(create_ix)
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
        return str(tx_sig.value)
    except Exception as e:
        import traceback
        print(f"An error occurred in send_spl_token:")
        traceback.print_exc()
        return None


# --- CLAIM ENDPOINT (Rewritten to use the database) ---
@app.route("/claim", methods=['POST'])
def claim_tokens():
    data = request.get_json()
    if not data or 'wallet_address' not in data:
        return jsonify({"error": "Wallet address is missing!"}), 400

    wallet_address_str = data['wallet_address']
    ip_address = request.remote_addr

    # Check the database for recent claims from this wallet OR this IP
    cooldown_time_limit = datetime.utcnow() - COOLDOWN_PERIOD

    recent_claim = Claim.query.filter(
        (Claim.wallet_address == wallet_address_str) | (Claim.ip_address == ip_address),
        Claim.last_claim_time > cooldown_time_limit
    ).first()

    if recent_claim:
        time_since_claim = datetime.utcnow() - recent_claim.last_claim_time
        time_remaining = COOLDOWN_PERIOD - time_since_claim
        return jsonify(
            {"error": f"Cooldown! Please wait {round(time_remaining.total_seconds() / 3600, 1)} more hours."}), 429

    # If no recent claim, proceed to send tokens
    try:
        recipient_pubkey = PublicKey(wallet_address_str)
        tx_signature = send_spl_token(recipient_pubkey, AMOUNT_TO_SEND)

        if tx_signature:
            # Check if a record already exists for this user to update it
            existing_claim = Claim.query.filter(
                (Claim.wallet_address == wallet_address_str) | (Claim.ip_address == ip_address)
            ).first()

            if existing_claim:
                existing_claim.last_claim_time = datetime.utcnow()
                existing_claim.wallet_address = wallet_address_str  # Update wallet in case IP was used before
                existing_claim.ip_address = ip_address  # Update IP in case wallet was used before
            else:
                # Create a new record
                new_claim = Claim(
                    wallet_address=wallet_address_str,
                    ip_address=ip_address,
                    last_claim_time=datetime.utcnow()
                )
                db.session.add(new_claim)

            db.session.commit()  # Save the changes to the database

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