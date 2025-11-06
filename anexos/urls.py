from django.urls import path, include
from rest_framework.routers import DefaultRouter
from anexos.api.views.anexos_viewset import AnexoViewSet

router = DefaultRouter()
router.register(r'anexos', AnexoViewSet, basename='anexo')

urlpatterns = [
    path('', include(router.urls)),
]
