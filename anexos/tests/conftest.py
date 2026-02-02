import os
import pytest
from pytest_factoryboy import register
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Registrar factories
from anexos.tests.factories import (
    AnexoFactory,
    AnexoPDFFactory,
    AnexoImagemFactory,
    AnexoTXTFactory,
    AnexoDREFactory,
    AnexoGIPEFactory,
)

register(AnexoFactory)
register(AnexoPDFFactory)
register(AnexoImagemFactory)
register(AnexoTXTFactory)
register(AnexoDREFactory)
register(AnexoGIPEFactory)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def arquivo_pdf_mock():
    """Retorna um arquivo PDF mockado para testes"""
    return SimpleUploadedFile(
        name='documento.pdf',
        content=b'%PDF-1.4 fake pdf content for testing',
        content_type='application/pdf'
    )


@pytest.fixture
def arquivo_imagem_mock():
    """Retorna um arquivo de imagem mockado para testes"""
    return SimpleUploadedFile(
        name='imagem.jpg',
        content=b'\xff\xd8\xff\xe0\x00\x10JFIF fake jpeg content',
        content_type='image/jpeg'
    )


@pytest.fixture(autouse=True)
def mock_minio_storage(monkeypatch):
    """
    Mock automático do MinIO Storage para todos os testes.
    Evita chamadas reais ao MinIO durante os testes.
    """
    from anexos import storage
    
    # Criar classe de storage mockado
    class MockMinioStorage:
        def __init__(self, *args, **kwargs):
            """Inicializa storage mockado - não precisa de configuração real"""
            pass
        
        def save(self, name, content, max_length=None):
            """Simula salvamento (método público)"""
            return self._save(name, content)
        
        def _save(self, name, content):
            """Simula salvamento sem acessar MinIO"""
            return name
        
        def delete(self, name):
            """Simula exclusão"""
            pass
        
        def size(self, name):
            """Simula retorno de tamanho"""
            return 1024
        
        def url(self, name):
            """Simula geração de URL"""
            return f"http://fake-minio-url.com/bucket/{name}"
        
        
        def generate_filename(self, filename):
            """Gera nome de arquivo"""
            import os
            from datetime import datetime
            now = datetime.now()
            path = f"anexos/{now.year}/{now.month:02d}/{now.day:02d}/"
            return os.path.join(path, filename)
        
    
    # Substituir a classe MinioStorage pela versão mockada
    monkeypatch.setattr(storage, 'MinioStorage', MockMinioStorage)
    
    return MockMinioStorage

