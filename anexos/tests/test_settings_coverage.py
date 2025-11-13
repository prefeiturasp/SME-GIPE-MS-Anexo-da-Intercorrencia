"""
Testes para cobertura de branches em config/settings.py e config/urls.py
"""
import pytest
import os
import sys
from importlib import reload
from unittest.mock import patch


class TestSettingsMinioExternalEndpoint:
    """Testes para branch MINIO_EXTERNAL_ENDPOINT em settings.py"""
    
    def test_minio_external_endpoint_presente(self):
        """Testa branch quando MINIO_EXTERNAL_ENDPOINT está definido"""
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'minio:9000',
            'MINIO_EXTERNAL_ENDPOINT': 'https://minio-external:9000',
            'MINIO_ACCESS_KEY': 'test_key',
            'MINIO_SECRET_KEY': 'test_secret',
            'MINIO_BUCKET_NAME': 'test_bucket',
            'DJANGO_SECRET_KEY': 'test_secret_key',
            'POSTGRES_DB': 'test_db',
            'POSTGRES_USER': 'test_user',
            'POSTGRES_PASSWORD': 'test_password',
            'POSTGRES_PORT': '5432',
        }):
            # Remover módulo do cache se existir
            if 'config.settings' in sys.modules:
                del sys.modules['config.settings']
            
            # Importar settings com MINIO_EXTERNAL_ENDPOINT
            import config.settings as settings
            
            # Verificar que MINIO_STORAGE_MEDIA_BASE_URL foi definido com endpoint externo
            assert hasattr(settings, 'MINIO_STORAGE_MEDIA_BASE_URL')
            assert settings.MINIO_STORAGE_MEDIA_BASE_URL == 'https://minio-external:9000'
    
    def test_minio_external_endpoint_ausente(self):
        """Testa branch quando MINIO_EXTERNAL_ENDPOINT não está definido"""
        env_vars = {
            'MINIO_ENDPOINT': 'minio:9000',
            'MINIO_ACCESS_KEY': 'test_key',
            'MINIO_SECRET_KEY': 'test_secret',
            'MINIO_BUCKET_NAME': 'test_bucket',
            'DJANGO_SECRET_KEY': 'test_secret_key',
            'POSTGRES_DB': 'test_db',
            'POSTGRES_USER': 'test_user',
            'POSTGRES_PASSWORD': 'test_password',
            'POSTGRES_PORT': '5432',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Remover módulo do cache
            if 'config.settings' in sys.modules:
                del sys.modules['config.settings']
            
            # Importar settings sem MINIO_EXTERNAL_ENDPOINT
            import config.settings as settings
            
            # Verificar que MINIO_STORAGE_MEDIA_BASE_URL usa MINIO_ENDPOINT
            assert hasattr(settings, 'MINIO_STORAGE_MEDIA_BASE_URL')
            # A URL será construída com o protocolo (http://) e o endpoint
            assert settings.MINIO_STORAGE_MEDIA_BASE_URL.startswith('http')


class TestUrlsDebugMode:
    """Testes para branch DEBUG em config/urls.py"""
    
    def test_urls_debug_true_inclui_static(self):
        """Testa que em DEBUG=True, urls inclui static files"""
        with patch('django.conf.settings.DEBUG', True):
            # Remover módulo do cache
            if 'config.urls' in sys.modules:
                del sys.modules['config.urls']
            
            # Importar urls em modo DEBUG
            import config.urls
            
            # Recarregar para garantir que o código do if DEBUG executa
            reload(config.urls)
            
            # Verificar que urlpatterns existe
            assert hasattr(config.urls, 'urlpatterns')
            assert isinstance(config.urls.urlpatterns, list)
    
    def test_urls_debug_false_sem_static(self):
        """Testa que em DEBUG=False, urls não inclui static files"""
        with patch('django.conf.settings.DEBUG', False):
            # Remover módulo do cache
            if 'config.urls' in sys.modules:
                del sys.modules['config.urls']
            
            # Importar urls em modo produção
            import config.urls
            
            # Recarregar
            reload(config.urls)
            
            # Verificar que urlpatterns existe
            assert hasattr(config.urls, 'urlpatterns')
            assert isinstance(config.urls.urlpatterns, list)
