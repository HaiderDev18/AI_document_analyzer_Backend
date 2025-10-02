# AI Document Process Backend

A Django REST Framework (DRF) backend application for AI-powered document processing with comprehensive user
authentication, document analysis, intelligent chat, and usage analytics.

## 🚀 Project Overview

This backend provides a complete AI document processing pipeline that allows users to upload documents, extract and
analyze content, engage in intelligent conversations with their documents, and track their AI usage—all through a clean,
RESTful API.

## 🏗️ System Architecture & Flow

### Core Application Flow

```
1. User Registration/Authentication
   ↓
2. Document Upload & Processing
   ↓
3. AI-Powered Analysis & Storage
   ↓
4. Intelligent Chat with Documents
   ↓
5. Analytics & Usage Tracking
```

### Detailed Workflow

#### **Phase 1: User Onboarding**

- Users register with email, username, and profile information
- JWT-based authentication provides secure access
- Each user gets a unique Pinecone namespace for document isolation
- User profiles can be customized with additional information

#### **Phase 2: Document Processing Pipeline**

```
Document Upload → Text Extraction → Content Chunking → Embedding Generation → Vector Storage
```

1. **Upload**: Users upload PDF, DOC, or DOCX files
2. **Text Extraction**: Raw text is extracted using specialized processors
3. **AI Summarization**: OpenAI generates intelligent summaries
4. **Content Chunking**: Text is split into optimized chunks for embeddings
5. **Vector Embeddings**: OpenAI creates semantic embeddings for each chunk
6. **Vector Storage**: Embeddings are stored in Pinecone with metadata
7. **Analytics Tracking**: Token usage is recorded for monitoring

#### **Phase 3: Intelligent Interaction**

- Users engage in natural language conversations about their documents
- RAG (Retrieval-Augmented Generation) system finds relevant document context
- OpenAI generates contextually aware responses
- Chat sessions maintain conversation history
- All interactions are tracked for analytics

#### **Phase 4: Analytics & Monitoring**

- Real-time token usage tracking across all features
- User-specific analytics dashboards
- Usage breakdowns by feature (chat, summarization, embedding)
- Administrative insights for system monitoring

---

## 📦 Application Architecture

### **🔐 Accounts App** (`accounts/`)

**Purpose**: Complete user authentication and profile management system

**Core Responsibilities:**

- **User Registration & Authentication**: JWT-based secure authentication
- **Profile Management**: Extended user profiles with customizable information
- **Namespace Management**: Automatic Pinecone namespace creation for document isolation
- **Admin Integration**: Comprehensive user management through Django admin

**Key Features:**

- Custom User model extending Django's AbstractUser
- Automatic profile creation via Django signals
- Password change and profile update functionality
- User-specific namespacing for data isolation

---

### **📄 Documents App** (`documents/`)

**Purpose**: Comprehensive document upload, processing, and management system

**Core Responsibilities:**

- **File Upload Management**: Secure upload of PDF, DOC, DOCX files
- **Text Extraction**: Advanced text extraction from various document formats
- **AI Processing**: Automatic summarization and content analysis
- **Vector Processing**: Document embedding generation and storage
- **Status Tracking**: Real-time processing status monitoring

**Key Features:**

- **Multi-format Support**: PDF, DOC, DOCX processing
- **Bulk Upload**: Process multiple documents simultaneously
- **Document Validation**: File type, size, and content validation
- **AI Integration**: OpenAI-powered summarization and embedding
- **Pinecone Integration**: Vector storage for semantic search
- **Analytics Integration**: Token usage tracking for all operations

**Processing Pipeline:**

```
Upload → Validation → Text Extraction → Summarization → Chunking → Embedding → Storage
```

---

### **💬 Chat App** (`chat/`)

**Purpose**: Intelligent conversational AI system with document context awareness

**Core Responsibilities:**

- **Session Management**: Organized conversation sessions per user
- **RAG Implementation**: Retrieval-Augmented Generation for document-aware responses
- **Message Processing**: Intelligent message handling and response generation
- **Context Retention**: Conversation history and context management
- **Analytics Integration**: Chat-specific usage tracking

