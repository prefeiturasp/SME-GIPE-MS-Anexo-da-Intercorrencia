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
