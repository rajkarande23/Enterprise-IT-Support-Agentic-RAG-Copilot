import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.services.tickets import (
    init_ticket_table,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
)

class TestITTickets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_ticket_table()
        cls.client = TestClient(app)

    def test_01_ticket_service_crud(self):
        # 1. Create ticket
        ticket = create_ticket(
            title="VPN Connection Failure",
            description="Employee cannot connect to US-East VPN tunnel after password update.",
            category="Network / VPN",
            priority="High",
            requester_email="test.user@novacore.internal",
            source="test_service",
            agent_trace=["Router -> KB", "Evidence weak", "Auto Escalation"],
        )
        self.assertIsNotNone(ticket)
        self.assertTrue(ticket["ticket_id"].startswith("INC-"))
        self.assertEqual(ticket["status"], "Open")
        self.assertEqual(ticket["priority"], "High")
        self.assertEqual(ticket["title"], "VPN Connection Failure")
        self.assertEqual(len(ticket["agent_trace"]), 3)

        ticket_id = ticket["ticket_id"]

        # 2. Get ticket
        fetched = get_ticket(ticket_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["ticket_id"], ticket_id)
        self.assertEqual(fetched["requester_email"], "test.user@novacore.internal")

        # 3. Update status
        updated = update_ticket_status(ticket_id, "In Progress")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "In Progress")

        # 4. List tickets
        all_tickets = list_tickets()
        self.assertGreaterEqual(len(all_tickets), 1)
        self.assertTrue(any(t["ticket_id"] == ticket_id for t in all_tickets))

    def test_02_ticket_api_endpoints(self):
        # 1. POST /api/tickets
        payload = {
            "title": "Monitor Display Flickering",
            "description": "External Dell monitor displays black screen intermittently when connected via USB-C.",
            "category": "Hardware",
            "priority": "Medium",
            "requester_email": "jane.doe@novacore.internal",
        }
        res = self.client.post("/api/tickets", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("ticket", data)
        ticket_id = data["ticket"]["ticket_id"]
        self.assertTrue(ticket_id.startswith("INC-"))

        # 2. GET /api/tickets
        res = self.client.get("/api/tickets")
        self.assertEqual(res.status_code, 200)
        list_data = res.json()
        self.assertIn("tickets", list_data)
        self.assertIn("stats", list_data)
        self.assertGreaterEqual(list_data["stats"]["total"], 1)

        # 3. GET /api/tickets/{ticket_id}
        res = self.client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["ticket"]["ticket_id"], ticket_id)

        # 4. PATCH /api/tickets/{ticket_id}
        res = self.client.patch(f"/api/tickets/{ticket_id}", json={"status": "Resolved"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["ticket"]["status"], "Resolved")

if __name__ == "__main__":
    unittest.main()
