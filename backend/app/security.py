from cryptography.fernet import Fernet

from app.config import get_settings

_fernet = Fernet(get_settings().token_encryption_key)


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()
