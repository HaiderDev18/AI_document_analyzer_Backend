from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = "accounts"

urlpatterns = [
    # Authentication endpoints
    path("register/", views.user_registration, name="register"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("verify-token/", views.verify_token, name="verify_token"),
    # Profile endpoints
    path("profile/", views.UserProfileView.as_view(), name="profile"),
    path("profile/detail/", views.user_profile_detail, name="profile_detail"),
    path(
        "change-password/", views.ChangePasswordView.as_view(), name="change_password"
    ),
    # Admin endpoints
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("admin/dashboard/", views.admin_only_endpoint, name="admin_dashboard"),
    path(
        "admin/users/<uuid:user_id>/",
        views.get_user_profile_by_id,
        name="get_user_profile_by_id",
    ),
    # User deletion endpoints
    path("delete/", views.DeleteUserView.as_view(), name="delete_user"),
    path(
        "delete/<uuid:user_id>/",
        views.DeleteUserView.as_view(),
        name="delete_user_by_id",
    ),
]
