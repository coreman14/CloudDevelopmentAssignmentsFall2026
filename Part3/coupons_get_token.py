import json
import os
import time

import bcrypt
import boto3

from .auth_utils import create_token


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _users_table():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    options = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    if endpoint_url:
        options["endpoint_url"] = endpoint_url
    return boto3.resource("dynamodb", **options).Table(
        os.environ.get("DYNAMODB_USERS_TABLE", "users")
    )


def _request_body(event):
    body = event.get("body")
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        try:
            value = json.loads(body)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
    return None


def lambda_handler(event, context):
    body = _request_body(event)
    if body is None:
        return _response(400, {"message": "Request body must be a JSON object"})

    username = body.get("username")
    password = body.get("password")
    if not isinstance(username, str) or not username:
        return _response(400, {"message": "A username is required"})
    if not isinstance(password, str) or not password:
        return _response(400, {"message": "A password is required"})

    user = _users_table().get_item(Key={"username": username}).get("Item")
    if user is None:
        return _response(403, {"message": "Invalid username or password"})

    password_hash = user.get("password_hash")
    if not isinstance(password_hash, str):
        return _response(403, {"message": "Invalid username or password"})
    try:
        password_matches = bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        password_matches = False
    if not password_matches:
        return _response(403, {"message": "Invalid username or password"})

    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET must be configured")
    expires_in = int(os.environ.get("JWT_EXPIRATION_SECONDS", "3600"))
    issued_at = int(time.time())
    token = create_token(username, secret, expires_in=expires_in, now=issued_at)
    return _response(
        200,
        {
            "token": token,
            "expires_in": expires_in,
            "expires_at": issued_at + expires_in,
        },
    )
