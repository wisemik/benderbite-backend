import os
import uuid
import logging
from decimal import Decimal, getcontext

from circle.web3 import developer_controlled_wallets as dc_wallets
from circle.web3 import smart_contract_platform, developer_controlled_wallets
from circle.web3 import utils as circle_utils

import requests
from dotenv import load_dotenv
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

# Configure logging
logging.basicConfig(level=logging.DEBUG)
# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from a .env file
load_dotenv()

ETH_SEPOLIA_ADDRESS = "979869da-9115-5f7d-917d-12d434e56ae7"

def call_contract_execution(name, address):
    # Retrieve necessary environment variables
    api_token = os.getenv('CIRCLE_API_KEY')
    wallet_id = 'f89bfdb1-ccf3-517a-8046-12cffeb406de'  # Example wallet ID
    contract_address = '0x5ad32460313e15a165703bd38a65965f4e7c4d0c'  # Example contract address
    encrypted_entity_secret = encrypt_entity_secret()

    # Generate a unique idempotency key
    idempotency_key = str(uuid.uuid4())

    # Construct the payload
    payload = {
        "idempotencyKey": idempotency_key,
        "walletId": wallet_id,
        "contractAddress": contract_address,
        "abiFunctionSignature": "register(string,address)",
        "abiParameters": [
            name, address
        ],
        "feeLevel": "HIGH",
        "entitySecretCiphertext": encrypted_entity_secret
    }

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    # Endpoint for contract execution
    url = "https://api.circle.com/v1/w3s/developer/transactions/contractExecution"

    try:
        # Send POST request
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        print("Contract execution response:", response.json())
        return f"https://app.ens.domains/{name}.benderbite.eth"
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occurred: {e.response.text}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def call_smartcontract():
    api_key = os.getenv('CIRCLE_API_KEY')
    entity_secret = os.getenv("CIRCLE_HEX_ENCODED_ENTITY_SECRET_KEY")
    scpClient = circle_utils.init_smart_contract_platform_client(api_key=api_key,
                                                                 entity_secret=entity_secret)

    # create an api instance
    api_instance = smart_contract_platform.ViewUpdateApi(scpClient)
    try:
        resposne = api_instance.get_contract(id='0192a688-2cbf-7ee0-8eeb-33947bd7e95f')
        print(resposne)
    except smart_contract_platform.ApiException as e:
        print("Exception when calling ViewUpdateApi->get_contract: %s\n" % e)

    api_instance = developer_controlled_wallets.TransactionsApi(scpClient)
    try:
        request = developer_controlled_wallets.CreateContractExecutionTransactionForDeveloperRequest.from_dict({
            "walletId": 'f89bfdb1-ccf3-517a-8046-12cffeb406de',
            "contractAddress": '0x5ad32460313e15a165703bd38a65965f4e7c4d0c',
            "abiFunctionSignature": 'safeMint(address, uint256)',
            "abiParameters": ['yertyert', '0x6E5eAf34c73D1CD0be4e24f923b97CF38e10d1f3'],
            "feeLevel": 'HIGH'
        })
        resposne = api_instance.create_developer_transaction_contract_execution(request)
        print(resposne)
    except developer_controlled_wallets.ApiException as e:
        print("Exception when calling TransactionsApi->create_developer_transaction_contract_execution: %s\n" % e)

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

MASTER_WALLET_ID = "f89bfdb1-ccf3-517a-8046-12cffeb406de"
MASTER_WALLET_ADDRESS = "0x11aaa9a23be5bc8388373a35343a4fbc94192599"


