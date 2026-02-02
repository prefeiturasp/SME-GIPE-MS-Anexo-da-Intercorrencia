from rest_framework.permissions import BasePermission
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class IsInternalServiceRequest(BasePermission):
    """
    Permission para requisições de microserviços internos.
    Valida um token compartilhado no header X-Internal-Service-Token.
    """
    
    def has_permission(self, request, view):
        # Token enviado no header
        token = request.headers.get('X-Internal-Service-Token')
        
        # Token esperado (configurado no settings)
        expected_token = getattr(settings, 'INTERNAL_SERVICE_TOKEN', None)
        
        if not expected_token:
            logger.warning("INTERNAL_SERVICE_TOKEN não configurado no settings")
            return False
        
        if token != expected_token:
            logger.warning(
                f"Token inválido recebido de {request.META.get('REMOTE_ADDR')}"
            )
            return False
        
        logger.debug(f"Token válido para requisição interna de {request.META.get('REMOTE_ADDR')}")
        return True