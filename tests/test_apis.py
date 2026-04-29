"""
Tests for utility.apis — OpenAI, Claude, and Gemini adapters.

All tests use unittest.mock so no real API keys or network calls are needed.

Run with:
    pytest tests/test_apis.py -v
or
    python -m pytest tests/test_apis.py -v
"""

from __future__ import annotations

import os
import sys
import types
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path when running from the repo root
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utility.apis.base import APIRequest, APIResponse, Provider
from utility.apis.errors import (
    APIConnectionError,
    APIError,
    APIKeyError,
    APIRateLimitError,
    APIResponseError,
    APIValidationError,
    handle_anthropic_error,
    handle_openai_error,
)


# ===========================================================================
# Helpers / fixtures
# ===========================================================================

def make_request(**kwargs) -> APIRequest:
    defaults = dict(
        system_query="You are a helpful assistant.",
        user_query="What is 2 + 2?",
        model="test-model",
        max_tokens=256,
        temperature=0.5,
        metadata={"test": True},
    )
    defaults.update(kwargs)
    return APIRequest(**defaults)


# ===========================================================================
# base.py — APIRequest / APIResponse
# ===========================================================================

class TestAPIRequest:
    def test_defaults(self):
        req = APIRequest(
            system_query="sys",
            user_query="usr",
            model="m",
        )
        assert req.max_tokens == 1024
        assert req.temperature == 0.7
        assert isinstance(req.metadata, dict)
        assert uuid.UUID(req.request_id)  # valid UUID

    def test_to_dict_roundtrip(self):
        req = make_request()
        d = req.to_dict()
        assert d["system_query"] == req.system_query
        assert d["user_query"] == req.user_query
        assert d["model"] == req.model
        assert d["request_id"] == req.request_id
        assert d["metadata"] == req.metadata

    def test_unique_request_ids(self):
        r1 = make_request()
        r2 = make_request()
        assert r1.request_id != r2.request_id


class TestAPIResponse:
    def test_error_response_factory(self):
        req = make_request()
        resp = APIResponse.error_response(req, Provider.OPENAI, "boom")
        assert resp.success is False
        assert resp.error == "boom"
        assert resp.content == ""
        assert resp.provider == Provider.OPENAI
        assert resp.request_id == req.request_id
        assert resp.metadata == req.metadata

    def test_to_dict_keys(self):
        req = make_request()
        resp = APIResponse(
            content="hello",
            model="gpt-4o-mini",
            provider=Provider.OPENAI,
            request_id=req.request_id,
            success=True,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            metadata={"k": "v"},
            latency_ms=123.4,
        )
        d = resp.to_dict()
        for key in ("request_id", "provider", "model", "success", "content",
                    "error", "usage", "metadata", "latency_ms"):
            assert key in d

    def test_provider_value_in_dict(self):
        req = make_request()
        resp = APIResponse.error_response(req, Provider.CLAUDE, "err")
        assert resp.to_dict()["provider"] == "claude"


# ===========================================================================
# errors.py
# ===========================================================================

class TestErrors:
    def test_base_error(self):
        e = APIError("msg", provider="openai", status_code=500)
        assert e.provider == "openai"
        assert e.status_code == 500
        assert "openai" in repr(e)

    def test_subclass_hierarchy(self):
        for cls in (APIKeyError, APIRateLimitError, APIConnectionError,
                    APIResponseError, APIValidationError):
            assert issubclass(cls, APIError)

    def test_handle_openai_error_no_package(self):
        """When openai is not importable, falls back to base APIError."""
        with patch.dict(sys.modules, {"openai": None}):
            err = handle_openai_error(ValueError("generic"), "openai")
        assert isinstance(err, APIError)

    def test_handle_anthropic_error_no_package(self):
        with patch.dict(sys.modules, {"anthropic": None}):
            err = handle_anthropic_error(ValueError("generic"), "claude")
        assert isinstance(err, APIError)


# ===========================================================================
# openai_api.py
# ===========================================================================

def _make_openai_response(content: str = "four", model: str = "gpt-4o-mini"):
    """Build a minimal mock that mimics openai.types.chat.ChatCompletion."""
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15

    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = model
    resp.model_dump.return_value = {"choices": []}
    return resp


