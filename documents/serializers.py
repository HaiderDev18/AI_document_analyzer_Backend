from rest_framework import serializers
from .models import Document
import os


import hashlib
from .models import FileAsset


class DocumentUploadSerializer(serializers.Serializer):
    # Accept explicit title or fall back to file name
    title = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()

    def validate(self, attrs):
        f = attrs["file"]
        max_bytes = 50 * 1024 * 1024  # 50MB; adjust as needed
        if f.size <= 0:
            raise serializers.ValidationError("Empty file.")
        if f.size > max_bytes:
            raise serializers.ValidationError("File too large.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        session = self.context.get("session")
        f = validated_data["file"]

        # Compute checksum + collect bytes (for DB storage)
        hasher = hashlib.sha256()
        chunks = []
        for chunk in f.chunks():
            hasher.update(chunk)
            chunks.append(chunk)
        blob = b"".join(chunks)
        checksum = hasher.hexdigest()

        file_name = f.name
        title = validated_data.get("title") or os.path.splitext(file_name)[0]
        ext = os.path.splitext(file_name)[1].lstrip(".")[:16]
        mime = getattr(f, "content_type", "")

        doc = Document.objects.create(
            title=title,
            file_name=file_name,
            file_ext=ext,
            file_mime=mime,
            file_size=f.size,
            checksum=checksum,
            user=user,
            session=session,
            status=Document.STATUS_PENDING,
        )

        FileAsset.objects.create(
            document=doc,
            blob=blob,
            size=f.size,
            mime_type=mime,
            checksum=checksum,
        )
        return doc


class DocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "file_name",
            "file_ext",
            "file_mime",
            "file_size",
            "status",
            "created_at",
            "updated_at",
            "session",
        )
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "file_name",
            "file_ext",
            "file_mime",
            "file_size",
            "status",
            "processing_error",
            "summary",
            "risk_factors",
            "created_at",
            "updated_at",
            "session",
        )
        read_only_fields = fields


class DocumentSummarySerializer(serializers.Serializer):
    document_id = serializers.IntegerField(required=True)
    summary = serializers.CharField(required=True)
    response = serializers.CharField(required=False)


class DocumentRiskFactorsSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(required=True)
    risk_factors = serializers.JSONField(required=True)
    response = serializers.CharField(required=False)


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
