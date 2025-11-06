"""
Storage customizado para MinIO usando minio SDK diretamente
"""
import logging
from django.core.files.storage import Storage
from django.core.files.base import File
from django.conf import settings
from django.utils.deconstruct import deconstructible
from minio import Minio
from minio.error import S3Error
from io import BytesIO
from urllib.parse import urljoin
from datetime import timedelta
import os


@deconstructible
class MinioStorage(Storage):
    """
    Storage customizado para MinIO
    """
    
    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.use_https = settings.MINIO_USE_HTTPS
        self.base_url = settings.MINIO_STORAGE_MEDIA_BASE_URL
        self.expires = settings.MINIO_STORAGE_PRESIGNED_URL_TTL

        logger = logging.getLogger(__name__)
        logger.warning(f"MinioStorage initialized with endpoint: {self.endpoint}, bucket: {self.bucket_name}, expires: {self.expires} minutes")

        # Cliente MinIO
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.use_https
        )
        
        # Criar bucket se não existir
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Cria o bucket se não existir"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            print(f"Erro ao verificar/criar bucket: {e}")
    
    def _save(self, name, content):
        """Salva um arquivo no MinIO"""
        try:
            # Ler conteúdo do arquivo
            content.seek(0)
            file_data = content.read()
            file_size = len(file_data)
            
            # Upload para MinIO
            self.client.put_object(
                self.bucket_name,
                name,
                BytesIO(file_data),
                file_size,
                content_type=getattr(content, 'content_type', 'application/octet-stream')
            )
            
            return name
        except S3Error as e:
            raise IOError(f"Erro ao salvar arquivo no MinIO: {e}")
    
    def _open(self, name, mode='rb'):
        """Abre um arquivo do MinIO"""
        try:
            response = self.client.get_object(self.bucket_name, name)
            file_data = response.read()
            response.close()
            response.release_conn()
            
            return File(BytesIO(file_data), name)
        except S3Error as e:
            raise IOError(f"Erro ao abrir arquivo do MinIO: {e}")
    
    def delete(self, name):
        """Deleta um arquivo do MinIO"""
        try:
            self.client.remove_object(self.bucket_name, name)
        except S3Error as e:
            print(f"Erro ao deletar arquivo do MinIO: {e}")
    
    def exists(self, name):
        """Verifica se um arquivo existe no MinIO"""
        try:
            self.client.stat_object(self.bucket_name, name)
            return True
        except S3Error:
            return False
    
    def size(self, name):
        """Retorna o tamanho do arquivo"""
        try:
            stat = self.client.stat_object(self.bucket_name, name)
            return stat.size
        except S3Error:
            return 0
    
    def url(self, name):
        """Retorna a URL pré-assinada do arquivo"""
        try:
            # Gera URL pré-assinada válida por 1 hora
            url = self.client.presigned_get_object(
                self.bucket_name,
                name,
                expires=timedelta(minutes=int(self.expires))  # timedelta em minutos
            )
            return url
        except S3Error:
            return f"{self.base_url}/{self.bucket_name}/{name}"
    
    def get_valid_name(self, name):
        """Retorna um nome de arquivo válido"""
        return name
    
    def get_available_name(self, name, max_length=None):
        """Retorna um nome de arquivo disponível"""
        # Se o arquivo existe, gera um nome único adicionando um sufixo
        if self.exists(name):
            dir_name, file_name = os.path.split(name)
            file_root, file_ext = os.path.splitext(file_name)
            count = 1
            while self.exists(name):
                name = os.path.join(dir_name, f"{file_root}_{count}{file_ext}")
                count += 1
        
        return name
