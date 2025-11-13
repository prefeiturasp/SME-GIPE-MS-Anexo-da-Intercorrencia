import factory
from factory.django import ImageField
from django.utils import timezone
from django.core.files.base import ContentFile
from io import BytesIO
import uuid

from anexos.models.anexo import Anexo


class AnexoFactory(factory.django.DjangoModelFactory):
    """Factory para criar instâncias de Anexo para testes"""
    
    class Meta:
        model = Anexo
        skip_postgeneration_save = True

    intercorrencia_uuid = factory.Faker('uuid4')
    perfil = Anexo.PERFIL_DIRETOR
    categoria = "boletim_ocorrencia"
    
    # Arquivo mockado - não salva no MinIO durante os testes
    @factory.lazy_attribute
    def arquivo(self):
        return ContentFile(
            b'%PDF-1.4 fake pdf content for testing',
            name=f'documento_{uuid.uuid4()}.pdf'
        )
    
    nome_original = factory.Faker('file_name', extension='pdf')
    tamanho_bytes = factory.Faker('random_int', min=1000, max=1048576)
    tipo_mime = 'application/pdf'
    usuario_username = factory.Faker('user_name')
    usuario_nome = factory.Faker('name')
    ativo = True


class AnexoPDFFactory(AnexoFactory):
    """Factory específica para anexos PDF"""
    
    @factory.lazy_attribute
    def arquivo(self):
        return ContentFile(
            b'%PDF-1.4 fake pdf content for testing',
            name=f'documento_{uuid.uuid4()}.pdf'
        )
    
    nome_original = factory.Faker('file_name', extension='pdf')
    tipo_mime = 'application/pdf'
    categoria = "boletim_ocorrencia"


class AnexoImagemFactory(AnexoFactory):
    """Factory específica para anexos de imagem"""
    
    @factory.lazy_attribute
    def arquivo(self):
        return ContentFile(
            b'\xff\xd8\xff\xe0\x00\x10JFIF fake jpeg content',
            name=f'imagem_{uuid.uuid4()}.jpg'
        )
    
    nome_original = factory.Faker('file_name', extension='jpg')
    tipo_mime = 'image/jpeg'
    categoria = "registro_ocorrencia_interno"


class AnexoTXTFactory(AnexoFactory):
    """Factory específica para anexos TXT"""
    
    @factory.lazy_attribute
    def arquivo(self):
        return ContentFile(
            b'Conteudo do arquivo de teste.',
            name=f'documento_{uuid.uuid4()}.txt'
        )
    
    nome_original = factory.Faker('file_name', extension='txt')
    tipo_mime = 'text/plain'


class AnexoDREFactory(AnexoFactory):
    """Factory específica para anexos do perfil DRE"""
    
    perfil = Anexo.PERFIL_DRE
    categoria = "relatorio_naapa"


class AnexoGIPEFactory(AnexoFactory):
    """Factory específica para anexos do perfil GIPE"""
    
    perfil = Anexo.PERFIL_GIPE
    categoria = "relatorio_supervisao_escolar"

