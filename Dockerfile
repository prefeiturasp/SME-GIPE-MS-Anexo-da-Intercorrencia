# Etapa única para produção
FROM python:3.12-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Diretório da aplicação
WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copiar toda a pasta de requirements
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements/production.txt


# Copia o restante da aplicação
COPY . .

# Expõe a porta padrão do Gunicorn
EXPOSE 8000

# Comando de entrada
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
