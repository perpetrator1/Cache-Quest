# Cache Quest - Docker Deployment

## Quick Start

### Prerequisites
- Docker
- Docker Compose

### Start Everything

```bash
./start.sh
```

Or manually:

```bash
docker-compose up -d
```

### Services

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin

### Default Admin Credentials

- **Username**: `admin`
- **Password**: `adminpass123`

## Docker Commands

### Start all services
```bash
docker-compose up -d
```

### Start with logs
```bash
docker-compose up
```

### Stop all services
```bash
docker-compose down
```

### Stop and remove volumes (delete database)
```bash
docker-compose down -v
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

### Rebuild containers
```bash
docker-compose build
docker-compose up -d
```

### Execute commands in containers
```bash
# Django shell
docker-compose exec backend python manage.py shell

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Run migrations
docker-compose exec backend python manage.py migrate

# Run tests
docker-compose exec backend python manage.py test

# Access PostgreSQL
docker-compose exec db psql -U cache_quest_user -d cache_quest
```

### Access container shell
```bash
# Backend
docker-compose exec backend bash

# Frontend
docker-compose exec frontend sh

# Database
docker-compose exec db bash
```

## Development Workflow

### Backend Development

1. Code changes are automatically reflected (volume mount)
2. Django dev server auto-reloads
3. View logs: `docker-compose logs -f backend`

### Frontend Development

1. Code changes trigger Vite HMR (hot module reload)
2. View logs: `docker-compose logs -f frontend`

### Database

- Data persists in Docker volume `postgres_data`
- To reset database: `docker-compose down -v`

## Environment Variables

### Backend (.env.docker)

```env
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgis://cache_quest_user:cache_quest_pass@db:5432/cache_quest
ALLOWED_HOSTS=localhost,127.0.0.1,backend
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
```

## Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Compose                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Frontend   │  │   Backend    │  │  PostgreSQL  │ │
│  │  (Node 18)   │  │ (Python 3.11)│  │  + PostGIS   │ │
│  │              │  │              │  │              │ │
│  │  Vite + React│  │    Django    │  │   Database   │ │
│  │   Port 5173  │  │   Port 8000  │  │   Port 5432  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│         │                 │                   │         │
│         └─────────────────┼───────────────────┘         │
│                           │                             │
└───────────────────────────┼─────────────────────────────┘
                            │
                    Volume: postgres_data
                    Volume: media_files
```

## Troubleshooting

### Port already in use

```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :5173
sudo lsof -i :5432

# Stop the process or change ports in docker-compose.yml
```

### Database connection issues

```bash
# Check if database is healthy
docker-compose ps

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Frontend not connecting to backend

1. Check VITE_API_URL in frontend/.env
2. Ensure backend is running: `docker-compose logs backend`
3. Check CORS settings in Django

### Reset everything

```bash
# Stop and remove everything
docker-compose down -v

# Rebuild and start
docker-compose build --no-cache
docker-compose up -d
```

## Production Deployment

For production, update:

1. **Backend**:
   - Set `DEBUG=False`
   - Use strong `SECRET_KEY`
   - Configure proper `ALLOWED_HOSTS`
   - Use production database credentials
   - Set up nginx/gunicorn

2. **Frontend**:
   - Build production bundle: `npm run build`
   - Serve with nginx
   - Update API URL to production backend

3. **Database**:
   - Use managed PostgreSQL service or
   - Set up proper backups
   - Use strong passwords

