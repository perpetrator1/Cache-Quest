# Cache Quest

An open-source geocaching platform built with Django 4.2, PostGIS, and Django REST Framework.

## Features

- **Custom User Management**: Role-based access (admin/participant) with admin-only account creation
- **Geocaching Spots**: Create and manage geocaching locations with PostGIS-powered mapping
- **Find Tracking**: Track user discoveries with unique spot codes
- **Django Admin**: Full-featured admin interface for managing users, spots, and finds

## Tech Stack

- Python 3.11
- Django 4.2
- Django REST Framework
- PostgreSQL + PostGIS
- django-allauth (authentication)
- dj-database-url (database configuration)
- python-decouple (environment management)

## Project Structure

```
Cache-Quest/
├── cache_quest/          # Django project settings
│   ├── __init__.py
│   ├── settings.py       # Main settings file
│   ├── urls.py          # URL configuration
│   ├── wsgi.py          # WSGI application
│   └── asgi.py          # ASGI application
├── core/                # Main application
│   ├── migrations/      # Database migrations
│   ├── __init__.py
│   ├── models.py        # User, Spot, Find models
│   ├── admin.py         # Django admin configuration
│   ├── apps.py          # App configuration
│   ├── adapters.py      # Custom allauth adapter
│   ├── views.py         # Views (placeholder)
│   └── tests.py         # Tests (placeholder)
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.11
- PostgreSQL with PostGIS extension
- pip and virtualenv

### 2. Database Setup

Install PostgreSQL and PostGIS:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib postgis

# macOS (using Homebrew)
brew install postgresql postgis
```

Create the database:

```bash
# Start PostgreSQL service
sudo service postgresql start  # Linux
brew services start postgresql  # macOS

# Create database with PostGIS
sudo -u postgres psql
CREATE DATABASE cache_quest_db;
\c cache_quest_db
CREATE EXTENSION postgis;
\q
```

### 3. Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 4. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

Required environment variables:
- `SECRET_KEY`: Django secret key (generate a new one for production)
- `DEBUG`: Set to `True` for development
- `DATABASE_URL`: PostgreSQL connection string
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

### 5. Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### 6. Create Superuser

```bash
# Create the first admin user
python manage.py createsuperuser
```

Note: The superuser will automatically get `role="admin"` assigned.

### 7. Run Development Server

```bash
python manage.py runserver
```

Access the application:
- Admin interface: http://127.0.0.1:8000/admin/
- API authentication: http://127.0.0.1:8000/api-auth/

## Models

### User
Custom user extending `AbstractUser` with:
- `role`: "admin" or "participant" (default: "participant")
- `display_name`: Optional display name
- `is_active`: Enable/disable accounts
- Superusers automatically get `role="admin"`

### Spot
Geocaching locations with:
- `name`, `description`, `clue`
- `exact_location`: PostGIS PointField (SRID=4326)
- `fuzzy_radius_meters`: 5-100 meters (validated)
- `unique_code`: Auto-generated 6-char alphanumeric code
- `is_active`: Enable/disable spots
- `created_by`, `created_at`, `updated_at`

### Find
User discoveries with:
- `spot`: FK to Spot (PROTECT deletion)
- `found_by`: FK to User (CASCADE deletion)
- `found_at`: Auto timestamp
- Unique constraint: (spot, found_by)

## Key Features

### No Self-Registration
Users cannot register themselves. All accounts must be created by admins through the Django admin interface.

### Protected Deletions
Spots with existing finds cannot be deleted (enforced via `on_delete=PROTECT`). Admin interface shows helpful error messages.

### Unique Code Generation
Each spot gets a unique 6-character alphanumeric code, auto-generated with collision detection.

### Find Counting
Admin interface displays annotated find counts for users and spots.

### Deactivated Users
Deactivated users (`is_active=False`) retain their finds but cannot log in.

## Admin Interface

### User Admin
- View: role, is_active, find count, last login
- Filter: role, is_active, staff status
- Search: username, email, display_name

### Spot Admin
- View: name, is_active, find count, creator, created date
- Filter: is_active, created date
- Search: name, unique_code
- Readonly: unique_code, timestamps
- Protected deletion handling

### Find Admin
- View: spot, found_by, found_at
- Filter: spot, found_at
- Search: spot name, username
- Readonly: found_at

## License

See LICENSE file for details.
