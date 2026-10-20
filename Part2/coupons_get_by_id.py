import json
import os
from decimal import Decimal

import boto3


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _table():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    options = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    if endpoint_url:
        options["endpoint_url"] = endpoint_url
    return boto3.resource("dynamodb", **options).Table(
        os.environ.get("DYNAMODB_TABLE", "coupons")
    )


def lambda_handler(event, context):
    path_parameters = event.get("pathParameters") or {}
    coupon_id = path_parameters.get("id")
    if not coupon_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "A coupon id path parameter is required"}),
        }

    response = _table().get_item(Key={"id": coupon_id}, ConsistentRead=False)
    coupon = response.get("Item")
    if coupon is None:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "Coupon not found"}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(coupon, default=_json_default),
    }
