# create_token.py (Final Corrected Version)

import os
import time
import traceback
from dotenv import load_dotenv

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID

# --- CONFIGURATION ---
load_dotenv()

# 1. Make sure your .env file is correct
SECRET_KEY_STRING = os.getenv("SECRET_KEY")
if not SECRET_KEY_STRING:
    raise ValueError("SECRET_KEY not found in .env file!")
CREATOR_KEYPAIR = Keypair.from_base58_string(SECRET_KEY_STRING)

# 2. Paste your personal RPC URL here!
RPC_URL = "https://snowy-sleek-moon.solana-mainnet.quiknode.pro/b782686111aa4eac5d9df855722fc24d95c7cc98/"
client = Client(RPC_URL) # <-- This line must be here, in the global scope

# 3. Token settings
DECIMALS = 6
TOTAL_SUPPLY = 1_000_000_000 * (10**DECIMALS)


def main():
    print(f"👑 Using creator wallet: {CREATOR_KEYPAIR.pubkey()}")

    try:
        # Step 1: CREATE THE TOKEN'S MINT ACCOUNT
        print("🚀 Step 1: Creating the token mint account...")
        token_client = Token.create_mint(
            conn=client,  # <-- Now it can find `client`!
            payer=CREATOR_KEYPAIR,
            mint_authority=CREATOR_KEYPAIR.pubkey(),
            decimals=DECIMALS,
            program_id=TOKEN_PROGRAM_ID,
            freeze_authority=None,
            skip_confirmation=False
        )
        new_token_mint_address = token_client.pubkey
        print(f"✅ Token Mint Created! Address: {new_token_mint_address}")
        print("✨✨✨ COPY THIS ADDRESS! YOU NEED IT FOR THE FAUCET! ✨✨✨")

        # Give the network a moment to catch up
        print("\n...Giving the network 10 seconds to catch up...")
        time.sleep(10)
        print("...Continuing!")

        # Step 2: CREATE A TOKEN ACCOUNT FOR YOUR WALLET
        print("\n🚀 Step 2: Creating a token account for your wallet...")
        dest_token_account = token_client.create_associated_token_account(
            owner=CREATOR_KEYPAIR.pubkey(),
            skip_confirmation=False
        )
        print(f"✅ Your wallet's token account: {dest_token_account}")

        # Step 3: MINT THE TOTAL SUPPLY
        print(f"\n🚀 Step 3: Minting {TOTAL_SUPPLY / (10**DECIMALS):,} tokens...")
        token_client.mint_to(
            dest=dest_token_account,
            mint_authority=CREATOR_KEYPAIR,
            amount=int(TOTAL_SUPPLY)
        )
        print("✅ Tokens minted successfully!")
        print("\n🎉🎉🎉 ALL DONE! Your new token is ready! 🎉🎉🎉")

    except Exception:
        print(f"😿 An error occurred. Here is the full error report:")
        traceback.print_exc()


if __name__ == "__main__":
    main()