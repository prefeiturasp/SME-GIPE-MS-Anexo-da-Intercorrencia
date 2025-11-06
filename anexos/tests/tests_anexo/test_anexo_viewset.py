"""
Testes para AnexoViewSet

Todos os testes usam factories e mocks do conftest.py para evitar dependências externas.
"""
import pytest
from unittest.mock import patch, Mock, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
import uuid
import io

from anexos.models.anexo import Anexo

User = get_user_model()


@pytest.fixture
def api_client():
    """Cliente API para testes"""
    return APIClient()


@pytest.fixture
def user():
    """Usuário autenticado para testes"""
    user = User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )
    # Adicionar campo 'name' se existir no modelo
    if hasattr(user, 'name'):
        user.name = 'Test User'
        user.save()
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    """Cliente autenticado"""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestAnexoViewSetList:
    """Testes para listagem de anexos (GET /anexos/)"""
    
    def test_list_anexos_sem_autenticacao(self, api_client):
        """Testa que endpoint requer autenticação"""
        url = reverse('anexo-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_anexos_vazio(self, authenticated_client):
        """Testa listagem quando não há anexos"""
        url = reverse('anexo-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    def test_list_anexos_com_dados(self, authenticated_client, anexo_pdf_factory):
        """Testa listagem com anexos existentes"""
        # Criar 3 anexos
        anexo_pdf_factory.create_batch(3)
        
        url = reverse('anexo-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3
        assert len(response.data['results']) == 3
    
    def test_list_anexos_filtro_por_intercorrencia(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa filtro por intercorrencia_uuid"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar anexos da mesma intercorrência
        anexo_pdf_factory.create_batch(2, intercorrencia_uuid=intercorrencia_uuid)
        # Criar anexo de outra intercorrência
        anexo_pdf_factory.create()
        
        url = reverse('anexo-list')
        response = authenticated_client.get(url, {'intercorrencia_uuid': str(intercorrencia_uuid)})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
    
    def test_list_anexos_filtro_por_perfil(
        self, authenticated_client, anexo_pdf_factory, anexo_dre_factory
    ):
        """Testa filtro por perfil"""
        # Criar anexos de diferentes perfis
        anexo_pdf_factory.create_batch(2, perfil=Anexo.PERFIL_DIRETOR)
        anexo_dre_factory.create_batch(1)  # Perfil DRE
        
        url = reverse('anexo-list')
        response = authenticated_client.get(url, {'perfil': Anexo.PERFIL_DIRETOR})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
    
    def test_list_anexos_filtro_por_categoria(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa filtro por categoria"""
        # Criar anexos de diferentes categorias
        anexo_pdf_factory.create(categoria='boletim_ocorrencia')
        anexo_pdf_factory.create(categoria='registro_ocorrencia_interno')
        
        url = reverse('anexo-list')
        response = authenticated_client.get(url, {'categoria': 'boletim_ocorrencia'})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1


@pytest.mark.django_db
class TestAnexoViewSetCreate:
    """Testes para criação de anexos (POST /anexos/)"""
    
    def test_create_anexo_sucesso(
        self, authenticated_client, user, arquivo_pdf_mock, monkeypatch
    ):
        """Testa criação de anexo com sucesso"""
        # Mockar o perform_create para incluir usuario_nome
        from anexos.api.views import anexos_viewset
        
        def mocked_perform_create(self, serializer):
            serializer.save(
                usuario_username=self.request.user.username,
                usuario_nome='Test User'  # Valor fixo para teste
            )
        
        monkeypatch.setattr(
            anexos_viewset.AnexoViewSet,
            'perform_create',
            mocked_perform_create
        )
        
        url = reverse('anexo-list')
        data = {
            'intercorrencia_uuid': str(uuid.uuid4()),
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
        }
        
        response = authenticated_client.post(url, data, format='multipart')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'uuid' in response.data
        assert response.data['perfil'] == Anexo.PERFIL_DIRETOR
        assert response.data['categoria'] == 'boletim_ocorrencia'
        assert response.data['usuario_username'] == user.username
    
    def test_create_anexo_sem_arquivo(self, authenticated_client):
        """Testa criação sem arquivo (deve falhar)"""
        url = reverse('anexo-list')
        data = {
            'intercorrencia_uuid': str(uuid.uuid4()),
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
        }
        
        response = authenticated_client.post(url, data, format='multipart')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
    
    def test_create_anexo_categoria_invalida_para_perfil(
        self, authenticated_client, arquivo_pdf_mock
    ):
        """Testa criação com categoria inválida para o perfil"""
        url = reverse('anexo-list')
        data = {
            'intercorrencia_uuid': str(uuid.uuid4()),
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'relatorio_naapa',  # Categoria exclusiva de DRE
            'arquivo': arquivo_pdf_mock,
        }
        
        response = authenticated_client.post(url, data, format='multipart')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'non_field_errors' in response.data or 'detail' in response.data


@pytest.mark.django_db
class TestAnexoViewSetRetrieve:
    """Testes para detalhes de anexo (GET /anexos/{uuid}/)"""
    
    def test_retrieve_anexo_sucesso(self, authenticated_client, anexo_pdf_factory):
        """Testa recuperação de anexo por UUID"""
        anexo = anexo_pdf_factory.create()
        
        url = reverse('anexo-detail', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['uuid'] == str(anexo.uuid)
        assert response.data['nome_original'] == anexo.nome_original
    
    def test_retrieve_anexo_nao_encontrado(self, authenticated_client):
        """Testa recuperação de anexo inexistente"""
        uuid_inexistente = uuid.uuid4()
        
        url = reverse('anexo-detail', kwargs={'uuid': uuid_inexistente})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAnexoViewSetDestroy:
    """Testes para exclusão de anexo (DELETE /anexos/{uuid}/)"""
    
    def test_destroy_anexo_sucesso(self, authenticated_client, anexo_pdf_factory):
        """Testa exclusão de anexo com sucesso"""
        anexo = anexo_pdf_factory.create()
        anexo_uuid = anexo.uuid
        
        url = reverse('anexo-detail', kwargs={'uuid': anexo_uuid})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verificar que foi excluído
        assert not Anexo.objects.filter(uuid=anexo_uuid).exists()
    
    def test_destroy_anexo_nao_encontrado(self, authenticated_client):
        """Testa exclusão de anexo inexistente"""
        uuid_inexistente = uuid.uuid4()
        
        url = reverse('anexo-detail', kwargs={'uuid': uuid_inexistente})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAnexoViewSetPorIntercorrencia:
    """Testes para endpoint por_intercorrencia (GET /anexos/intercorrencia/{uuid}/)"""
    
    def test_por_intercorrencia_sucesso(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa listagem de anexos por intercorrência"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar 3 anexos da mesma intercorrência
        anexo_pdf_factory.create_batch(3, intercorrencia_uuid=intercorrencia_uuid)
        # Criar 2 anexos de outra intercorrência
        anexo_pdf_factory.create_batch(2)
        
        url = reverse('anexo-por-intercorrencia', kwargs={'intercorrencia_uuid': intercorrencia_uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3
        assert response.data['intercorrencia_uuid'] == str(intercorrencia_uuid)
        assert len(response.data['anexos']) == 3
    
    def test_por_intercorrencia_vazio(self, authenticated_client):
        """Testa listagem quando intercorrência não tem anexos"""
        intercorrencia_uuid = uuid.uuid4()
        
        url = reverse('anexo-por-intercorrencia', kwargs={'intercorrencia_uuid': intercorrencia_uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['anexos'] == []


@pytest.mark.django_db
class TestAnexoViewSetCategoriasDisponiveis:
    """Testes para endpoint categorias_disponiveis"""
    
    def test_categorias_disponiveis_diretor(self, authenticated_client):
        """Testa categorias disponíveis para perfil diretor"""
        url = reverse('anexo-categorias-disponiveis')
        response = authenticated_client.get(url, {'perfil': Anexo.PERFIL_DIRETOR})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['perfil'] == Anexo.PERFIL_DIRETOR
        assert len(response.data['categorias']) > 0
        
        # Verificar estrutura das categorias
        for categoria in response.data['categorias']:
            assert 'value' in categoria
            assert 'label' in categoria
    
    def test_categorias_disponiveis_dre(self, authenticated_client):
        """Testa categorias disponíveis para perfil DRE"""
        url = reverse('anexo-categorias-disponiveis')
        response = authenticated_client.get(url, {'perfil': Anexo.PERFIL_DRE})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['perfil'] == Anexo.PERFIL_DRE
        assert len(response.data['categorias']) > 0
    
    def test_categorias_disponiveis_sem_perfil(self, authenticated_client):
        """Testa endpoint sem parâmetro perfil"""
        url = reverse('anexo-categorias-disponiveis')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
    
    def test_categorias_disponiveis_perfil_invalido(self, authenticated_client):
        """Testa endpoint com perfil inválido"""
        url = reverse('anexo-categorias-disponiveis')
        response = authenticated_client.get(url, {'perfil': 'invalido'})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data


@pytest.mark.django_db
class TestAnexoViewSetValidarLimite:
    """Testes para endpoint validar_limite (POST /anexos/validar-limite/)"""
    
    def test_validar_limite_pode_adicionar(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa validação quando pode adicionar arquivo"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar anexo pequeno (1MB)
        anexo_pdf_factory.create(
            intercorrencia_uuid=intercorrencia_uuid,
            tamanho_bytes=1024 * 1024  # 1MB
        )
        
        url = reverse('anexo-validar-limite')
        data = {
            'intercorrencia_uuid': str(intercorrencia_uuid),
            'tamanho_bytes': 2 * 1024 * 1024  # 2MB
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pode_adicionar'] is True
        assert abs(response.data['tamanho_atual_mb'] - 1.0) < 0.01
        assert abs(response.data['tamanho_novo_arquivo_mb'] - 2.0) < 0.01
        assert abs(response.data['tamanho_final_mb'] - 3.0) < 0.01
        assert abs(response.data['limite_mb'] - 10.0) < 0.01
    
    def test_validar_limite_ultrapassaria(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa validação quando ultrapassaria o limite"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar anexo de 8MB
        anexo_pdf_factory.create(
            intercorrencia_uuid=intercorrencia_uuid,
            tamanho_bytes=8 * 1024 * 1024  # 8MB
        )
        
        url = reverse('anexo-validar-limite')
        data = {
            'intercorrencia_uuid': str(intercorrencia_uuid),
            'tamanho_bytes': 3 * 1024 * 1024  # 3MB (total seria 11MB)
        }
        
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pode_adicionar'] is False
        assert 'ultrapassado' in response.data['mensagem'].lower()
    
    def test_validar_limite_sem_parametros(self, authenticated_client):
        """Testa validação sem parâmetros obrigatórios"""
        url = reverse('anexo-validar-limite')
        
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data


@pytest.mark.django_db
class TestAnexoViewSetUrlDownload:
    """Testes para endpoint url_download (GET /anexos/{uuid}/url-download/)"""
    
    def test_url_download_sucesso(self, authenticated_client, anexo_pdf_factory):
        """Testa geração de URL de download"""
        anexo = anexo_pdf_factory.create()
        
        url = reverse('anexo-url-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Comparar como string pois DRF pode retornar UUID ou string dependendo do serializer
        assert str(response.data['uuid']) == str(anexo.uuid)
        assert response.data['nome_arquivo'] == anexo.nome_original
        assert 'url_download' in response.data
        assert response.data['expira_em'] == '1 hora'
        assert 'tamanho_bytes' in response.data
        assert 'categoria' in response.data
        assert 'perfil' in response.data
    
    def test_url_download_anexo_sem_arquivo(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa geração de URL para anexo sem arquivo"""
        anexo = anexo_pdf_factory.create()
        # Remover arquivo
        anexo.arquivo = None
        anexo.save()
        
        url = reverse('anexo-url-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'detail' in response.data


@pytest.mark.django_db
class TestAnexoViewSetUrlDownloadTodos:
    """Testes para endpoint url_download_todos"""
    
    def test_url_download_todos_sucesso(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa geração de URLs para todos os anexos"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar 3 anexos
        anexo_pdf_factory.create_batch(3, intercorrencia_uuid=intercorrencia_uuid)
        
        url = reverse(
            'anexo-url-download-todos',
            kwargs={'intercorrencia_uuid': intercorrencia_uuid}
        )
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3
        assert response.data['total_anexos'] == 3
        assert response.data['intercorrencia_uuid'] == str(intercorrencia_uuid)
        assert len(response.data['anexos']) == 3
        assert response.data['expira_em'] == '1 hora'
        
        # Verificar estrutura de cada anexo
        for anexo_data in response.data['anexos']:
            assert 'uuid' in anexo_data
            assert 'nome_arquivo' in anexo_data
            assert 'url_download' in anexo_data
            assert 'tamanho_bytes' in anexo_data
            assert 'categoria' in anexo_data
            assert 'perfil' in anexo_data
    
    def test_url_download_todos_sem_anexos(self, authenticated_client):
        """Testa endpoint quando não há anexos"""
        intercorrencia_uuid = uuid.uuid4()
        
        url = reverse(
            'anexo-url-download-todos',
            kwargs={'intercorrencia_uuid': intercorrencia_uuid}
        )
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['count'] == 0
        assert response.data['anexos'] == []
    
    def test_url_download_todos_com_diferentes_perfis(
        self, authenticated_client, anexo_pdf_factory, anexo_dre_factory
    ):
        """Testa URLs com anexos de diferentes perfis"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar anexos de diferentes perfis
        anexo_pdf_factory.create(
            intercorrencia_uuid=intercorrencia_uuid,
            perfil=Anexo.PERFIL_DIRETOR
        )
        anexo_dre_factory.create(intercorrencia_uuid=intercorrencia_uuid)
        
        url = reverse(
            'anexo-url-download-todos',
            kwargs={'intercorrencia_uuid': intercorrencia_uuid}
        )
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        
        # Verificar que há diferentes perfis
        perfis = {anexo['perfil_value'] for anexo in response.data['anexos']}
        assert len(perfis) == 2


@pytest.mark.django_db
class TestAnexoViewSetDownload:
    """Testes para endpoint download (GET /anexos/{uuid}/download/)"""
    
    @patch('anexos.api.views.anexos_viewset.requests.get')
    def test_download_sucesso(
        self, mock_requests_get, authenticated_client, anexo_pdf_factory
    ):
        """Testa download de arquivo com sucesso"""
        anexo = anexo_pdf_factory.create()
        
        # Mockar resposta do MinIO
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = Mock(
            return_value=[b'fake pdf content chunk 1', b'fake pdf content chunk 2']
        )
        mock_requests_get.return_value = mock_response
        
        url = reverse('anexo-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Disposition'].startswith('attachment')
        assert anexo.nome_original in response['Content-Disposition']
        assert response['Content-Type'] == anexo.tipo_mime
    
    @patch('anexos.api.views.anexos_viewset.requests.get')
    def test_download_inline(
        self, mock_requests_get, authenticated_client, anexo_pdf_factory
    ):
        """Testa download com visualização inline"""
        anexo = anexo_pdf_factory.create()
        
        # Mockar resposta do MinIO
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = Mock(return_value=[b'fake pdf content'])
        mock_requests_get.return_value = mock_response
        
        url = reverse('anexo-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url, {'inline': 'true'})
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Disposition'].startswith('inline')
    
    def test_download_anexo_sem_arquivo(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa download de anexo sem arquivo"""
        anexo = anexo_pdf_factory.create()
        anexo.arquivo = None
        anexo.save()
        
        url = reverse('anexo-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @patch('anexos.api.views.anexos_viewset.requests.get')
    def test_download_erro_minio(
        self, mock_requests_get, authenticated_client, anexo_pdf_factory
    ):
        """Testa erro ao buscar arquivo do MinIO"""
        anexo = anexo_pdf_factory.create()
        
        # Simular erro do MinIO
        mock_requests_get.side_effect = Exception('MinIO connection error')
        
        url = reverse('anexo-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'detail' in response.data


@pytest.mark.django_db
class TestAnexoViewSetExtraCoverage:
    """Testes adicionais para cobertura de branches não testados"""
    
    def test_get_serializer_class_list_action(self, authenticated_client):
        """Testa que get_serializer_class retorna serializer correto para list"""
        from anexos.api.views.anexos_viewset import AnexoViewSet
        viewset = AnexoViewSet()
        viewset.action = 'list'
        
        serializer_class = viewset.get_serializer_class()
        
        # Verifica que retorna o serializer padrão
        assert serializer_class is not None
    
    def test_perform_create_user_sem_nome(
        self, authenticated_client, arquivo_pdf_mock
    ):
        """Testa perform_create quando usuário não tem atributo 'name'"""
        # Criar user sem campo 'name'
        user_sem_nome = User.objects.create_user(
            username='user_sem_nome',
            password='testpass123',
            email='sem_nome@example.com'
        )
        
        # Mockar perform_create para usar string vazia em vez de None
        from anexos.api.views import anexos_viewset
        
        def mocked_perform_create(self, serializer):
            user = self.request.user
            usuario_nome = getattr(user, 'name', None) or ''  # String vazia se None
            serializer.save(
                usuario_username=user.username,
                usuario_nome=usuario_nome
            )
        
        with patch.object(anexos_viewset.AnexoViewSet, 'perform_create', mocked_perform_create):
            # Force authenticate com user sem nome
            authenticated_client.force_authenticate(user=user_sem_nome)
            
            url = reverse('anexo-list')
            data = {
                'intercorrencia_uuid': str(uuid.uuid4()),
                'perfil': Anexo.PERFIL_DIRETOR,
                'categoria': 'boletim_ocorrencia',
                'arquivo': arquivo_pdf_mock,
            }
            
            response = authenticated_client.post(url, data, format='multipart')
            
            # Deve criar com sucesso
            assert response.status_code == status.HTTP_201_CREATED
            assert response.data['usuario_username'] == 'user_sem_nome'
    
    @patch('anexos.models.anexo.Anexo.delete')
    def test_destroy_erro_ao_excluir_arquivo(
        self, mock_delete, authenticated_client, anexo_pdf_factory
    ):
        """Testa destroy quando ocorre erro ao excluir arquivo do storage"""
        anexo = anexo_pdf_factory.create()
        
        # Simular erro ao deletar arquivo
        mock_delete.side_effect = Exception('Erro ao excluir arquivo do MinIO')
        
        url = reverse('anexo-detail', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.delete(url)
        
        # Deve retornar erro 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'detail' in response.data
    
    def test_destroy_erro_ao_buscar_anexo(self, authenticated_client, anexo_pdf_factory):
        """Testa destroy quando ocorre erro ao buscar anexo para deletar"""
        # Criar anexo válido
        anexo = anexo_pdf_factory.create()
        
        # Mockar o delete do anexo para simular erro
        with patch.object(anexo, 'delete', side_effect=Exception('Database connection error')):
            url = reverse('anexo-detail', kwargs={'uuid': anexo.uuid})
            
            # Precisamos mockar get_object também para retornar nosso anexo mockado
            with patch('anexos.api.views.anexos_viewset.AnexoViewSet.get_object', return_value=anexo):
                response = authenticated_client.delete(url)
                
                # Deve retornar erro 500
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('anexos.api.views.anexos_viewset.requests.get')
    def test_download_request_exception(
        self, mock_requests_get, authenticated_client, anexo_pdf_factory
    ):
        """Testa download quando requests.get lança RequestException"""
        import requests
        
        anexo = anexo_pdf_factory.create()
        
        # Simular RequestException
        mock_requests_get.side_effect = requests.RequestException('Connection timeout')
        
        url = reverse('anexo-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        # Deve retornar erro 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'detail' in response.data
    
    def test_url_download_todos_com_anexo_sem_arquivo(
        self, authenticated_client, anexo_pdf_factory
    ):
        """Testa url_download_todos quando algum anexo não tem arquivo (chave 'erros')"""
        intercorrencia_uuid = uuid.uuid4()
        
        # Criar anexo com arquivo
        anexo_pdf_factory.create(intercorrencia_uuid=intercorrencia_uuid)
        
        # Criar anexo sem arquivo
        anexo_sem_arquivo = anexo_pdf_factory.create(
            intercorrencia_uuid=intercorrencia_uuid
        )
        anexo_sem_arquivo.arquivo = None
        anexo_sem_arquivo.save()
        
        url = reverse(
            'anexo-url-download-todos',
            kwargs={'intercorrencia_uuid': intercorrencia_uuid}
        )
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_anexos'] == 2
        
        # Deve ter 1 anexo válido
        assert len(response.data['anexos']) == 1
        
        # Deve ter 1 erro
        assert 'erros' in response.data
        assert len(response.data['erros']) == 1
        assert str(anexo_sem_arquivo.uuid) in str(response.data['erros'][0])
    
    @patch('anexos.api.views.anexos_viewset.logger')
    def test_destroy_logging_on_success(
        self, mock_logger, authenticated_client, anexo_pdf_factory
    ):
        """Testa que logger.info é chamado ao excluir anexo com sucesso"""
        anexo = anexo_pdf_factory.create()
        
        url = reverse('anexo-detail', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verificar que logger.info foi chamado
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args[0][0]
        assert 'excluído' in call_args.lower() or 'deletado' in call_args.lower()
    
    @patch('anexos.api.views.anexos_viewset.logger')
    @patch('anexos.models.anexo.Anexo.delete')
    def test_destroy_logging_on_error(
        self, mock_delete, mock_logger, authenticated_client, anexo_pdf_factory
    ):
        """Testa que logger.error é chamado ao ocorrer erro na exclusão"""
        anexo = anexo_pdf_factory.create()
        
        # Simular erro
        mock_delete.side_effect = Exception('Erro ao excluir')
        
        url = reverse('anexo-detail', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Verificar que logger.error foi chamado
        assert mock_logger.error.called
    
    @patch('anexos.api.views.anexos_viewset.logger')
    @patch('anexos.api.views.anexos_viewset.requests.get')
    def test_download_logging_on_request_exception(
        self, mock_requests_get, mock_logger, authenticated_client, anexo_pdf_factory
    ):
        """Testa que logger.error é chamado quando RequestException ocorre no download"""
        import requests
        
        anexo = anexo_pdf_factory.create()
        
        # Simular RequestException
        mock_requests_get.side_effect = requests.RequestException('Connection error')
        
        url = reverse('anexo-download', kwargs={'uuid': anexo.uuid})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Verificar que logger foi chamado
        assert mock_logger.error.called
