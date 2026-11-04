import base64
import binascii
import hashlib
import hmac
import json
import time


class TokenValidationError(ValueError):
    pass


def _encode_segment(value):
    encoded = base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return encoded.rstrip(b"=").decode("ascii")


def _decode_segment(value):
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        value + padding, altchars=b"-_", validate=True
    )


def create_token(subject, secret, expires_in=3600, now=None):
    if not subject or not secret:
        raise ValueError("A token subject and signing secret are required")
    if expires_in <= 0:
        raise ValueError("Token lifetime must be greater than zero")

    issued_at = int(time.time() if now is None else now)
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment(
        {"sub": subject, "iat": issued_at, "exp": issued_at + expires_in}
    )
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode(
        "ascii"
    )
    return f"{signing_input}.{encoded_signature}"


def validate_token(token, secret, now=None):
    try:
        if not isinstance(token, str) or not secret:
            raise TokenValidationError("Token or signing secret is missing")

        parts = token.split(".")
        if len(parts) != 3:
            raise TokenValidationError("Token format is invalid")

        header = json.loads(_decode_segment(parts[0]))
        claims = json.loads(_decode_segment(parts[1]))
        signature = _decode_segment(parts[2])
        if not isinstance(header, dict) or header.get("alg") != "HS256":
            raise TokenValidationError("Token algorithm is invalid")
        if not isinstance(claims, dict):
            raise TokenValidationError("Token claims are invalid")

        signing_input = f"{parts[0]}.{parts[1]}"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise TokenValidationError("Token signature is invalid")

        subject = claims.get("sub")
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        if not isinstance(subject, str) or not subject:
            raise TokenValidationError("Token subject is invalid")
        if (
            isinstance(issued_at, bool)
            or not isinstance(issued_at, int)
            or isinstance(expires_at, bool)
            or not isinstance(expires_at, int)
        ):
            raise TokenValidationError("Token timestamps are invalid")

        current_time = int(time.time() if now is None else now)
        if issued_at > current_time or expires_at <= current_time:
            raise TokenValidationError("Token is not currently valid")
        return claims
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        if isinstance(error, TokenValidationError):
            raise
        raise TokenValidationError("Token is malformed") from error
