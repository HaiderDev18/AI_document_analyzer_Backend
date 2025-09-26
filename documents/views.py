from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Document
from .serializers import (
    DocumentUploadSerializer,
    DocumentSerializer,
    DocumentListSerializer,
    DocumentSummarySerializer,
    DocumentRiskFactorsSerializer,
)
from .services.document_processor import extract_text_from_files
from .services.openai_service import OpenAIService
from .services.pinecone_service import PineconeEmbedding

# from analytics.services import AnalyticsHelper
from chat.models import ChatSession
from django.db import IntegrityError
import uuid
from chat.serializers import ChatSessionSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions


class DocumentUploadView(generics.CreateAPIView):
    """
    Upload and process multiple documents, attach session if provided or create a new session.
    """

    serializer_class = DocumentUploadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Get or create session
            session_id = request.data.get("session_id")
            session = None

            if session_id:
                # Try to get the session from the database
                try:
                    session = ChatSession.objects.get(id=session_id, user=request.user)
                except ChatSession.DoesNotExist:
                    return Response(
                        {
                            "error": "Session not found or you do not have permission to access it."
                        },
                        status=404,
                    )
            else:
                # Create new session if no session_id is provided
                session = ChatSession.objects.create(user=request.user)

            # pinecone_embedding = PineconeEmbedding(namespace=session.namespace)

            # Add session to the data before passing to the serializer
            uploaded_documents = []
            files = request.FILES.getlist("files")  # Handle multiple files

            if not files:
                return Response(
                    {"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Iterate over files
            for file in files:
                request.data["file"] = file  # Set the current file
                request.data["session"] = session  # Associate the session
                # if document already exists, return error
                if session:
                    if Document.objects.filter(
                        file_name=file.name,
                        user=request.user,
                        session=session,
                        deleted_at__isnull=True,
                    ).exists():
                        return Response(
                            {"response": "Document already exists"},
                            status=status.HTTP_204_NO_CONTENT,
                        )

                # Pass the request data to the serializer
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)  # Validate the serializer

                # Save the document, and the session will be associated with the document
                document = serializer.save(session=session)

                # Process document
                self._process_document(document, namespace=session.namespace)

                # uploaded_docs.append(document)
                # Append the document to the uploaded_documents list
                uploaded_documents.append(document)
                # print("session", session.__dict__)
            # Return success response for multiple documents
            return Response(
                {
                    "message": f"Successfully uploaded {len(uploaded_documents)} document(s).",
                    "documents": DocumentSerializer(uploaded_documents, many=True).data,
                    "session_id": session.id,
                    "session_namespace": session.namespace,
                },
                status=status.HTTP_201_CREATED,
            )

        except IntegrityError:
            return Response(
                {"error": "Database integrity error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_document(self, document, namespace):
        try:
            document.status = "processing"
            document.save()

            with open(document.file_path, "rb") as f:
                # text = DocumentProcessor.extract_text(f.read(), document.file_type)
                text = extract_text_from_files([document.file_path])

            # with open('uploads/extracted_text.txt', 'w') as f:
            #     f.write(text)

            document.raw_text = text
            document.save()
            # check document exists in
            PineconeEmbedding(namespace=namespace).main(
                text=text,
                file_name=document.file_name,
                file_path=document.file_path,
                user=document.user,
            )
            # import json
            # summary, response = OpenAIService().generate_summary(text)
            # document.summary =
            # risk_factors = OpenAIService().generate_risk_factors(text)
            # try:
            #     risk_factors = risk_factors.replace("```json", "").replace("```", "")
            #     risk_factors = json.loads(risk_factors)
            # except json.JSONDecodeError:
            #     risk_factors = {"risk_factors": []}
            # document.risk_factors = risk_factors
            document.save()

            document.status = "completed"
            document.save()
        except Exception:
            document.status = "failed"
            document.save()
            raise


class DocumentSummaryGenerator(generics.CreateAPIView):
    serializer_class = DocumentSummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, document_id):
        try:
            print("document_id", document_id)
            document = Document.objects.filter(
                id=document_id, user=request.user, deleted_at__isnull=True
            ).first()
            if not document:
                return Response(
                    {"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND
                )
            else:
                if document.status != "completed":
                    return Response(
                        {"error": "Document is not completed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                summary, response = OpenAIService().generate_summary(document.raw_text)
                # if response:
                #     AnalyticsHelper.log_summarization_usage(
                #         user=document.user,
                #         openai_response=response,
                #         document_title=document.title,
                #     )
                document.summary = summary
                document.save()
                return Response(
                    {
                        "document_id": document.id,
                        "title": document.title,
                        "session_id": document.session.id,
                        "summary": summary,
                    },
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            return Response(
                {"error generating summary": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


import json


class RiskFactorsGenerator(generics.CreateAPIView):
    serializer_class = DocumentRiskFactorsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, document_id):
        try:
            document = Document.objects.get(
                id=document_id, user=request.user, deleted_at__isnull=True
            )
            if document.status != "completed":
                return Response(
                    {"error": "Document is not completed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            risk_factors, response = OpenAIService().generate_risk_factors(
                document.raw_text
            )
            try:
                # risk_factors = risk_factors.replace("```json", "").replace("```", "")
                risk_factors = json.loads(risk_factors)

            except json.JSONDecodeError:
                risk_factors = {"risk_factors": []}
            # if response:
            #     AnalyticsHelper.log_summarization_usage(
            #         user=document.user,
            #         openai_response=response,
            #         document_title=document.title,
            #     )
            document.risk_factors = risk_factors
            document.save()
            return Response(
                {
                    "document_id": document.id,
                    "title": document.title,
                    "session_id": document.session.id,
                    "risk_factors": risk_factors,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error generating risk factors": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentListView(generics.ListAPIView):
    """
    List user's documents (excluding soft deleted)
    """

    serializer_class = DocumentListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get base queryset based on user role
        if self.request.user.role == "admin":
            base_queryset = Document.objects.filter(deleted_at__isnull=True)
            documents_count = base_queryset.count()
        else:
            base_queryset = Document.objects.filter(
                user=self.request.user, deleted_at__isnull=True
            )
            documents_count = base_queryset.count()

        # Get pagination parameters
        page = int(self.request.GET.get("page", 1))
        length = int(self.request.GET.get("length", 5))
        skip = self.request.GET.get("skip")

        # Validate length parameter
        if length > 100:
            length = 100
        elif length < 1:
            length = 10

        # Calculate offset
        if skip is not None:
            offset = int(skip)
            current_page = (offset // length) + 1
        else:
            if page < 1:
                page = 1
            offset = (page - 1) * length
            current_page = page

        # Get documents with custom pagination
        paginated_documents = base_queryset.order_by("-created_at")[
            offset : offset + length
        ]

        # Calculate pagination metadata
        total_pages = (documents_count + length - 1) // length  # Ceiling division
        has_next = offset + length < documents_count
        has_previous = offset > 0

        # Store pagination data for response
        self.pagination_data = {
            "message": "Documents retrieved successfully",
            "statistics": {
                "total_documents": documents_count,
            },
            "documents": {
                "total_count": documents_count,
                "page": current_page,
                "length": length,
                "skip": offset,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "results": paginated_documents,
            },
        }

        return paginated_documents

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Update the results with serialized data
        self.pagination_data["documents"]["results"] = serializer.data

        return Response(self.pagination_data, status=status.HTTP_200_OK)


class DocumentHasSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, document_id):
        try:
            document = Document.objects.get(
                id=document_id, user=request.user, deleted_at__isnull=True
            )
            print("document", document.__dict__)
            return Response({"has_session": document.session is not None}, status=200)
        except Document.DoesNotExist:
            return Response({"error": "Document not found"}, status=404)


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a specific document by ID (must belong to current user)
    """

    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter documents to only return those belonging to the current user and not soft-deleted
        """
        return Document.objects.filter(user=self.request.user, deleted_at__isnull=True)

    def retrieve(self, request, *args, **kwargs):
        """
        Get document by ID - ensures document belongs to current user
        """
        document = self.get_object()

        # Retrieve the associated session if it exists
        session_data = None
        if document.session:
            session_data = ChatSessionSerializer(document.session).data

        # Serialize the document
        document_data = self.get_serializer(document).data

        # Include session data in the response
        response_data = {
            "document": document_data,
            "session": {
                "id": session_data["id"],
                "title": session_data["title"],
                "namespace": session_data["namespace"],
                "created_at": session_data["created_at"],
            },  # Include the session details if available
        }

        return Response(response_data, status=status.HTTP_200_OK)


class DocumentSoftDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, document_id):
        try:
            document = Document.objects.get(
                id=document_id, user=request.user, deleted_at__isnull=True
            )
            document.soft_delete()
            return Response({"message": "Document soft deleted"}, status=200)
        except Document.DoesNotExist:
            return Response({"error": "Document not found"}, status=404)


def destroy(self, request, *args, **kwargs):
    document = self.get_object()
    use_soft = request.query_params.get("soft", "true").lower() == "true"

    if use_soft:
        document.soft_delete()
        return Response({"message": "Document soft deleted"}, status=status.HTTP_200_OK)
    else:
        document.delete()
        return Response(
            {"message": "Document hard deleted"}, status=status.HTTP_204_NO_CONTENT
        )


class SessionDocumentsView(generics.ListAPIView):
    """
    List all documents within a specific session with pagination
    """

    serializer_class = DocumentListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        session_id = self.kwargs.get("session_id")

        try:
            # Verify session exists and belongs to user
            session = ChatSession.objects.get(id=session_id, user=self.request.user)
        except ChatSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found or you do not have permission to access it"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get base queryset for documents in this session
        base_queryset = Document.objects.filter(
            session=session, deleted_at__isnull=True
        )
        documents_count = base_queryset.count()

        # Get pagination parameters
        page = int(self.request.GET.get("page", 1))
        length = int(self.request.GET.get("length", 5))
        skip = self.request.GET.get("skip")

        # Validate length parameter
        if length > 100:
            length = 100
        elif length < 1:
            length = 10

        # Calculate offset
        if skip is not None:
            offset = int(skip)
            current_page = (offset // length) + 1
        else:
            if page < 1:
                page = 1
            offset = (page - 1) * length
            current_page = page

        # Get documents with custom pagination
        paginated_documents = base_queryset.order_by("-created_at")[
            offset : offset + length
        ]

        # Calculate pagination metadata
        total_pages = (documents_count + length - 1) // length  # Ceiling division
        has_next = offset + length < documents_count
        has_previous = offset > 0

        # Store pagination data for response
        self.pagination_data = {
            "message": "Session documents retrieved successfully",
            "statistics": {
                "total_documents": documents_count,
                "session_id": str(session.id),
                "session_title": session.title,
            },
            "documents": {
                "total_count": documents_count,
                "page": current_page,
                "length": length,
                "skip": offset,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "results": paginated_documents,
            },
        }

        return paginated_documents

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Update the results with serialized data
        self.pagination_data["documents"]["results"] = serializer.data

        return Response(self.pagination_data, status=status.HTTP_200_OK)


class SessionRiskFactorsView(APIView):
    """
    Get all risk factors from documents within a specific session
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            # Verify session exists and belongs to user
            session = ChatSession.objects.get(id=session_id, user=request.user)
            print("session", session.__dict__)
        except ChatSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found or you do not have permission to access it"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all documents in the session
        documents = Document.objects.filter(session=session, deleted_at__isnull=True)
        print("total documents", documents.count())

        # Collect all unique risk factors
        # all_risk_factors = set()
        all_risk_factors = []
        for document in documents:
            if document.risk_factors:
                all_risk_factors.extend(document.risk_factors.get("risk_factors", []))
                # # Handle different risk_factors formats
                # if isinstance(document.risk_factors, dict):
                #     # If risk_factors is a dictionary, extract values
                #     for category, risks in document.risk_factors.items():
                #         if isinstance(risks, list):
                #             all_risk_factors.update(risks)
                #         elif isinstance(risks, str):
                #             all_risk_factors.add(risks)
                # elif isinstance(document.risk_factors, list):
                #     # If risk_factors is a list
                #     all_risk_factors.update(document.risk_factors)
                # elif isinstance(document.risk_factors, str):
                #     # If risk_factors is a string
                #     all_risk_factors.add(document.risk_factors)

        # Convert to list and sort
        # risk_factors_list = sorted(list(all_risk_factors))

        return Response(
            {
                "session_id": str(session.id),
                "session_title": session.title,
                "total_documents": documents.count(),
                "total_risk_factors": len(all_risk_factors),
                "risk_factors": all_risk_factors,
            },
            status=status.HTTP_200_OK,
        )


class SessionSummariesView(APIView):
    """
    Get all summaries from documents within a specific session
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            # Verify session exists and belongs to user
            session = ChatSession.objects.get(id=session_id, user=request.user)
            print("session", session.__dict__)
        except ChatSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found or you do not have permission to access it"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all documents in the session
        documents = Document.objects.filter(session=session, deleted_at__isnull=True)
        print("total documents", documents.count())

        # Collect all unique risk factors
        # all_risk_factors = set()
        all_summaries = []
        for document in documents:
            if document.summary:
                all_summaries.append(document.summary)
                # # Handle different risk_factors formats
                # if isinstance(document.risk_factors, dict):
                #     # If risk_factors is a dictionary, extract values
                #     for category, risks in document.risk_factors.items():
                #         if isinstance(risks, list):
                #             all_risk_factors.update(risks)
                #         elif isinstance(risks, str):
                #             all_risk_factors.add(risks)
                # elif isinstance(document.risk_factors, list):
                #     # If risk_factors is a list
                #     all_risk_factors.update(document.risk_factors)
                # elif isinstance(document.risk_factors, str):
                #     # If risk_factors is a string
                #     all_risk_factors.add(document.risk_factors)

        # Convert to list and sort
        # risk_factors_list = sorted(list(all_risk_factors))

        return Response(
            {
                "session_id": str(session.id),
                "session_title": session.title,
                "total_documents": documents.count(),
                "total_summaries": len(all_summaries),
                "summaries": all_summaries,
            },
            status=status.HTTP_200_OK,
        )
