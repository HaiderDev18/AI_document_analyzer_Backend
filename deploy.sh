#!/bin/bash

# Railway deployment script
echo "Starting Railway deployment..."

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Create superuser if it doesn't exist (optional)
echo "Checking for superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('No superuser found. You can create one after deployment.')
else:
    print('Superuser already exists.')
"

echo "Deployment preparation complete!"
echo "Starting server with gunicorn..."

# Start the server
exec uvicorn AI_doc_process.asgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120