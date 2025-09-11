# test_library.py

print("--- Starting the library test ---")

try:
    from spl.token.client import Token
    from solders.pubkey import Pubkey

    print("Successfully imported Token and Pubkey.")

    # These are just example addresses for the test
    owner_key = Pubkey.from_string("Bbe9EKucv1261gYkS4p5w2D7i2cZ6vAm1Z7T1pY8a8s3")
    mint_key = Pubkey.from_string("5FMU7DUgkD8cA8hBXc4QSsLA7PzJGSfYEtZBYA1hoCf2")

    print(f"Testing with Owner: {owner_key}")
    print(f"Testing with Mint: {mint_key}")

    # This is the function call that is failing in app.py
    ata_address = Token.get_associated_token_address(
        owner=owner_key,
        mint=mint_key
    )

    print("\n✅ SUCCESS! The function exists and it worked!")
    print(f"The calculated Associated Token Account address is: {ata_address}")

except Exception as e:
    print("\n❌ FAILED! The test caught an error.")
    print(f"The error is: {e}")

print("\n--- Test finished ---")