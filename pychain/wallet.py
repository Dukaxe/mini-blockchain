"""Wallet: cặp khóa ECDSA (đường cong secp256k1, giống Bitcoin) và địa chỉ ví."""
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def address_from_public_key(public_key_hex: str) -> str:
    """Địa chỉ ví = 40 ký tự đầu của SHA-256(public key)."""
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]


class Wallet:
    def __init__(self, private_key=None):
        self.private_key = private_key or ec.generate_private_key(ec.SECP256K1())

    @property
    def public_key_hex(self) -> str:
        raw = self.private_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        return raw.hex()

    @property
    def address(self) -> str:
        return address_from_public_key(self.public_key_hex)

    def sign(self, message: str) -> str:
        signature = self.private_key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
        return signature.hex()

    # Lưu / nạp khóa bí mật dạng PEM để dùng lại ví giữa các lần chạy
    def to_pem(self) -> str:
        return self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

    @classmethod
    def from_pem(cls, pem: str) -> "Wallet":
        return cls(serialization.load_pem_private_key(pem.encode(), password=None))


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), bytes.fromhex(public_key_hex)
        )
        public_key.verify(bytes.fromhex(signature_hex), message.encode(), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False