**Key Features:**

- **Session-Based Conversations**: Organized chat sessions with custom titles
- **Document Context Retrieval**: Semantic search through user's uploaded documents
- **Intelligent Response Generation**: Context-aware AI responses using OpenAI
- **Multi-turn Conversations**: Maintains conversation context across exchanges
- **Automatic Title Generation**: Smart session naming based on conversation content
- **Fallback Mechanisms**: Graceful handling when document context is unavailable

**RAG Workflow:**

```
User Query → Document Search → Context Retrieval → Response Generation → Analytics Tracking
```

---

### **📊 Analytics App** (`analytics/`)

**Purpose**: Comprehensive token usage tracking and analytics system

**Core Responsibilities:**

- **Real-time Tracking**: Automatic token usage monitoring across all AI operations
- **User Analytics**: Individual user usage summaries and statistics
- **Feature Breakdown**: Usage analysis by feature type (chat, summarization, embedding)
- **Administrative Insights**: System-wide analytics for monitoring and optimization

**Key Features:**

- **Automatic Token Tracking**: Seamless integration with all OpenAI API calls
- **Feature-Specific Analytics**: Separate tracking for chat, summarization, and embedding operations
- **User Summaries**: Aggregated usage data per user with automatic updates
- **Historical Data**: Detailed usage history with time-based analytics
- **Admin Dashboard**: Read-only admin interface for monitoring system usage

**Analytics Data Flow:**

```
AI Operation → Token Extraction → Usage Logging → Summary Updates → Dashboard Display
```

---

## 🔄 Inter-App Integration

### **Seamless Data Flow**

- **Accounts ↔ Documents**: User authentication enables document ownership and namespacing
- **Documents ↔ Analytics**: All document processing operations are tracked for token usage
- **Documents ↔ Chat**: Uploaded documents provide context for intelligent conversations
- **Chat ↔ Analytics**: All chat interactions are monitored for usage analytics
- **All Apps ↔ Admin**: Centralized administration interface for all system components

### **Shared Services**

- **OpenAI Service**: Centralized AI operations across documents and chat
- **Pinecone Service**: Vector storage and retrieval for documents and chat
- **Analytics Service**: Usage tracking integration for all AI operations

---

## 🛠️ Technical Foundation

### **Core Technologies**

- **Backend Framework**: Django 5.2.1 with Django REST Framework 3.15.2
- **Authentication**: JWT with Simple JWT for stateless authentication
- **AI Services**: OpenAI API for text processing, summarization, and chat
- **Vector Database**: Pinecone for semantic search and document retrieval
- **Database**: SQLite (development) with PostgreSQL support (production)
- **Environment Management**: Python-decouple for secure configuration

### **Architecture Principles**

- **Simplicity First**: Clean, focused implementation following .cursorrules guidelines
- **No Background Jobs**: Synchronous processing for simplicity (no Celery/Redis)
- **RESTful Design**: Standard DRF conventions and patterns
- **Security by Design**: JWT authentication with user data isolation
- **Comprehensive Tracking**: Built-in analytics for all AI operations

---

## 📋 Project Scope & Rules

### **Core Features (As per .cursorrules)**

- ✅ **User Authentication**: Complete signup, login, and profile management
- ✅ **Document Processing**: Multi-format upload with AI-powered analysis
- ✅ **Intelligent Chat**: RAG-enabled conversations with document context
- ✅ **Analytics Tracking**: Comprehensive OpenAI token usage monitoring
- ✅ **Admin Panel**: Django admin for user and system management

### **Development Principles**

- **Simple & Focused**: Intentionally straightforward implementation
- **No Over-Engineering**: Avoid unnecessary complexity and abstractions
- **DRF Standards**: Follow Django REST Framework best practices
- **Clean Code**: Modular, well-commented, and maintainable codebase
- **Environment-Based**: Secure configuration through environment variables

---

## 🚦 Quick Start

### **Prerequisites**

- Python 3.8+
- Virtual environment (recommended)
- OpenAI API key
- Pinecone API key

### **Installation**

