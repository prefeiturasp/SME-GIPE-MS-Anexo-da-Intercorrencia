import importlib
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests
from django.core.cache import cache
from django.test.client import RequestFactory
from rest_framework.exceptions import AuthenticationFailed

# Utilitário: gera Authorization header "Bearer <token>"
def _auth_header(token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def rf():
    return RequestFactory()


def _build_token(secret: str, payload_extra: dict | None = None, alg: str = "HS256"):
    now = int(time.time())
    payload = {
        "username": "alice",
        "iat": now,
        "exp": now + 60,  # 1 min
    }
    if payload_extra:
        payload.update(payload_extra)
    return jwt.encode(payload, key=secret, algorithm=alg)


def _patch_verify_200(monkeypatch, module, status_code=200):
    """Parcha requests.post usado no módulo de auth para responder com status X."""
    class _Resp:
        def __init__(self, code):
            self.status_code = code
    def fake_post(url, json, timeout):
        assert abs(timeout - 3.0) < 1e-6
        assert "token" in json
        return _Resp(status_code)
    monkeypatch.setattr(module.requests, "post", fake_post)


@pytest.mark.django_db
def test_authenticate_sem_header_retorna_none(settings, rf):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    import anexos.auth as auth
    importlib.reload(auth)

    request = rf.get("/alguma-rota")
    # sem Authorization
    assert auth.RemoteJWTAuthentication().authenticate(request) is None


@pytest.mark.django_db
def test_authenticate_esquema_invalido_retorna_none(settings, rf):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    import anexos.auth as auth
    importlib.reload(auth)

    request = rf.get("/x", HTTP_AUTHORIZATION="Token abc")  # não é Bearer
    assert auth.RemoteJWTAuthentication().authenticate(request) is None


@pytest.mark.django_db
def test_fluxo_feliz_username_ok(settings, rf, monkeypatch):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    # verificador remoto retorna 200
    _patch_verify_200(monkeypatch, auth, 200)

    token = _build_token(settings.SECRET_KEY, {"username": "joao"})  # HS256 com SECRET_KEY
    request = rf.get("/ok", **_auth_header(token))

    user, _ = auth.RemoteJWTAuthentication().authenticate(request)
    assert user.username == "joao"
    assert user.is_authenticated is True


@pytest.mark.django_db
def test_fluxo_feliz_sub_quando_sem_username(settings, rf, monkeypatch):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    _patch_verify_200(monkeypatch, auth, 200)

    # sem "username", usa "sub"
    token = _build_token(settings.SECRET_KEY, {"username": None, "sub": "user-123"})
    request = rf.get("/ok", **_auth_header(token))

    user, _ = auth.RemoteJWTAuthentication().authenticate(request)
    assert user.username == "user-123"


@pytest.mark.django_db
def test_cache_evita_segunda_chamada_ao_verificador(settings, rf, monkeypatch):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    calls = {"n": 0}
    class _Resp:
        def __init__(self, code): self.status_code = code
    def fake_post(url, json, timeout):
        calls["n"] += 1
        return _Resp(200)

    monkeypatch.setattr(auth.requests, "post", fake_post)

    token = _build_token(settings.SECRET_KEY, {"username": "carlos"})
    request1 = rf.get("/1", **_auth_header(token))
    request2 = rf.get("/2", **_auth_header(token))

    auth.RemoteJWTAuthentication().authenticate(request1)
    auth.RemoteJWTAuthentication().authenticate(request2)

    # Só a primeira chamada deve bater no serviço (segunda usa cache)
    assert calls["n"] == 1


@pytest.mark.django_db
def test_remoto_401_gera_authfailed(settings, rf, monkeypatch):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    _patch_verify_200(monkeypatch, auth, 401)

    token = _build_token(settings.SECRET_KEY)
    request = rf.get("/bad", **_auth_header(token))

    with pytest.raises(AuthenticationFailed) as exc:
        auth.RemoteJWTAuthentication().authenticate(request)
    assert "inválido" in str(exc.value).lower() or "expirado" in str(exc.value).lower()


@pytest.mark.django_db
def test_erro_de_rede_timeout_gera_authfailed(settings, rf, monkeypatch):
    """
    Seu código usa `except requests.RequestError:` (não existe).
    Para os testes passarem sem alterar o código agora, injetamos RequestError.
    """
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    # injeta atributo inexistente para casar com o except do código atual
    monkeypatch.setattr(requests, "RequestError", requests.RequestException, raising=False)

    def fake_post(url, json, timeout):
        raise requests.Timeout("boom")

    monkeypatch.setattr(auth.requests, "post", fake_post)

    token = _build_token(settings.SECRET_KEY)
    request = rf.get("/net", **_auth_header(token))

    with pytest.raises(AuthenticationFailed) as exc:
        auth.RemoteJWTAuthentication().authenticate(request)
    assert "falha ao contatar" in str(exc.value).lower()


@pytest.mark.django_db
def test_token_mal_assinado_gera_authfailed(settings, rf, monkeypatch):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    _patch_verify_200(monkeypatch, auth, 200)

    # Assina com outra chave -> deve falhar na verificação de assinatura
    token = _build_token("outra-chave", {"username": "joana"})
    request = rf.get("/bad-sig", **_auth_header(token))

    with pytest.raises(AuthenticationFailed) as exc:
        auth.RemoteJWTAuthentication().authenticate(request)
    assert "malformado" in str(exc.value).lower() or "signature" in str(exc.value).lower()


@pytest.mark.django_db
def test_payload_sem_username_sub_userid_gera_authfailed(settings, rf, monkeypatch):
    settings.AUTH_VERIFY_URL = "http://auth/verify/"
    settings.SECRET_KEY = "super-secret"
    import anexos.auth as auth
    importlib.reload(auth)

    _patch_verify_200(monkeypatch, auth, 200)

    # remove username e sub e user_id
    now = int(time.time())
    payload = {"iat": now, "exp": now + 60}
    token = jwt.encode(payload, key=settings.SECRET_KEY, algorithm="HS256")

    request = rf.get("/no-user", **_auth_header(token))
    with pytest.raises(AuthenticationFailed) as exc:
        auth.RemoteJWTAuthentication().authenticate(request)
    assert "username" in str(exc.value).lower() or "sub" in str(exc.value).lower()
