"""
URL configuration for core app API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import login_view, logout_view, me_view, UserViewSet, SpotViewSet, spot_updates_view

# Router for admin user management and spots
router = DefaultRouter()
router.register(r'admin/users', UserViewSet, basename='admin-users')
router.register(r'spots', SpotViewSet, basename='spots')

urlpatterns = [
    # Auth endpoints (public)
    path('auth/login/', login_view, name='auth-login'),
    path('auth/logout/', logout_view, name='auth-logout'),
    path('auth/me/', me_view, name='auth-me'),
    
    # Spot updates polling endpoint
    path('spots/updates/', spot_updates_view, name='spot-updates'),
    
    # Admin endpoints and spot CRUD (via router)
    path('', include(router.urls)),
]
