import json
import os

from .auth_utils import TokenValidationError, validate_token


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _bearer_token(event):
    headers = event.get("headers") or {}
    authorization = next(
        (
            value
            for name, value in headers.items()
            if name.lower() == "authorization"
        ),
        None,
    )
    if not isinstance(authorization, str):
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def lambda_handler(event, context):
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET must be configured")

    token = _bearer_token(event)
    if token is None:
        return _response(403, {"message": "A valid bearer token is required"})

    try:
        claims = validate_token(token, secret)
    except TokenValidationError:
        return _response(403, {"message": "Token is invalid or expired"})

    return _response(
        200,
        {"message": "Token is valid", "username": claims["sub"]},
    )
