import struct
import unittest
import zlib
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from google.genai.errors import ClientError, ServerError

import ai_service
from ai_service import AIServiceError
from main import app
from schemas import ChatResponse, CrackAnalysis, DailySiteResponse, SafetyAnalysis, WeatherResponse


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    chunk = chunk_type + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)


def _one_pixel_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">2I5B", 1, 1, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\xff"))
        + _png_chunk(b"IEND", b"")
    )


class BackendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_safety_upload_passes_image_to_multimodal_service(self):
        expected = SafetyAnalysis(
            summary="A partial construction area is visible.",
            overall_risk="Uncertain",
            limitations=["The view is incomplete."],
        )
        with patch("main.generate_structured", new=AsyncMock(return_value=expected)) as generate:
            response = self.client.post(
                "/api/site-safety/analyze",
                files={"image": ("site.png", _one_pixel_png(), "image/png")},
                data={"context": "North side of the building"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["analysis"]["summary"], expected.summary)
        self.assertEqual(generate.await_args.kwargs["image_bytes"], _one_pixel_png())
        self.assertEqual(generate.await_args.kwargs["mime_type"], "image/png")

    def test_safety_endpoint_returns_sanitized_ai_error(self):
        with patch(
            "main.generate_structured",
            new=AsyncMock(side_effect=AIServiceError(504, "AI connection timed out safely.")),
        ):
            response = self.client.post(
                "/api/site-safety/analyze",
                files={"image": ("site.png", _one_pixel_png(), "image/png")},
            )
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"], "AI connection timed out safely.")

    def test_image_validation_rejects_unsupported_corrupt_missing_and_oversized(self):
        damaged_png = bytearray(_one_pixel_png())
        damaged_png[-20] ^= 1
        unsupported = self.client.post(
            "/api/crack-analysis/analyze",
            files={"image": ("notes.txt", b"not an image", "text/plain")},
        )
        corrupt = self.client.post(
            "/api/site-safety/analyze",
            files={"image": ("bad.png", bytes(damaged_png), "image/png")},
        )
        missing = self.client.post("/api/site-safety/analyze")
        oversized = self.client.post(
            "/api/crack-analysis/analyze",
            files={"image": ("large.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")},
        )
        self.assertEqual(unsupported.status_code, 400)
        self.assertEqual(corrupt.status_code, 400)
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(oversized.status_code, 413)

    def test_crack_endpoint_returns_validated_model_schema(self):
        expected = {
            "summary": "A thin diagonal line is visible.",
            "crack_visible": True,
            "characteristics": ["Diagonal", "Thin"],
            "category": "Diagonal",
            "indicative_severity": "Minor",
            "possible_causes": ["Cause is uncertain."],
            "concerns": [],
            "recommended_next_steps": ["Arrange an inspection if it changes."],
            "limitations": ["Image-only observation."],
        }
        with patch("main.generate_structured", new=AsyncMock(return_value=CrackAnalysis(**expected))):
            response = self.client.post(
                "/api/crack-analysis/analyze",
                files={"image": ("wall.png", _one_pixel_png(), "image/png")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["analysis"], expected)

    def test_project_plan_and_valuation_are_deterministic_and_labeled(self):
        plan = self.client.post(
            "/api/project-plan",
            json={
                "project_type": "Residential",
                "built_up_area_sqm": 100,
                "floors": 2,
                "budget_inr": 5_000_000,
                "target_timeline_days": 200,
            },
        )
        self.assertEqual(plan.status_code, 200)
        plan_data = plan.json()
        self.assertEqual(plan_data["estimate_status"], "INDICATIVE")
        self.assertAlmostEqual(
            sum(item["estimated_cost_inr"] for item in plan_data["cost_breakdown"]),
            5_000_000,
        )
        self.assertEqual(sum(item["duration_days"] for item in plan_data["cost_breakdown"]), 200)

        valuation = self.client.post(
            "/api/property-valuation",
            json={
                "city": "Pune",
                "property_type": "Apartment",
                "built_up_area_sqm": 80,
                "condition": "Average",
            },
        )
        self.assertEqual(valuation.status_code, 200)
        self.assertEqual(valuation.json()["estimate_status"], "NEEDS_LOCAL_REFERENCE_RATE")
        self.assertIsNone(valuation.json()["estimated_value_range_inr"])

        with_reference = self.client.post(
            "/api/property-valuation",
            json={
                "city": "Pune",
                "property_type": "Apartment",
                "built_up_area_sqm": 80,
                "condition": "Average",
                "reference_price_per_sqm_inr": 100_000,
                "reference_monthly_rent_inr": 25_000,
                "investment_cost_inr": 8_000_000,
            },
        )
        self.assertEqual(with_reference.status_code, 200)
        self.assertEqual(with_reference.json()["currency"], "INR")
        self.assertIsNotNone(with_reference.json()["gross_rental_yield_percent_range"])

    def test_input_validation_rejects_invalid_plans_and_blank_chat(self):
        invalid_plan = self.client.post(
            "/api/project-plan",
            json={"project_type": "Home", "built_up_area_sqm": 0, "floors": 1},
        )
        blank_chat = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(invalid_plan.status_code, 422)
        self.assertEqual(blank_chat.status_code, 422)

    def test_weather_without_observations_does_not_call_ai(self):
        with patch("main.generate_structured", new=AsyncMock()) as generate:
            response = self.client.post(
                "/api/weather-advisory",
                json={"activity": "Exterior concrete pour", "location": "Pune"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendation"], "INSUFFICIENT INFORMATION")
        self.assertIn("not independently verified", response.json()["source_label"])
        generate.assert_not_awaited()

    def test_chat_daily_and_weather_use_submitted_context_and_validated_outputs(self):
        with patch(
            "main.generate_structured",
            new=AsyncMock(return_value=ChatResponse(reply="Use the project specification.", caveats=[])),
        ) as generate:
            chat = self.client.post(
                "/api/chat",
                json={
                    "message": "What should I check before concrete placement?",
                    "history": [{"role": "user", "content": "We are on the foundation stage."}],
                },
            )
        self.assertEqual(chat.status_code, 200)
        self.assertEqual(chat.json()["reply"], "Use the project specification.")
        self.assertIn("foundation stage", generate.await_args.args[0])

        daily_output = DailySiteResponse(
            summary="Two tasks are planned.",
            reported_progress=["User reported excavation complete."],
            pending_tasks=["Check formwork."],
        )
        with patch("main.generate_structured", new=AsyncMock(return_value=daily_output)) as generate:
            daily = self.client.post(
                "/api/daily-site-assistant",
                json={
                    "site_update": "Excavation completed on the north side.",
                    "planned_activities": ["Formwork inspection"],
                },
            )
        self.assertEqual(daily.status_code, 200)
        self.assertEqual(daily.json()["reported_progress"], ["User reported excavation complete."])
        self.assertIn("Excavation completed", generate.await_args.args[0])

        weather_output = WeatherResponse(
            recommendation="INSUFFICIENT INFORMATION",
            explanation="Activity-specific thresholds were not provided.",
            limitations=["Conditions are user-reported and unverified."],
        )
        with patch("main.generate_structured", new=AsyncMock(return_value=weather_output)):
            weather = self.client.post(
                "/api/weather-advisory",
                json={
                    "activity": "Exterior concrete pour",
                    "condition_description": "Light rain reported by site team",
                    "precipitation_mm_per_hour": 1.5,
                },
            )
        self.assertEqual(weather.status_code, 200)
        self.assertEqual(weather.json()["recommendation"], "INSUFFICIENT INFORMATION")
        self.assertEqual(len(weather.json()["conditions_used"]), 2)


class AIServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_json_is_rejected(self):
        with patch("ai_service._generate_content", return_value="not a JSON response"):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 502)

    async def test_valid_json_with_invalid_schema_is_rejected(self):
        invalid_schema = '{"summary":"Report","overall_risk":"Critical"}'
        with patch("ai_service._generate_content", return_value=invalid_schema):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 502)

    async def test_missing_api_key_is_a_configuration_error(self):
        with patch("os.getenv", return_value=None):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("not configured", caught.exception.detail)

    async def test_authentication_error_is_not_retried(self):
        auth_error = ClientError(401, {"error": {"status": "UNAUTHENTICATED"}}, None)
        with (
            patch("ai_service.MAX_AI_RETRIES", 3),
            patch("ai_service._generate_content", side_effect=auth_error) as generate,
        ):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("credentials", caught.exception.detail)
        self.assertEqual(generate.call_count, 1)

    async def test_transient_httpx_timeout_is_retried_then_succeeds(self):
        valid_response = '{"summary":"Visible site","overall_risk":"Uncertain","hazards":[]}'
        with (
            patch("ai_service.MAX_AI_RETRIES", 1),
            patch("ai_service.asyncio.sleep", new=AsyncMock()),
            patch(
                "ai_service._generate_content",
                side_effect=[httpx.ConnectTimeout("TLS timeout"), valid_response],
            ) as generate,
        ):
            result = await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(result.summary, "Visible site")
        self.assertEqual(generate.call_count, 2)

    async def test_exhausted_httpx_timeouts_return_504_after_bounded_attempts(self):
        with (
            patch("ai_service.MAX_AI_RETRIES", 2),
            patch("ai_service.asyncio.sleep", new=AsyncMock()),
            patch(
                "ai_service._generate_content",
                side_effect=httpx.ConnectTimeout("TLS handshake timed out"),
            ) as generate,
        ):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 504)
        self.assertIn("timed out", caught.exception.detail)
        self.assertEqual(generate.call_count, 3)

    async def test_quota_error_is_distinct_and_not_retried(self):
        quota_error = ClientError(
            429,
            {"error": {"status": "RESOURCE_EXHAUSTED"}},
            None,
        )
        with (
            patch("ai_service.MAX_AI_RETRIES", 3),
            patch("ai_service._generate_content", side_effect=quota_error) as generate,
        ):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 429)
        self.assertIn("quota limit", caught.exception.detail)
        self.assertEqual(generate.call_count, 1)

    async def test_upstream_error_retries_a_bounded_number_of_times(self):
        upstream_error = ServerError(503, {"error": {"status": "UNAVAILABLE"}}, None)
        with (
            patch("ai_service.MAX_AI_RETRIES", 1),
            patch("ai_service.asyncio.sleep", new=AsyncMock()),
            patch("ai_service._generate_content", side_effect=upstream_error) as generate,
        ):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(generate.call_count, 2)


if __name__ == "__main__":
    unittest.main()
