# app.py (Now with a real database!)

import os
import base58
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy  # New import
import requests
from werkzeug.middleware.proxy_fix import ProxyFix
import time

# --- Load Secret Environment Variables ---
load_dotenv()

# --- App & Database Setup ---
app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Load the database URL from our .env file
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)  # Initialize the database connection

# Add your IP2Proxy API key here, nya!
IP2PROXY_API_KEY = os.getenv("IP2PROXY_API_KEY")
if not IP2PROXY_API_KEY:
    raise ValueError("IP2PROXY_API_KEY not found in .env file!")

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


# --- Create the table if it doesn't exist commented out due to crash, prefer create manual table---
#with app.app_context():
#    db.create_all()

# --- VPN/Proxy Detection Helper Function (Add it here, nya!) ---
def is_ip_proxy_or_vpn(ip_address):
    # The API endpoint is a GET request, with the IP and API key as parameters.
    # We use a f-string to insert the ip_address and API key dynamically.
    api_url = f"https://api.ip2proxy.com/?ip={ip_address}&key={IP2PROXY_API_KEY}&format=json"

    try:
        response = requests.get(api_url)
        # Check if the API call was successful
        if response.status_code == 200:
            data = response.json()
            # The API returns 'isProxy' as a string. 'NO' means it's not a proxy.
            if data.get('isProxy') and data.get('isProxy') != 'NO':
                print(f"VPN/Proxy detected for IP: {ip_address}")
                return True
            else:
                return False
        else:
            # The API call failed, so we can't be sure.
            # We'll return False to avoid blocking good users by accident.
            return False
    except requests.exceptions.RequestException as e:
        print(f"VPN/Proxy detection API call failed: {e}")
        return False

# --- HELPER FUNCTION TO SEND TOKEN (No changes here) ---
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

        account_found = False
        for i in range(10):  # Try up to 10 times
            print(f"DEBUG: Checking for destination ATA, attempt {i + 1}...")
            try:
                account_info = client.get_account_info(dest_token_account)
                if account_info.value is not None:
                    print("DEBUG: Destination ATA found!")
                    account_found = True
                    break  # Exit the loop if account is found
            except Exception as e:
                print(f"DEBUG: Error while checking for ATA, will retry: {e}")

            print("DEBUG: ATA not found yet, waiting 2 seconds...")
            time.sleep(2)  # Wait for 2 seconds before trying again

        if not account_found:
            print("ERROR: Destination ATA not found after multiple retries.")
            raise Exception("Could not find the destination token account after creation.")

        # Nya! We no longer need to check or create the ATA here.
        # We assume the user has created it themselves, nya!

        txn = Transaction()
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


# --- CLAIM ENDPOINT (Updated with debugging logs) ---
@app.route("/claim", methods=['POST'])
def claim_tokens():
    data = request.get_json()
    if not data or 'wallet_address' not in data:
        return jsonify({"error": "Wallet address is missing!"}), 400

    wallet_address_str = data['wallet_address']
    ip_address = request.remote_addr

    print(f"DEBUG: Processing claim request for wallet: {wallet_address_str} from IP: {ip_address}")

    if is_ip_proxy_or_vpn(ip_address):
        return jsonify({"error": "Proxy, VPN, or Tor detected. Please disable it to claim tokens."}), 403

    cooldown_time_limit = datetime.utcnow() - COOLDOWN_PERIOD
    print(f"DEBUG: Cooldown limit is: {cooldown_time_limit.isoformat()}")

    # The query checks for a recent claim from this wallet OR this IP
    recent_claim = Claim.query.filter(
        (Claim.wallet_address == wallet_address_str) | (Claim.ip_address == ip_address),
        Claim.last_claim_time > cooldown_time_limit
    ).first()

    if recent_claim:
        print(f"DEBUG: Recent claim found! Wallet: {recent_claim.wallet_address}, IP: {recent_claim.ip_address}")
        time_since_claim = datetime.utcnow() - recent_claim.last_claim_time
        time_remaining = COOLDOWN_PERIOD - time_since_claim
        return jsonify(
            {"error": f"Cooldown! Please wait {round(time_remaining.total_seconds() / 3600, 1)} more hours."}), 429

    print("DEBUG: No recent claim found. Proceeding to send tokens.")

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
                existing_claim.wallet_address = wallet_address_str
                existing_claim.ip_address = ip_address
                print(f"DEBUG: Updating existing claim record for wallet: {wallet_address_str}")
            else:
                new_claim = Claim(
                    wallet_address=wallet_address_str,
                    ip_address=ip_address,
                    last_claim_time=datetime.utcnow()
                )
                db.session.add(new_claim)
                print(f"DEBUG: Creating new claim record for wallet: {wallet_address_str}")

            db.session.commit()

            token_amount_display = AMOUNT_TO_SEND / (10 ** 6)
            return jsonify({
                "success": True,
                "message": f"{token_amount_display} tokens sent!",
                "transaction_signature": tx_signature
            })
        else:
            print("DEBUG: Failed to send tokens, no transaction signature.")
            return jsonify({"error": "Failed to send tokens."}), 500

    except Exception:
        print("DEBUG: An exception occurred during token sending.")
        return jsonify({"error": "Invalid Solana wallet address."}), 400


# --- Main Server Run ---
if __name__ == "__main__":
    app.run(debug=True)