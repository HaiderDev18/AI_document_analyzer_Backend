#!/bin/bash
# Railway deployment script
echo "Starting Railway deployment..."

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create database if it doesn't exist (for Docker PostgreSQL)
echo "Setting up database..."
docker exec -it be-document-analyzer-postgres-1 psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'ai_doc_process'" | grep -q 1 || \
docker exec -it be-document-analyzer-postgres-1 psql -U postgres -c "CREATE DATABASE ai_doc_process"

# Collect static files
echo "Collecting static files..."
python3 manage.py collectstatic --noinput

# Run database migrations
echo "Running database migrations..."
python3 manage.py migrate

# Create superuser if it doesn't exist
echo "Checking for superuser..."
python3 manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('No superuser found. You can create one after deployment.')
else:
    print('Superuser already exists.')
"

echo "Deployment preparation complete!"
echo "Starting server with uvicorn on port ${PORT:-8000}..."

# Start the server
exec uvicorn AI_doc_process.asgi:application --host 0.0.0.0 --port ${PORT:-8000} --workers 4 --timeout-keep-alive 120