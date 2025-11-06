import os
from .modelo_base import ModeloBase
from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class Anexo(ModeloBase):
    """
    Modelo para armazenar anexos de intercorrências.
    Arquivos são salvos no MinIO.
    """
    # Perfis que podem anexar arquivos
    PERFIL_DIRETOR = "diretor"
    PERFIL_ASSISTENTE = "assistente"
    PERFIL_DRE = "dre"
    PERFIL_GIPE = "gipe"

    PERFIL_CHOICES = [
        (PERFIL_DIRETOR, "Diretor"),
        (PERFIL_ASSISTENTE, "Assistente"),
        (PERFIL_DRE, "DRE"),
        (PERFIL_GIPE, "GIPE"),
    ]

    # Categorias por perfil
    CATEGORIA_DIRETOR_CHOICES = [
        ("boletim_ocorrencia", "Boletim de ocorrência"),
        ("registro_ocorrencia_interno", "Registro de ocorrência interno"),
        ("protocolo_conselho_tutelar", "Protocolo do Conselho Tutelar"),
        ("instrucao_normativa_20_2020", "Instrução normativa 20/2020"),
    ]

    CATEGORIA_DRE_CHOICES = [
        ("relatorio_naapa", "Relatório do NAAPA"),
        ("relatorio_cefai", "Relatório do CEFAI"),
        ("relatorio_sts", "Relatório do STS"),
        ("relatorio_cpca", "Relatório do CPCA"),
        ("oficio_gcm", "Ofício Guarda Civil Metropolitana (GCM)"),
    ]

    CATEGORIA_GIPE_CHOICES = [
        ("boletim_ocorrencia", "Boletim de ocorrência"),
        ("registro_intercorrencia", "Registro de intercorrência"),
        ("protocolo_conselho_tutelar", "Protocolo Conselho Tutelar"),
        ("instrucao_normativa_20_2020", "Instrução Normativa 20/2020"),
        ("relatorio_naapa", "Relatório do NAAPA"),
        ("relatorio_supervisao_escolar", "Relatório da Supervisão Escolar"),
        ("relatorio_cefai", "Relatório do CEFAI"),
        ("relatorio_sts", "Relatório do STS"),
        ("relatorio_cpca", "Relatório do CPCA"),
        ("oficio_gcm", "Ofício Guarda Civil Metropolitana (GCM)"),
    ]

    # Todas as categorias combinadas
    CATEGORIA_CHOICES = (
        CATEGORIA_DIRETOR_CHOICES + CATEGORIA_DRE_CHOICES + CATEGORIA_GIPE_CHOICES
    )

    # Relacionamento com intercorrência (UUID externo)
    intercorrencia_uuid = models.UUIDField(
        verbose_name="UUID da Intercorrência",
        help_text="UUID da intercorrência no micro serviço de intercorrências",
        db_index=True,
    )

    # Perfil que anexou o arquivo
    perfil = models.CharField(
        max_length=20,
        choices=PERFIL_CHOICES,
        verbose_name="Perfil que anexou",
        help_text="Perfil do usuário que anexou o arquivo",
    )

    # Categoria do anexo
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIA_CHOICES,
        verbose_name="Categoria do anexo",
        help_text="Categoria/tipo do documento anexado",
    )

    # Arquivo
    arquivo = models.FileField(
        upload_to="anexos/%Y/%m/%d/",
        verbose_name="Arquivo",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpeg",
                    "jpg",
                    "png",  # Imagens
                    "mp4",  # Vídeo
                    "pdf",
                    "xlsx",
                    "docx",
                    "txt",  # Documentos
                ]
            )
        ],
    )

    # Metadados do arquivo
    nome_original = models.CharField(
        max_length=255, verbose_name="Nome original do arquivo"
    )

    tamanho_bytes = models.BigIntegerField(
        verbose_name="Tamanho do arquivo (bytes)",
        help_text="Tamanho do arquivo em bytes",
    )

    tipo_mime = models.CharField(
        max_length=100, verbose_name="Tipo MIME", help_text="Tipo MIME do arquivo"
    )

    # Informações do usuário
    usuario_username = models.CharField(
        max_length=150,
        verbose_name="Username do usuário",
        help_text="Username do usuário que anexou o arquivo",
    )

    usuario_nome = models.CharField(
        max_length=200, verbose_name="Nome do usuário", blank=True
    )

    # Controle
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se False, o arquivo foi 'excluído' logicamente",
    )

    excluido_em = models.DateTimeField(
        blank=True, null=True, verbose_name="Excluído em"
    )

    excluido_por = models.CharField(
        max_length=150, blank=True, verbose_name="Excluído por"
    )

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"
        indexes = [
            models.Index(fields=["intercorrencia_uuid", "perfil"]),
            models.Index(fields=["intercorrencia_uuid", "ativo"]),
            models.Index(fields=["usuario_username"]),
            models.Index(fields=["categoria"]),
        ]

    def __str__(self):
        return f"{self.nome_original} - {self.get_categoria_display()}"

    def clean(self):
        """Validações customizadas"""
        errors = {}

        # Validar categoria por perfil
        if self.perfil and self.categoria:
            categorias_validas = self.get_categorias_validas_por_perfil(self.perfil)
            if self.categoria not in [cat[0] for cat in categorias_validas]:
                errors["categoria"] = (
                    f"Categoria '{self.categoria}' não é válida para o perfil '{self.perfil}'."
                )

        # Validar tamanho do arquivo
        if self.arquivo and hasattr(self.arquivo, "size"):
            if self.arquivo.size > 10 * 1024 * 1024:  # 10MB
                errors["arquivo"] = "Arquivo muito grande. Tamanho máximo: 10MB."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Preencher metadados do arquivo
        if self.arquivo:
            if not self.nome_original:
                self.nome_original = os.path.basename(self.arquivo.name)

            if hasattr(self.arquivo, "size") and not self.tamanho_bytes:
                self.tamanho_bytes = self.arquivo.size

            if hasattr(self.arquivo, "content_type") and not self.tipo_mime:
                self.tipo_mime = self.arquivo.content_type

        super().save(*args, **kwargs)

    def excluir_logicamente(self, usuario_username):
        """Exclusão lógica do anexo"""
        self.ativo = False
        self.excluido_em = timezone.now()
        self.excluido_por = usuario_username
        self.save()

    @staticmethod
    def get_categorias_validas_por_perfil(perfil):
        """Retorna categorias válidas para um perfil"""
        if perfil == Anexo.PERFIL_DIRETOR or perfil == Anexo.PERFIL_ASSISTENTE:
            return Anexo.CATEGORIA_DIRETOR_CHOICES
        elif perfil == Anexo.PERFIL_DRE:
            return Anexo.CATEGORIA_DRE_CHOICES
        elif perfil == Anexo.PERFIL_GIPE:
            return Anexo.CATEGORIA_GIPE_CHOICES
        return []

    @staticmethod
    def get_tamanho_total_intercorrencia(intercorrencia_uuid):
        """Retorna tamanho total de anexos de uma intercorrência (em bytes)"""
        total = Anexo.objects.filter(
            intercorrencia_uuid=intercorrencia_uuid, ativo=True
        ).aggregate(total=models.Sum("tamanho_bytes"))["total"]

        return total or 0

    @staticmethod
    def pode_adicionar_anexo(intercorrencia_uuid, tamanho_novo_arquivo):
        """Verifica se pode adicionar um novo anexo sem ultrapassar o limite"""
        LIMITE_TOTAL = 10 * 1024 * 1024  # 10MB

        tamanho_atual = Anexo.get_tamanho_total_intercorrencia(intercorrencia_uuid)
        tamanho_final = tamanho_atual + tamanho_novo_arquivo

        return tamanho_final <= LIMITE_TOTAL

    @property
    def tamanho_formatado(self):
        """Retorna tamanho formatado (KB, MB)"""
        
        if self and self.tamanho_bytes is not None:
            
            if self.tamanho_bytes < 1024:
                return f"{self.tamanho_bytes} bytes"
            elif self.tamanho_bytes < 1024 * 1024:
                return f"{self.tamanho_bytes / 1024:.2f} KB"
            else:
                return f"{self.tamanho_bytes / (1024 * 1024):.2f} MB"
        else:
            return "0 bytes"

    @property
    def extensao(self):
        """Retorna extensão do arquivo"""
        return os.path.splitext(self.nome_original)[1].lower()

    @property
    def e_imagem(self):
        """Verifica se é imagem"""
        return self.extensao in [".jpg", ".jpeg", ".png"]

    @property
    def e_video(self):
        """Verifica se é vídeo"""
        return self.extensao == ".mp4"

    @property
    def e_documento(self):
        """Verifica se é documento"""
        return self.extensao in [".pdf", ".xlsx", ".docx", ".txt"]

