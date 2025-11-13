import time
import requests
import jwt
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
import logging

logger = logging.getLogger(__name__)

VERIFY_URL = settings.AUTH_VERIFY_URL
ME_URL = getattr(settings, 'AUTH_ME_URL', None)

@dataclass
class ExternalUser:
    username: str
    name: str | None = None
    cargo_codigo: int | None = None
    unidade_codigo_eol: str | None = None
    dre_codigo_eol: str | None = None
    is_authenticated: bool = True

class RemoteJWTAuthentication(BaseAuthentication):
    """
    Autentica usuário via JWT validando no serviço de autenticação remoto.
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != b"bearer" or len(auth) != 2:
            return None

        token = auth[1].decode("utf-8")
        user_payload = self._verify_and_get_payload(token)
        
        logger.info("Payload do usuário: %s", user_payload)

        username = (
            user_payload.get("username") 
            or user_payload.get("sub") 
            or user_payload.get("user_id")
        )
        if not username:
            raise AuthenticationFailed("Token sem 'username' ou 'sub'.")

        # Buscar informações adicionais do usuário
        user_info = self._get_user_info(token, username) if ME_URL else {}
        
        user = ExternalUser(
            username=username,
            name=user_payload.get("name") or user_info.get("name"),
            cargo_codigo=user_payload.get("perfil_codigo") 
                         or user_payload.get("cargo_codigo") 
                         or user_info.get("cargo_codigo"),
            unidade_codigo_eol=user_info.get("unidade_codigo_eol"),
            dre_codigo_eol=user_info.get("dre_codigo_eol"),
        )
        
        logger.info("Usuário autenticado: %s (cargo: %s)", user.username, user.cargo_codigo)

        return (user, None)

    def _verify_and_get_payload(self, token: str) -> dict:
        logger.info("Verificando token no serviço de auth: %s", VERIFY_URL)
        cache_key = f"jwtv:{hash(token)}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Enviando requisição para o serviço de auth... {VERIFY_URL}")
            r = requests.post(VERIFY_URL, json={"token": token}, timeout=3.0)
            logger.info("Resposta do serviço de auth: %s", r.status_code)
        except requests.RequestException as e:
            raise AuthenticationFailed(f"Falha ao contatar serviço de autenticação: {e}")

        if r.status_code != 200:
            raise AuthenticationFailed("Token inválido ou expirado.")

        try:
            payload = jwt.decode(
                token,
                key=settings.AUTH_PUBLIC_KEY if hasattr(settings, "AUTH_PUBLIC_KEY") else settings.SECRET_KEY,
                algorithms=["HS256", "RS256"],
                options={"verify_signature": True}
            )
        except jwt.PyJWTError:
            raise AuthenticationFailed("Token malformado.")

        now = int(time.time())
        exp = int(payload.get("exp", now + 60))
        ttl = max(1, min(60, exp - now))
        cache.set(cache_key, payload, ttl)
        return payload

    def _get_user_info(self, token: str, username: str) -> dict:
        """Busca informações adicionais do usuário"""
        cache_key = f"user_info:{username}:{hash(token)}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Buscando informações do usuário: {ME_URL}")
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.get(ME_URL, headers=headers, timeout=3.0)
            logger.info("Resposta do /me: %s", r.status_code)

            if r.status_code == 200:
                user_data = r.json()
                info = self._parse_user_data(user_data)
                cache.set(cache_key, info, 30)
                return info
            else:
                logger.warning("Falha ao buscar dados do usuário: status %s", r.status_code)
                return {}

        except requests.RequestException as e:
            logger.warning("Erro ao buscar informações do usuário: %s", e)
            return {}

    def _parse_user_data(self, user_data: dict) -> dict:
        """Extrai informações relevantes do dicionário de dados do usuário"""
        info = {
            'name': user_data.get('name') or user_data.get('first_name'),
            'cargo_codigo': user_data.get('cargo_codigo') or user_data.get('perfil_codigo'),
            'unidade_codigo_eol': None,
            'dre_codigo_eol': None
        }

        if user_data.get('unidade_codigo_eol'):
            info['unidade_codigo_eol'] = user_data['unidade_codigo_eol']
        if user_data.get('dre_codigo_eol'):
            info['dre_codigo_eol'] = user_data['dre_codigo_eol']

        unidade = user_data.get('unidade') or user_data.get('escola')
        if unidade:
            info['unidade_codigo_eol'] = unidade.get('codigo_eol') or unidade.get('codigo')
            dre = unidade.get('dre')
            if dre:
                info['dre_codigo_eol'] = dre.get('codigo_eol') or dre.get('codigo')

        dre = user_data.get('dre')
        if dre:
            info['dre_codigo_eol'] = dre.get('codigo_eol') or dre.get('codigo')

        return info