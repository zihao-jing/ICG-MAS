"""
utility.apis — Unified LLM API adapters for OpenAI, Claude, and Gemini.

Quick start
-----------
    from utility.apis import APIRequest, APIResponse
    from utility.apis import openai_api, claude_api, gemini_api

    req = APIRequest(
        system_query="You are a helpful assistant.",
        user_query="What is the capital of France?",
        model="gpt-4o-mini",
    )
    resp = openai_api.single_request(req)
    print(resp.content)

Environment variables
---------------------
    OPENAI_API_KEY    — required by openai_api
    ANTHROPIC_API_KEY — required by claude_api
    GEMINI_API_KEY    — required by gemini_api

Error handling
--------------
    from utility.apis.errors import (
        APIError,
        APIKeyError,
        APIRateLimitError,
        APIConnectionError,
        APIResponseError,
        APIValidationError,
    )
"""

from .base import APIRequest, APIResponse, Provider
from .errors import (
    APIConnectionError,
    APIError,
    APIKeyError,
    APIRateLimitError,
    APIResponseError,
    APIValidationError,
)
from . import claude_api, gemini_api, openai_api, openrouter_api

__all__ = [
    # Data structures
    "APIRequest",
    "APIResponse",
    "Provider",
    # Errors
    "APIError",
    "APIKeyError",
    "APIRateLimitError",
    "APIConnectionError",
    "APIResponseError",
    "APIValidationError",
    # Provider modules
    "openai_api",
    "claude_api",
    "gemini_api",
    "openrouter_api",
]
