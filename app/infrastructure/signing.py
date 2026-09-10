import hashlib
import hmac

from pydantic import SecretStr


def sign_payload(payload: bytes, secret: SecretStr) -> str:
    digest = hmac.new(
        secret.get_secret_value().encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def verify_signature(payload: bytes, signature: str, secret: SecretStr) -> bool:
    return hmac.compare_digest(signature, sign_payload(payload, secret))
