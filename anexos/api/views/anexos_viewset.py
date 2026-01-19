from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, StreamingHttpResponse, FileResponse
import requests
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes


from anexos.models.anexo import Anexo
from anexos.api.serializers.anexo_serializer import (
    AnexoSerializer,
    AnexoListSerializer,
    CategoriasDisponiveisSerializer,
)

import logging

logger = logging.getLogger(__name__)

class AnexoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar anexos de intercorrências.
    
    Endpoints:
    - GET    /anexos/                                              # Lista todos os anexos do usuário
    - POST   /anexos/                                              # Cria novo anexo
    - GET    /anexos/{uuid}/                                       # Detalhes de um anexo
    - DELETE /anexos/{uuid}/                                       # Exclui fisicamente um anexo
    - GET    /anexos/{uuid}/download/                              # Faz streaming do arquivo
    - GET    /anexos/{uuid}/url-download/                          # Gera URL pré-assinada para download
    - GET    /anexos/intercorrencia/{uuid}/                        # Lista anexos de uma intercorrência
    - GET    /anexos/intercorrencia/{uuid}/url-download-todos/     # URLs de download de todos os anexos
    - GET    /anexos/categorias-disponiveis/                       # Lista categorias por perfil
    - POST   /anexos/validar-limite/                               # Valida limite de tamanho
    """
    
    queryset = Anexo.objects.filter(ativo=True)
    serializer_class = AnexoSerializer
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    lookup_field = 'uuid'
    
    @extend_schema(
        summary="Listar anexos",
        description="Lista todos os anexos ativos. Pode ser filtrado por intercorrencia_uuid, perfil ou categoria.",
        parameters=[
            OpenApiParameter(
                name='intercorrencia_uuid',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filtrar por UUID da intercorrência',
                required=False
            ),
            OpenApiParameter(
                name='perfil',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=['diretor', 'assistente', 'dre', 'gipe', 'UE'],
                description=(
                    'Filtrar por perfil\n'
                    '- diretor\n'
                    '- assistente\n'
                    '- dre\n'
                    '- gipe\n'
                    '- UE (diretor + assistente)'
                ),
            ),
            OpenApiParameter(
                name='categoria',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filtrar por categoria',
                required=False
            ),
        ],
        responses={200: AnexoListSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        """Lista anexos com filtros opcionais"""
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        """Filtra anexos baseado no perfil do usuário"""
        qs = super().get_queryset()
        
        # Filtros por query params
        intercorrencia_uuid = self.request.query_params.get('intercorrencia_uuid')
        perfil = self.request.query_params.get('perfil')
        categoria = self.request.query_params.get('categoria')
        
        if intercorrencia_uuid:
            qs = qs.filter(intercorrencia_uuid=intercorrencia_uuid)
        
        if perfil:
            if perfil.upper() == 'UE':
                qs = qs.filter(perfil__in=['diretor', 'assistente'])
            else:
                qs = qs.filter(perfil=perfil)

        if categoria:
            qs = qs.filter(categoria=categoria)
        
        return qs
    
    def get_serializer_class(self):
        """Retorna serializer apropriado"""
        if self.action == 'list':
            return AnexoListSerializer
        return AnexoSerializer
    
    @extend_schema(
        summary="Criar novo anexo",
        description="""
        Cria um novo anexo para uma intercorrência.
        
        **Regras de validação:**
        - Tamanho máximo do arquivo: 10MB
        - Tamanho máximo total por intercorrência: 10MB
        - Extensões permitidas: jpeg, jpg, png, mp4, pdf, xlsx, docx, txt
        - A categoria deve ser válida para o perfil selecionado
        
        **Campos obrigatórios:**
        - intercorrencia_uuid: UUID da intercorrência
        - perfil: Perfil do usuário (diretor, assistente, dre, gipe)
        - categoria: Categoria do documento
        - arquivo: Arquivo a ser enviado
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'intercorrencia_uuid': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': 'UUID da intercorrência'
                    },
                    'perfil': {
                        'type': 'string',
                        'enum': ['diretor', 'assistente', 'dre', 'gipe'],
                        'description': 'Perfil do usuário que está anexando'
                    },
                    'categoria': {
                        'type': 'string',
                        'description': 'Categoria do documento (deve ser válida para o perfil)'
                    },
                    'arquivo': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Arquivo a ser enviado (máx 10MB)'
                    }
                },
                'required': ['intercorrencia_uuid', 'perfil', 'categoria', 'arquivo']
            }
        },
        responses={
            201: AnexoSerializer,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Exemplo de criação de anexo',
                description='Exemplo de como criar um anexo',
                value={
                    'intercorrencia_uuid': '123e4567-e89b-12d3-a456-426614174000',
                    'perfil': 'diretor',
                    'categoria': 'boletim_ocorrencia',
                },
                request_only=True,
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        """Cria um novo anexo com upload de arquivo"""
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        summary="Atualizar anexo completamente",
        description="""
        Atualiza todos os campos de um anexo existente (PUT).
        
        **Importante:**
        - Este endpoint substitui TODOS os campos do anexo
        - Todos os campos obrigatórios devem ser enviados
        - O arquivo pode ser substituído enviando um novo arquivo
        - Se não enviar novo arquivo, o arquivo atual será mantido
        
        **Campos obrigatórios:**
        - intercorrencia_uuid: UUID da intercorrência
        - perfil: Perfil do usuário (diretor, assistente, dre, gipe)
        - categoria: Categoria do documento
        
        **Campos opcionais:**
        - arquivo: Novo arquivo (se quiser substituir o atual)
        
        **Regras de validação:**
        - Tamanho máximo do arquivo: 10MB
        - Extensões permitidas: jpeg, jpg, png, mp4, pdf, xlsx, docx, txt
        - A categoria deve ser válida para o perfil selecionado
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'intercorrencia_uuid': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': 'UUID da intercorrência'
                    },
                    'perfil': {
                        'type': 'string',
                        'enum': ['diretor', 'assistente', 'dre', 'gipe'],
                        'description': 'Perfil do usuário'
                    },
                    'categoria': {
                        'type': 'string',
                        'description': 'Categoria do documento'
                    },
                    'arquivo': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Novo arquivo (opcional - mantém o atual se não enviado)'
                    }
                },
                'required': ['intercorrencia_uuid', 'perfil', 'categoria']
            }
        },
        responses={
            200: AnexoSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
    def update(self, request, *args, **kwargs):
        """Atualiza completamente um anexo (PUT)"""
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Atualizar anexo parcialmente",
        description="""
        Atualiza apenas alguns campos de um anexo existente (PATCH).
        
        **Vantagem do PATCH sobre PUT:**
        - Você pode atualizar apenas os campos que desejar
        - Não é necessário enviar todos os campos obrigatórios
        - Os campos não enviados permanecem inalterados
        
        **Campos que podem ser atualizados:**
        - intercorrencia_uuid: Mudar o UUID da intercorrência
        - perfil: Alterar o perfil
        - categoria: Alterar a categoria (deve ser válida para o perfil)
        - arquivo: Substituir o arquivo atual
        
        **Exemplos de uso:**
        - Mudar apenas a categoria: envie apenas `categoria`
        - Substituir apenas o arquivo: envie apenas `arquivo`
        - Mudar perfil e categoria: envie `perfil` e `categoria`
        
        **Regras de validação:**
        - Tamanho máximo do arquivo: 10MB
        - Extensões permitidas: jpeg, jpg, png, mp4, pdf, xlsx, docx, txt
        - Se alterar perfil, a categoria deve ser válida para o novo perfil
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'intercorrencia_uuid': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': 'UUID da intercorrência (opcional)'
                    },
                    'perfil': {
                        'type': 'string',
                        'enum': ['diretor', 'assistente', 'dre', 'gipe'],
                        'description': 'Perfil do usuário (opcional)'
                    },
                    'categoria': {
                        'type': 'string',
                        'description': 'Categoria do documento (opcional)'
                    },
                    'arquivo': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Novo arquivo para substituir o atual (opcional)'
                    }
                }
            }
        },
        responses={
            200: AnexoSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
    def partial_update(self, request, *args, **kwargs):
        """Atualiza parcialmente um anexo (PATCH)"""
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Obter detalhes de um anexo",
        description="""
        Retorna todos os detalhes de um anexo específico.
        
        **Informações retornadas:**
        - Metadados do anexo (UUID, nome, tamanho, tipo)
        - Informações da intercorrência
        - Perfil e categoria
        - URL do arquivo
        - Propriedades úteis (é imagem?, é vídeo?, etc.)
        - Dados de auditoria (criado em, usuário)
        """,
        responses={
            200: AnexoSerializer,
            404: OpenApiTypes.OBJECT,
        }
    )
    def retrieve(self, request, *args, **kwargs):
        """Retorna detalhes de um anexo específico"""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Excluir anexo",
        description="""
        Exclui permanentemente um anexo do sistema.
        
        **Importante:**
        - Esta ação é IRREVERSÍVEL
        - O arquivo físico será removido do MinIO
        - O registro será removido do banco de dados
        - Não há exclusão lógica (soft delete)
        
        **O que acontece:**
        1. Remove o arquivo físico do storage (MinIO)
        2. Remove o registro do banco de dados
        3. Registra a operação nos logs
        
        **Resposta de sucesso:**
        - Status 204 No Content
        - Corpo vazio (sem conteúdo)
        """,
        responses={
            204: None,
            404: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        }
    )
    def destroy(self, request, *args, **kwargs):
        """
        DELETE /anexos/{uuid}/
        Exclui o anexo do banco de dados e remove o arquivo físico do MinIO
        """
        anexo = self.get_object()
        
        # Log da exclusão
        logger.info(
            f"Iniciando exclusão do anexo {anexo.uuid} "
            f"({anexo.nome_original}) por usuário {request.user.username}"
        )
        
        # Armazenar informações antes de deletar
        arquivo_path = anexo.arquivo.name if anexo.arquivo else None
        anexo_uuid = anexo.uuid
        nome_arquivo = anexo.nome_original
        
        try:
            # Excluir arquivo físico do MinIO se existir
            if arquivo_path:
                try:
                    anexo.arquivo.delete(save=False)
                    logger.info(
                        f"Arquivo físico {arquivo_path} excluído do MinIO "
                        f"para anexo {anexo_uuid}"
                    )
                except Exception as e:
                    logger.error(
                        f"Erro ao excluir arquivo físico {arquivo_path} do MinIO "
                        f"para anexo {anexo_uuid}: {str(e)}"
                    )
                    # Continua com a exclusão do registro mesmo se falhar a exclusão do arquivo
            
            # Excluir registro do banco de dados
            anexo.delete()
            
            logger.info(
                f"Anexo {anexo_uuid} ({nome_arquivo}) excluído com sucesso "
                f"por usuário {request.user.username}"
            )
            
            return Response(
                {
                    'detail': 'Anexo excluído com sucesso.',
                    'uuid': str(anexo_uuid),
                    'nome_arquivo': nome_arquivo
                },
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            logger.error(
                f"Erro ao excluir anexo {anexo_uuid}: {str(e)}"
            )
            return Response(
                {'detail': 'Erro ao excluir anexo. Tente novamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        """Preenche dados do usuário autenticado"""
        user = self.request.user
        
        serializer.save(
            usuario_username=user.username,
            usuario_nome=getattr(user, 'name', None)
        )
        
        logger.info(
            f"Anexo criado: {serializer.instance.uuid} por {user.username}"
        )
    
    @action(detail=False, methods=['get'], url_path='intercorrencia/(?P<intercorrencia_uuid>[^/.]+)')
    def por_intercorrencia(self, request, intercorrencia_uuid=None):
        """
        GET /anexos/intercorrencia/{uuid}/
        Lista todos os anexos de uma intercorrência específica
        """
        anexos = self.get_queryset().filter(
            intercorrencia_uuid=intercorrencia_uuid
        )
        
        # Ordenar por perfil e categoria
        anexos = anexos.order_by('perfil', 'categoria', '-criado_em')
        
        serializer = AnexoListSerializer(
            anexos, many=True, context={'request': request}
        )
        
        return Response({
            'count': anexos.count(),
            'intercorrencia_uuid': intercorrencia_uuid,
            'anexos': serializer.data
        })
    
    
    @extend_schema(
        summary="Listar categorias disponíveis por perfil",
        description=(
            "Retorna as categorias de anexos disponíveis para um determinado perfil de usuário.\n\n"
            "**Perfis válidos:**\n"
            "- `diretor`: Diretor de escola\n"
            "- `assistente`: Assistente de diretor\n"
            "- `dre`: Diretor Regional de Educação\n"
            "- `gipe`: Gerência de Infraestrutura Predial e Escolar\n\n"
            "**Categorias disponíveis:**\n"
            "- Cada perfil tem acesso a categorias específicas de documentos\n"
            "- As categorias são definidas pela regra de negócio do sistema\n"
            "- Útil para popular dropdowns e validar categorias antes de criar anexos"
        ),
        parameters=[
            OpenApiParameter(
                name='perfil',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Perfil do usuário',
                enum=['diretor', 'assistente', 'dre', 'gipe'],
                examples=[
                    OpenApiExample(
                        'Diretor',
                        value='diretor',
                        description='Categorias disponíveis para diretor de escola'
                    ),
                    OpenApiExample(
                        'Assistente',
                        value='assistente',
                        description='Categorias disponíveis para assistente de diretor'
                    ),
                    OpenApiExample(
                        'DRE',
                        value='dre',
                        description='Categorias disponíveis para DRE'
                    ),
                    OpenApiExample(
                        'GIPE',
                        value='gipe',
                        description='Categorias disponíveis para GIPE'
                    ),
                ]
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'perfil': {
                        'type': 'string',
                        'description': 'Perfil consultado'
                    },
                    'categorias': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'value': {
                                    'type': 'string',
                                    'description': 'Valor da categoria (usado no campo categoria do anexo)'
                                },
                                'label': {
                                    'type': 'string',
                                    'description': 'Rótulo amigável da categoria (para exibição)'
                                }
                            }
                        }
                    }
                },
                'example': {
                    'perfil': 'diretor',
                    'categorias': [
                        {'value': 'fotos', 'label': 'Fotos'},
                        {'value': 'documentos', 'label': 'Documentos'},
                        {'value': 'orcamentos', 'label': 'Orçamentos'}
                    ]
                }
            },
            400: OpenApiTypes.OBJECT
        },
        tags=['Anexos']
    )
    @action(detail=False, methods=['get'], url_path='categorias-disponiveis')
    def categorias_disponiveis(self, request):
        """
        GET /anexos/categorias-disponiveis/?perfil=diretor
        Retorna categorias disponíveis para um perfil
        """
        perfil = request.query_params.get('perfil')
        
        if not perfil:
            return Response(
                {'detail': 'Parâmetro perfil é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if perfil not in dict(Anexo.PERFIL_CHOICES):
            return Response(
                {'detail': f'Perfil {perfil} inválido. Valores válidos: diretor, assistente, dre, gipe'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        categorias = Anexo.get_categorias_validas_por_perfil(perfil)
        
        return Response({
            'perfil': perfil,
            'categorias': [
                {'value': cat[0], 'label': cat[1]}
                for cat in categorias
            ]
        })
        
    @extend_schema(
        summary="Validar limite de tamanho",
        description=(
            "Valida se um novo arquivo pode ser adicionado a uma intercorrência "
            "sem ultrapassar o limite de 10MB por intercorrência.\n\n"
            "**Regras de Validação:**\n"
            "- Tamanho total dos anexos de uma intercorrência não pode ultrapassar 10MB\n"
            "- Retorna informações sobre tamanho atual, novo arquivo e total final\n"
            "- Útil para validação antes de fazer upload de arquivo\n\n"
            "**Exemplo de uso:**\n"
            "Antes de fazer upload de um arquivo de 2MB, consulte este endpoint para "
            "verificar se não ultrapassará o limite."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'intercorrencia_uuid': {
                        'type': 'string',
                        'format': 'uuid',
                        'description': 'UUID da intercorrência',
                        'example': 'e277e19b-3f8f-445e-91d0-0decdf964937'
                    },
                    'tamanho_bytes': {
                        'type': 'integer',
                        'description': 'Tamanho do arquivo em bytes',
                        'example': 2048000,
                        'minimum': 1
                    }
                },
                'required': ['intercorrencia_uuid', 'tamanho_bytes']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'pode_adicionar': {
                        'type': 'boolean',
                        'description': 'Se o arquivo pode ser adicionado sem ultrapassar o limite'
                    },
                    'tamanho_atual_mb': {
                        'type': 'number',
                        'description': 'Tamanho total atual dos anexos em MB'
                    },
                    'tamanho_novo_arquivo_mb': {
                        'type': 'number',
                        'description': 'Tamanho do novo arquivo em MB'
                    },
                    'tamanho_final_mb': {
                        'type': 'number',
                        'description': 'Tamanho total que ficará após adicionar o arquivo em MB'
                    },
                    'limite_mb': {
                        'type': 'number',
                        'description': 'Limite máximo permitido em MB',
                        'example': 10.0
                    },
                    'mensagem': {
                        'type': 'string',
                        'description': 'Mensagem descritiva do resultado'
                    }
                },
                'example': {
                    'pode_adicionar': True,
                    'tamanho_atual_mb': 3.5,
                    'tamanho_novo_arquivo_mb': 2.0,
                    'tamanho_final_mb': 5.5,
                    'limite_mb': 10.0,
                    'mensagem': 'OK'
                }
            },
            400: OpenApiTypes.OBJECT
        },
        tags=['Anexos']
    )
    @action(
        detail=False, 
        methods=['post'], 
        url_path='validar-limite',
        parser_classes=[JSONParser]  # Aceita apenas JSON neste endpoint
    )
    def validar_limite(self, request):
        """
        POST /anexos/validar-limite/
        Valida se um arquivo pode ser adicionado sem ultrapassar o limite
        
        Content-Type: application/json
        
        Body: {
            "intercorrencia_uuid": "...",
            "tamanho_bytes": 1024000
        }
        """
        
        
        intercorrencia_uuid = request.data.get('intercorrencia_uuid')
        tamanho_bytes = request.data.get('tamanho_bytes')
        
        if not intercorrencia_uuid or not tamanho_bytes:
            return Response(
                {'detail': 'intercorrencia_uuid e tamanho_bytes são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pode_adicionar = Anexo.pode_adicionar_anexo(
            intercorrencia_uuid, int(tamanho_bytes)
        )
        
        tamanho_atual = Anexo.get_tamanho_total_intercorrencia(intercorrencia_uuid)
        tamanho_atual_mb = tamanho_atual / (1024 * 1024)
        tamanho_novo_mb = int(tamanho_bytes) / (1024 * 1024)
        tamanho_final_mb = (tamanho_atual + int(tamanho_bytes)) / (1024 * 1024)
        
        return Response({
            'pode_adicionar': pode_adicionar,
            'tamanho_atual_mb': round(tamanho_atual_mb, 2),
            'tamanho_novo_arquivo_mb': round(tamanho_novo_mb, 2),
            'tamanho_final_mb': round(tamanho_final_mb, 2),
            'limite_mb': 10.0,
            'mensagem': 'OK' if pode_adicionar else 'Limite de 10MB seria ultrapassado'
        })
    
    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, uuid=None):
        """
        GET /anexos/{uuid}/download/
        Faz streaming do arquivo do MinIO através do Django
        
        Query params:
        - inline=true: Visualiza no navegador (para imagens/PDFs)
        - inline=false ou ausente: Força download
        
        A URL do MinIO é pré-assinada internamente, mas o download 
        passa pelo Django para evitar conflitos de autenticação.
        """
        anexo = self.get_object()
        
        # Verificar se o arquivo existe
        if not anexo.arquivo:
            return Response(
                {'detail': 'Anexo não possui arquivo associado.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Gera URL pré-assinada através do storage do MinIO
            url_download = anexo.arquivo.url
            
            # Verificar se é para visualizar inline ou fazer download
            inline = request.query_params.get('inline', 'false').lower() == 'true'
            
            logger.info(
                f"Iniciando {'visualização' if inline else 'download'} do anexo {anexo.uuid} "
                f"({anexo.nome_original}) por usuário {request.user.username}"
            )
            
            # Faz requisição ao MinIO sem headers de autenticação
            minio_response = requests.get(url_download, stream=True)
            minio_response.raise_for_status()
            
            # Determinar content type
            content_type = anexo.tipo_mime or 'application/octet-stream'
            
            # Retorna o arquivo como streaming response
            file_response = StreamingHttpResponse(
                minio_response.iter_content(chunk_size=8192),
                content_type=content_type
            )
            
            # Headers para controlar como o navegador trata o arquivo
            if inline:
                # Visualizar no navegador (imagens, PDFs, etc)
                file_response['Content-Disposition'] = f'inline; filename="{anexo.nome_original}"'
            else:
                # Forçar download
                file_response['Content-Disposition'] = f'attachment; filename="{anexo.nome_original}"'
            
            file_response['Content-Length'] = str(anexo.tamanho_bytes)
            file_response['Cache-Control'] = 'private, max-age=3600'  # Cache por 1 hora
            
            return file_response
            
        except requests.RequestException as e:
            logger.error(
                f"Erro ao fazer download do MinIO para anexo {anexo.uuid}: {str(e)}"
            )
            return Response(
                {'detail': 'Erro ao fazer download do arquivo. Tente novamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(
                f"Erro ao processar download para anexo {anexo.uuid}: {str(e)}"
            )
            return Response(
                {'detail': 'Erro ao processar download. Tente novamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='url-download')
    def url_download(self, request, uuid=None):
        """
        GET /anexos/{uuid}/url-download/
        Gera URL pré-assinada temporária para download do anexo do MinIO
        
        A URL gerada expira em 1 hora e permite acesso direto ao arquivo.
        """
        anexo = self.get_object()
        
        # Verificar se o arquivo existe
        if not anexo.arquivo:
            return Response(
                {'detail': 'Anexo não possui arquivo associado.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Gera URL pré-assinada através do storage do MinIO
            # O método url() já está configurado para gerar URLs com expiração
            url_download = anexo.arquivo.url
            
            logger.info(
                f"URL de download gerada para anexo {anexo.uuid} "
                f"por usuário {request.user.username}"
            )
            
            return Response({
                'uuid': anexo.uuid,
                'nome_arquivo': anexo.nome_original,
                'tamanho_bytes': anexo.tamanho_bytes,
                'tamanho_formatado': anexo.tamanho_formatado,
                'tipo_mime': anexo.tipo_mime,
                'url_download': url_download,
                'expira_em': '1 hora',
                'categoria': anexo.get_categoria_display(),
                'perfil': anexo.get_perfil_display(),
            })
            
        except Exception as e:
            logger.error(
                f"Erro ao gerar URL de download para anexo {anexo.uuid}: {str(e)}"
            )
            return Response(
                {'detail': 'Erro ao gerar URL de download. Tente novamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='intercorrencia/(?P<intercorrencia_uuid>[^/.]+)/url-download-todos')
    def url_download_todos(self, request, intercorrencia_uuid=None):
        """
        GET /anexos/intercorrencia/{uuid}/url-download-todos/
        Retorna URLs públicas pré-assinadas para download de todos os anexos de uma intercorrência
        
        As URLs geradas expiram em 1 hora e permitem acesso direto aos arquivos.
        Útil para download em lote ou integração com outros sistemas.
        """
        anexos = self.get_queryset().filter(
            intercorrencia_uuid=intercorrencia_uuid
        )
        
        if not anexos.exists():
            return Response(
                {
                    'detail': 'Nenhum anexo encontrado para esta intercorrência.',
                    'intercorrencia_uuid': intercorrencia_uuid,
                    'count': 0,
                    'anexos': []
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Ordenar por perfil e categoria
        anexos = anexos.order_by('perfil', 'categoria', '-criado_em')
        
        anexos_com_urls = []
        erros = []
        
        for anexo in anexos:
            try:
                # Verificar se o anexo possui arquivo
                if not anexo.arquivo:
                    erros.append({
                        'uuid': str(anexo.uuid),
                        'nome_arquivo': anexo.nome_original,
                        'erro': 'Anexo não possui arquivo associado'
                    })
                    continue
                
                # Gerar URL pré-assinada
                url_download = anexo.arquivo.url
                
                anexos_com_urls.append({
                    'uuid': str(anexo.uuid),
                    'nome_arquivo': anexo.nome_original,
                    'tamanho_bytes': anexo.tamanho_bytes,
                    'tamanho_formatado': anexo.tamanho_formatado,
                    'tipo_mime': anexo.tipo_mime,
                    'categoria': anexo.get_categoria_display(),
                    'categoria_value': anexo.categoria,
                    'perfil': anexo.get_perfil_display(),
                    'perfil_value': anexo.perfil,
                    'url_download': url_download,
                    'criado_em': anexo.criado_em,
                    'usuario_nome': anexo.usuario_nome or anexo.usuario_username,
                })
                
            except Exception as e:
                logger.error(
                    f"Erro ao gerar URL para anexo {anexo.uuid}: {str(e)}"
                )
                erros.append({
                    'uuid': str(anexo.uuid),
                    'nome_arquivo': anexo.nome_original,
                    'erro': 'Erro ao gerar URL de download'
                })
        
        logger.info(
            f"URLs de download geradas para {len(anexos_com_urls)} anexos "
            f"da intercorrência {intercorrencia_uuid} por usuário {request.user.username}"
        )
        
        response_data = {
            'intercorrencia_uuid': intercorrencia_uuid,
            'count': len(anexos_com_urls),
            'total_anexos': anexos.count(),
            'anexos': anexos_com_urls,
            'expira_em': '1 hora',
        }
        
        # Incluir erros se houver
        if erros:
            response_data['erros'] = erros
            response_data['count_erros'] = len(erros)
        
        return Response(response_data)