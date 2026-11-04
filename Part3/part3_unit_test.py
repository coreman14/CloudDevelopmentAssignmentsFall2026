import json
import os
import unittest
from unittest.mock import MagicMock, patch

import bcrypt

from Part3 import auth_utils, coupons_get_token, coupons_to_secure


class AuthTokenTest(unittest.TestCase):
    def test_round_trip_and_expiration(self):
        token = auth_utils.create_token("tester1", "test-secret", now=100)

        claims = auth_utils.validate_token(token, "test-secret", now=101)

        self.assertEqual(claims, {"sub": "tester1", "iat": 100, "exp": 3700})

    def test_rejects_bad_signature_and_expired_token(self):
        token = auth_utils.create_token("tester1", "test-secret", now=100)
        expired = auth_utils.create_token(
            "tester1", "test-secret", expires_in=1, now=100
        )

        with self.assertRaises(auth_utils.TokenValidationError):
            auth_utils.validate_token(token, "wrong-secret", now=101)
        with self.assertRaises(auth_utils.TokenValidationError):
            auth_utils.validate_token(expired, "test-secret", now=101)

    def test_rejects_malformed_token(self):
        with self.assertRaises(auth_utils.TokenValidationError):
            auth_utils.validate_token("not-a-jwt", "test-secret")


class CouponsGetTokenTest(unittest.TestCase):
    def setUp(self):
        self.table = MagicMock()
        self.resource = MagicMock()
        self.resource.Table.return_value = self.table
        self.resource_patch = patch(
            "Part3.coupons_get_token.boto3.resource",
            return_value=self.resource,
        )
        self.resource_patch.start()
        self.addCleanup(self.resource_patch.stop)
        self.environment_patch = patch.dict(
            os.environ,
            {"JWT_SECRET": "test-secret", "JWT_EXPIRATION_SECONDS": "1800"},
        )
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.password_hash = bcrypt.hashpw(
            b"correct-password", bcrypt.gensalt(rounds=4)
        ).decode("ascii")
        self.table.get_item.return_value = {
            "Item": {"username": "tester1", "password_hash": self.password_hash}
        }

    def test_returns_token_and_expiration_for_valid_credentials(self):
        response = coupons_get_token.lambda_handler(
            {
                "body": json.dumps(
                    {"username": "tester1", "password": "correct-password"}
                )
            },
            None,
        )
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["expires_in"], 1800)
        self.assertGreater(payload["expires_at"], 0)
        self.assertEqual(
            auth_utils.validate_token(payload["token"], "test-secret")["sub"],
            "tester1",
        )
        self.table.get_item.assert_called_once_with(Key={"username": "tester1"})

    def test_returns_forbidden_for_wrong_password_or_unknown_user(self):
        wrong_password = coupons_get_token.lambda_handler(
            {
                "body": json.dumps(
                    {"username": "tester1", "password": "wrong-password"}
                )
            },
            None,
        )
        self.table.get_item.return_value = {}
        unknown_user = coupons_get_token.lambda_handler(
            {
                "body": json.dumps(
                    {"username": "missing", "password": "correct-password"}
                )
            },
            None,
        )

        self.assertEqual(wrong_password["statusCode"], 403)
        self.assertEqual(unknown_user["statusCode"], 403)

    def test_returns_forbidden_for_malformed_stored_hash(self):
        self.table.get_item.return_value = {
            "Item": {"username": "tester1", "password_hash": "not-a-bcrypt-hash"}
        }

        response = coupons_get_token.lambda_handler(
            {
                "body": json.dumps(
                    {"username": "tester1", "password": "correct-password"}
                )
            },
            None,
        )

        self.assertEqual(response["statusCode"], 403)

    def test_rejects_malformed_request_body(self):
        response = coupons_get_token.lambda_handler({"body": "not-json"}, None)

        self.assertEqual(response["statusCode"], 400)
        self.table.get_item.assert_not_called()


class CouponsToSecureTest(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(os.environ, {"JWT_SECRET": "test-secret"})
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

    def test_accepts_valid_bearer_token(self):
        token = auth_utils.create_token("tester1", "test-secret")
        response = coupons_to_secure.lambda_handler(
            {"headers": {"Authorization": f"Bearer {token}"}}, None
        )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["username"], "tester1")

    def test_returns_forbidden_for_missing_or_invalid_token(self):
        missing = coupons_to_secure.lambda_handler({}, None)
        invalid = coupons_to_secure.lambda_handler(
            {"headers": {"authorization": "Bearer invalid"}}, None
        )

        self.assertEqual(missing["statusCode"], 403)
        self.assertEqual(invalid["statusCode"], 403)


if __name__ == "__main__":
    unittest.main()