def pay_to_winner(amount, winner_address):
    getcontext().prec = 28  # Set appropriate precision

    logger.info(f"pay_to_winner called with amount: {amount}, winner_address: {winner_address}")

    # Retrieve necessary environment variables
    api_token = os.getenv('CIRCLE_API_KEY')
    logger.debug(f"CIRCLE_API_KEY retrieved: {'Yes' if api_token else 'No'}")

    # Construct the request URL and parameters
    url = 'https://api.circle.com/v1/w3s/transactions'

    params = {
        'blockchain': 'ETH-SEPOLIA',
        'custodyType': 'DEVELOPER',
        'destinationAddress': winner_address,
        'operation': 'TRANSFER',
        'state': 'CONFIRMED'
    }

    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request params: {params}")

    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

    payments = []  # List to store the payments

    try:
        # Send GET request
        logger.info("Sending GET request to Circle API to retrieve transactions")
        response = requests.get(url, headers=headers, params=params)
        logger.debug(f"Response status code: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Response data: {data}")

        data = data.get('data', [])
        transactions = data.get('transactions', [])
        logger.info(f"Found {len(transactions)} transactions")

        source_address_amounts = {}
        total_contributed_amount = Decimal('0')

        for transaction in transactions:
            logger.debug(f"Processing transaction ID: {transaction.get('id')}")
            if (transaction.get('tokenId') == ETH_SEPOLIA_ADDRESS and
                transaction.get('state') == 'CONFIRMED' and
                transaction.get('transactionType') == 'INBOUND'):

                source_address = transaction.get('sourceAddress')
                logger.debug(f"Transaction source address: {source_address}")
                amounts = transaction.get('amounts', [])
                for amt_str in amounts:
                    amt = Decimal(amt_str)
                    logger.debug(f"Amount in transaction: {amt}")
                    if source_address in source_address_amounts:
                        source_address_amounts[source_address] += amt
                    else:
                        source_address_amounts[source_address] = amt
                    total_contributed_amount += amt

        logger.info(f"Total contributed amount: {total_contributed_amount}")

        if total_contributed_amount == Decimal('0'):
            logger.warning("No contributions found.")
            return payments  # Return empty list

        # Convert amount parameter to Decimal
        total_amount_to_pay = Decimal(amount)
        logger.info(f"Total amount to pay: {total_amount_to_pay}")

        # For each sourceAddress, compute amount to pay and call pay_from_master
        for source_address, contributed_amount in source_address_amounts.items():
            logger.debug(f"Computing payment for source address: {source_address}")
            proportion = contributed_amount / total_contributed_amount
            amount_to_pay = total_amount_to_pay * proportion
            # Round amount_to_pay appropriately, e.g., to 6 decimal places
            amount_to_pay = amount_to_pay.quantize(Decimal('0.000001'))
            # Convert amount_to_pay to string
            amount_to_pay_str = format(amount_to_pay, 'f')
            logger.info(f"Paying {amount_to_pay_str} to {source_address}")
            # Call pay_from_master(amount_to_pay_str, source_address)
            transfer_result = pay_from_master(amount_to_pay_str, source_address)
            logger.debug(f"Transfer result: {transfer_result}")
            # Append the payment details to the list
            payments.append({
                'amount': amount_to_pay_str,
                'source_address': source_address,
                'transfer_result': transfer_result
            })

        logger.info(f"Payments made: {payments}")
        return payments  # Return the list of payments

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e.response.text}")
        return payments  # Return whatever payments have been processed so far
    except Exception as e:
        logger.exception("An error occurred in pay_to_winner")
        return payments  # Return whatever payments have been processed so far


def pay_to_master(amount: str, from_address: str):
    return create_transfer(from_address,
                                   ETH_SEPOLIA_ADDRESS,
                                      amount, MASTER_WALLET_ADDRESS)

def pay_from_master(amount: str, to_address: str):
    return create_transfer(MASTER_WALLET_ID,
                                   ETH_SEPOLIA_ADDRESS,
                                      amount, to_address)


def create_transfer(from_wallet_id: str, from_token_id: str, amount: str, destination_address: str):
    print("Creating transfer from wallet ID:", from_wallet_id, "from_token_id:", from_token_id,
          "to address:", destination_address, "with amount:", amount)
    entitySecretCipherText = encrypt_entity_secret()

    # wallet_id = "f89bfdb1-ccf3-517a-8046-12cffeb406de"

    #generate new uuid for idempotency key
    idempotencyKey = uuid.uuid4()

    # print(idempotencyKey)

    payload = {
        "idempotencyKey": str(idempotencyKey),
        "entitySecretCipherText": entitySecretCipherText,
        "amounts": [amount],
        "destinationAddress": destination_address,
        "feeLevel": "HIGH",
        "tokenId": from_token_id,
        "walletId": from_wallet_id
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer "+os.getenv('CIRCLE_API_KEY')
    }

    url = "https://api.circle.com/v1/w3s/developer/transactions/transfer"

    try:
        response = requests.post(url, json=payload, headers=headers)
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response text: {response.text}")
        response.raise_for_status()
        logger.info(f"Transfer successful. Response: {response.text}")
        return response.json().get('data').get('id')
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during transfer: {e.response.text}")
        return None
    except Exception as e:
        logger.exception("An error occurred during create_transfer")
        return None


def wallet_balance(wallet_id: str, ref_token_id: str = ETH_SEPOLIA_ADDRESS):
    print("Getting wallet balance for wallet ID:", wallet_id)
    api_key = os.getenv('CIRCLE_API_KEY')

    url = f"https://api.circle.com/v1/w3s/wallets/{wallet_id}/balances"
    headers = {
        "Authorization": f"Bearer {api_key}",  # Using the API key for authentication
        "Content-Type": "application/json"  # Ensuring the payload is sent as JSON
    }
    response = requests.request("GET", url, headers=headers)

    # Parse the response to get the amount
    try:
        data = response.json()
        print(data)
        token_balances = data.get("data", {}).get("tokenBalances", [])

        for token_balance in token_balances:
            # Assuming we want to extract the first token balance
            token_amount = token_balance.get("amount", "0")  # Default to 0 if amount is missing
            token_id = token_balance.get("token", "").get("id", "")  # Default to empty string if token ID is missing
            if token_id == ref_token_id:
                print(f"Token amount: {token_amount}")
                print(f"Token ID: {token_id}")
                return token_amount
        print("No token balances found.")
        return "0"
    except Exception as e:
        print(f"Error parsing wallet balance: {e}")
        return "0"
