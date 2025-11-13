def test_swagger_ui_available(client):
    resp = client.get("/api-anexos/v1/docs/")
    assert resp.status_code in (200, 302)  # Swagger serve/redirect