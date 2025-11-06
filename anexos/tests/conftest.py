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
def anexo_file_path(tmp_path):
    file_path = tmp_path / "test_anexo.txt"
    with open(file_path, "w") as f:
        f.write("Conteúdo do anexo de teste.")
    return file_path


@pytest.fixture
def arquivo_pdf_mock():
    """Retorna um arquivo PDF mockado para testes"""
    return SimpleUploadedFile(
        name='documento.pdf',
        content=b'%PDF-1.4 fake pdf content for testing',
        content_type='application/pdf'
    )


@pytest.fixture
def arquivo_txt_mock():
    """Retorna um arquivo TXT mockado para testes"""
    return SimpleUploadedFile(
        name='documento.txt',
        content=b'Conteudo do arquivo de teste.',
        content_type='text/plain'
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
        
        def _open(self, name, mode='rb'):
            """Simula abertura de arquivo"""
            from django.core.files.base import File
            return File(BytesIO(b'fake file content'), name)
        
        def delete(self, name):
            """Simula exclusão"""
            pass
        
        def exists(self, name):
            """Simula verificação de existência"""
            return True
        
        def size(self, name):
            """Simula retorno de tamanho"""
            return 1024
        
        def url(self, name):
            """Simula geração de URL"""
            return f"http://fake-minio-url.com/bucket/{name}"
        
        def get_valid_name(self, name):
            """Retorna nome válido"""
            return name
        
        def get_available_name(self, name, max_length=None):
            """Retorna nome disponível"""
            return name
        
        def generate_filename(self, filename):
            """Gera nome de arquivo"""
            import os
            from datetime import datetime
            now = datetime.now()
            path = f"anexos/{now.year}/{now.month:02d}/{now.day:02d}/"
            return os.path.join(path, filename)
        
        def path(self, name):
            """Retorna caminho do arquivo"""
            return name
    
    # Substituir a classe MinioStorage pela versão mockada
    monkeypatch.setattr(storage, 'MinioStorage', MockMinioStorage)
    
    return MockMinioStorage


@pytest.fixture
def mock_minio_client():
    """
    Mock do cliente MinIO para testes que precisam interagir diretamente com o cliente.
    """
    with patch('anexos.storage.Minio') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dos métodos principais
        mock_client.bucket_exists.return_value = True
        mock_client.make_bucket.return_value = None
        mock_client.put_object.return_value = None
        mock_client.get_object.return_value = MagicMock()
        mock_client.remove_object.return_value = None
        mock_client.stat_object.return_value = MagicMock(size=1024)
        mock_client.presigned_get_object.return_value = "http://fake-presigned-url.com"
        
        yield mock_client    