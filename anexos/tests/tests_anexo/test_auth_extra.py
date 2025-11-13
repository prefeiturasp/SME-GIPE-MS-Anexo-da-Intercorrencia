"""
Testes adicionais para anexos.auth

Cobre branches de erro, caching e parsing de dados do usuário.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import jwt
import time
from rest_framework.exceptions import AuthenticationFailed
from django.core.cache import cache

from anexos.auth import RemoteJWTAuthentication, ExternalUser


@pytest.fixture
def auth():
    """Fixture para RemoteJWTAuthentication"""
    return RemoteJWTAuthentication()


@pytest.fixture
def mock_request_with_token():
    """Fixture para request mockado com token Bearer"""
    request = Mock()
    request.META = {'HTTP_AUTHORIZATION': 'Bearer fake_token_12345'}
    return request


@pytest.mark.django_db
class TestRemoteJWTAuthenticationVerifyPayload:
    """Testes para _verify_and_get_payload"""
    
    def test_verify_request_exception_raises_authentication_failed(self, auth):
        """Testa que RequestException ao chamar o serviço de auth lança AuthenticationFailed"""
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.RequestException('Connection error')
            
            with pytest.raises(AuthenticationFailed) as exc_info:
                auth._verify_and_get_payload('fake_token')
            
            assert 'Falha ao contatar serviço de autenticação' in str(exc_info.value)
    
    def test_verify_non_200_raises_authentication_failed(self, auth):
        """Testa que resposta não-200 do serviço lança AuthenticationFailed"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response
            
            with pytest.raises(AuthenticationFailed) as exc_info:
                auth._verify_and_get_payload('fake_token')
            
            assert 'Token inválido ou expirado' in str(exc_info.value)
    
    def test_verify_jwt_decode_error_raises_authentication_failed(self, auth):
        """Testa que erro ao decodificar JWT lança AuthenticationFailed"""
        with patch('requests.post') as mock_post, \
             patch('jwt.decode') as mock_decode:
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            mock_decode.side_effect = jwt.PyJWTError('Invalid token')
            
            with pytest.raises(AuthenticationFailed) as exc_info:
                auth._verify_and_get_payload('fake_token')
            
            assert 'Token malformado' in str(exc_info.value)
    
    def test_verify_caches_payload(self, auth):
        """Testa que payload é cacheado e não chama requests novamente"""
        # Limpar cache antes do teste
        cache.clear()
        
        with patch('requests.post') as mock_post, \
             patch('jwt.decode') as mock_decode:
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            # Payload com exp distante no futuro
            payload = {
                'username': 'testuser',
                'exp': int(time.time()) + 3600  # Expira em 1 hora
            }
            mock_decode.return_value = payload
            
            # Primeira chamada
            result1 = auth._verify_and_get_payload('fake_token')
            
            # Segunda chamada com mesmo token
            result2 = auth._verify_and_get_payload('fake_token')
            
            # Deve ter chamado requests.post apenas uma vez
            assert mock_post.call_count == 1
            assert result1 == payload
            assert result2 == payload


@pytest.mark.django_db
class TestRemoteJWTAuthenticationGetUserInfo:
    """Testes para _get_user_info"""
    
    def test_get_user_info_request_exception_returns_empty_dict(self, auth):
        """Testa que RequestException retorna dicionário vazio"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException('Connection error')
            
            result = auth._get_user_info('fake_token', 'testuser')
            
            assert result == {}
    
    def test_get_user_info_non_200_returns_empty_dict(self, auth):
        """Testa que resposta não-200 retorna dicionário vazio"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            result = auth._get_user_info('fake_token', 'testuser')
            
            assert result == {}
    
    def test_get_user_info_success_returns_parsed_data(self, auth):
        """Testa que resposta 200 retorna dados parseados"""
        # Limpar cache
        cache.clear()
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'name': 'Test User',
                'cargo_codigo': 123
            }
            mock_get.return_value = mock_response
            
            result = auth._get_user_info('fake_token', 'testuser')
            
            assert result['name'] == 'Test User'
            assert result['cargo_codigo'] == 123
    
    def test_get_user_info_caches_result(self, auth):
        """Testa que resultado é cacheado"""
        cache.clear()
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'name': 'Test User'}
            mock_get.return_value = mock_response
            
            # Primeira chamada
            result1 = auth._get_user_info('fake_token', 'testuser')
            
            # Segunda chamada
            result2 = auth._get_user_info('fake_token', 'testuser')
            
            # Deve ter chamado requests.get apenas uma vez
            assert mock_get.call_count == 1
            assert result1 == result2


