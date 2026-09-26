from httpx import AsyncClient


async def test_http_exception_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "unauthorized", "message": "Not authenticated", "fields": None}
    }


async def test_validation_error_uses_error_envelope_with_fields(client: AsyncClient) -> None:
    response = await client.post("/auth/login", json={"email": "missing-password@example.com"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "password" in body["error"]["fields"]
