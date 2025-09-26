from rest_framework import serializers
from .models import Document
from .services.document_processor import DocumentProcessor
import os
from AI_doc_process import settings
import uuid
from django.core.files.storage import default_storage
from chat.models import ChatSession
from rest_framework.response import Response
from rest_framework import serializers
from .models import Document
import os
import uuid
from django.core.files.storage import default_storage
from django.conf import settings


class DocumentUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = ["file"]

    def validate_file(self, file):
        """
        Validate the uploaded file's extension.
        """
        allowed_extensions = [".pdf", ".doc", ".docx"]
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Allowed file types: {', '.join(allowed_extensions)}"
            )

        # Additional validation through DocumentProcessor can be added if necessary
        is_valid, error_message = DocumentProcessor().validate_file(
            file, ext.lstrip(".")
        )
        if not is_valid:
            raise serializers.ValidationError(error_message)
        return file

    def create(self, validated_data):
        """
        Create the Document instance, handle file saving, and associate session.
        """
        file = validated_data["file"]
        user = self.context["request"].user
        title = validated_data.get("title") or file.name
        ext = os.path.splitext(file.name)[1].lower()
        unique_filename = f"{uuid.uuid4()}{ext}"
        path = default_storage.save(f"documents/{unique_filename}", file)
        full_path = os.path.join(settings.MEDIA_ROOT, path)

        # Retrieve session from context
        session = validated_data["session"]
        print("*************serializer session", session.__dict__)
        document = Document.objects.create(
            user=user,
            title=title,
            file_name=file.name,
            file_path=full_path,
            file_type=ext.lstrip("."),
            file_size=file.size,
            status="pending",
            session=session,
        )

        return document


class BulkDocumentUploadSerializer(serializers.Serializer):
    """
    Serializer for bulk document upload
    """

    files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        allow_empty=False,
        max_length=10,  # Limit to 10 files per bulk upload
    )

    def validate_files(self, files):
        """
        Validate all uploaded files
        """
        if len(files) > 10:
            raise serializers.ValidationError(
                "Maximum 10 files allowed per bulk upload"
            )

        allowed_extensions = [".pdf", ".doc", ".docx"]
        processor = DocumentProcessor()

        for file in files:
            # Check file extension
            file_extension = file.name.lower().split(".")[-1]
            if f".{file_extension}" not in allowed_extensions:
                raise serializers.ValidationError(
                    f"File '{file.name}': Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
                )

            # Use DocumentProcessor for additional validation
            is_valid, error_message = processor.validate_file(file, file_extension)
            if not is_valid:
                raise serializers.ValidationError(
                    f"File '{file.name}': {error_message}"
                )

        return files


class DocumentSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Document
    """

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file_name",
            "file_path",
            "file_type",
            "file_size",
            "status",
            "summary",
            "risk_factors",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "file_name",
            "file_path",
            "file_size",
            "file_type",
            "created_at",
            "updated_at",
        ]


class DocumentSummarySerializer(serializers.Serializer):
    document_id = serializers.IntegerField(required=True)
    summary = serializers.CharField(required=True)
    response = serializers.CharField(required=False)


class DocumentRiskFactorsSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(required=True)
    risk_factors = serializers.JSONField(required=True)
    response = serializers.CharField(required=False)


from chat.models import ChatSession
from chat.serializers import SessionSerializer


class DocumentListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing documents
    """

    session = SessionSerializer(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file_name",
            "file_type",
            "file_size",
            "status",
            "session",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "file_name",
            "file_size",
            "file_type",
            "created_at",
            "updated_at",
        ]


class BulkUploadResponseSerializer(serializers.Serializer):
    """
    Serializer for bulk upload response
    """

    successful_uploads = DocumentSerializer(many=True, read_only=True)
    failed_uploads = serializers.ListField(
        child=serializers.DictField(), read_only=True
    )
    total_files = serializers.IntegerField(read_only=True)
    successful_count = serializers.IntegerField(read_only=True)
    failed_count = serializers.IntegerField(read_only=True)