@pytest.mark.django_db
class TestRemoteJWTAuthenticationParseUserData:
    """Testes para _parse_user_data"""
    
    def test_parse_user_data_basic_fields(self, auth):
        """Testa parsing de campos básicos"""
        user_data = {
            'name': 'Test User',
            'cargo_codigo': 123
        }
        
        result = auth._parse_user_data(user_data)
        
        assert result['name'] == 'Test User'
        assert result['cargo_codigo'] == 123
        assert result['unidade_codigo_eol'] is None
        assert result['dre_codigo_eol'] is None
    
    def test_parse_user_data_with_first_name(self, auth):
        """Testa parsing quando tem first_name em vez de name"""
        user_data = {
            'first_name': 'Test User',
            'perfil_codigo': 456
        }
        
        result = auth._parse_user_data(user_data)
        
        assert result['name'] == 'Test User'
        assert result['cargo_codigo'] == 456
    
    def test_parse_user_data_with_direct_eol_codes(self, auth):
        """Testa parsing com códigos EOL diretos"""
        user_data = {
            'name': 'Test',
            'unidade_codigo_eol': 'UNI123',
            'dre_codigo_eol': 'DRE456'
        }
        
        result = auth._parse_user_data(user_data)
        
        assert result['unidade_codigo_eol'] == 'UNI123'
        assert result['dre_codigo_eol'] == 'DRE456'
    
    def test_parse_user_data_with_nested_unidade(self, auth):
        """Testa parsing com estrutura aninhada de unidade"""
        user_data = {
            'name': 'Test',
            'unidade': {
                'codigo_eol': 'UNI789',
                'dre': {
                    'codigo_eol': 'DRE321'
                }
            }
        }
        
        result = auth._parse_user_data(user_data)
        
        assert result['unidade_codigo_eol'] == 'UNI789'
        assert result['dre_codigo_eol'] == 'DRE321'
    
    def test_parse_user_data_with_escola(self, auth):
        """Testa parsing quando unidade está como 'escola'"""
        user_data = {
            'name': 'Test',
            'escola': {
                'codigo': 'ESC123',
                'dre': {
                    'codigo': 'DRE999'
                }
            }
        }
        
        result = auth._parse_user_data(user_data)
        
        assert result['unidade_codigo_eol'] == 'ESC123'
        assert result['dre_codigo_eol'] == 'DRE999'
    
    def test_parse_user_data_with_top_level_dre(self, auth):
        """Testa parsing com DRE em nível superior"""
        user_data = {
            'name': 'Test',
            'dre': {
                'codigo_eol': 'DRE_TOP'
            }
        }
        
        result = auth._parse_user_data(user_data)
        
        assert result['dre_codigo_eol'] == 'DRE_TOP'


@pytest.mark.django_db
class TestRemoteJWTAuthenticationAuthenticate:
    """Testes para método authenticate completo"""
    
    def test_authenticate_success_flow(self, auth, mock_request_with_token):
        """Testa fluxo completo de autenticação bem-sucedida"""
        payload = {
            'username': 'testuser',
            'name': 'Test User',
            'perfil_codigo': 123,
            'exp': int(time.time()) + 3600
        }
        
        user_info = {
            'unidade_codigo_eol': 'UNI123',
            'dre_codigo_eol': 'DRE456'
        }
        
        with patch.object(auth, '_verify_and_get_payload', return_value=payload), \
             patch.object(auth, '_get_user_info', return_value=user_info):
            
            user, token_data = auth.authenticate(mock_request_with_token)
            
            # Verificar tipo e atributos do usuário
            assert user.__class__.__name__ == 'ExternalUser'
            assert user.username == 'testuser'
            assert user.name == 'Test User'
            assert user.cargo_codigo == 123
            assert user.unidade_codigo_eol == 'UNI123'
            assert user.dre_codigo_eol == 'DRE456'
            assert user.is_authenticated is True
            assert token_data is None
    
    def test_authenticate_no_bearer_header_returns_none(self, auth):
        """Testa que request sem Bearer retorna None"""
        request = Mock()
        request.META = {}
        
        result = auth.authenticate(request)
        
        assert result is None
    
    def test_authenticate_invalid_header_format_returns_none(self, auth):
        """Testa que header malformado retorna None"""
        request = Mock()
        request.META = {'HTTP_AUTHORIZATION': 'Basic invalid'}
        
        result = auth.authenticate(request)
        
        assert result is None
    
    def test_authenticate_missing_username_raises(self, auth, mock_request_with_token):
        """Testa que payload sem username lança AuthenticationFailed"""
        payload = {
            'exp': int(time.time()) + 3600
            # Sem username, sub ou user_id
        }
        
        with patch.object(auth, '_verify_and_get_payload', return_value=payload):
            with pytest.raises(AuthenticationFailed) as exc_info:
                auth.authenticate(mock_request_with_token)
            
            assert "Token sem 'username' ou 'sub'" in str(exc_info.value)
    
    def test_authenticate_uses_sub_as_fallback(self, auth, mock_request_with_token):
        """Testa que usa 'sub' quando 'username' não existe"""
        payload = {
            'sub': 'user_from_sub',
            'exp': int(time.time()) + 3600
        }
        
        with patch.object(auth, '_verify_and_get_payload', return_value=payload), \
             patch.object(auth, '_get_user_info', return_value={}):
            
            user, _ = auth.authenticate(mock_request_with_token)
            
            assert user.username == 'user_from_sub'
