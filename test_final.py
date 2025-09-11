# test_final.py

print("--- Starting the definitive Associated Token Account test ---")

try:
    # We will use a more direct function from this module
    from spl.associated_token_account import get_associated_token_address
    from solders.pubkey import Pubkey

    print("Successfully imported the correct function.")

    # Create dummy owner and mint addresses
    owner = Pubkey.new_unique()
    mint = Pubkey.new_unique()

    print(f"Testing with random owner: {owner}")
    print(f"Testing with random mint: {mint}")

    # The REAL test with the simpler, correct function
    ata_address = get_associated_token_address(owner, mint)

    print("\n✅ SUCCESS! The function exists, imported, and ran correctly!")
    print(f"The calculated Associated Token Account address is: {ata_address}")

except Exception as e:
    import traceback

    print("\n❌ FAILED! The test caught an error.")
    traceback.print_exc()

print("\n--- Test finished ---")