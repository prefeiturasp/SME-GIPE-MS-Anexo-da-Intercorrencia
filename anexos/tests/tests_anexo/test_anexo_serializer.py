import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory
from anexos.models.anexo import Anexo
from anexos.api.serializers.anexo_serializer import (
    AnexoSerializer,
    AnexoListSerializer,
    CategoriasDisponiveisSerializer,
)
from anexos.tests.factories import (
    AnexoFactory,
    AnexoPDFFactory,
    AnexoImagemFactory,
    AnexoDREFactory,
)


@pytest.mark.django_db
class TestAnexoSerializer:
    """Testes do AnexoSerializer com dados mockados"""
    
    def test_serializacao_anexo_completo(self):
        """Testa a serialização de um anexo com todos os campos"""
        anexo = AnexoPDFFactory()
        serializer = AnexoSerializer(anexo)
        data = serializer.data
        
        # Campos básicos
        assert 'id' in data
        assert 'uuid' in data
        assert data['perfil'] == anexo.perfil
        assert data['categoria'] == anexo.categoria
        assert data['ativo'] is True
        
        # Campos read-only
        assert 'perfil_display' in data
        assert 'categoria_display' in data
        assert 'tamanho_formatado' in data
        assert 'extensao' in data
        
        # Propriedades booleanas
        assert 'e_imagem' in data
        assert 'e_video' in data
        assert 'e_documento' in data
    
    def test_criacao_anexo_com_serializer(self, arquivo_pdf_mock):
        """Testa a criação de anexo através do serializer"""
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        anexo = serializer.save()
        
        assert anexo.id is not None
        assert anexo.perfil == Anexo.PERFIL_DIRETOR
        assert anexo.categoria == 'boletim_ocorrencia'
        assert anexo.nome_original == 'documento.pdf'
        assert anexo.tipo_mime == 'application/pdf'
        assert anexo.tamanho_bytes > 0
    
    def test_validacao_arquivo_muito_grande(self):
        """Testa validação de arquivo maior que 10MB"""
        # Criar arquivo mock maior que 10MB
        arquivo_grande = SimpleUploadedFile(
            name='arquivo_grande.pdf',
            content=b'x' * (11 * 1024 * 1024),  # 11MB
            content_type='application/pdf'
        )
        
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_grande,
        }
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        
        assert 'detail' in serializer.errors
        assert 'muito grande' in str(serializer.errors['detail']).lower()
    
    def test_validacao_extensao_invalida(self):
        """Testa validação de extensão de arquivo não permitida"""
        arquivo_invalido = SimpleUploadedFile(
            name='arquivo.exe',
            content=b'fake executable content',
            content_type='application/x-msdownload'
        )
        
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_invalido,
        }
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        assert 'detail' in serializer.errors
        # Verificar se a mensagem contém informação sobre extensão
        erro_msg = str(serializer.errors['detail']).lower()
        assert 'exe' in erro_msg or 'extensão' in erro_msg or 'extension' in erro_msg
    
    def test_validacao_categoria_invalida_para_perfil(self, arquivo_pdf_mock):
        """Testa validação de categoria inválida para o perfil"""
        # Categoria de DRE para perfil Diretor (inválido)
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'relatorio_naapa',  # Categoria de DRE
            'arquivo': arquivo_pdf_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        assert 'detail' in serializer.errors
        assert 'não é válida' in str(serializer.errors['detail']).lower()

    def test_validacao_categoria_valida_para_perfil(self, arquivo_pdf_mock):
        """Testa validação de categoria válida para o perfil"""
        # Categoria de Diretor para perfil Diretor (válido)
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
    
    def test_validacao_limite_tamanho_intercorrencia(self, arquivo_pdf_mock):
        """Testa validação do limite de 10MB por intercorrência"""
        uuid_intercorrencia = '123e4567-e89b-12d3-a456-426614174000'
        
        # Criar anexo existente de 9MB
        AnexoFactory(
            intercorrencia_uuid=uuid_intercorrencia,
            tamanho_bytes=9 * 1024 * 1024
        )
        
        # Tentar adicionar mais 2MB (ultrapassaria o limite)
        arquivo_2mb = SimpleUploadedFile(
            name='documento.pdf',
            content=b'x' * (2 * 1024 * 1024),
            content_type='application/pdf'
        )
        
        data = {
            'intercorrencia_uuid': uuid_intercorrencia,
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_2mb,
        }
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        assert 'detail' in serializer.errors
        assert 'limite' in str(serializer.errors['detail']).lower()

    def test_validacao_limite_tamanho_dentro_do_limite(self, arquivo_pdf_mock):
        """Testa que validação passa quando dentro do limite"""
        uuid_intercorrencia = '123e4567-e89b-12d3-a456-426614174000'
        
        # Criar anexo existente de 5MB
        AnexoFactory(
            intercorrencia_uuid=uuid_intercorrencia,
            tamanho_bytes=5 * 1024 * 1024
        )
        
        # Adicionar arquivo pequeno (deve passar)
        data = {
            'intercorrencia_uuid': uuid_intercorrencia,
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
    
    def test_campos_read_only(self, arquivo_pdf_mock):
        """Testa que campos read-only não podem ser alterados"""
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
            # Tentando forçar valores read-only
            'uuid': '00000000-0000-0000-0000-000000000000',
            'nome_original': 'nome_forcado.pdf',
            'tamanho_bytes': 999999,
            'tipo_mime': 'text/plain',
            'ativo': False,
        }
        
        serializer = AnexoSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        anexo = serializer.save()
        
        # Verificar que os campos foram preenchidos corretamente
        # e não com os valores fornecidos
        assert str(anexo.uuid) != '00000000-0000-0000-0000-000000000000'
        assert anexo.nome_original == 'documento.pdf'  # Do arquivo real
        assert anexo.tipo_mime == 'application/pdf'  # Do arquivo real
        assert anexo.ativo is True  # Padrão do modelo
    
    def test_arquivo_url_com_request_context(self):
        """Testa geração de arquivo_url com request no contexto"""
        anexo = AnexoPDFFactory()
        
        # Criar request factory mockado
        factory = APIRequestFactory()
        request = factory.get('/')
        
        serializer = AnexoSerializer(anexo, context={'request': request})
        data = serializer.data
        
        assert 'arquivo_url' in data
        # URL deve conter o domínio do request
        if data['arquivo_url']:
            assert 'http' in data['arquivo_url']
    
    def test_arquivo_url_sem_request_context(self):
        """Testa que arquivo_url é None sem request no contexto"""
        anexo = AnexoPDFFactory()
        
        serializer = AnexoSerializer(anexo)  # Sem contexto
        data = serializer.data
        
        assert data['arquivo_url'] is None
    
    def test_extensoes_permitidas(self):
        """Testa todas as extensões permitidas"""
        extensoes_validas = ['jpeg', 'jpg', 'png', 'mp4', 'pdf', 'xlsx', 'docx', 'txt']
        uuid_intercorrencia = '123e4567-e89b-12d3-a456-426614174000'
        
        for ext in extensoes_validas:
            arquivo = SimpleUploadedFile(
                name=f'arquivo.{ext}',
                content=b'fake content',
                content_type='application/octet-stream'
            )
            
            data = {
                'intercorrencia_uuid': uuid_intercorrencia,
                'perfil': Anexo.PERFIL_DIRETOR,
                'categoria': 'boletim_ocorrencia',
                'arquivo': arquivo,
            }
            
            serializer = AnexoSerializer(data=data)
            assert serializer.is_valid(), f'Extensão {ext} deveria ser válida: {serializer.errors}'
    
    def test_perfis_e_categorias_validas(self, arquivo_pdf_mock):
        """Testa combinações válidas de perfis e categorias"""
        combinacoes_validas = [
            (Anexo.PERFIL_DIRETOR, 'boletim_ocorrencia', '123e4567-e89b-12d3-a456-426614174001'),
            (Anexo.PERFIL_DIRETOR, 'registro_ocorrencia_interno', '123e4567-e89b-12d3-a456-426614174002'),
            (Anexo.PERFIL_ASSISTENTE, 'boletim_ocorrencia', '123e4567-e89b-12d3-a456-426614174003'),
            (Anexo.PERFIL_DRE, 'relatorio_naapa', '123e4567-e89b-12d3-a456-426614174004'),
            (Anexo.PERFIL_DRE, 'relatorio_cefai', '123e4567-e89b-12d3-a456-426614174005'),
            (Anexo.PERFIL_GIPE, 'boletim_ocorrencia', '123e4567-e89b-12d3-a456-426614174006'),
            (Anexo.PERFIL_GIPE, 'relatorio_supervisao_escolar', '123e4567-e89b-12d3-a456-426614174007'),
        ]
        
        for perfil, categoria, uuid_intercorrencia in combinacoes_validas:
            data = {
                'intercorrencia_uuid': uuid_intercorrencia,
                'perfil': perfil,
                'categoria': categoria,
                'arquivo': arquivo_pdf_mock,
            }
            
            serializer = AnexoSerializer(data=data)
            assert serializer.is_valid(), \
                f'Combinação {perfil}/{categoria} deveria ser válida: {serializer.errors}'


