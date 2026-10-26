import struct
import unittest
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

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
            hazards=[],
            ppe_concerns=[],
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

    def test_health_and_preflight_return_cors_headers_for_configured_frontends(self):
        allowed_origins = [
            "https://multimodal-construction-intelligence-platform-e9ynp62dx.vercel.app",
            "https://multimodal-construction-intelligenc-two.vercel.app",
            "http://localhost:5173",
        ]
        for origin in allowed_origins:
            with self.subTest(origin=origin):
                health = self.client.get("/health", headers={"Origin": origin})
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.headers.get("access-control-allow-origin"), origin)
                self.assertEqual(health.headers.get("access-control-allow-credentials"), "true")

                preflight = self.client.options(
                    "/api/project-plan",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(preflight.status_code, 200)
                self.assertEqual(preflight.headers.get("access-control-allow-origin"), origin)
                self.assertIn("POST", preflight.headers.get("access-control-allow-methods", ""))
                self.assertEqual(preflight.headers.get("access-control-allow-credentials"), "true")

    def test_cors_rejects_unlisted_origins(self):
        response = self.client.get(
            "/health",
            headers={"Origin": "https://unlisted.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

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
        self.assertEqual(plan_data["estimated_duration_days"], 200)
        self.assertEqual(sum(item["duration_days"] for item in plan_data["cost_breakdown"]), plan_data["estimated_duration_days"])
        self.assertEqual(len(plan_data["risks"]), 3)
        self.assertEqual(plan_data["cost_breakdown"][0]["depends_on"], [])
        self.assertIn("Design, approvals, and mobilization", plan_data["cost_breakdown"][1]["depends_on"])

        small_budget_plan = self.client.post(
            "/api/project-plan",
            json={
                "project_type": "Residential",
                "built_up_area_sqm": 0.1,
                "budget_inr": 0.01,
                "target_timeline_days": 5,
            },
        )
        self.assertEqual(small_budget_plan.status_code, 200)
        small_budget_data = small_budget_plan.json()
        self.assertAlmostEqual(
            sum(item["estimated_cost_inr"] for item in small_budget_data["cost_breakdown"]),
            small_budget_data["estimated_cost_inr"],
        )
        self.assertEqual(
            sum(item["duration_days"] for item in small_budget_data["cost_breakdown"]),
            small_budget_data["estimated_duration_days"],
        )

        valuation = self.client.post(
            "/api/property-valuation",
            json={
                "city": "Pune",
                "property_type": "Apartment",
                "area_sqm": 80,
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

        plot = self.client.post(
            "/api/property-valuation",
            json={
                "city": "Pune",
                "property_type": "Plot",
                "area_sqm": 100,
                "condition": "Good",
                "building_age_years": 50,
                "reference_price_per_sqm_inr": 20_000,
            },
        )
        self.assertEqual(plot.status_code, 200)
        self.assertIn("not applied to a plot", plot.json()["adjustment_breakdown"][2])

    def test_input_validation_rejects_invalid_plans_and_blank_chat(self):
        invalid_plan = self.client.post(
            "/api/project-plan",
            json={"project_type": "Home", "built_up_area_sqm": 0, "floors": 1},
        )
        blank_chat = self.client.post("/api/chat", json={"message": "   "})
        unsupported_plan = self.client.post(
            "/api/project-plan",
            json={"project_type": "Unspecified", "built_up_area_sqm": 50, "floors": 1},
        )
        blank_list_item = self.client.post(
            "/api/daily-site-assistant",
            json={"site_update": "Reported progress.", "planned_activities": [""]},
        )
        self.assertEqual(invalid_plan.status_code, 422)
        self.assertEqual(unsupported_plan.status_code, 422)
        self.assertEqual(blank_list_item.status_code, 422)
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
            risks=[],
            suggested_next_actions=["Check formwork."],
            coordination_points=[],
            limitations=["Summary uses the user-provided update only."],
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
            risks=[],
            precautions=["Check official alerts and site procedures."],
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
    async def test_sdk_configuration_uses_the_configured_gemini_model_and_closes_client(self):
        client = MagicMock()
        client.models.generate_content.return_value.text = (
            '{"summary":"Visible site","overall_risk":"Uncertain","hazards":[],'
            '"ppe_concerns":[],"limitations":["Image coverage is limited."]}'
        )
        with patch("ai_service.genai.Client", return_value=client) as create_client:
            response = ai_service._generate_content("test-key", "task", None, None)

        self.assertIn('"summary":"Visible site"', response)
        create_client.assert_called_once()
        options = create_client.call_args.kwargs["http_options"]
        self.assertEqual(options["timeout"], 60_000)
        self.assertEqual(options["retry_options"]["attempts"], 1)
        generation = client.models.generate_content.call_args.kwargs
        self.assertEqual(generation["model"], "gemini-3.8-flash")
        self.assertIn("untrusted data", generation["config"].system_instruction)
        client.close.assert_called_once()

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

    async def test_incomplete_but_parseable_json_is_rejected_instead_of_defaulted(self):
        with patch("ai_service._generate_content", return_value='{"overall_risk":"Uncertain"}'):
            with self.assertRaises(AIServiceError) as caught:
                await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn("required data format", caught.exception.detail)

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
        valid_response = (
            '{"summary":"Visible site","overall_risk":"Uncertain","hazards":[],'
            '"ppe_concerns":[],"limitations":["Image coverage is limited."]}'
        )
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

    async def test_retry_backoff_is_exponential_jittered_and_bounded(self):
        valid_response = (
            '{"summary":"Visible site","overall_risk":"Uncertain","hazards":[],'
            '"ppe_concerns":[],"limitations":["Image coverage is limited."]}'
        )
        with (
            patch("ai_service.MAX_AI_RETRIES", 3),
            patch("ai_service.random.uniform", return_value=0.25) as jitter,
            patch("ai_service.asyncio.sleep", new=AsyncMock()) as sleep,
            patch(
                "ai_service._generate_content",
                side_effect=[httpx.ConnectTimeout("TLS timeout")] * 3 + [valid_response],
            ) as generate,
        ):
            await ai_service.generate_structured("prompt", SafetyAnalysis)
        self.assertEqual(generate.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [1.25, 2.25, 4.25])
        self.assertEqual(jitter.call_count, 3)

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
