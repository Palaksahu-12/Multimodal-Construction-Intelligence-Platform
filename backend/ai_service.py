import asyncio
import json
import logging
import random
from typing import TypeVar

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)
MAX_AI_RETRIES = 3
AI_REQUEST_TIMEOUT_MS = 60_000


class AIServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _provider_status(exc: Exception) -> int | None:
    status_code = getattr(exc, "code", None)
    if isinstance(status_code, int):
        return status_code
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status
    return None


def _provider_is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, TimeoutError, ConnectionError, OSError)):
        return True
    status_code = _provider_status(exc)
    return isinstance(exc, ServerError) and status_code in {500, 502, 503, 504}


def _provider_error(exc: Exception) -> AIServiceError:
    status_code = _provider_status(exc)
    if status_code == 401 or status_code == 403:
        return AIServiceError(
            503,
            "Gemini rejected the configured credentials or project access. Check server-side API configuration.",
        )
    if status_code == 429:
        return AIServiceError(
            429,
            "Gemini rate or quota limit reached. Please wait for the provider limit to reset and try again.",
        )
    if status_code == 504:
        return AIServiceError(
            504,
            "The AI provider timed out after several attempts. Please try again shortly.",
        )
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return AIServiceError(
            504,
            "The AI service connection timed out after several attempts. Please try again shortly.",
        )
    if isinstance(exc, (httpx.TransportError, ConnectionError, OSError)):
        return AIServiceError(
            503,
            "The AI service could not be reached after several attempts. Please check the network and try again.",
        )
    if status_code in {500, 502, 503}:
        return AIServiceError(
            503,
            "The AI service is temporarily unavailable. Please retry in a moment.",
        )
    if isinstance(exc, APIError):
        return AIServiceError(
            502,
            "Gemini rejected the request. Check the image, request data, and configured model access.",
        )
    return AIServiceError(502, "AI generation failed. Please try again later.")


def _parse_json_response(text: str) -> object:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].strip()

    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character in "{[":
            parsed, _ = decoder.raw_decode(cleaned[index:])
            return parsed
    raise ValueError("No JSON object found in Gemini response.")


def _generate_content(
    api_key: str,
    prompt: str,
    image_bytes: bytes | None,
    mime_type: str | None,
) -> str:
    client = genai.Client(
        api_key=api_key,
        http_options={
            "timeout": AI_REQUEST_TIMEOUT_MS,
            "retry_options": {
                "attempts": 1,
                "initial_delay": 1.0,
                "max_delay": 4.0,
                "exp_base": 2.0,
                "jitter": 0.5,
                "http_status_codes": [500, 502, 503, 504],
            },
        },
    )
    contents: list[object] = [prompt]
    if image_bytes is not None and mime_type is not None:
        contents.insert(0, types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=2_048,
        ),
    )
    if not getattr(response, "text", None):
        raise ValueError("Gemini returned an empty response.")
    return response.text


async def generate_structured(
    prompt: str,
    response_model: type[ModelT],
    image_bytes: bytes | None = None,
    mime_type: str | None = None,
) -> ModelT:
    from os import getenv

    api_key = getenv("GEMINI_API_KEY")
    if not api_key:
        raise AIServiceError(503, "Gemini API key is not configured. Set GEMINI_API_KEY on the backend.")

    for attempt in range(MAX_AI_RETRIES + 1):
        try:
            response_text = await asyncio.to_thread(
                _generate_content,
                api_key,
                prompt,
                image_bytes,
                mime_type,
            )
            try:
                parsed = _parse_json_response(response_text)
                return response_model.model_validate(parsed)
            except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
                logger.warning("Gemini returned invalid structured output for %s.", response_model.__name__)
                raise AIServiceError(
                    502,
                    "The AI response did not match the required data format. Please try again.",
                ) from exc
        except AIServiceError:
            raise
        except Exception as exc:
            retryable = _provider_is_retryable(exc)
            status_code = _provider_status(exc)
            if retryable and attempt < MAX_AI_RETRIES:
                delay = min(2**attempt, 4) + random.uniform(0.1, 0.8)
                logger.warning(
                    "Gemini transient failure (%s); retrying attempt %d of %d after %.2fs.",
                    status_code or type(exc).__name__,
                    attempt + 2,
                    MAX_AI_RETRIES + 1,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            if isinstance(exc, (APIError, httpx.HTTPError, TimeoutError, ConnectionError, OSError)):
                raise _provider_error(exc) from exc
            logger.exception("Unexpected error during Gemini structured generation.")
            raise AIServiceError(502, "AI generation failed unexpectedly. Please try again later.") from exc

    raise AIServiceError(503, "The AI service could not complete the request. Please try again later.")
