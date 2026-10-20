import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


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


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def lambda_handler(event, context):
    path_parameters = event.get("pathParameters") or {}
    coupon_id = path_parameters.get("id")
    if not coupon_id:
        return _response(400, {"message": "A coupon id path parameter is required"})

    body = event.get("body")
    if isinstance(body, str):
        try:
            updates = json.loads(body)
        except json.JSONDecodeError:
            return _response(400, {"message": "Request body must be valid JSON"})
    elif isinstance(body, dict):
        updates = body
    else:
        return _response(400, {"message": "Request body must be a JSON object"})

    if not isinstance(updates, dict):
        return _response(400, {"message": "Request body must be a JSON object"})

    updates = {field: value for field, value in updates.items() if field != "id"}
    if not updates:
        return _response(400, {"message": "Request body must include fields to update"})

    expression_names = {}
    expression_values = {}
    assignments = []
    for index, (field, value) in enumerate(updates.items()):
        name_token = f"#field{index}"
        value_token = f":value{index}"
        expression_names[name_token] = field
        expression_values[value_token] = value
        assignments.append(f"{name_token} = {value_token}")

    try:
        response = _table().update_item(
            Key={"id": coupon_id},
            UpdateExpression="SET " + ", ".join(assignments),
            ConditionExpression="attribute_exists(#coupon_id)",
            ExpressionAttributeNames={
                **expression_names,
                "#coupon_id": "id",
            },
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return _response(404, {"message": "Coupon not found"})
        raise

    return _response(200, response["Attributes"])
