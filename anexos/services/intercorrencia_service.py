from django.conf import settings
import requests
import logging
logger = logging.getLogger(__name__)


class ExternalServiceError(Exception): ...

BASE = settings.INTERCORRENCIAS_API_URL.rstrip('/')

def get_detalhes_intercorrencia(intercorrencia_uuid: str, token: str) -> dict | None:
    
    """Obtém detalhes da intercorrência a partir do serviço externo."""
    
    url = f"{BASE}/verify-intercorrencia/{intercorrencia_uuid}/"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        error_content = None
        if e.response is not None:
            try:
                error_content = e.response.json()
            except Exception:
                error_content = e.response.text
        logger.error(f"Erro HTTP ao obter detalhes da intercorrência {intercorrencia_uuid}: {e} - Conteúdo: {error_content}")
        raise ExternalServiceError(error_content or str(e))
    except requests.RequestException as e:
        logger.error(f"Erro ao obter detalhes da intercorrência {intercorrencia_uuid}: {e}")
        raise ExternalServiceError(f"Não foi possível obter detalhes da intercorrência: {e}")