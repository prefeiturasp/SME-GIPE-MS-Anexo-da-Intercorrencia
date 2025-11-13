import os
from venv import logger
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from anexos.models.anexo import Anexo
from anexos.services import intercorrencia_service
from anexos.services.intercorrencia_service import ExternalServiceError

class AnexoSerializer(serializers.ModelSerializer):
    """Serializer para criação e atualização de anexos"""
    
    # Campos adicionais read-only
    tamanho_formatado = serializers.CharField(
        read_only=True,
        help_text="Tamanho do arquivo formatado (ex: 2.5 MB)"
    )
    extensao = serializers.CharField(
        read_only=True,
        help_text="Extensão do arquivo (ex: pdf, jpg)"
    )
    e_imagem = serializers.BooleanField(
        read_only=True,
        help_text="Indica se o arquivo é uma imagem"
    )
    e_video = serializers.BooleanField(
        read_only=True,
        help_text="Indica se o arquivo é um vídeo"
    )
    e_documento = serializers.BooleanField(
        read_only=True,
        help_text="Indica se o arquivo é um documento"
    )
    categoria_display = serializers.CharField(
        source='get_categoria_display', 
        read_only=True,
        help_text="Nome amigável da categoria"
    )
    perfil_display = serializers.CharField(
        source='get_perfil_display', 
        read_only=True,
        help_text="Nome amigável do perfil"
    )
    
    # URL do arquivo (será preenchido pelo MinIO)
    arquivo_url = serializers.SerializerMethodField(
        help_text="URL completa para acesso ao arquivo"
    )
    
    class Meta:
        model = Anexo
        fields = (
            'id', 'uuid', 'intercorrencia_uuid', 'perfil', 'perfil_display',
            'categoria', 'categoria_display', 'arquivo', 'arquivo_url',
            'nome_original', 'tamanho_bytes', 'tamanho_formatado', 'tipo_mime',
            'extensao', 'e_imagem', 'e_video', 'e_documento',
            'usuario_username', 'usuario_nome', 'ativo',
            'criado_em', 'atualizado_em'
        )
        read_only_fields = (
            'id', 'uuid', 'nome_original', 'tamanho_bytes', 'tipo_mime',
            'usuario_username', 'usuario_nome', 'ativo',
            'criado_em', 'atualizado_em'
        )
    
    @extend_schema_field(OpenApiTypes.STR)
    def get_arquivo_url(self, obj):
        """Retorna URL do arquivo no MinIO"""
        if obj.arquivo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.arquivo.url)
        return None
    
    def _get_token_from_request(self):
        """Obtém o token do request. Retorna None se não disponível."""
        request = self.context.get('request')
        if not request or not hasattr(request, 'META'):
            return None
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        return auth_header.split(' ')[1]
    
    def validate_arquivo(self, value):
        """Valida o arquivo enviado"""
        # Validar tamanho do arquivo individual (máx 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                'Arquivo muito grande. Tamanho máximo permitido: 10MB.'
            )
        
        # Validar extensão
        extensao = value.name.split('.')[-1].lower()
        extensoes_permitidas = ['jpeg', 'jpg', 'png', 'mp4', 'pdf', 'xlsx', 'docx', 'txt']
        
        if extensao not in extensoes_permitidas:
            raise serializers.ValidationError(
                f'Extensão .{extensao} não permitida. '
                f'Extensões permitidas: {", ".join(extensoes_permitidas)}'
            )
        
        return value
    
    def validate_categoria(self, value):
        """Valida se a categoria é válida para o perfil"""
        perfil = self.initial_data.get('perfil') or (
            self.instance.perfil if self.instance else None
        )
        
        if perfil and value:
            categorias_validas = Anexo.get_categorias_validas_por_perfil(perfil)
            if value not in [cat[0] for cat in categorias_validas]:
                raise serializers.ValidationError(
                    f"Categoria '{value}' não é válida para o perfil '{perfil}'."
                )
        
        return value
    
    def validate(self, attrs):
        """Validações gerais"""
        # Validar limite total de 10MB por intercorrência
        if 'arquivo' in attrs and 'intercorrencia_uuid' in attrs:
            intercorrencia_uuid = attrs['intercorrencia_uuid']
            tamanho_arquivo = attrs['arquivo'].size
            
            if not Anexo.pode_adicionar_anexo(intercorrencia_uuid, tamanho_arquivo):
                tamanho_atual = Anexo.get_tamanho_total_intercorrencia(intercorrencia_uuid)
                tamanho_atual_mb = tamanho_atual / (1024 * 1024)
                
                raise serializers.ValidationError({
                    'arquivo': f'Limite de 10MB por intercorrência seria ultrapassado. '
                               f'Atualmente: {tamanho_atual_mb:.2f}MB de 10MB.'
                })
                
        # Validar intercorrência no serviço externo (apenas se token disponível)
        if 'intercorrencia_uuid' in attrs:
            token = self._get_token_from_request()
            
            # Só valida se o token estiver disponível (requisições via API)
            # Em testes unitários ou outros contextos, essa validação é pulada
            if token:
                try:
                    intercorrencia_uuid = attrs['intercorrencia_uuid']
                    intercorrencia = intercorrencia_service.get_detalhes_intercorrencia(
                        intercorrencia_uuid, 
                        token=token
                    )
                    logger.info(f"Detalhes da intercorrência obtidos: {intercorrencia}")
                except ExternalServiceError as e:
                    raise serializers.ValidationError({"detail": str(e)})

        return attrs
    
    def is_valid(self, raise_exception=False):
        
        valid = super().is_valid(raise_exception=False)
        if not valid:
            first_field, first_error_list = next(iter(self.errors.items()))
            message = first_error_list[0] if isinstance(first_error_list, list) else str(first_error_list)

            if isinstance(self._errors, dict) and "detail" in self._errors:
                error_dict = self._errors
            else:
                error_dict = {"detail": f"{first_field}: {message}"}

            self._errors = error_dict

            if raise_exception:
                raise serializers.ValidationError(self._errors)

        return valid
    
    def create(self, validated_data):
        """Cria um novo anexo preenchendo metadados do arquivo"""
        arquivo = validated_data.get('arquivo')
        
        if arquivo:
            # Preencher metadados que não vêm automaticamente
            if hasattr(arquivo, 'content_type'):
                validated_data['tipo_mime'] = arquivo.content_type
            if hasattr(arquivo, 'size'):
                validated_data['tamanho_bytes'] = arquivo.size
            if hasattr(arquivo, 'name'):
                validated_data['nome_original'] = os.path.basename(arquivo.name)
        
        return super().create(validated_data)


class AnexoListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagem"""
    
    categoria_display = serializers.CharField(
        source='get_categoria_display', 
        read_only=True,
        help_text="Nome amigável da categoria"
    )
    perfil_display = serializers.CharField(
        source='get_perfil_display', 
        read_only=True,
        help_text="Nome amigável do perfil"
    )
    tamanho_formatado = serializers.CharField(
        read_only=True,
        help_text="Tamanho do arquivo formatado (ex: 2.5 MB)"
    )
    extensao = serializers.CharField(
        read_only=True,
        help_text="Extensão do arquivo (ex: pdf, jpg)"
    )
    arquivo_url = serializers.SerializerMethodField(
        help_text="URL completa para acesso ao arquivo"
    )
    
    class Meta:
        model = Anexo
        fields = (
            'uuid', 'nome_original', 'categoria', 'categoria_display',
            'perfil', 'perfil_display', 'tamanho_formatado', 'extensao',
            'arquivo_url', 'criado_em', 'usuario_username'
        )
    
    @extend_schema_field(OpenApiTypes.STR)
    def get_arquivo_url(self, obj):
        """Retorna URL do arquivo no MinIO"""
        if obj.arquivo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.arquivo.url)
        return None


class CategoriasDisponiveisSerializer(serializers.Serializer):
    """Serializer para retornar categorias disponíveis por perfil"""
    
    perfil = serializers.ChoiceField(choices=Anexo.PERFIL_CHOICES)
    categorias = serializers.SerializerMethodField()
    
    def get_categorias(self, obj):
        """Retorna lista de categorias para o perfil"""
        perfil = obj.get('perfil')
        categorias = Anexo.get_categorias_validas_por_perfil(perfil)
        
        return [
            {
                'value': cat[0],
                'label': cat[1]
            }
            for cat in categorias
        ]
