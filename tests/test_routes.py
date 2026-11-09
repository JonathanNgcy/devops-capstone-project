"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from unittest.mock import patch
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"
HTTPS_ENVIRON = {"wsgi.url_scheme": "https"}


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        talisman.force_https = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ADD YOUR TEST CASES HERE ...

    def test_read_account(self):
        """It should retrieve every field of an existing account."""
        account = self._create_accounts(1)[0]
        response = self.client.get(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), account.serialize())

    def test_read_account_not_found(self):
        """It should return 404 for an unknown account."""
        response = self.client.get(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_accounts(self):
        """It should list all accounts, including an initially empty list."""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), [])
        accounts = self._create_accounts(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {account["id"] for account in response.get_json()},
            {account.id for account in accounts},
        )

    def test_update_account(self):
        """It should persist an update without creating another account."""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data["phone_number"] = "555-1111"
        response = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), data)
        response = self.client.get(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.get_json(), data)
        self.assertEqual(len(self.client.get(BASE_URL).get_json()), 1)

    def test_update_account_not_found(self):
        """It should return 404 when updating an unknown account."""
        response = self.client.put(f"{BASE_URL}/0", json=AccountFactory().serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_account_invalid_body(self):
        """It should reject invalid JSON fields and unsupported media types."""
        account = self._create_accounts(1)[0]
        url = f"{BASE_URL}/{account.id}"
        self.assertEqual(self.client.put(url, json={}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.put(url, data="invalid").status_code,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    def test_delete_account(self):
        """It should remove an account and allow repeated deletion."""
        account = self._create_accounts(1)[0]
        url = f"{BASE_URL}/{account.id}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(BASE_URL).get_json(), [])
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT)

    def test_create_account_location(self):
        """It should return a usable Location URL for the created account."""
        response = self.client.post(BASE_URL, json=AccountFactory().serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        found = self.client.get(response.headers["Location"])
        self.assertEqual(found.status_code, status.HTTP_200_OK)
        self.assertEqual(found.get_json(), response.get_json())

    def test_security_headers(self):
        """It should return the required security headers over HTTPS."""
        response = self.client.get("/", environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        headers = {
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'; object-src 'none'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        for name, value in headers.items():
            self.assertEqual(response.headers.get(name), value)

    def test_cors_security(self):
        """It should return the course's public API CORS policy."""
        response = self.client.get("/", environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_method_not_allowed(self):
        """It should return a JSON error for an unsupported API method."""
        response = self.client.patch(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.get_json()["error"], "Method not Allowed")

    def test_internal_server_error(self):
        """It should handle an unexpected backend failure without exposing a traceback."""
        with patch("service.routes.Account.all", side_effect=RuntimeError("simulated failure")):
            with patch.dict(app.config, {"TESTING": False, "PROPAGATE_EXCEPTIONS": False}):
                response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.get_json()["error"], "Internal Server Error")
