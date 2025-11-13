"""
Testes para exercitar fixtures e factories do conftest.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import io


@pytest.mark.django_db
class TestConftestFixtures:
    """Testes para exercitar fixtures do conftest.py"""
    
    def test_arquivo_pdf_mock_fixture(self, arquivo_pdf_mock):
        """Testa que fixture arquivo_pdf_mock retorna arquivo válido"""
        assert arquivo_pdf_mock is not None
        assert hasattr(arquivo_pdf_mock, 'name')
        assert hasattr(arquivo_pdf_mock, 'read')
        assert arquivo_pdf_mock.name.endswith('.pdf')
    
    def test_arquivo_imagem_mock_fixture(self, arquivo_imagem_mock):
        """Testa que fixture arquivo_imagem_mock retorna imagem válida"""
        assert arquivo_imagem_mock is not None
        assert hasattr(arquivo_imagem_mock, 'name')
        assert arquivo_imagem_mock.name.endswith(('.jpg', '.png', '.jpeg'))
    
    def test_mock_minio_storage_fixture(self, mock_minio_storage):
        """Testa que fixture mock_minio_storage funciona corretamente"""
        # Fixture é aplicada automaticamente, apenas verificar que não lança erro
        assert mock_minio_storage is not None


@pytest.mark.django_db
class TestFactories:
    """Testes para exercitar factories"""
    
    def test_anexo_pdf_factory_lazy_attribute(self, anexo_pdf_factory):
        """Testa que lazy attributes das factories são executados"""
        # Criar anexo para exercitar lazy attributes
        anexo = anexo_pdf_factory.create()
        
        # Verificar que campos foram preenchidos
        assert anexo.nome_original is not None
        assert anexo.tipo_mime is not None
        assert anexo.tamanho_bytes > 0
        assert anexo.intercorrencia_uuid is not None
    
    def test_anexo_dre_factory_lazy_attribute(self, anexo_dre_factory):
        """Testa lazy attributes da factory DRE"""
        anexo = anexo_dre_factory.create()
        
        # Verificar campos específicos de DRE (perfil em lowercase)
        assert anexo.perfil == 'dre'
        assert anexo.categoria in [
            'relatorio_naapa', 'relatorio_cefai',
            'relatorio_sts', 'relatorio_cpca', 'oficio_gcm'
        ]
    
    def test_anexo_gipe_factory_lazy_attribute(self, anexo_gipe_factory):
        """Testa lazy attributes da factory GIPE"""
        anexo = anexo_gipe_factory.create()
        
        # Verificar campos específicos de GIPE
        assert anexo.perfil == 'gipe'
        assert anexo.categoria in [
            'boletim_ocorrencia', 'registro_intercorrencia',
            'protocolo_conselho_tutelar', 'instrucao_normativa_20_2020',
            'relatorio_naapa', 'relatorio_supervisao_escolar',
            'relatorio_cefai', 'relatorio_sts', 'relatorio_cpca', 'oficio_gcm'
        ]
    
    def test_anexo_imagem_factory_lazy_attribute(self, anexo_imagem_factory):
        """Testa lazy attributes da factory de imagem"""
        anexo = anexo_imagem_factory.create()
        
        # Verificar que é imagem (e_imagem é property, não método)
        assert anexo.tipo_mime.startswith('image/')
        assert anexo.e_imagem is True
    
    def test_factory_build_vs_create(self, anexo_pdf_factory):
        """Testa diferença entre build e create"""
        # Build não salva no banco
        anexo_build = anexo_pdf_factory.build()
        assert anexo_build.pk is None
        
        # Create salva no banco
        anexo_create = anexo_pdf_factory.create()
        assert anexo_create.pk is not None
    
    def test_factory_batch_creation(self, anexo_pdf_factory):
        """Testa criação em lote com create_batch"""
        anexos = anexo_pdf_factory.create_batch(5)
        
        assert len(anexos) == 5
        for anexo in anexos:
            assert anexo.pk is not None
            assert anexo.nome_original is not None
