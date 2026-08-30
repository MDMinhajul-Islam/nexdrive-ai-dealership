"""Tests for the server-side Retell Web SDK bridge."""

import asyncio
import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import retell as retell_routes
from app.schemas.retell import RetellWebCallRequest, RetellWebCallResponse
from app.services import retell as retell_service
from app.services.retell import (
    RetellConfigurationError,
    RetellInvalidResponseError,
    RetellUnavailableError,
    RetellUpstreamRequestError,
    create_web_call,
)
from app.utils.config import Settings


REQUEST_BODY = {
    "customer_id": "CUST-000005",
    "assigned_salesperson": "SP-001",
}
TEST_API_KEY = "test-retell-secret"


def _settings(api_key: str = TEST_API_KEY, agent_id: str = "agent-test") -> Settings:
    return Settings(retell_api_key=api_key, retell_agent_id=agent_id)


def _request() -> RetellWebCallRequest:
    return RetellWebCallRequest(**REQUEST_BODY)


def test_create_web_call_sends_trusted_configuration_and_dynamic_variables():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={"access_token": "temporary-token", "call_id": "call-123"},
        )

    response = asyncio.run(
        create_web_call(
            _request(),
            settings=_settings(),
            current_date=date(2026, 8, 30),
            transport=httpx.MockTransport(handler),
        )
    )

    assert response == RetellWebCallResponse(
        access_token="temporary-token", call_id="call-123"
    )
    assert captured["authorization"] == f"Bearer {TEST_API_KEY}"
    assert captured["body"] == {
        "agent_id": "agent-test",
        "retell_llm_dynamic_variables": {
            "customer_id": "CUST-000005",
            "assigned_salesperson": "SP-001",
            "current_date": "2026-08-30",
        },
    }


@pytest.mark.parametrize("status_code", [200, 201])
def test_create_web_call_accepts_valid_2xx_response(status_code):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"access_token": "temporary-token", "call_id": "call-123"},
        )

    response = asyncio.run(
        create_web_call(
            _request(),
            settings=_settings(),
            transport=httpx.MockTransport(handler),
        )
    )

    assert response.access_token == "temporary-token"
    assert response.call_id == "call-123"


def test_create_web_call_generates_current_date_server_side(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 1)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"access_token": "temporary-token", "call_id": "call-123"},
        )

    monkeypatch.setattr(retell_service, "date", FixedDate)
    asyncio.run(
        create_web_call(
            _request(),
            settings=_settings(),
            transport=httpx.MockTransport(handler),
        )
    )

    variables = captured["retell_llm_dynamic_variables"]
    assert variables["current_date"] == "2026-09-01"


def test_retell_route_returns_only_frontend_fields_and_never_api_key(monkeypatch):
    async def successful_call(_request):
        return RetellWebCallResponse(
            access_token="temporary-token", call_id="call-123"
        )

    monkeypatch.setattr(retell_routes, "create_web_call", successful_call)
    response = TestClient(app).post(
        "/api/retell/create-web-call", json=REQUEST_BODY
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "access_token": "temporary-token",
        "call_id": "call-123",
    }
    assert TEST_API_KEY not in response.text


@pytest.mark.parametrize(
    "body",
    [
        {**REQUEST_BODY, "customer_id": "bad-customer"},
        {**REQUEST_BODY, "assigned_salesperson": "bad-salesperson"},
        {"assigned_salesperson": "SP-001"},
        {"customer_id": "CUST-000005"},
    ],
)
def test_retell_route_rejects_invalid_or_missing_ids(body):
    response = TestClient(app).post("/api/retell/create-web-call", json=body)
    assert response.status_code == 422


def test_retell_route_rejects_client_owned_trusted_fields():
    client = TestClient(app)
    for field, value in (
        ("current_date", "2020-01-01"),
        ("agent_id", "attacker-agent"),
        ("retell_api_key", "attacker-key"),
    ):
        response = client.post(
            "/api/retell/create-web-call",
            json={**REQUEST_BODY, field: value},
        )
        assert response.status_code == 422


