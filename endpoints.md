# API Endpoints Documentation

## 📱 User Management Endpoints

### Authentication
- `POST /accounts/register/`
  - Register a new user account
  - Required fields: username, email, password, password_confirm, first_name, last_name
  - Optional fields: role (defaults to 'user')

- `POST /accounts/login/`
  - User login with JWT tokens
  - Required fields: email, password
  - Returns access and refresh tokens

- `POST /accounts/logout/`
  - Logout user and blacklist refresh token
  - Requires authentication
  - Required fields: refresh_token


### User Profile
- `GET /accounts/profile/`
  - Get and update user profile
  - Requires authentication
  - Supports GET and PATCH methods


- `POST /accounts/change-password/`
  - Change user password
  - Requires authentication
  - Required fields: old_password, new_password, new_password_confirm

### User Management (Admin Only)
- `GET /accounts/users/`
  - List all users with pagination
  - Requires admin role
  - Query parameters:
    - page (default: 1)
    - length (default: 5, max: 100)
    - skip (optional)

- `GET /accounts/admin/dashboard/`
  - Get admin dashboard data
  - Requires admin role
  - Includes user statistics and paginated user list
  - Query parameters:
    - page (default: 1)
    - length (default: 10, max: 100)
    - skip (optional)

### User Deletion
- `DELETE /accounts/delete/`
  - Self-delete user account
  - Requires authentication
  - Deletes user's own account

- `DELETE /accounts/delete/<user_id>/`
  - Admin delete user account
  - Requires admin role
  - Deletes specified user's account
  - Cannot delete own account through this endpoint

## 🔒 Authentication Requirements

### Public Endpoints
- User registration
- User login
- Token refresh

### Protected Endpoints
- All other endpoints require valid JWT token
- Admin-only endpoints require admin role

## 📝 Notes
- All timestamps are in UTC
- JWT tokens expire after 5 minutes (access) and 24 hours (refresh)
- User roles: 'user' (default) and 'admin'
- Soft deletion is used for user accounts
- Pagination is consistent across all list endpoints

## 📄 Document Management Endpoints

### Document Upload & Processing
- `POST /documents/upload/`
  - Upload and process multiple documents
  - Creates or attaches to existing chat session
  - Required fields: files (multiple files)
  - Optional fields: session_id
  - Features:
    - Supports multiple file uploads
    - Extracts text from DOC/PDF
    - Generates embeddings
    - Creates document summaries
    - Extracts risk factors
    - Associates with chat session

### Document Listing & Retrieval
- `GET /documents/`
  - List all user's documents with pagination
  - Excludes soft-deleted documents
  - Query parameters:
    - page (default: 1)
    - length (default: 5, max: 100)
    - skip (optional)
  - Admin users see all documents
  - Regular users see only their documents

- `GET /documents/session/<session_id>/documents/`
  - List all documents within a specific session
  - Includes pagination
  - Query parameters:
    - page (default: 1)
    - length (default: 5, max: 100)
    - skip (optional)
  - Verifies session ownership
  - Excludes soft-deleted documents

### Document Details & Management
- `GET /documents/<document_id>/`
  - Get detailed information about a specific document
  - Includes:
    - Document metadata
    - Associated session info
    - Summary
    - Risk factors
    - Processing status
  - Requires document ownership

- `GET /documents/<document_id>/has-session/`
  - Check if document is associated with a chat session
  - Returns boolean response
  - Useful for UI state management

### Document Deletion
- `DELETE /documents/<document_id>/soft-delete/`
  - Soft delete a document
  - Document remains in database but marked as deleted
  - Requires document ownership
  - Can be restored if needed

### Document Processing Features
- Text extraction from DOC/PDF files
- Automatic text chunking for embeddings
- OpenAI-based summary generation
- Risk factor extraction
- Pinecone vector storage
- Session-based document organization

### Notes
- All document endpoints require authentication
- File size limits apply to uploads
- Processing happens synchronously
- Documents are associated with session's Pinecone namespace
- Pagination is consistent across all list endpoints

## 💬 Chat Management Endpoints

### Chat Sessions
- `GET /chat/sessions/`
  - List all chat sessions for the authenticated user
  - Includes pagination
  - Query parameters:
    - page (default: 1)
    - length (default: 5, max: 100)
    - skip (optional)
  - Features:
    - Orders by newest first
    - Excludes deleted sessions
    - Includes session metadata

- `GET /chat/sessions/<session_id>/`
  - Get detailed information about a specific chat session
  - Includes:
    - Session metadata
    - Associated documents
    - Chat history
    - Pinecone namespace
  - Requires session ownership

### Chat Messages
- `GET /chat/sessions/<session_id>/messages/`
  - Get all messages for a specific chat session
  - Includes:
    - User messages
    - AI responses
    - Message timestamps
    - Token counts
  - Messages are ordered chronologically
  - Requires session ownership

- `POST /chat/message`
  - Send a message and get AI response
  - Required fields:
    - session_id
    - message
  - Features:
    - RAG-based responses using document context
    - Token counting for analytics
    - Message history tracking
    - Context-aware responses
  - Process:
    1. Searches relevant document context
    2. Generates AI response using context
    3. Stores both user message and AI response
    4. Tracks token usage for analytics

### Chat Features
- Document Context Integration
  - Uses Pinecone for semantic search
  - Retrieves relevant document chunks
  - Enhances AI responses with document context

- Message Management
  - Chronological message ordering
  - Token usage tracking
  - Message type differentiation (user/assistant)

- Session Organization
  - Unique namespace per session
  - Document association
  - Message history preservation

### Notes
- All chat endpoints require authentication
- Sessions are user-specific
- Messages are stored with token counts for analytics
- RAG (Retrieval-Augmented Generation) is used for context-aware responses
- Chat sessions can be associated with multiple documents
- Pagination is consistent across all list endpoints
