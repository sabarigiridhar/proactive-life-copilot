import tempfile
import unittest
from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient

from backend.core.settings import Settings
from backend.main import create_app


class ApiFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            environment="test",
            database_path=root / "api.db",
            chroma_path=root / "chroma",
            cors_origins=["http://localhost:3000"],
        )
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_openapi_exposes_versioned_health_route(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/health", response.json()["paths"])

    def test_health_returns_consistent_success_shape_and_dependencies(self):
        response = self.client.get(
            "/api/v1/health", headers={"x-request-id": "test-request-id"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "test-request-id")
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["request_id"], "test-request-id")
        self.assertEqual(payload["data"]["environment"], "test")
        self.assertIn(payload["data"]["status"], ["ok", "degraded"])
        self.assertIn(payload["data"]["database"]["status"], ["ok", "error"])
        self.assertIn(payload["data"]["vector_store"]["status"], ["ok", "error"])

    def test_cors_uses_configured_local_origins(self):
        response = self.client.options(
            "/api/v1/health",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:3000",
        )

    def test_http_errors_use_consistent_error_shape(self):
        response = self.client.get("/api/v1/missing")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "http_error")
        self.assertIsNotNone(payload["request_id"])

    def test_validation_errors_use_consistent_error_shape(self):
        router = APIRouter()

        @router.get("/api/v1/needs-int")
        def needs_int(value: int):
            return {"value": value}

        self.app.include_router(router)

        response = self.client.get("/api/v1/needs-int", params={"value": "nope"})

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