```bash
# Clone repository
git clone <repository-url>
cd AI_Doc_Process_Backend

# Make sure you have Python 3.12.6 installed for optimal performance.
# Setup virtual environment
python -m venv drf_env
source drf_env/bin/activate  # On Windows: drf_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Make sure you have docker installed and running.
docker compose up -d  # For PostgreSQL and Redis

# Configure environment
cp .env.example .env
# Edit .env with your API keys and configuration

# Setup database
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Run development server
uvicorn AI_doc_process.asgi:application --reload
```

---

## 📁 Project Structure

```
AI_Doc_Process_Backend/
├── accounts/                    # User authentication & profile management
│   ├── models.py               # User and UserProfile models
│   ├── serializers.py          # Authentication serializers
│   ├── views.py                # Auth API views
│   ├── admin.py                # User admin interface
│   └── signals.py              # Profile creation signals
├── documents/                   # Document processing system
│   ├── models.py               # Document model
│   ├── serializers.py          # Document upload serializers
│   ├── views.py                # Document processing views
│   ├── admin.py                # Document admin interface
│   └── services/               # Document processing services
│       ├── document_processor.py   # Text extraction
│       ├── openai_service.py       # AI operations
│       └── pinecone_service.py     # Vector operations
├── chat/                        # Intelligent chat system
│   ├── models.py               # Chat session and message models
│   ├── serializers.py          # Chat serializers
│   ├── views.py                # Chat API views
│   ├── admin.py                # Chat admin interface
│   └── services/               # Chat services
│       └── rag_service.py          # RAG implementation
├── analytics/                   # Usage analytics system
│   ├── models.py               # Analytics models
│   ├── serializers.py          # Analytics serializers
│   ├── views.py                # Analytics API views
│   ├── services.py             # Analytics tracking services
│   └── admin.py                # Analytics admin interface
├── AI_doc_process/              # Main project configuration
│   ├── settings.py             # Django settings
│   ├── urls.py                 # URL routing
│   └── wsgi.py                 # WSGI configuration
├── requirements.txt             # Python dependencies
├── .env.example                # Environment template
├── .cursorrules                # Development guidelines
└── README.md                   # Project documentation
```

---

## 🔧 Configuration

### **Environment Variables**

Essential configuration for the application:

| Variable           | Purpose             | Example                |
|--------------------|---------------------|------------------------|
| `SECRET_KEY`       | Django security key | `your-secret-key-here` |
| `DEBUG`            | Development mode    | `True`                 |
| `OPENAI_API_KEY`   | AI processing       | `sk-...`               |
| `PINECONE_API_KEY` | Vector database     | `your-pinecone-key`    |
| `DATABASE_URL`     | Database connection | `sqlite:///db.sqlite3` |

### **Admin Interface**

Access the Django admin panel at `/admin/` for:

- User management and analytics
- Document monitoring and status tracking
- Chat session oversight
- System-wide usage analytics
- Token usage monitoring

---

## 🎯 Use Cases

### **Document Analysis Workflow**

1. Upload research papers, reports, or documentation
2. System automatically extracts text and generates summaries
3. Documents are processed for semantic search
4. Engage in conversations about document content
5. Track AI usage across all operations

### **Intelligent Document Chat**

1. Ask questions about uploaded documents
2. System retrieves relevant context from documents
3. AI provides contextually aware responses
4. Maintain conversation history across sessions
5. Access previous conversations and insights

### **Usage Analytics**

1. Monitor OpenAI token consumption
2. Track usage by feature (chat, summarization, embedding)
3. View historical usage patterns
4. Administrative oversight of system usage

---

## 🔮 Future Enhancements

Based on the project scope, potential future additions include:

- Advanced risk factor extraction algorithms
- Enhanced document processing capabilities
- Extended analytics and reporting features
- Performance optimizations for large document sets

---

## 📞 Support & Development

This project follows the simplicity-first approach outlined in `.cursorrules`. All development should maintain the
clean, focused architecture while expanding functionality within the defined scope.

For development guidelines, refer to the `.cursorrules` file which defines the project's development principles and
constraints. 