from drf_spectacular.extensions import OpenApiAuthenticationExtension

class RemoteJWTAuthScheme(OpenApiAuthenticationExtension):
    # caminho completo da sua classe de auth
    target_class = "anexos.auth.RemoteJWTAuthentication"
    # nome do esquema que aparecerá no Swagger (e que será referenciado em SECURITY)
    name = "Bearer"

    def get_security_definition(self, auto_schema):
        # define o esquema OpenAPI correspondente à sua auth
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
