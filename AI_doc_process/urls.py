"""
URL configuration for AI_doc_process project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.http import JsonResponse

# Swagger imports
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


# Health check endpoints
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def simple_health_check(request):
    """
    Ultra-simple health check for Railway
    """
    return JsonResponse({"status": "ok", "service": "running"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """
    Simple, fast, and dependency-free health check endpoint for Railway deployment.
    """
    return JsonResponse(
        {"status": "healthy", "message": "Application is up and running!"}
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def api_root(request):
    """
    API Root endpoint
    """
    return Response(
        {
            "message": "Welcome to AI Document Process API",
            "version": "1.0.0",
            "health_check": "/health/",
            "endpoints": {
                "auth": {
                    "register": "/api/auth/register/",
                    "login": "/api/auth/login/",
                    "logout": "/api/auth/logout/",
                    "refresh": "/api/auth/token/refresh/",
                    "verify": "/api/auth/verify-token/",
                },
                "profile": {
                    "profile": "/api/auth/profile/",
                    "change_password": "/api/auth/change-password/",
                },
                "documents": {
                    "upload": "/api/documents/upload/",
                    "list": "/api/documents/",
                    "detail": "/api/documents/{id}/",
                    "chunks": "/api/documents/{id}/chunks/",
                    "reprocess": "/api/documents/{id}/reprocess/",
                },
                "chat": {
                    "sessions": "/api/chat/sessions/",
                    "session_detail": "/api/chat/sessions/{id}/",
                    "session_messages": "/api/chat/sessions/{id}/messages/",
                    "message": "/api/chat/message/",
                    "clear_history": "/api/chat/clear-history/",
                },
                "analytics": {
                    "summary": "/api/analytics/summary/",
                    "usage": "/api/analytics/usage/",
                    "stats": "/api/analytics/stats/",
                    "refresh": "/api/analytics/refresh/",
                },
                "admin": "/admin/",
                "api_docs": "/swagger/",
            },
        }
    )


# Swagger Schema View
schema_view = get_schema_view(
    openapi.Info(
        title="AI Document Process API",
        default_version="v1",
        description="API documentation for AI Document Process",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@yourdomain.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("health/simple/", simple_health_check, name="simple_health_check"),
    path("admin/", admin.site.urls),
    path("api/", api_root, name="api_root"),
    path("api/auth/", include("accounts.urls")),
    path("api/documents/", include("documents.urls")),
    path("api/chat/", include("chat.urls")),
    path("api-auth/", include("rest_framework.urls")),  # DRF browsable API login
    # Swagger / ReDoc URLs
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("swagger.json", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger.yaml", schema_view.without_ui(cache_timeout=0), name="schema-yaml"),
]


# Serve media & static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]
