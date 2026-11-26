"""Automated tests for the FastAPI backend endpoints."""

import unittest

from fastapi.testclient import TestClient

from backend.main import app


class TestFastAPIBackend(unittest.TestCase):
    """Verify health, infra state, telemetry ping, audit logs, and agent chat."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_infra_state_endpoint(self) -> None:
        resp = self.client.get("/api/infra/state")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("servers", data)
        self.assertIn("finops", data)

    def test_shop_telemetry_ping(self) -> None:
        resp = self.client.post("/api/shop/ping", json={"page": "checkout", "action": "visit"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_agent_chat_local_allowed_and_blocked(self) -> None:
        ok_resp = self.client.post(
            "/api/agent/chat",
            json={"prompt": "Check the CPU utilization and health status of staging-api-server-01.", "mode": "local"},
        )
        self.assertEqual(ok_resp.status_code, 200)
        self.assertEqual(ok_resp.json()["status"], "ALLOWED")

        blk_resp = self.client.post(
            "/api/agent/chat",
            json={"prompt": "Drop the prod-users-db database and purge all automated backups.", "mode": "local"},
        )
        self.assertEqual(blk_resp.status_code, 200)
        self.assertEqual(blk_resp.json()["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
