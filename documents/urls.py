from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    # Upload
    path("upload/", views.DocumentUploadView.as_view(), name="upload"),
    # Collection & item
    path("", views.DocumentListView.as_view(), name="list"),
    path(
        "<uuid:pk>/", views.DocumentDetailView.as_view(), name="detail"
    ),  # DELETE here supports soft/hard via ?soft=
    # AI-generated content (POST)
    path(
        "<uuid:document_id>/summary/",
        views.DocumentSummaryView.as_view(),
        name="document-summary",
    ),
    path(
        "<uuid:document_id>/risk-factors/",
        views.RiskFactorsView.as_view(),
        name="document-risk-factors",
    ),
    # Session-scoped collections (prefixed with 'session/' to avoid UUID route collisions)
    path(
        "session/<uuid:session_id>/documents/",
        views.SessionDocumentsView.as_view(),
        name="session-documents",
    ),
    path(
        "session/<uuid:session_id>/risk-factors/",
        views.SessionRiskFactorsView.as_view(),
        name="session-risk-factors",
    ),
    path(
        "session/<uuid:session_id>/summaries/",
        views.SessionSummariesView.as_view(),
        name="session-summaries",
    ),
    path(
        "<uuid:document_id>/download/",
        views.DocumentDownloadView.as_view(),
        name="document-download",
    ),
]