@pytest.mark.django_db
class TestAnexoListSerializer:
    """Testes do AnexoListSerializer"""
    
    def test_serializacao_lista_campos_corretos(self):
        """Testa que o serializer de lista contém apenas os campos necessários"""
        anexo = AnexoPDFFactory()
        serializer = AnexoListSerializer(anexo)
        data = serializer.data
        
        # Campos que devem estar presentes
        campos_esperados = [
            'uuid', 'nome_original', 'categoria', 'categoria_display',
            'perfil', 'perfil_display', 'tamanho_formatado', 'extensao',
            'arquivo_url', 'criado_em', 'usuario_username'
        ]
        
        for campo in campos_esperados:
            assert campo in data, f'Campo {campo} deveria estar presente'
        
        # Campos que NÃO devem estar presentes
        campos_nao_esperados = ['arquivo', 'tipo_mime', 'e_imagem', 'e_video']
        
        for campo in campos_nao_esperados:
            assert campo not in data, f'Campo {campo} não deveria estar presente'
    
    def test_serializacao_multiplos_anexos(self):
        """Testa serialização de múltiplos anexos"""
        anexos = [
            AnexoPDFFactory(),
            AnexoImagemFactory(),
            AnexoDREFactory(),
        ]
        
        serializer = AnexoListSerializer(anexos, many=True)
        data = serializer.data
        
        assert len(data) == 3
        assert all('uuid' in item for item in data)
        assert all('nome_original' in item for item in data)
    
    def test_arquivo_url_com_request(self):
        """Testa geração de arquivo_url no list serializer"""
        anexo = AnexoPDFFactory()
        
        factory = APIRequestFactory()
        request = factory.get('/')
        
        serializer = AnexoListSerializer(anexo, context={'request': request})
        data = serializer.data
        
        assert 'arquivo_url' in data


