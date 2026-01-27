import logging

import pytest
from django.test.client import RequestFactory

from anexos.permissions import IsInternalServiceRequest


@pytest.fixture
def rf():
    return RequestFactory()


def test_sem_token_configurado_retorna_false(settings, rf, caplog):
    settings.INTERNAL_SERVICE_TOKEN = None

    request = rf.get("/qualquer", HTTP_X_INTERNAL_SERVICE_TOKEN="abc")

    with caplog.at_level(logging.WARNING):
        assert IsInternalServiceRequest().has_permission(request, None) is False

    assert "INTERNAL_SERVICE_TOKEN não configurado" in caplog.text


def test_token_invalido_retorna_false(settings, rf, caplog):
    settings.INTERNAL_SERVICE_TOKEN = "segredo"

    request = rf.get(
        "/qualquer",
        HTTP_X_INTERNAL_SERVICE_TOKEN="errado",
        REMOTE_ADDR="10.0.0.1",
    )

    with caplog.at_level(logging.WARNING):
        assert IsInternalServiceRequest().has_permission(request, None) is False

    assert "Token inválido" in caplog.text
    assert "10.0.0.1" in caplog.text


def test_token_valido_retorna_true(settings, rf, caplog):
    settings.INTERNAL_SERVICE_TOKEN = "segredo"

    request = rf.get(
        "/qualquer",
        HTTP_X_INTERNAL_SERVICE_TOKEN="segredo",
        REMOTE_ADDR="10.0.0.2",
    )

    with caplog.at_level(logging.DEBUG):
        assert IsInternalServiceRequest().has_permission(request, None) is True

    assert "Token válido" in caplog.text
