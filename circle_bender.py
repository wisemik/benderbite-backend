import os
import uuid
import logging
from circle.web3 import developer_controlled_wallets as dc_wallets
from circle.web3 import utils as circle_utils
import requests
from dotenv import load_dotenv
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from a .env file
load_dotenv()

def initialize_wallet(project_label, wallet_label, reference_id):
    # Begin wallet initialization

    # Encrypt the entity secret
    encrypted_entity_secret = encrypt_entity_secret()

    # Generate a unique idempotency key
    idempotency_key = str(uuid.uuid4())

    # Retrieve the API token from environment variables
    api_token = os.getenv('CIRCLE_API_KEY')
    if not api_token:
        print("Error: CIRCLE_API_KEY is not set in the environment variables!")
        return

    # Initialize the developer-controlled wallets client
    api_client = circle_utils.init_developer_controlled_wallets_client(
        api_key=api_token,
        entity_secret=os.getenv("CIRCLE_HEX_ENCODED_ENTITY_SECRET_KEY")
    )

    # Create an instance of the WalletSets API
    wallet_sets_service = dc_wallets.WalletSetsApi(api_client)

    try:
        # Construct the wallet set request
        wallet_set_request = dc_wallets.CreateWalletSetRequest.from_dict({
            "name": project_label,  # Use the project label as the wallet set name
            "accountType": "SCA"
        })
        wallet_set_response = wallet_sets_service.create_wallet_set(wallet_set_request)

        # Retrieve the wallet set object
        wallet_set = wallet_set_response.data.wallet_set

        # Obtain the wallet set ID
        wallet_set_id = wallet_set.actual_instance.id

        # Define the endpoint for wallet creation
        wallets_endpoint = "https://api.circle.com/v1/w3s/developer/wallets"

        payload = f"""{{
            "blockchains": [
                "ETH-SEPOLIA"
            ],
            "metadata": [
                {{
                    "name": "{wallet_label}",
                    "refId": "{reference_id}"
                }}
            ],
            "count": 1,
            "entitySecretCiphertext": "{encrypted_entity_secret}",
            "idempotencyKey": "{idempotency_key}",
            "accountType": "SCA",
            "walletSetId": "{wallet_set_id}"
        }}"""
        headers = {
            "Authorization": f"Bearer {api_token}",  # Use the API token for authentication
            "Content-Type": "application/json"  # Specify the content type as JSON
        }

        # Send a POST request to create the wallet
        response = requests.post(wallets_endpoint, headers=headers, data=payload)
        print("Wallet created", response.text)
        wallet_data = response.json().get('data', {}).get('wallets', [])[0]
        return wallet_data.get('id'), wallet_data.get('address')

    except Exception as e:
        print(f"Error creating wallet set: {e}")

def encrypt_entity_secret():
    # Retrieve the public key and the entity secret from environment variables
    public_key_pem = os.getenv('CIRCLE_PUBLIC_KEY')
    hex_encoded_secret = os.getenv('CIRCLE_HEX_ENCODED_ENTITY_SECRET_KEY')

    # Convert the hex-encoded secret to bytes
    entity_secret_bytes = bytes.fromhex(hex_encoded_secret)

    # Ensure the entity secret is 32 bytes long
    if len(entity_secret_bytes) != 32:
        raise ValueError("Invalid entity secret length. Expected 32 bytes.")

    # Import the public key
    public_key = RSA.import_key(public_key_pem)

    # Encrypt the entity secret using the public key and OAEP padding with SHA256
    cipher_rsa = PKCS1_OAEP.new(key=public_key, hashAlgo=SHA256)
    encrypted_secret = cipher_rsa.encrypt(entity_secret_bytes)

    # Encode the encrypted data to base64
    encrypted_secret_base64 = base64.b64encode(encrypted_secret)

    # Decode the base64 bytes to a string
    encrypted_entity_secret = encrypted_secret_base64.decode()

    return encrypted_entity_secret