@pytest.mark.django_db
class TestCategoriasDisponiveisSerializer:
    """Testes do CategoriasDisponiveisSerializer"""
    
    def test_serializacao_categorias_diretor(self):
        """Testa serialização de categorias para perfil Diretor"""
        data_input = {'perfil': Anexo.PERFIL_DIRETOR}
        serializer = CategoriasDisponiveisSerializer(data_input)
        data = serializer.data
        
        assert 'perfil' in data
        assert 'categorias' in data
        assert data['perfil'] == Anexo.PERFIL_DIRETOR
        assert len(data['categorias']) == 4
        assert all('value' in cat for cat in data['categorias'])
        assert all('label' in cat for cat in data['categorias'])
    
    def test_serializacao_categorias_dre(self):
        """Testa serialização de categorias para perfil DRE"""
        data_input = {'perfil': Anexo.PERFIL_DRE}
        serializer = CategoriasDisponiveisSerializer(data_input)
        data = serializer.data
        
        assert data['perfil'] == Anexo.PERFIL_DRE
        assert len(data['categorias']) == 5
    
    def test_serializacao_categorias_gipe(self):
        """Testa serialização de categorias para perfil GIPE"""
        data_input = {'perfil': Anexo.PERFIL_GIPE}
        serializer = CategoriasDisponiveisSerializer(data_input)
        data = serializer.data
        
        assert data['perfil'] == Anexo.PERFIL_GIPE
        assert len(data['categorias']) == 10  # GIPE tem todas as categorias
    
    def test_formato_categorias(self):
        """Testa o formato das categorias retornadas"""
        data_input = {'perfil': Anexo.PERFIL_DIRETOR}
        serializer = CategoriasDisponiveisSerializer(data_input)
        data = serializer.data
        
        # Verificar estrutura de cada categoria
        for categoria in data['categorias']:
            assert isinstance(categoria, dict)
            assert 'value' in categoria
            assert 'label' in categoria
            assert isinstance(categoria['value'], str)
            assert isinstance(categoria['label'], str)
            assert len(categoria['value']) > 0
            assert len(categoria['label']) > 0
    
    def test_categorias_assistente_igual_diretor(self):
        """Testa que Assistente tem as mesmas categorias que Diretor"""
        data_diretor = {'perfil': Anexo.PERFIL_DIRETOR}
        data_assistente = {'perfil': Anexo.PERFIL_ASSISTENTE}
        
        serializer_diretor = CategoriasDisponiveisSerializer(data_diretor)
        serializer_assistente = CategoriasDisponiveisSerializer(data_assistente)
        
        categorias_diretor = serializer_diretor.data['categorias']
        categorias_assistente = serializer_assistente.data['categorias']
        
        assert len(categorias_diretor) == len(categorias_assistente)
        
        # Verificar que os values são os mesmos
        values_diretor = {cat['value'] for cat in categorias_diretor}
        values_assistente = {cat['value'] for cat in categorias_assistente}
        
        assert values_diretor == values_assistente


