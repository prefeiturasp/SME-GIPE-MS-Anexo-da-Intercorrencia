"""
Testes para spectacular_ext.py

Testa a extensão OpenAPI para autenticação JWT customizada.
"""
import pytest
from unittest.mock import Mock
from anexos.spectacular_ext import RemoteJWTAuthScheme


class TestRemoteJWTAuthScheme:
    """Testes para RemoteJWTAuthScheme"""
    
    def test_get_security_definition_structure(self):
        """Testa que get_security_definition retorna estrutura correta"""
        # Criar um mock target para passar ao construtor
        mock_target = Mock()
        scheme = RemoteJWTAuthScheme(target=mock_target)
        
        # Passar None como auto_schema (não é usado no método)
        result = scheme.get_security_definition(auto_schema=None)
        
        assert result['type'] == 'http'
        assert result['scheme'] == 'bearer'
        assert result['bearerFormat'] == 'JWT'
    
    def test_target_class_attribute(self):
        """Testa que target_class aponta para a classe de autenticação correta"""
        assert RemoteJWTAuthScheme.target_class == 'anexos.auth.RemoteJWTAuthentication'
    
    def test_name_attribute(self):
        """Testa que name é 'Bearer'"""
        assert RemoteJWTAuthScheme.name == 'Bearer'
