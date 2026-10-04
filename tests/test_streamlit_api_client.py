import unittest

import httpx

from life_copilot.ui.api_client import ApiClientError, LifeCopilotApiClient


def envelope(data=None, *, success=True, message=None):
    return {
        "success": success,
        "data": data,
        "error": None if success else {"code": "test_error", "message": message},
        "request_id": "test-request",
    }


class StreamlitApiClientTests(unittest.TestCase):
    def _client(self, handler):
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(
            transport=transport,
            base_url="http://api.test/api/v1/",
        )
        return LifeCopilotApiClient(
            "http://api.test/api/v1",
            client=http_client,
        )

    def test_client_uses_versioned_http_contracts_and_parses_typed_results(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/messages"):
                return httpx.Response(
                    200,
                    json=envelope(
                        {
                            "thread_id": "thread-1",
                            "response_type": "query_answer",
                            "assistant_text": "Total: INR 350.",
                            "draft": None,
                            "evidence": [{"currency": "INR", "total": 350}],
                            "date_range": None,
                            "confidence": 1,
                        }
                    ),
                )
            if request.url.path.endswith("/logs/wealth"):
                return httpx.Response(
                    200,
                    json=envelope(
                        {
                            "domain": "wealth",
                            "items": [],
                            "page": 1,
                            "page_size": 50,
                            "total": 0,
                            "total_pages": 0,
                        }
                    ),
                )
            if request.url.path.endswith("/media/transcriptions"):
                return httpx.Response(200, json=envelope({"text": "voice text"}))
            raise AssertionError(request.url.path)

        client = self._client(handler)
        message = client.send_message(
            thread_id="thread-1",
            message="How much did I spend?",
        )
        records = client.list_records("wealth")
        media = client.transcribe_audio(
            filename="recording.wav",
            content=b"audio",
            content_type="audio/wav",
        )

        self.assertEqual(message.response_type, "query_answer")
        self.assertEqual(message.evidence[0]["total"], 350)
        self.assertEqual(records.total, 0)
        self.assertEqual(media.text, "voice text")
        self.assertEqual(
            [request.url.path for request in requests],
            [
                "/api/v1/messages",
                "/api/v1/logs/wealth",
                "/api/v1/media/transcriptions",
            ],
        )
        self.assertTrue(
            requests[-1].headers["content-type"].startswith("multipart/form-data")
        )
        self.assertTrue(all("x-request-id" in request.headers for request in requests))
        client.close()

    def test_api_error_uses_server_message_without_exposing_response_details(self):
        def handler(_request):
            return httpx.Response(
                422,
                json=envelope(
                    success=False,
                    message="The request payload or parameters are invalid.",
                ),
            )

        client = self._client(handler)
        with self.assertRaises(ApiClientError) as context:
            client.patch_record("wealth", 1, {"amount": -1})

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(
            str(context.exception),
            "The request payload or parameters are invalid.",
        )
        client.close()

    def test_connection_and_malformed_response_errors_are_safe(self):
        def disconnected(request):
            raise httpx.ConnectError("private connection detail", request=request)

        disconnected_client = self._client(disconnected)
        with self.assertRaises(ApiClientError) as connection_context:
            disconnected_client.list_records("health")
        self.assertIn("backend is running", str(connection_context.exception))
        self.assertNotIn("private", str(connection_context.exception))
        disconnected_client.close()

        def malformed(_request):
            return httpx.Response(200, content=b"not-json")

        malformed_client = self._client(malformed)
        with self.assertRaises(ApiClientError) as malformed_context:
            malformed_client.delete_record("learning", 1)
        self.assertIn("unreadable response", str(malformed_context.exception))
        malformed_client.close()

        def wrong_shape(_request):
            return httpx.Response(200, json=["not", "an", "envelope"])

        wrong_shape_client = self._client(wrong_shape)
        with self.assertRaises(ApiClientError) as wrong_shape_context:
            wrong_shape_client.list_records("health")
        self.assertIn("unexpected response", str(wrong_shape_context.exception))
        wrong_shape_client.close()

    def test_confirmation_dashboard_and_record_mutations_are_typed(self):
        def handler(request):
            path = request.url.path
            if path.endswith("/logs/confirm"):
                return httpx.Response(
                    201,
                    json=envelope(
                        {
                            "thread_id": "thread-1",
                            "assistant_text": "Saved 1 confirmed record(s).",
                            "daily_status": {
                                "entry_date": "2026-10-04",
                                "health_complete": False,
                                "wealth_reviewed": True,
                                "learning_complete": False,
                                "is_complete": False,
                            },
                            "entities": [],
                            "warnings": [],
                        }
                    ),
                )
            if path.endswith("/dashboard/summary"):
                return httpx.Response(
                    200,
                    json=envelope(
                        {
                            "status_date": "2026-10-04",
                            "daily_status": {
                                "entry_date": "2026-10-04",
                                "health_complete": False,
                                "wealth_reviewed": True,
                                "learning_complete": False,
                                "is_complete": False,
                            },
                        }
                    ),
                )
            if request.method == "PATCH":
                return httpx.Response(
                    200,
                    json=envelope(
                        {
                            "domain": "wealth",
                            "record": {"id": 1, "amount": 125},
                            "warnings": [],
                        }
                    ),
                )
            if request.method == "DELETE":
                return httpx.Response(
                    200,
                    json=envelope(
                        {"domain": "wealth", "deleted_id": 1, "warnings": []}
                    ),
                )
            raise AssertionError(path)

        client = self._client(handler)
        confirmation = client.confirm_log(
            thread_id="thread-1",
            draft={"entry_date": "2026-10-04"},
        )
        dashboard = client.get_dashboard_summary(
            status_date=confirmation.daily_status.entry_date
        )
        updated = client.patch_record("wealth", 1, {"amount": 125})
        deleted = client.delete_record("wealth", 1)

        self.assertTrue(confirmation.daily_status.wealth_reviewed)
        self.assertEqual(dashboard.status_date.isoformat(), "2026-10-04")
        self.assertEqual(updated.record["amount"], 125)
        self.assertEqual(deleted.deleted_id, 1)
        client.close()


if __name__ == "__main__":
    unittest.main()
