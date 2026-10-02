#!/usr/bin/env python
"""
Print a new VAPID key pair for Web Push (docs/feature_spec/mobile-notifications §5.2).

Set the output as environment variables on the API service, once per
environment. Changing the keys later cuts off every existing device: each
has to turn notifications on again.

Usage (inside Docker, or a shell on the Railway API service):
    python scripts/generate_vapid_keys.py
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private = _b64url(key.private_numbers().private_value.to_bytes(32, "big"))
    public = _b64url(key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    ))
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
    print("VAPID_SUBJECT=mailto:you@yourdomain")


if __name__ == "__main__":
    main()
