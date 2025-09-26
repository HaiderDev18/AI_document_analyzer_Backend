from django.urls import path

# from . import views
from .views import (
    ChatSessionListView,
    ChatSessionDetailView,
    chat_session_messages,
    ChatView,
)

app_name = "chat"

# urlpatterns = [
#     # Chat sessions
#     path('sessions/', views.SessionListView.as_view(), name='session_list'),
#     path('sessions/<uuid:id>/', views.SessionDetailView.as_view(), name='session_detail'),
#     path('sessions/<uuid:session_id>/messages/', views.chat_session_messages, name='session-messages'),

#     # Chat messaging
#     # path('message/', views.chat_message, name='chat-message'),
#     path('message/', views.ChatView.as_view(), name='chat'),

#     # Utility endpoints
#     path('clear-history/', views.clear_chat_history, name='clear-history'),
# ]

urlpatterns = [
    path("sessions/", ChatSessionListView.as_view(), name="session-list"),
    path("sessions/<uuid:id>/", ChatSessionDetailView.as_view(), name="session-detail"),
    path(
        "sessions/messages/<uuid:session_id>/",
        chat_session_messages,
        name="session-messages",
    ),
    # path('chat-sessions/create/', create_chat_session, name='create-chat-session'),
    path("message/", ChatView.as_view(), name="chat-message"),
]
