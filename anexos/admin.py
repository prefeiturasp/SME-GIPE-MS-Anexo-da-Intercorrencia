from django.contrib import admin
from django.utils.html import format_html
from anexos.models import Anexo


@admin.register(Anexo)
class AnexoAdmin(admin.ModelAdmin):
    list_display = (
        'nome_original_truncado', 'categoria_display_custom', 'perfil', 
        'tamanho_formatado', 'usuario_username', 'ativo', 'criado_em'
    )
    list_filter = ('perfil', 'categoria', 'ativo', 'criado_em')
    search_fields = (
        'nome_original', 'usuario_username', 'intercorrencia_uuid'
    )
    readonly_fields = (
        'uuid', 'nome_original', 'tamanho_bytes', 'tipo_mime',
        'tamanho_formatado', 'extensao', 'criado_em', 'atualizado_em',
        'excluido_em', 'excluido_por', 'preview_arquivo'
    )
    
    fieldsets = (
        ('Informações Principais', {
            'fields': (
                'uuid', 'intercorrencia_uuid', 'perfil', 'categoria'
            )
        }),
        ('Arquivo', {
            'fields': (
                'arquivo', 'preview_arquivo', 'nome_original', 
                'tamanho_bytes', 'tamanho_formatado', 'tipo_mime', 'extensao'
            )
        }),
        ('Usuário', {
            'fields': ('usuario_username', 'usuario_nome')
        }),
        ('Controle', {
            'fields': (
                'ativo', 'excluido_em', 'excluido_por',
                'criado_em', 'atualizado_em'
            )
        }),
    )
    
    def nome_original_truncado(self, obj):
        """Trunca nome do arquivo para exibição"""
        if len(obj.nome_original) > 50:
            return obj.nome_original[:47] + '...'
        return obj.nome_original
    nome_original_truncado.short_description = 'Arquivo'
    
    def categoria_display_custom(self, obj):
        """Exibe categoria com cor por perfil"""
        cores = {
            'diretor': '#3498db',
            'dre': '#2ecc71',
            'gipe': '#e74c3c'
        }
        cor = cores.get(obj.perfil, '#95a5a6')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            cor,
            obj.get_categoria_display()
        )
    categoria_display_custom.short_description = 'Categoria'
    
    def preview_arquivo(self, obj):
        """Mostra preview de imagens"""
        if obj.e_imagem and obj.arquivo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.arquivo.url
            )
        return '-'
    preview_arquivo.short_description = 'Preview'
