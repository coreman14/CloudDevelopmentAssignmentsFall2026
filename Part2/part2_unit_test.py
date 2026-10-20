import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from Part2 import coupons_get_by_id, coupons_update


class CouponsGetByIdTest(unittest.TestCase):
    def setUp(self):
        self.table = MagicMock()
        self.resource = MagicMock()
        self.resource.Table.return_value = self.table
        self.resource_patch = patch(
            "Part2.coupons_get_by_id.boto3.resource", return_value=self.resource
        )
        self.resource_patch.start()
        self.addCleanup(self.resource_patch.stop)

    def test_returns_coupon_by_path_id_using_eventual_read(self):
        coupon = {
            "id": "coupon-123",
            "provider_id": "provider-1",
            "discount": Decimal("12.5"),
        }
        self.table.get_item.return_value = {"Item": coupon}

        response = coupons_get_by_id.lambda_handler(
            {"pathParameters": {"id": "coupon-123"}}, None
        )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {**coupon, "discount": 12.5})
        self.table.get_item.assert_called_once_with(
            Key={"id": "coupon-123"}, ConsistentRead=False
        )

    def test_returns_not_found_when_coupon_is_missing(self):
        self.table.get_item.return_value = {}

        response = coupons_get_by_id.lambda_handler(
            {"pathParameters": {"id": "missing"}}, None
        )

        self.assertEqual(response["statusCode"], 404)

    def test_rejects_missing_path_id(self):
        response = coupons_get_by_id.lambda_handler({}, None)

        self.assertEqual(response["statusCode"], 400)
        self.table.get_item.assert_not_called()


class CouponsUpdateTest(unittest.TestCase):
    def setUp(self):
        self.table = MagicMock()
        self.resource = MagicMock()
        self.resource.Table.return_value = self.table
        self.resource_patch = patch(
            "Part2.coupons_update.boto3.resource", return_value=self.resource
        )
        self.resource_patch.start()
        self.addCleanup(self.resource_patch.stop)

    def test_updates_fields_without_changing_path_id(self):
        updated_coupon = {
            "id": "coupon-123",
            "provider_id": "provider-1",
            "description": "Updated offer",
        }
        self.table.update_item.return_value = {"Attributes": updated_coupon}

        response = coupons_update.lambda_handler(
            {
                "pathParameters": {"id": "coupon-123"},
                "body": json.dumps(
                    {"id": "different-id", "description": "Updated offer"}
                ),
            },
            None,
        )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), updated_coupon)
        self.table.update_item.assert_called_once_with(
            Key={"id": "coupon-123"},
            UpdateExpression="SET #field0 = :value0",
            ConditionExpression="attribute_exists(#coupon_id)",
            ExpressionAttributeNames={
                "#field0": "description",
                "#coupon_id": "id",
            },
            ExpressionAttributeValues={":value0": "Updated offer"},
            ReturnValues="ALL_NEW",
        )

    def test_returns_not_found_when_coupon_does_not_exist(self):
        self.table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "UpdateItem",
        )

        response = coupons_update.lambda_handler(
            {"pathParameters": {"id": "missing"}, "body": '{"name":"Offer"}'},
            None,
        )

        self.assertEqual(response["statusCode"], 404)

    def test_rejects_invalid_json(self):
        response = coupons_update.lambda_handler(
            {"pathParameters": {"id": "coupon-123"}, "body": "not-json"},
            None,
        )

        self.assertEqual(response["statusCode"], 400)
        self.table.update_item.assert_not_called()

    def test_rejects_empty_update(self):
        response = coupons_update.lambda_handler(
            {"pathParameters": {"id": "coupon-123"}, "body": '{"id":"other"}'},
            None,
        )

        self.assertEqual(response["statusCode"], 400)
        self.table.update_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
