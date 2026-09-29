# Part 1: unit test for the coupons_list Lambda handler.
import json
import unittest

from coupons_list import lambda_handler


class CouponsListTest(unittest.TestCase):
    def test_api_gateway_event_returns_success_message(self):
        event = {"httpMethod": "GET", "path": "/coupons_poc"}
        response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            json.loads(response["body"]),
            {"message": "Coupons API is working successfully"},
        )


if __name__ == "__main__":
    unittest.main()
