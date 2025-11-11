import pytest
import requests
from unittest.mock import patch, MagicMock

from django.conf import settings   
from anexos.services.intercorrencia_service import (
    get_detalhes_intercorrencia,
    ExternalServiceError
)
class TestIntercorrenciaService:
    """Testes para o serviço de intercorrência"""

    def setup_method(self):
        self.intercorrencia_uuid = "123e4567-e89b-12d3-a456-426614174000"
        self.token = "test_token"   
        
    @patch("anexos.services.intercorrencia_service.requests.get")
    def test_get_detalhes_intercorrencia_sucesso(self, mock_get):
        """Testa obtenção bem-sucedida dos detalhes da intercorrência"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "uuid": self.intercorrencia_uuid,
            "descricao": "Intercorrência de teste"
        }
        mock_get.return_value = mock_response

        detalhes = get_detalhes_intercorrencia(self.intercorrencia_uuid, self.token)

        assert detalhes["uuid"] == self.intercorrencia_uuid
        assert detalhes["descricao"] == "Intercorrência de teste"
        mock_get.assert_called_once_with(
            f"{settings.INTERCORRENCIAS_API_URL.rstrip('/')}/verify-intercorrencia/{self.intercorrencia_uuid}/",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5
        )  
        
    @patch("anexos.services.intercorrencia_service.requests.get")
    def test_get_detalhes_intercorrencia_http_error(self, mock_get):
        """Testa tratamento de erro HTTP ao obter detalhes da intercorrência"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_response.json.return_value = {"detail": "Intercorrência não encontrada"}
        mock_get.return_value = mock_response

        with pytest.raises(ExternalServiceError) as exc_info:
            get_detalhes_intercorrencia(self.intercorrencia_uuid, self.token)

        assert "Intercorrência não encontrada" in str(exc_info.value)
        mock_get.assert_called_once_with(
            f"{settings.INTERCORRENCIAS_API_URL.rstrip('/')}/verify-intercorrencia/{self.intercorrencia_uuid}/",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5
        )
        
        
    @patch("anexos.services.intercorrencia_service.requests.get")
    def test_get_detalhes_intercorrencia_request_exception(self, mock_get):
        """Testa tratamento de exceção de requisição ao obter detalhes da intercorrência"""
        mock_get.side_effect = requests.RequestException("Erro de conexão")

        with pytest.raises(ExternalServiceError) as exc_info:
            get_detalhes_intercorrencia(self.intercorrencia_uuid, self.token)

        assert "Não foi possível obter detalhes da intercorrência" in str(exc_info.value)
        mock_get.assert_called_once_with(
            f"{settings.INTERCORRENCIAS_API_URL.rstrip('/')}/verify-intercorrencia/{self.intercorrencia_uuid}/",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5
        )
    
    @patch("anexos.services.intercorrencia_service.requests.get")
    def test_get_detalhes_intercorrencia_http_error_resposta_texto(self, mock_get):
        """Testa tratamento de erro HTTP quando a resposta não é JSON (cai no except Exception)"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        # Simula que response.json() lança exceção (não é JSON válido)
        mock_response.json.side_effect = ValueError("Não é JSON válido")
        # Quando cair no except, deve usar response.text
        mock_response.text = "Erro no servidor: Internal Server Error"
        mock_get.return_value = mock_response

        with pytest.raises(ExternalServiceError) as exc_info:
            get_detalhes_intercorrencia(self.intercorrencia_uuid, self.token)

        assert "Erro no servidor: Internal Server Error" in str(exc_info.value)
        mock_get.assert_called_once_with(
            f"{settings.INTERCORRENCIAS_API_URL.rstrip('/')}/verify-intercorrencia/{self.intercorrencia_uuid}/",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5
        )
    
        
    
        