@pytest.mark.parametrize(
    ("api_key", "agent_id"),
    [("", "agent-test"), (TEST_API_KEY, "")],
)
def test_missing_retell_configuration_returns_safe_503(
    monkeypatch, api_key, agent_id
):
    monkeypatch.setattr(
        retell_service,
        "get_settings",
        lambda: _settings(api_key=api_key, agent_id=agent_id),
    )
    response = TestClient(app).post(
        "/api/retell/create-web-call", json=REQUEST_BODY
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Retell service is not configured"}
    assert TEST_API_KEY not in response.text


def test_retell_timeout_and_network_failures_are_sanitized():
    for error in (
        httpx.ReadTimeout("private timeout detail"),
        httpx.ConnectError("private network detail"),
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            error.request = request
            raise error

        with pytest.raises(RetellUnavailableError) as caught:
            asyncio.run(
                create_web_call(
                    _request(),
                    settings=_settings(),
                    transport=httpx.MockTransport(handler),
                )
            )
        assert "private" not in str(caught.value)


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (400, RetellUpstreamRequestError),
        (401, RetellUpstreamRequestError),
        (422, RetellUpstreamRequestError),
        (500, RetellUnavailableError),
    ],
)
def test_retell_non_2xx_responses_are_sanitized(status_code, expected_exception):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="private upstream details")

    with pytest.raises(expected_exception) as caught:
        asyncio.run(
            create_web_call(
                _request(),
                settings=_settings(),
                transport=httpx.MockTransport(handler),
            )
        )
    assert caught.value.upstream_status == status_code
    assert "private upstream details" not in str(caught.value)


def test_retell_non_2xx_logs_only_allowlisted_safe_diagnostics(caplog):
    upstream_access_token = "upstream-access-token-must-not-log"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={
            "message": "Authentication failed",
            "code": "invalid_api_key",
            "access_token": upstream_access_token,
            "authorization": f"Bearer {TEST_API_KEY}",
            "headers": {"Authorization": f"Bearer {TEST_API_KEY}"},
        })

    caplog.set_level("WARNING", logger="app.services.retell")
    with pytest.raises(RetellUpstreamRequestError):
        asyncio.run(
            create_web_call(
                _request(),
                settings=_settings(),
                transport=httpx.MockTransport(handler),
            )
        )

    assert "status=401" in caplog.text
    assert "code=invalid_api_key" in caplog.text
    assert "message=Authentication failed" in caplog.text
    assert TEST_API_KEY not in caplog.text
    assert upstream_access_token not in caplog.text
    assert "Authorization" not in caplog.text
    assert "access_token" not in caplog.text


def test_retell_diagnostics_redact_sensitive_selected_fields(caplog):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={
            "message": f"Authorization Bearer {TEST_API_KEY}",
            "code": "access_token_invalid",
        })

    caplog.set_level("WARNING", logger="app.services.retell")
    with pytest.raises(RetellUpstreamRequestError):
        asyncio.run(
            create_web_call(
                _request(),
                settings=_settings(),
                transport=httpx.MockTransport(handler),
            )
        )

    assert "status=422" in caplog.text
    assert "message=[redacted]" in caplog.text
    assert "code=[redacted]" in caplog.text
    assert TEST_API_KEY not in caplog.text
    assert "Bearer" not in caplog.text
    assert "access_token_invalid" not in caplog.text


@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (201, {"call_id": "call-123"}),
        (200, {"access_token": "temporary-token"}),
        (200, {}),
        (200, []),
    ],
)
def test_retell_response_missing_required_bootstrap_fields_is_rejected(
    status_code, payload
):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    with pytest.raises(RetellInvalidResponseError):
        asyncio.run(
            create_web_call(
                _request(),
                settings=_settings(),
                transport=httpx.MockTransport(handler),
            )
        )


@pytest.mark.parametrize(
    ("exception", "status_code", "detail"),
    [
        (
            RetellUpstreamRequestError("private", upstream_status=401),
            502,
            {
                "message": "Retell rejected the web call request.",
                "upstream_status": 401,
            },
        ),
        (RetellUnavailableError("private"), 503, "Retell service unavailable"),
        (
            RetellUnavailableError("private", upstream_status=500),
            503,
            {"message": "Retell service unavailable.", "upstream_status": 500},
        ),
        (
            RetellInvalidResponseError("private"),
            502,
            "Retell returned an invalid response",
        ),
    ],
)
def test_retell_route_maps_service_failures_to_safe_errors(
    monkeypatch, exception, status_code, detail
):
    async def failed_call(_request):
        raise exception

    monkeypatch.setattr(retell_routes, "create_web_call", failed_call)
    response = TestClient(app).post(
        "/api/retell/create-web-call", json=REQUEST_BODY
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert "private" not in response.text