@pytest.mark.django_db
class TestAnexoSerializerValidacoes:
    """Testes específicos de validações do AnexoSerializer"""
    
    def test_campos_obrigatorios(self):
        """Testa que campos obrigatórios são validados"""
        data = {}
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        
        # Campos obrigatórios
        erro_msg = str(serializer.errors['detail']).lower()
        assert 'intercorrencia_uuid' in erro_msg

    
    def test_intercorrencia_uuid_invalido(self, arquivo_pdf_mock):
        """Testa validação de UUID inválido"""
        data = {
            'intercorrencia_uuid': 'uuid-invalido',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        erro_msg = str(serializer.errors['detail']).lower()
        assert 'intercorrencia_uuid' in erro_msg
    
    def test_perfil_invalido(self, arquivo_pdf_mock):
        """Testa validação de perfil inválido"""
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': 'perfil_inexistente',
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_pdf_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert not serializer.is_valid()
        erro_msg = str(serializer.errors['detail']).lower()
        assert 'perfil' in erro_msg
    
    def test_criacao_preenche_metadados_automaticamente(self, arquivo_imagem_mock):
        """Testa que metadados do arquivo são preenchidos automaticamente"""
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_imagem_mock,
        }
        
        serializer = AnexoSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        anexo = serializer.save()
        
        # Metadados preenchidos automaticamente
        assert anexo.nome_original is not None
        assert anexo.tamanho_bytes > 0
        assert anexo.tipo_mime is not None
        assert anexo.nome_original == 'imagem.jpg'
        assert anexo.tipo_mime == 'image/jpeg'
    
    def test_validacao_tamanho_exato_limite(self):
        """Testa validação com arquivo exatamente no limite (10MB)"""
        arquivo_10mb = SimpleUploadedFile(
            name='documento.pdf',
            content=b'x' * (10 * 1024 * 1024),  # Exatamente 10MB
            content_type='application/pdf'
        )
        
        data = {
            'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
            'perfil': Anexo.PERFIL_DIRETOR,
            'categoria': 'boletim_ocorrencia',
            'arquivo': arquivo_10mb,
        }
        
        serializer = AnexoSerializer(data=data)
        # Deve ser válido (limite é 10MB, não maior que 10MB)
        assert serializer.is_valid(), serializer.errors
