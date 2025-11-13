"""
Testes para MinioStorage

Todos os testes usam mocks para evitar dependências do MinIO real.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from django.core.files.base import File, ContentFile
from io import BytesIO
from minio.error import S3Error
from datetime import timedelta

from anexos.storage import MinioStorage


def create_s3_error(code='Error', message='Error message'):
    """Helper para criar S3Error com assinatura correta"""
    mock_response = Mock()
    mock_response.status = 404
    mock_response.reason = 'Not Found'
    
    return S3Error(
        mock_response,
        code=code,
        message=message,
        resource='/test',
        request_id='123',
        host_id='456'
    )


@pytest.fixture
def mock_minio_client():
    """Mock do cliente MinIO"""
    with patch('anexos.storage.Minio') as mock_minio:
        client = MagicMock()
        mock_minio.return_value = client
        
        # Configurar comportamentos padrão
        client.bucket_exists.return_value = True
        client.make_bucket.return_value = None
        
        yield client


@pytest.fixture
def storage(mock_minio_client):
    """Instância do MinioStorage com cliente mockado"""
    with patch('anexos.storage.settings') as mock_settings:
        mock_settings.MINIO_ENDPOINT = 'localhost:9000'
        mock_settings.MINIO_ACCESS_KEY = 'minioadmin'
        mock_settings.MINIO_SECRET_KEY = 'minioadmin'
        mock_settings.MINIO_BUCKET_NAME = 'anexos'
        mock_settings.MINIO_USE_HTTPS = False
        mock_settings.MINIO_STORAGE_MEDIA_BASE_URL = 'http://localhost:9000'
        
        storage = MinioStorage()
        storage.client = mock_minio_client
        
        return storage


@pytest.mark.django_db
class TestMinioStorageInit:
    """Testes de inicialização do MinioStorage"""
    
    def test_init_com_configuracoes(self, mock_minio_client):
        """Testa inicialização com configurações do settings"""
        with patch('anexos.storage.settings') as mock_settings:
            mock_settings.MINIO_ENDPOINT = 'minio.example.com:9000'
            mock_settings.MINIO_ACCESS_KEY = 'test_access'
            mock_settings.MINIO_SECRET_KEY = 'test_secret'
            mock_settings.MINIO_BUCKET_NAME = 'test-bucket'
            mock_settings.MINIO_USE_HTTPS = True
            mock_settings.MINIO_STORAGE_MEDIA_BASE_URL = 'https://minio.example.com'
            
            storage = MinioStorage()
            
            assert storage.endpoint == 'minio.example.com:9000'
            assert storage.access_key == 'test_access'
            assert storage.secret_key == 'test_secret'
            assert storage.bucket_name == 'test-bucket'
            assert storage.use_https is True
            assert storage.base_url == 'https://minio.example.com'
    
    def test_ensure_bucket_exists_cria_bucket(self, mock_minio_client):
        """Testa criação de bucket quando não existe"""
        with patch('anexos.storage.settings') as mock_settings:
            mock_settings.MINIO_ENDPOINT = 'localhost:9000'
            mock_settings.MINIO_ACCESS_KEY = 'minioadmin'
            mock_settings.MINIO_SECRET_KEY = 'minioadmin'
            mock_settings.MINIO_BUCKET_NAME = 'anexos'
            mock_settings.MINIO_USE_HTTPS = False
            mock_settings.MINIO_STORAGE_MEDIA_BASE_URL = 'http://localhost:9000'
            
            mock_minio_client.bucket_exists.return_value = False
            
            MinioStorage()  # Chama __init__ que deve criar o bucket
            
            mock_minio_client.bucket_exists.assert_called_once_with('anexos')
            mock_minio_client.make_bucket.assert_called_once_with('anexos')
    
    def test_ensure_bucket_exists_nao_cria_se_existe(self, mock_minio_client):
        """Testa que não cria bucket se já existe"""
        with patch('anexos.storage.settings') as mock_settings:
            mock_settings.MINIO_ENDPOINT = 'localhost:9000'
            mock_settings.MINIO_ACCESS_KEY = 'minioadmin'
            mock_settings.MINIO_SECRET_KEY = 'minioadmin'
            mock_settings.MINIO_BUCKET_NAME = 'anexos'
            mock_settings.MINIO_USE_HTTPS = False
            mock_settings.MINIO_STORAGE_MEDIA_BASE_URL = 'http://localhost:9000'
            
            mock_minio_client.bucket_exists.return_value = True
            
            MinioStorage()  # Chama __init__ que NÃO deve criar bucket
            
            mock_minio_client.bucket_exists.assert_called_once_with('anexos')
            mock_minio_client.make_bucket.assert_not_called()
    
    def test_ensure_bucket_exists_trata_erro(self, mock_minio_client, capsys):
        """Testa tratamento de erro ao criar bucket"""
        with patch('anexos.storage.settings') as mock_settings:
            mock_settings.MINIO_ENDPOINT = 'localhost:9000'
            mock_settings.MINIO_ACCESS_KEY = 'minioadmin'
            mock_settings.MINIO_SECRET_KEY = 'minioadmin'
            mock_settings.MINIO_BUCKET_NAME = 'anexos'
            mock_settings.MINIO_USE_HTTPS = False
            mock_settings.MINIO_STORAGE_MEDIA_BASE_URL = 'http://localhost:9000'
            
            mock_minio_client.bucket_exists.side_effect = create_s3_error(
                'BucketError', 'Erro ao verificar bucket'
            )
            
            MinioStorage()  # Deve capturar exceção e imprimir erro
            
            captured = capsys.readouterr()
            assert 'Erro ao verificar/criar bucket' in captured.out


@pytest.mark.django_db
class TestMinioStorageSave:
    """Testes do método _save"""
    
    def test_save_arquivo_sucesso(self, storage):
        """Testa salvamento de arquivo com sucesso"""
        content = ContentFile(b'Conteudo do arquivo', name='test.txt')
        content.content_type = 'text/plain'
        
        result = storage._save('teste/test.txt', content)
        
        assert result == 'teste/test.txt'
        storage.client.put_object.assert_called_once()
        
        # Verificar argumentos da chamada
        call_args = storage.client.put_object.call_args
        assert call_args[0][0] == 'anexos'  # bucket_name
        assert call_args[0][1] == 'teste/test.txt'  # object_name
        assert call_args[0][3] == 19  # tamanho do conteúdo
        assert call_args[1]['content_type'] == 'text/plain'
    
    def test_save_arquivo_sem_content_type(self, storage):
        """Testa salvamento sem content_type (usa padrão)"""
        content = ContentFile(b'Conteudo')
        # ContentFile não tem content_type por padrão, então será usado o padrão
        
        result = storage._save('test.bin', content)
        
        assert result == 'test.bin'
        call_args = storage.client.put_object.call_args
        assert call_args[1]['content_type'] == 'application/octet-stream'
    
    def test_save_arquivo_erro_s3(self, storage):
        """Testa tratamento de erro do MinIO ao salvar"""
        storage.client.put_object.side_effect = create_s3_error(
            'PutError', 'Erro ao fazer upload'
        )
        
        content = ContentFile(b'Conteudo')
        
        with pytest.raises(IOError) as exc_info:
            storage._save('test.txt', content)
        
        assert 'Erro ao salvar arquivo no MinIO' in str(exc_info.value)
    
    def test_save_arquivo_grande(self, storage):
        """Testa salvamento de arquivo grande"""
        # Simular arquivo de 5MB
        large_content = b'X' * (5 * 1024 * 1024)
        content = ContentFile(large_content, name='large.bin')
        
        result = storage._save('large.bin', content)
        
        assert result == 'large.bin'
        call_args = storage.client.put_object.call_args
        assert call_args[0][3] == 5 * 1024 * 1024


@pytest.mark.django_db
class TestMinioStorageOpen:
    """Testes do método _open"""
    
    def test_open_arquivo_sucesso(self, storage):
        """Testa abertura de arquivo com sucesso"""
        # Mockar resposta do MinIO
        mock_response = MagicMock()
        mock_response.read.return_value = b'Conteudo do arquivo'
        storage.client.get_object.return_value = mock_response
        
        file_obj = storage._open('test.txt')
        
        assert isinstance(file_obj, File)
        assert file_obj.read() == b'Conteudo do arquivo'
        
        storage.client.get_object.assert_called_once_with('anexos', 'test.txt')
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()
    
    def test_open_arquivo_nao_encontrado(self, storage):
        """Testa abertura de arquivo que não existe"""
        storage.client.get_object.side_effect = create_s3_error(
            'NoSuchKey', 'Arquivo não encontrado'
        )
        
        with pytest.raises(IOError) as exc_info:
            storage._open('inexistente.txt')
        
        assert 'Erro ao abrir arquivo do MinIO' in str(exc_info.value)
    
    def test_open_arquivo_binario(self, storage):
        """Testa abertura de arquivo binário"""
        binary_content = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG header
        mock_response = MagicMock()
        mock_response.read.return_value = binary_content
        storage.client.get_object.return_value = mock_response
        
        file_obj = storage._open('image.png', mode='rb')
        
        assert file_obj.read() == binary_content


@pytest.mark.django_db
class TestMinioStorageDelete:
    """Testes do método delete"""
    
    def test_delete_arquivo_sucesso(self, storage):
        """Testa exclusão de arquivo com sucesso"""
        storage.delete('test.txt')
        
        storage.client.remove_object.assert_called_once_with('anexos', 'test.txt')
    
    def test_delete_arquivo_nao_encontrado(self, storage, capsys):
        """Testa exclusão de arquivo que não existe (não deve lançar erro)"""
        storage.client.remove_object.side_effect = create_s3_error(
            'NoSuchKey', 'Arquivo não encontrado'
        )
        
        # Não deve lançar exceção
        storage.delete('inexistente.txt')
        
        captured = capsys.readouterr()
        assert 'Erro ao deletar arquivo do MinIO' in captured.out
    
    def test_delete_multiplos_arquivos(self, storage):
        """Testa exclusão de múltiplos arquivos"""
        arquivos = ['file1.txt', 'file2.pdf', 'file3.jpg']
        
        for arquivo in arquivos:
            storage.delete(arquivo)
        
        assert storage.client.remove_object.call_count == 3


@pytest.mark.django_db
class TestMinioStorageExists:
    """Testes do método exists"""
    
    def test_exists_arquivo_existente(self, storage):
        """Testa verificação de arquivo que existe"""
        mock_stat = MagicMock()
        mock_stat.size = 1024
        storage.client.stat_object.return_value = mock_stat
        
        result = storage.exists('test.txt')
        
        assert result is True
        storage.client.stat_object.assert_called_once_with('anexos', 'test.txt')
    
    def test_exists_arquivo_inexistente(self, storage):
        """Testa verificação de arquivo que não existe"""
        storage.client.stat_object.side_effect = create_s3_error(
            'NoSuchKey', 'Arquivo não encontrado'
        )
        
        result = storage.exists('inexistente.txt')
        
        assert result is False
    
    def test_exists_com_caminho_complexo(self, storage):
        """Testa verificação com caminho complexo"""
        mock_stat = MagicMock()
        storage.client.stat_object.return_value = mock_stat
        
        result = storage.exists('pasta/subpasta/arquivo.txt')
        
        assert result is True
        storage.client.stat_object.assert_called_once_with(
            'anexos', 'pasta/subpasta/arquivo.txt'
        )


@pytest.mark.django_db
class TestMinioStorageSize:
    """Testes do método size"""
    
    def test_size_arquivo_existente(self, storage):
        """Testa obtenção de tamanho de arquivo"""
        mock_stat = MagicMock()
        mock_stat.size = 2048
        storage.client.stat_object.return_value = mock_stat
        
        result = storage.size('test.txt')
        
        assert result == 2048
        storage.client.stat_object.assert_called_once_with('anexos', 'test.txt')
    
    def test_size_arquivo_inexistente(self, storage):
        """Testa tamanho de arquivo inexistente (retorna 0)"""
        storage.client.stat_object.side_effect = create_s3_error(
            'NoSuchKey', 'Arquivo não encontrado'
        )
        
        result = storage.size('inexistente.txt')
        
        assert result == 0
    
    def test_size_arquivo_vazio(self, storage):
        """Testa tamanho de arquivo vazio"""
        mock_stat = MagicMock()
        mock_stat.size = 0
        storage.client.stat_object.return_value = mock_stat
        
        result = storage.size('empty.txt')
        
        assert result == 0


@pytest.mark.django_db
class TestMinioStorageUrl:
    """Testes do método url"""
    
    def test_url_gera_presigned_url(self, storage):
        """Testa geração de URL pré-assinada"""
        storage.client.presigned_get_object.return_value = (
            'http://localhost:9000/anexos/test.txt?X-Amz-Signature=abc123'
        )
        
        result = storage.url('test.txt')
        
        assert 'X-Amz-Signature' in result
        assert 'test.txt' in result
        
        # Verificar chamada com timedelta
        call_args = storage.client.presigned_get_object.call_args
        assert call_args[0][0] == 'anexos'
        assert call_args[0][1] == 'test.txt'
        assert isinstance(call_args[1]['expires'], timedelta)
    
    def test_url_erro_fallback(self, storage):
        """Testa fallback quando erro ao gerar URL pré-assinada"""
        storage.client.presigned_get_object.side_effect = create_s3_error(
            'PresignError', 'Erro ao gerar URL'
        )
        
        result = storage.url('test.txt')
        
        # Deve retornar URL base sem assinatura
        assert result == 'http://localhost:9000/anexos/test.txt'
    
    def test_url_com_caminho_complexo(self, storage):
        """Testa URL com caminho complexo"""
        storage.client.presigned_get_object.return_value = (
            'http://localhost:9000/anexos/pasta/subpasta/arquivo.pdf?sig=xyz'
        )
        
        result = storage.url('pasta/subpasta/arquivo.pdf')
        
        assert 'pasta/subpasta/arquivo.pdf' in result


@pytest.mark.django_db
class TestMinioStorageGetValidName:
    """Testes do método get_valid_name"""
    
    def test_get_valid_name_retorna_mesmo_nome(self, storage):
        """Testa que retorna o mesmo nome (sem modificação)"""
        assert storage.get_valid_name('test.txt') == 'test.txt'
        assert storage.get_valid_name('arquivo com espaços.pdf') == 'arquivo com espaços.pdf'
        assert storage.get_valid_name('arquivo-com-hífen.jpg') == 'arquivo-com-hífen.jpg'
    
    def test_get_valid_name_com_caracteres_especiais(self, storage):
        """Testa nome com caracteres especiais"""
        assert storage.get_valid_name('test@#$.txt') == 'test@#$.txt'
    
    def test_get_valid_name_com_caminho(self, storage):
        """Testa nome com caminho completo"""
        assert storage.get_valid_name('pasta/subpasta/arquivo.txt') == 'pasta/subpasta/arquivo.txt'


@pytest.mark.django_db
class TestMinioStorageGetAvailableName:
    """Testes do método get_available_name"""
    
    def test_get_available_name_arquivo_nao_existe(self, storage):
        """Testa quando arquivo não existe (retorna mesmo nome)"""
        storage.client.stat_object.side_effect = create_s3_error(
            'NoSuchKey', 'Arquivo não encontrado'
        )
        
        result = storage.get_available_name('test.txt')
        
        assert result == 'test.txt'
    
    def test_get_available_name_arquivo_existe(self, storage):
        """Testa quando arquivo existe (adiciona sufixo)"""
        # Criar mock_stat para arquivos que existem
        mock_stat = MagicMock()
        mock_stat.size = 1024
        
        # Primeiro: test.txt existe, segundo: test_1.txt não existe
        def stat_side_effect(bucket, name):
            if name == 'test.txt':
                return mock_stat
            else:
                raise create_s3_error('NoSuchKey', 'Not found')
        
        storage.client.stat_object.side_effect = stat_side_effect
        
        result = storage.get_available_name('test.txt')
        
        assert result == 'test_1.txt'
    
    def test_get_available_name_multiplos_conflitos(self, storage):
        """Testa quando múltiplos arquivos existem"""
        mock_stat = MagicMock()
        
        # test.txt, test_1.txt e test_2.txt existem, test_3.txt não
        def stat_side_effect(bucket, name):
            if name in ['test.txt', 'test_1.txt', 'test_2.txt']:
                return mock_stat
            else:
                raise create_s3_error('NoSuchKey', 'Not found')
        
        storage.client.stat_object.side_effect = stat_side_effect
        
        result = storage.get_available_name('test.txt')
        
        assert result == 'test_3.txt'
    
    def test_get_available_name_com_caminho(self, storage):
        """Testa nome disponível com caminho"""
        mock_stat = MagicMock()
        
        def stat_side_effect(bucket, name):
            if name == 'pasta/test.txt':
                return mock_stat
            else:
                raise create_s3_error('NoSuchKey', 'Not found')
        
        storage.client.stat_object.side_effect = stat_side_effect
        
        result = storage.get_available_name('pasta/test.txt')
        
        assert result == 'pasta/test_1.txt'
    
    def test_get_available_name_preserva_extensao(self, storage):
        """Testa que preserva a extensão do arquivo"""
        mock_stat = MagicMock()
        
        def stat_side_effect(bucket, name):
            if name == 'documento.pdf':
                return mock_stat
            else:
                raise create_s3_error('NoSuchKey', 'Not found')
        
        storage.client.stat_object.side_effect = stat_side_effect
        
        result = storage.get_available_name('documento.pdf')
        
        assert result == 'documento_1.pdf'
        assert result.endswith('.pdf')


@pytest.mark.django_db
class TestMinioStorageIntegration:
    """Testes de integração do MinioStorage"""
    
    def test_fluxo_completo_salvar_abrir_deletar(self, storage):
        """Testa fluxo completo: salvar -> abrir -> deletar"""
        # 1. Salvar
        content = ContentFile(b'Conteudo de teste', name='test.txt')
        storage._save('test.txt', content)
        
        # 2. Abrir
        mock_response = MagicMock()
        mock_response.read.return_value = b'Conteudo de teste'
        storage.client.get_object.return_value = mock_response
        
        file_obj = storage._open('test.txt')
        assert file_obj.read() == b'Conteudo de teste'
        
        # 3. Deletar
        storage.delete('test.txt')
        
        assert storage.client.put_object.called
        assert storage.client.get_object.called
        assert storage.client.remove_object.called
    
    def test_verificar_e_obter_informacoes(self, storage):
        """Testa verificação de existência e obtenção de informações"""
        mock_stat = MagicMock()
        mock_stat.size = 1024
        storage.client.stat_object.return_value = mock_stat
        
        # Verificar existência
        exists = storage.exists('test.txt')
        assert exists is True
        
        # Obter tamanho
        size = storage.size('test.txt')
        assert size == 1024
        
        # Obter URL
        storage.client.presigned_get_object.return_value = 'http://example.com/test.txt'
        url = storage.url('test.txt')
        assert 'test.txt' in url
    
    def test_nome_unico_com_conflito(self, storage):
        """Testa geração de nome único quando há conflito"""
        mock_stat = MagicMock()
        
        # arquivo.txt existe, arquivo_1.txt não existe
        def stat_side_effect(bucket, name):
            if name == 'arquivo.txt':
                return mock_stat
            else:
                raise create_s3_error('NoSuchKey', 'Not found')
        
        storage.client.stat_object.side_effect = stat_side_effect
        
        # Obter nome disponível
        available_name = storage.get_available_name('arquivo.txt')
        assert available_name == 'arquivo_1.txt'
        
        # Validar nome
        valid_name = storage.get_valid_name(available_name)
        assert valid_name == available_name
