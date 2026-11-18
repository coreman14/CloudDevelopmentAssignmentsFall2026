import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from botocore.exceptions import ClientError

from Part4 import coupons_import_presigned_url


class CouponsImportPresignedUrlTest(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(
            os.environ,
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCESS_KEY_ID": "test",
                "AWS_SECRET_ACCESS_KEY": "test",
                "S3_BUCKET": "coupons",
                "S3_ENDPOINT_URL": "http://localhost.localstack.cloud:4566",
                "PRESIGNED_URL_EXPIRATION_SECONDS": "300",
            },
        )
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

    def test_returns_presigned_put_url_for_coupon_json(self):
        response = coupons_import_presigned_url.lambda_handler({}, None)
        body = json.loads(response["body"])
        url = urlparse(body["upload_url"])
        query = parse_qs(url.query)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        self.assertEqual(body["method"], "PUT")
        self.assertEqual(body["bucket"], "coupons")
        self.assertEqual(body["key"], "coupon.json")
        self.assertEqual(body["expires_in"], 300)
        self.assertEqual(body["headers"], {"Content-Type": "application/json"})
        self.assertEqual(url.netloc, "localhost.localstack.cloud:4566")
        self.assertEqual(url.path, "/coupons/coupon.json")
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertEqual(query["X-Amz-Expires"], ["300"])
        self.assertIn("content-type", query["X-Amz-SignedHeaders"][0])
        self.assertIn("X-Amz-Signature", query)

    def test_returns_server_error_when_url_cannot_be_generated(self):
        with patch(
            "Part4.coupons_import_presigned_url.boto3.client"
        ) as client_factory:
            client_factory.return_value.generate_presigned_url.side_effect = (
                ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
            )
            response = coupons_import_presigned_url.lambda_handler({}, None)

        self.assertEqual(response["statusCode"], 500)

    def test_rejects_invalid_expiration_configuration(self):
        with patch.dict(os.environ, {"PRESIGNED_URL_EXPIRATION_SECONDS": "0"}):
            with self.assertRaises(RuntimeError):
                coupons_import_presigned_url.lambda_handler({}, None)


if __name__ == "__main__":
    unittest.main()
