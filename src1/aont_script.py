from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import hashlib

def aont_encrypt(plaintext, key):
    # Pad plaintext to AES block size
    padded = pad(plaintext, AES.block_size)
    # Generate a random key for the last step
    random_key = get_random_bytes(16)
    # Encrypt plaintext with AES in CBC mode using the key
    cipher = AES.new(key, AES.MODE_CBC)
    ciphertext = cipher.encrypt(padded)
    iv = cipher.iv
    # Create a hash over ciphertext + random_key
    h = hashlib.sha256(ciphertext + random_key).digest()
    # XOR the random_key with the hash to form a final block
    final_block = bytes(a ^ b for a, b in zip(random_key, h[:16]))
    # The output is ciphertext + final_block + IV
    return ciphertext + final_block + iv

def aont_decrypt(aont_data, key):
    # Split ciphertext, final_block, and iv
    iv = aont_data[-16:]
    final_block = aont_data[-32:-16]
    ciphertext = aont_data[:-32]
    # Recompute the hash to recover random_key
    h = hashlib.sha256(ciphertext + final_block).digest()
    random_key = bytes(a ^ b for a, b in zip(final_block, h[:16]))
    # Decrypt the ciphertext with AES CBC using original key and iv
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(ciphertext)
    # Unpad plaintext
    plaintext = unpad(padded_plaintext, AES.block_size)
    return plaintext

# Example usage
key = get_random_bytes(16)  # AES key for encryption
plaintext = b"Secret data to protect using AONT"

aont_data = aont_encrypt(plaintext, key)
recovered = aont_decrypt(aont_data, key)

print("Original:", plaintext)
print("AONT Data:", aont_data)
print("Recovered:", recovered)
