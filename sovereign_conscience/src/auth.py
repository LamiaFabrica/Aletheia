import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from flask_login import UserMixin
import secrets

# AES-256 key management
AES_KEY = os.environ.get('MEDUSA_AES_KEY')
if AES_KEY is None:
    # Generate a random key and warn the user (not persistent)
    AES_KEY = secrets.token_bytes(32)
    print("[WARNING] MEDUSA_AES_KEY not set. Using a random key for this session only.")
else:
    # If the key is base64-encoded, decode it; otherwise, use as bytes
    try:
        AES_KEY = base64.urlsafe_b64decode(AES_KEY)
    except Exception:
        AES_KEY = AES_KEY.encode()

IV = b'MedusaAES256Init'  # 16 bytes IV (for demonstration; in production, use a random IV per encryption)


def aes_encrypt(plaintext: str) -> str:
    backend = default_backend()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(IV), backend=backend)
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode()) + padder.finalize()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.urlsafe_b64encode(ct).decode()


def aes_decrypt(ciphertext: str) -> str:
    backend = default_backend()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(IV), backend=backend)
    decryptor = cipher.decryptor()
    ct = base64.urlsafe_b64decode(ciphertext)
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode()


class User(UserMixin):
    def __init__(self, username, encrypted_password):
        self.id = username
        self.encrypted_password = encrypted_password

    @staticmethod
    def get(username):
        # Only one user: 'Roylepython'
        if username == 'Roylepython':
            # AES-256 encrypted version of 'EN5FrsEFhm!*'
            encrypted_password = '1Qw1QwQwQwQwQwQwQwQwQw=='  # Placeholder, will be replaced below
            # Generate and store the encrypted password if not already set
            if encrypted_password == '1Qw1QwQwQwQwQwQwQwQwQw==':
                encrypted_password = aes_encrypt('EN5FrsEFhm!*')
            return User('Roylepython', encrypted_password)
        return None

    def check_password(self, password):
        try:
            return aes_encrypt(password) == self.encrypted_password
        except Exception:
            return False 