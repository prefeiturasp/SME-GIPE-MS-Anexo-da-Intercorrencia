"""
Testes para AnexoAdmin

Testa os métodos customizados do Django Admin para o modelo Anexo.
"""
import pytest
from django.contrib.admin.sites import AdminSite
from anexos.admin import AnexoAdmin
from anexos.models.anexo import Anexo


@pytest.fixture
def anexo_admin():
    """Fixture para AnexoAdmin"""
    return AnexoAdmin(Anexo, AdminSite())


@pytest.mark.django_db
class TestAnexoAdmin:
    """Testes para métodos customizados do AnexoAdmin"""
    
    def test_nome_original_truncado_nome_longo(self, anexo_admin, anexo_pdf_factory):
        """Testa truncamento de nome longo (>50 caracteres)"""
        # Criar anexo com nome longo
        nome_longo = 'a' * 60 + '.pdf'
        anexo = anexo_pdf_factory.create(nome_original=nome_longo)
        
        resultado = anexo_admin.nome_original_truncado(anexo)
        
        assert len(resultado) == 50  # 47 chars + '...'
        assert resultado.endswith('...')
        assert resultado.startswith('aaa')
    
    def test_nome_original_truncado_nome_curto(self, anexo_admin, anexo_pdf_factory):
        """Testa que nome curto não é truncado"""
        nome_curto = 'documento_curto.pdf'
        anexo = anexo_pdf_factory.create(nome_original=nome_curto)
        
        resultado = anexo_admin.nome_original_truncado(anexo)
        
        assert resultado == nome_curto
    
    def test_categoria_display_custom_perfil_diretor(self, anexo_admin, anexo_pdf_factory):
        """Testa exibição com cor para perfil diretor"""
        anexo = anexo_pdf_factory.create(
            perfil=Anexo.PERFIL_DIRETOR,
            categoria='boletim_ocorrencia'
        )
        
        resultado = anexo_admin.categoria_display_custom(anexo)
        
        # Verificar que retorna HTML com cor azul (#3498db)
        assert '#3498db' in resultado
        assert 'font-weight: bold' in resultado
        assert 'Boletim de ocorrência' in resultado
    
    def test_categoria_display_custom_perfil_dre(self, anexo_admin, anexo_dre_factory):
        """Testa exibição com cor para perfil DRE"""
        anexo = anexo_dre_factory.create(
            perfil=Anexo.PERFIL_DRE,
            categoria='relatorio_naapa'
        )
        
        resultado = anexo_admin.categoria_display_custom(anexo)
        
        # Verificar que retorna HTML com cor verde (#2ecc71)
        assert '#2ecc71' in resultado
        assert 'Relatório do NAAPA' in resultado
    
    def test_categoria_display_custom_perfil_gipe(self, anexo_admin, anexo_gipe_factory):
        """Testa exibição com cor para perfil GIPE"""
        anexo = anexo_gipe_factory.create(
            perfil=Anexo.PERFIL_GIPE,
            categoria='relatorio_supervisao_escolar'
        )
        
        resultado = anexo_admin.categoria_display_custom(anexo)
        
        # Verificar que retorna HTML com cor vermelha (#e74c3c)
        assert '#e74c3c' in resultado
        assert 'Relatório da Supervisão Escolar' in resultado
    
    def test_categoria_display_custom_perfil_desconhecido(self, anexo_admin, anexo_pdf_factory):
        """Testa cor padrão para perfil não mapeado"""
        anexo = anexo_pdf_factory.create(
            perfil=Anexo.PERFIL_ASSISTENTE,  # Não tem cor mapeada
            categoria='boletim_ocorrencia'
        )
        
        resultado = anexo_admin.categoria_display_custom(anexo)
        
        # Verificar que usa cor padrão cinza (#95a5a6)
        assert '#95a5a6' in resultado
    
    def test_preview_arquivo_para_imagem(self, anexo_admin, anexo_imagem_factory):
        """Testa preview para arquivo de imagem"""
        anexo = anexo_imagem_factory.create()
        
        resultado = anexo_admin.preview_arquivo(anexo)
        
        # Verificar que retorna tag <img>
        assert '<img src=' in resultado
        assert 'max-width: 200px' in resultado
        assert 'max-height: 200px' in resultado
    
    def test_preview_arquivo_para_nao_imagem(self, anexo_admin, anexo_pdf_factory):
        """Testa preview para arquivo não-imagem (PDF)"""
        anexo = anexo_pdf_factory.create()
        
        resultado = anexo_admin.preview_arquivo(anexo)
        
        # Verificar que retorna '-' para não-imagens
        assert resultado == '-'
    
    def test_preview_arquivo_sem_arquivo(self, anexo_admin, anexo_pdf_factory):
        """Testa preview quando anexo não tem arquivo"""
        anexo = anexo_pdf_factory.create()
        anexo.arquivo = None
        anexo.save()
        
        resultado = anexo_admin.preview_arquivo(anexo)
        
        assert resultado == '-'
