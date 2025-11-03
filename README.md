# Backend - Django + Django Rest Framework. SME GIPE MS Anexo Intercorrencia

## 🥞 Stack
- [Python v3.12](https://www.python.org/doc/)
- [Django v5.2.6](https://www.djangoproject.com/start/)
- [Django Rest Framework v3.16.1](https://www.django-rest-framework.org/)
- [Postgres v16.4](https://www.postgresql.org/docs/)
- [Django MinIO v4.1.0](https://www.postgresql.org/docs/)
- [Pytest v8.4.2](https://docs.pytest.org/en/stable/)

## 📁 Estrutura do Projeto


```
SME-GIPE-MS-ANEXO-DA-INTERCORRENCIA/
├── config/                  # Configurações globais do projeto Django
│   ├── __init__.py
│   ├── settings.py          # Configurações principais do Django (apps, DB, middlewares, etc.)
│   ├── urls.py              # Rotas globais do projeto
│   └── wsgi.py              # Configuração para WSGI (servidores como Gunicorn)
│
├── anexos/                  # Aplicação principal (domínio de Anexos)
│   ├── __init__.py
│   ├── admin.py             # Integração com o Django Admin
│   ├── apps.py              # Configuração da app
│   ├── models.py            # Modelos de dados (ORM)
│   ├── serializers.py       # Serializadores DRF (validação + transformação dos modelos)
│   ├── views.py             # Views DRF (endpoints, regras de API)
│   ├── urls.py              # Rotas da app
│   └── migrations/          # Arquivos de migração do banco de dados
│
├── tests/                   # Testes automatizados com Pytest
│   ├── __init__.py
│   ├── conftest.py          # Fixtures globais de teste
│   └── test_healthcheck.py  # Teste inicial de saúde (Swagger disponível)
│
├── requirements/            # Dependências do projeto
│   ├── base.txt             # Dependências comuns a todos os ambientes
│   ├── local.txt            # Dependências extras para desenvolvimento e testes
│   └── production.txt       # Dependências extras para produção
│
├── .env.sample              # Exemplo de variáveis de ambiente
├── .gitignore               # Arquivos/pastas ignorados pelo Git
├── LICENSE                  # Licença do projeto
├── manage.py                # CLI principal do Django
├── README.md                # Documentação do projeto
└── docker-compose.yml       # Orquestração local com Docker
```

## 🛠️ Configurando o projeto

Primeiro, clone o projeto:

### 🔄 via HTTPS
    $ git clone https://github.com/prefeiturasp/SME-GIPE-MS-Anexo-da-Intercorrencia.git

### 🔐 via SSH
    $ git@github.com:prefeiturasp/SME-GIPE-MS-Anexo-da-Intercorrencia.git
    
### 🐍 Criando e ativando uma virtual env
    $ python -m venv venv
    $ source venv/bin/activate  # Linux/macOS
    $ # ou venv\Scripts\activate no Windows

### 📦 Instalando as dependências do projeto
    $ pip install -r requirements/local.txt 

### 🗃️ Criando um banco do dados PostgreSQL usando createdb ou utilizando seu client preferido (pgAdmin, DBeaver...)
    $ createdb --username=postgres <project_slug>

> **_IMPORTANTE:_** Crie na raiz do projeto o arquivo _.env_ com base no .env.sample.
> Depois, em um terminal digite export DJANGO_READ_DOT_ENV_FILE=True e todas as variáveis serão lidas.

### ⚙️ Rodando as migrações
    $ python manage.py migrate

### 🚀 Executando o projeto
    $ python manage.py runserver

Feito tudo isso, o projeto estará executando no endereço [localhost:8000/api-anexos/v1/](http://localhost:8000/api-anexos/v1/).

### 👑 Opcional: Criando um super usuário
    $ python manage.py createsuperuser

### 🧪 Executando os testes com Pytest
    $ pytest

### 🧪 Executando a cobertura dos testes
    $ coverage run -m pytest
    $ coverage report -m
    $ coverage html
    $ open htmlcov/index.html

### 📄 Licença
Este projeto está sob a licença GNU AFFERO GENERAL PUBLIC LICENSE - veja o arquivo [LICENSE](./LICENSE) para detalhes.