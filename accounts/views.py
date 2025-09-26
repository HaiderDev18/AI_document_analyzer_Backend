from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import logout, authenticate
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    UserUpdateSerializer,
)
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.getLogger(__name__)


# Custom permission class for admin only
class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


# class UserRegistrationView(generics.CreateAPIView):
#     """
#     User registration endpoint
#     """
#     queryset = User.objects.all()
#     serializer_class = UserRegistrationSerializer
#     permission_classes = [permissions.AllowAny]

#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.save()

#         # Generate tokens
#         # refresh = RefreshToken.for_user(user)

#         return Response({
#             'message': 'User registered successfully',
#             'user': UserSerializer(user).data
#         }, status=status.HTTP_201_CREATED)


class UserLoginView(TokenObtainPairView):
    """
    User login endpoint with JWT tokens
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful",
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )


class UserLogoutView(APIView):
    """
    User logout endpoint - blacklists the refresh token
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # Django logout
            logout(request)

            return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get and update user profile
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        user_serializer = UserUpdateSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )

        if user_serializer.is_valid():
            user_serializer.save()

            # Update profile if profile data is provided
            profile_data = request.data.get("profile", {})
            if profile_data:
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile_serializer = UserProfileSerializer(
                    profile, data=profile_data, partial=True
                )
                if profile_serializer.is_valid():
                    profile_serializer.save()

            return Response(
                {
                    "message": "Profile updated successfully",
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Change user password
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data["new_password"])
            user.save()

            return Response(
                {"message": "Password changed successfully"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserListView(generics.ListAPIView):
    """
    List all users (admin only)
    """

    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if self.request.user.role == "admin":
            users_count = User.objects.count()
        else:
            users_count = User.objects.filter(id=self.request.user.id).count()

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

        # Get users with custom pagination
        all_users = User.objects.order_by("-created_at")[offset : offset + length]

        # Calculate pagination metadata
        total_pages = (users_count + length - 1) // length  # Ceiling division
        has_next = offset + length < users_count
        has_previous = offset > 0

        # Store pagination data for response
        self.pagination_data = {
            "message": "Users retrieved successfully",
            "statistics": {
                "total_users": users_count,
            },
            "users": {
                "total_count": users_count,
                "page": current_page,
                "length": length,
                "skip": offset,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "results": all_users,
            },
        }

        return all_users

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Update the results with serialized data
        self.pagination_data["users"]["results"] = serializer.data

        return Response(self.pagination_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_profile_detail(request):
    """
    Get current user profile details
    """
    user = request.user
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def verify_token(request):
    """
    Verify if the current token is valid
    """
    return Response(
        {"message": "Token is valid", "user": UserSerializer(request.user).data},
        status=status.HTTP_200_OK,
    )


class AdminDashboardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


@api_view(["GET"])
@permission_classes([IsAdminUser])
def get_user_profile_by_id(request, user_id):
    """
    Get user profile by ID
    """
    user = User.objects.get(id=user_id)
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_only_endpoint(request):
    """
    This endpoint is only accessible to admin users.
    Returns admin dashboard data with custom paginated users list and statistics.

    Query Parameters:
    - page: Page number (default: 1)
    - length: Number of records per page (default: 10, max: 100)
    - skip: Number of records to skip (optional, overrides page if provided)
    """
    # Get statistics
    users_count = User.objects.count()
    admin_count = User.objects.filter(role="admin").count()
    user_count = User.objects.filter(role="user").count()

    # Get pagination parameters
    page = int(request.GET.get("page", 1))
    length = int(request.GET.get("length", 10))
    skip = request.GET.get("skip")

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

    # Get users with custom pagination
    all_users = User.objects.order_by("-created_at")[offset : offset + length]

    # Calculate pagination metadata
    total_pages = (users_count + length - 1) // length  # Ceiling division
    has_next = offset + length < users_count
    has_previous = offset > 0

    # Serialize the users
    users_serializer = UserProfileSerializer(all_users, many=True)

    # Prepare the response data
    data = {
        "message": "Welcome Admin! Dashboard data retrieved successfully.",
        "statistics": {
            "total_users": users_count,
            "admin_users": admin_count,
            "regular_users": user_count,
        },
        "users": {
            "total_count": users_count,
            "page": current_page,
            "length": length,
            "skip": offset,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_previous": has_previous,
            "results": users_serializer.data,
        },
    }

    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def user_registration(request):
    """
    Register a new user account
    """
    try:
        logger.info(f"Registration request data: {request.data}")
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            logger.info("Serializer is valid, creating user...")
            user = serializer.save()  # This should return a User instance
            logger.info(f"User created successfully: {user}")
            logger.info(f"User type: {type(user)}")

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            response_data = {
                "message": "User registered successfully.",
                "user": UserProfileSerializer(
                    user
                ).data,  # Make sure this is using the User instance
                # 'tokens': {
                #     'access': str(refresh.access_token),
                #     'refresh': str(refresh),
                # }
            }
            logger.info("Registration successful")
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class DeleteUserView(APIView):
    """
    Delete user account - either self-deletion or admin deletion
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, user_id=None):
        # If user_id is provided, this is an admin deletion
        if user_id:
            # Check if the requesting user is an admin
            if not request.user.role == "admin":
                return Response(
                    {"error": "Only admin users can delete other users"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            try:
                user_to_delete = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # Prevent admin from deleting themselves
            if user_to_delete.id == request.user.id:
                return Response(
                    {
                        "error": "Admin users cannot delete their own account through this endpoint"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Delete the user
            user_to_delete.delete()
            return Response(
                {
                    "message": f"User {user_to_delete.email} has been deleted successfully"
                },
                status=status.HTTP_200_OK,
            )

        # Self-deletion
        user = request.user
        user.delete()
        return Response(
            {"message": "Your account has been deleted successfully"},
            status=status.HTTP_200_OK,
        )
