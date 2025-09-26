from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserProfile


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default="user")

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "password_confirm",
            "role",
            "first_name",
            "last_name",
        )
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        role = validated_data.get("role", "user")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role=role,
            password=password,
        )
        # UserProfile is automatically created by Django signal
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password.")
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled.")
            attrs["user"] = user
            return attrs
        else:
            raise serializers.ValidationError("Must include email and password.")


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile
    """

    # username = serializers.CharField(source='user.username', read_only=True)  # Access username through user relation
    email = serializers.EmailField(
        source="user.email", read_only=True
    )  # Access email through user relation

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "email",
            # 'first_name',
            # 'last_name',
            "bio",
            "location",
            "birth_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user information
    """

    profile = UserProfileSerializer(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_verified",
            "date_joined",
            "profile",
        )
        read_only_fields = ("id", "email", "is_verified", "date_joined")


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password
    """

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user information
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username")

    def validate_username(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value
