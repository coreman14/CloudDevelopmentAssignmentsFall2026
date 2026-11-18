import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

UPLOAD_KEY = "coupon.json"
UPLOAD_CONTENT_TYPE = "application/json"


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _s3_client():
    options = {
        "region_name": os.environ.get("AWS_REGION", "us-east-1"),
        # Path-style URLs keep the bucket name out of the hostname so the
        # signed host matches what the client calls.
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    if endpoint_url:
        options["endpoint_url"] = endpoint_url
    return boto3.client("s3", **options)


def _expiration_seconds():
    try:
        expires_in = int(os.environ.get("PRESIGNED_URL_EXPIRATION_SECONDS", "300"))
    except ValueError as error:
        raise RuntimeError("PRESIGNED_URL_EXPIRATION_SECONDS must be an integer") from error
    if expires_in <= 0:
        raise RuntimeError("PRESIGNED_URL_EXPIRATION_SECONDS must be greater than zero")
    return expires_in


def lambda_handler(event, context):
    bucket = os.environ.get("S3_BUCKET", "coupons")
    expires_in = _expiration_seconds()

    try:
        upload_url = _s3_client().generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket,
                "Key": UPLOAD_KEY,
                "ContentType": UPLOAD_CONTENT_TYPE,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
    except (BotoCoreError, ClientError):
        return _response(500, {"message": "Unable to generate a presigned upload URL"})

    return _response(
        200,
        {
            "upload_url": upload_url,
            "method": "PUT",
            "bucket": bucket,
            "key": UPLOAD_KEY,
            "expires_in": expires_in,
            "headers": {"Content-Type": UPLOAD_CONTENT_TYPE},
        },
    )
