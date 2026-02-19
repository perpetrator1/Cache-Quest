#!/bin/bash

# Cache Quest - Docker Setup Script

echo "🚀 Starting Cache Quest with Docker..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start containers
echo "🔨 Building containers..."
docker-compose build

echo "▶️  Starting containers..."
docker-compose up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Run migrations
echo "🔄 Running database migrations..."
docker-compose exec backend python manage.py migrate

# Create admin user
echo "👤 Creating admin user (username: admin, password: adminpass123)..."
docker-compose exec backend python manage.py shell -c "
from core.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_user(
        username='admin',
        password='adminpass123',
        role='admin',
        is_active=True,
        is_superuser=True,
        is_staff=True
    )
    print('✓ Admin user created')
else:
    print('✓ Admin user already exists')
"

echo ""
echo "✅ Cache Quest is now running!"
echo ""
echo "📍 Services:"
echo "   - Frontend: http://localhost:5173"
echo "   - Backend API: http://localhost:8000"
echo "   - Django Admin: http://localhost:8000/admin"
echo ""
echo "🔐 Admin credentials:"
echo "   Username: admin"
echo "   Password: adminpass123"
echo ""
echo "📊 View logs: docker-compose logs -f"
echo "🛑 Stop: docker-compose down"
echo ""
