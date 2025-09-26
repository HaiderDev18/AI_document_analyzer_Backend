from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    # Document management endpoints
    path("upload/", views.DocumentUploadView.as_view(), name="upload"),
    path(
        "<uuid:document_id>/has-session/",
        views.DocumentHasSessionView.as_view(),
        name="document-has-session",
    ),
    path("", views.DocumentListView.as_view(), name="list"),
    path("<uuid:pk>/", views.DocumentDetailView.as_view(), name="detail"),
    path(
        "<uuid:session_id>/documents/",
        views.SessionDocumentsView.as_view(),
        name="session_documents",
    ),
    # path('<uuid:document_id>/reprocess/', views.reprocess_document, name='reprocess'),
    path(
        "session/<uuid:session_id>/risk-factors/",
        views.SessionRiskFactorsView.as_view(),
        name="session_risk_factors",
    ),
    path(
        "session/<uuid:session_id>/summaries/",
        views.SessionSummariesView.as_view(),
        name="session_summaries",
    ),
    path(
        "<uuid:document_id>/soft-delete/",
        views.DocumentSoftDeleteView.as_view(),
        name="document-soft-delete",
    ),
    path(
        "<uuid:document_id>/summary/",
        views.DocumentSummaryGenerator.as_view(),
        name="document-summary",
    ),
    path(
        "<uuid:document_id>/risk-factors/",
        views.RiskFactorsGenerator.as_view(),
        name="document-risk-factors",
    ),
]