class TestOpenAIAPI:
    def _patch_client(self, mock_response):
        """Context manager that injects a fake openai client."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        import utility.apis.openai_api as mod
        return patch.object(mod, "_client", mock_client)

    def test_single_request_success(self):
        import utility.apis.openai_api as mod

        req = make_request(model="gpt-4o-mini")
        mock_resp = _make_openai_response("four")

        with self._patch_client(mock_resp):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
                resp = mod.single_request(req)

        assert resp.success is True
        assert resp.content == "four"
        assert resp.provider == Provider.OPENAI
        assert resp.request_id == req.request_id
        assert resp.usage["total_tokens"] == 15
        assert resp.metadata["finish_reason"] == "stop"

    def test_single_request_error_captured(self):
        import utility.apis.openai_api as mod

        req = make_request(model="gpt-4o-mini")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("network error")

        with patch.object(mod, "_client", mock_client):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
                resp = mod.single_request(req)

        assert resp.success is False
        assert "network error" in resp.error

    def test_batch_request_preserves_order(self):
        import utility.apis.openai_api as mod

        requests = [make_request(user_query=f"q{i}") for i in range(4)]
        mock_client = MagicMock()

        def _side_effect(**kwargs):
            user_msg = kwargs["messages"][1]["content"]
            return _make_openai_response(content=f"ans:{user_msg}")

        mock_client.chat.completions.create.side_effect = _side_effect

        with patch.object(mod, "_client", mock_client):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
                responses = mod.batch_request(requests, max_workers=2)

        assert len(responses) == 4
        for i, resp in enumerate(responses):
            assert resp.request_id == requests[i].request_id
            assert f"ans:q{i}" == resp.content

    def test_batch_request_empty(self):
        import utility.apis.openai_api as mod
        assert mod.batch_request([]) == []

    def test_missing_api_key_raises(self):
        import utility.apis.openai_api as mod

        # Reset cached client
        original = mod._client
        mod._client = None
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        try:
            with patch.dict(os.environ, env, clear=True):
                with patch.dict(sys.modules, {"openai": MagicMock()}):
                    with pytest.raises(APIKeyError):
                        mod._get_client()
        finally:
            mod._client = original


# ===========================================================================
# claude_api.py
# ===========================================================================

def _make_anthropic_response(content: str = "four", model: str = "claude-haiku-4-5"):
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5

    block = MagicMock()
    block.text = content

    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
    resp.model = model
    resp.stop_reason = "end_turn"
    resp.model_dump.return_value = {}
    return resp


class TestClaudeAPI:
    def _patch_client(self, mock_response):
        import utility.apis.claude_api as mod
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        return patch.object(mod, "_client", mock_client)

    def test_single_request_success(self):
        import utility.apis.claude_api as mod

        req = make_request(model="claude-haiku-4-5-20251001")
        mock_resp = _make_anthropic_response("four")

        with self._patch_client(mock_resp):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-test"}):
                resp = mod.single_request(req)

        assert resp.success is True
        assert resp.content == "four"
        assert resp.provider == Provider.CLAUDE
        assert resp.usage["prompt_tokens"] == 10
        assert resp.usage["completion_tokens"] == 5
        assert resp.usage["total_tokens"] == 15
        assert resp.metadata["stop_reason"] == "end_turn"

    def test_single_request_error_captured(self):
        import utility.apis.claude_api as mod

        req = make_request()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("timeout")

        with patch.object(mod, "_client", mock_client):
            resp = mod.single_request(req)

        assert resp.success is False
        assert "timeout" in resp.error

    def test_batch_request_preserves_order(self):
        import utility.apis.claude_api as mod

        requests = [make_request(user_query=f"q{i}") for i in range(3)]
        mock_client = MagicMock()

        def _side_effect(**kwargs):
            user_content = kwargs["messages"][0]["content"]
            return _make_anthropic_response(content=f"ans:{user_content}")

        mock_client.messages.create.side_effect = _side_effect

        with patch.object(mod, "_client", mock_client):
            responses = mod.batch_request(requests, max_workers=2)

        assert len(responses) == 3
        for i, resp in enumerate(responses):
            assert resp.request_id == requests[i].request_id

    def test_batch_request_empty(self):
        import utility.apis.claude_api as mod
        assert mod.batch_request([]) == []

    def test_missing_api_key_raises(self):
        import utility.apis.claude_api as mod

        original = mod._client
        mod._client = None
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        try:
            with patch.dict(os.environ, env, clear=True):
                with patch.dict(sys.modules, {"anthropic": MagicMock()}):
                    with pytest.raises(APIKeyError):
                        mod._get_client()
        finally:
            mod._client = original


# ===========================================================================
# gemini_api.py
# ===========================================================================

def _make_genai_mock(content: str = "four"):
    """Build a fake google.generativeai module + response."""
    genai = MagicMock()

    usage = MagicMock()
    usage.prompt_token_count = 10
    usage.candidates_token_count = 5

    candidate = MagicMock()
    candidate.finish_reason = "STOP"
    candidate.safety_ratings = []

    response = MagicMock()
    response.text = content
    response.usage_metadata = usage
    response.candidates = [candidate]

    def _to_dict(_self):
        return {"text": content}

    type(response).to_dict = _to_dict

    model_instance = MagicMock()
    model_instance.generate_content.return_value = response
    genai.GenerativeModel.return_value = model_instance

    return genai, response


class TestGeminiAPI:
    def test_single_request_success(self):
        import utility.apis.gemini_api as mod

        req = make_request(model="gemini-2.0-flash")
        genai_mock, _ = _make_genai_mock("four")

        with patch("utility.apis.gemini_api._get_genai", return_value=genai_mock):
            with patch("utility.apis.gemini_api._configure_genai"):
                resp = mod.single_request(req)

        assert resp.success is True
        assert resp.content == "four"
        assert resp.provider == Provider.GEMINI
        assert resp.usage["prompt_tokens"] == 10
        assert resp.usage["completion_tokens"] == 5

    def test_single_request_error_captured(self):
        import utility.apis.gemini_api as mod

        req = make_request()
        genai_mock = MagicMock()
        genai_mock.GenerativeModel.side_effect = RuntimeError("api down")

        with patch("utility.apis.gemini_api._get_genai", return_value=genai_mock):
            with patch("utility.apis.gemini_api._configure_genai"):
                resp = mod.single_request(req)

        assert resp.success is False
        assert "api down" in resp.error

    def test_single_request_blocked_response(self):
        """response.text raises ValueError when content is blocked."""
        import utility.apis.gemini_api as mod

        req = make_request()
        genai_mock, response_mock = _make_genai_mock()
        # Simulate a blocked response
        type(response_mock).text = property(
            fget=lambda _: (_ for _ in ()).throw(ValueError("blocked"))
        )

        with patch("utility.apis.gemini_api._get_genai", return_value=genai_mock):
            with patch("utility.apis.gemini_api._configure_genai"):
                resp = mod.single_request(req)

        assert resp.success is True
        assert resp.content == ""  # empty on blocked

    def test_batch_request_preserves_order(self):
        import utility.apis.gemini_api as mod

        requests = [make_request(user_query=f"q{i}") for i in range(3)]

        call_count = [0]

        def _side_effect(user_query):
            idx = call_count[0]
            call_count[0] += 1
            genai_mock, response = _make_genai_mock(content=f"ans:{user_query}")
            return response

        genai_mock = MagicMock()
        model_instance = MagicMock()
        model_instance.generate_content.side_effect = _side_effect
        genai_mock.GenerativeModel.return_value = model_instance

        with patch("utility.apis.gemini_api._get_genai", return_value=genai_mock):
            with patch("utility.apis.gemini_api._configure_genai"):
                responses = mod.batch_request(requests, max_workers=2)

        assert len(responses) == 3
        for i, resp in enumerate(responses):
            assert resp.request_id == requests[i].request_id

    def test_batch_request_empty(self):
        import utility.apis.gemini_api as mod
        assert mod.batch_request([]) == []

    def test_missing_api_key_raises(self):
        import utility.apis.gemini_api as mod

        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        genai_mock = MagicMock()

        with patch.dict(os.environ, env, clear=True):
            with patch("utility.apis.gemini_api._get_genai", return_value=genai_mock):
                with pytest.raises(APIKeyError):
                    mod._configure_genai(genai_mock)


# ===========================================================================
# Integration-style: __init__.py public surface
# ===========================================================================

class TestPackagePublicSurface:
    def test_imports(self):
        from utility.apis import (  # noqa: F401
            APIConnectionError,
            APIError,
            APIKeyError,
            APIRateLimitError,
            APIRequest,
            APIResponse,
            APIResponseError,
            APIValidationError,
            Provider,
            claude_api,
            gemini_api,
            openai_api,
        )

    def test_provider_enum_values(self):
        assert Provider.OPENAI.value == "openai"
        assert Provider.CLAUDE.value == "claude"
        assert Provider.GEMINI.value == "gemini"

    def test_metadata_round_trip(self):
        """Custom metadata set on request must appear in response."""
        import utility.apis.openai_api as mod

        req = make_request(metadata={"job_id": "abc123", "priority": 1})
        mock_resp = _make_openai_response("answer")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch.object(mod, "_client", mock_client):
            resp = mod.single_request(req)

        assert resp.metadata["job_id"] == "abc123"
        assert resp.metadata["priority"] == 1

    def test_request_id_echoed_in_response(self):
        import utility.apis.claude_api as mod

        req = make_request()
        fixed_id = "fixed-id-1234"
        req.request_id = fixed_id
        mock_resp = _make_anthropic_response()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp

        with patch.object(mod, "_client", mock_client):
            resp = mod.single_request(req)

        assert resp.request_id == fixed_id
