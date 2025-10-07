import json
import tempfile
import os
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from .models import Document
import logging
from .serializers import (
    DocumentUploadSerializer,
    DocumentSerializer,
    DocumentListSerializer,
)
from chat.models import ChatSession
from chat.serializers import ChatSessionSerializer
from .services.document_processor import extract_text_from_files
from .services.openai_service import OpenAIService
from .services.pinecone_service import PineconeService


class DocumentUploadView(generics.CreateAPIView):
    serializer_class = DocumentUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        session_id = request.data.get("session_id")
        if session_id:
            session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        else:
            session = ChatSession.objects.create(user=request.user)

        files = request.FILES.getlist("files") or (
            [request.FILES["file"]] if "file" in request.FILES else []
        )
        if not files:
            return Response(
                {"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        created_docs = []
        results = []
        with transaction.atomic():
            for f in files:
                s = self.get_serializer(
                    data={"file": f, "title": request.data.get("title", "")},
                    context={"request": request, "session": session},
                )
                try:
                    s.is_valid(raise_exception=True)
                    doc = s.save()
                    created_docs.append(doc)
                    results.append(
                        {
                            "file": f.name,
                            "document_id": str(doc.id),
                            "status": "accepted",
                        }
                    )
                except Exception as e:
                    return Response(
                        {"error": f"Failed to accept {f.name}: {e}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        for doc in created_docs:
            self._process_document(doc, session.namespace)

        return Response(
            {
                "message": f"Successfully uploaded {len(created_docs)} document(s).",
                "documents": DocumentSerializer(created_docs, many=True).data,
                "session": {
                    "id": str(session.id),
                    "title": session.title,
                    "namespace": session.namespace,
                    "created_at": session.created_at,
                },
                "results": results,
            },
            status=status.HTTP_201_CREATED,
        )

    def _process_document(self, document: Document, namespace: str):
        if document.status not in (Document.STATUS_PENDING, Document.STATUS_FAILED):
            return
        document.status = Document.STATUS_PROCESSING
        document.processing_error = ""
        document.save(update_fields=["status", "processing_error", "updated_at"])

        asset = document.asset
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=f".{document.file_ext}" or "")
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(asset.blob)

            text = extract_text_from_files([tmp_path])

            PineconeService(namespace=namespace).engine.main(
                text=text,
                file_name=document.file_name,
                file_path=f"db://{document.id}",
                user=document.user,
            )

            document.status = Document.STATUS_COMPLETED
            document.save(update_fields=["status", "updated_at"])
        except Exception as e:
            document.status = Document.STATUS_FAILED
            document.processing_error = str(e)
            document.save(update_fields=["status", "processing_error", "updated_at"])
            raise
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


class DocumentSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, document_id):
        doc = get_object_or_404(
            Document, id=document_id, user=request.user, deleted_at__isnull=True
        )
        if doc.status != Document.STATUS_COMPLETED:
            return Response(
                {"error": "Document is not completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract on demand from DB bytes (no persistence of raw_text)
        asset = doc.asset
        fd, tmp_path = tempfile.mkstemp(suffix=f".{doc.file_ext}" or "")
        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(asset.blob)
            text = extract_text_from_files([tmp_path])
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        summary, _ = OpenAIService().generate_summary(text)
        doc.summary = summary or ""
        doc.save(update_fields=["summary", "updated_at"])
        return Response(
            {
                "document_id": str(doc.id),
                "title": doc.title,
                "session_id": str(doc.session.id) if doc.session else None,
                "summary": doc.summary,
            },
            status=status.HTTP_200_OK,
        )


class RiskFactorsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, document_id):
        doc = get_object_or_404(
            Document, id=document_id, user=request.user, deleted_at__isnull=True
        )
        if doc.status != Document.STATUS_COMPLETED:
            return Response(
                {"error": "Document is not completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset = doc.asset
        fd, tmp_path = tempfile.mkstemp(suffix=f".{doc.file_ext}" or "")
        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(asset.blob)
            text = extract_text_from_files([tmp_path])
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        rf_json, _ = OpenAIService().generate_risk_factors(text)
        try:
            risk = json.loads(rf_json)
        except Exception:
            risk = {"risk_factors": []}
        doc.risk_factors = risk
        doc.save(update_fields=["risk_factors", "updated_at"])
        return Response(
            {
                "document_id": str(doc.id),
                "title": doc.title,
                "session_id": str(doc.session.id) if doc.session else None,
                "risk_factors": risk,
            },
            status=status.HTTP_200_OK,
        )


class DocumentListView(generics.ListAPIView):
    serializer_class = DocumentListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = (
            Document.all_objects
            if getattr(self.request.user, "role", "user") == "admin"
            else Document.objects
        )
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().order_by("-created_at")
        page = self.paginate_queryset(queryset)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(queryset, many=True)
        return Response(ser.data)


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects

    def retrieve(self, request, *args, **kwargs):
        doc = self.get_object()
        doc_data = self.get_serializer(doc).data
        resp = {"document": doc_data}
        if doc.session:
            resp["session"] = ChatSessionSerializer(doc.session).data
        return Response(resp, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        doc = self.get_object()
        use_soft = request.query_params.get("soft", "true").lower() == "true"
        if use_soft:
            doc.soft_delete()
            return Response(
                {"message": "Document soft deleted"}, status=status.HTTP_200_OK
            )
        else:
            return super().destroy(request, *args, **kwargs)


from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        doc = Document.objects.get(
            id=document_id, deleted_at__isnull=True
        )
        asset = doc.asset
        response = HttpResponse(
            asset.blob, content_type=asset.mime_type or "application/octet-stream"
        )
        response["Content-Disposition"] = f'attachment; filename="{doc.file_name}"'
        response["Content-Length"] = asset.size
        return response


class SessionDocumentsView(generics.ListAPIView):
    serializer_class = DocumentListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        session_id = self.kwargs.get("session_id")
        session = get_object_or_404(ChatSession, id=session_id, user=self.request.user)
        return Document.objects.filter(session=session)


class SessionRiskFactorsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, user=self.request.user)
        docs = Document.objects.filter(session=session)
        all_rf = []
        for d in docs:
            if d.risk_factors:
                all_rf.extend(d.risk_factors.get("risk_factors", []))
        return Response(
            {
                "session_id": str(session.id),
                "session_title": session.title,
                "total_documents": docs.count(),
                "total_risk_factors": len(all_rf),
                "risk_factors": all_rf,
            }
        )


class SessionSummariesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, user=self.request.user)
        docs = Document.objects.filter(session=session)
        summaries = []
        for d in docs:
            if d.summary:
                summaries.append(d.summary)
        return Response(
            {
                "session_id": str(session.id),
                "session_title": session.title,
                "total_documents": docs.count(),
                "total_summaries": len(summaries),
                "summaries": summaries,
            }
        )
