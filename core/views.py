from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.db.models import Count, Q
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import User, Spot, Find
from core.serializers import (
    LoginSerializer, UserInfoSerializer, LoginResponseSerializer,
    UserListSerializer, UserCreateSerializer, UserUpdateSerializer,
    UserDetailSerializer,
    SpotCreateSerializer, SpotUpdateSerializer, SpotAdminListSerializer,
    SpotAdminDetailSerializer, SpotPublicListSerializer, SpotClueSerializer,
    FindUpdateSerializer
)
from core.permissions import IsAdminRole, check_last_admin


# ============================================================================
# AUTH ENDPOINTS (Public)
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='10/m', method='POST')
def login_view(request):
    """
    POST /api/auth/login/
    
    Accepts username + password, returns token and user info.
    
    Edge cases:
    - is_active=False: 403 "Your account has been deactivated. Contact an admin."
    - Wrong credentials: 401 "Invalid username or password."
    - Rate limit: max 10 per IP per minute, returns 429
    """
    # Check if rate limited
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return Response(
            {'error': 'Too many login attempts. Try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    serializer = LoginSerializer(data=request.data)
    
    try:
        serializer.is_valid(raise_exception=True)
    except Exception as e:
        # Handle different error codes
        if hasattr(e, 'detail') and isinstance(e.detail, dict):
            error_detail = e.detail
            if hasattr(error_detail.get('non_field_errors', [{}])[0], 'code'):
                code = error_detail['non_field_errors'][0].code
                message = str(error_detail['non_field_errors'][0])
                
                if code == 'account_deactivated':
                    return Response(
                        {'error': message},
                        status=status.HTTP_403_FORBIDDEN
                    )
                elif code == 'invalid_credentials':
                    return Response(
                        {'error': message},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
        
        # Default error handling
        return Response(
            {'error': 'Invalid username or password.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    user = serializer.validated_data['user']
    
    # Get or create token
    token, created = Token.objects.get_or_create(user=user)
    
    # Return token and user info
    return Response({
        'token': token.key,
        'id': user.id,
        'username': user.username,
        'role': user.role,
        'display_name': user.display_name
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    POST /api/auth/logout/
    
    Delete the user's token. Idempotent - returns 200 even if no token exists.
    """
    # Try to get token from Authorization header
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Token '):
        token_key = auth_header.split(' ')[1]
        Token.objects.filter(key=token_key).delete()
    
    # Also delete token if user is authenticated
    if request.user.is_authenticated:
        Token.objects.filter(user=request.user).delete()
    
    return Response(
        {'message': 'Successfully logged out.'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    GET /api/auth/me/
    
    Return current user info: id, username, role, display_name, find_count, date_joined.
    """
    serializer = UserInfoSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================================================
# ADMIN USER MANAGEMENT ENDPOINTS
# ============================================================================

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for admin user management.
    
    - POST /api/admin/users/ - create user
    - GET /api/admin/users/ - list users
    - GET /api/admin/users/<id>/ - retrieve user
    - PATCH /api/admin/users/<id>/ - update user
    - DELETE /api/admin/users/<id>/ - delete user
    """
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        """
        Return all users with find_count annotation.
        Support ?search= and ?role= filters.
        """
        queryset = User.objects.annotate(_find_count=Count('finds'))
        
        # Search filter
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(email__icontains=search)
            )
        
        # Role filter
        role = self.request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
        
        return queryset.order_by('-date_joined')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'retrieve':
            return UserDetailSerializer
        else:  # list
            return UserListSerializer
    
    def create(self, request, *args, **kwargs):
        """
        POST /api/admin/users/
        
        Create a new user. All accounts start with is_active=True.
        
        Edge cases:
        - Username already exists: 400 "Username already taken."
        - Password under 8 chars: 400 "Password must be at least 8 characters."
        - Invalid role: 400 with valid choices listed.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Return the created user
        response_serializer = UserDetailSerializer(user)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def partial_update(self, request, *args, **kwargs):
        """
        PATCH /api/admin/users/<id>/
        
        Update role, display_name, email, is_active, or reset password.
        
        Edge cases:
        - Admin cannot deactivate themselves
        - Admin cannot demote themselves
        - Cannot remove the last active admin
        - Password validation if provided
        """
        user = self.get_object()
        
        # Check if admin is trying to modify their own account
        if user.id == request.user.id:
            # Check if trying to deactivate self
            if 'is_active' in request.data and not request.data['is_active']:
                return Response(
                    {'error': 'You cannot deactivate your own account.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if trying to demote self
            if 'role' in request.data and request.data['role'] != 'admin':
                return Response(
                    {'error': 'You cannot change your own role.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if this would leave no active admins
        if user.role == 'admin' and user.is_active:
            # Check if deactivating
            if 'is_active' in request.data and not request.data['is_active']:
                if check_last_admin(user):
                    return Response(
                        {'error': 'Cannot remove the last active admin.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check if demoting
            if 'role' in request.data and request.data['role'] != 'admin':
                if check_last_admin(user):
                    return Response(
                        {'error': 'Cannot remove the last active admin.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # Proceed with update
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated user
        response_serializer = UserDetailSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/admin/users/<id>/
        
        Hard delete user. Finds are CASCADE deleted.
        
        Edge cases:
        - Admin cannot delete themselves
        - Cannot delete last active admin
        """
        user = self.get_object()
        
        # Check if admin is trying to delete themselves
        if user.id == request.user.id:
            return Response(
                {'error': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if this would leave no active admins
        if user.role == 'admin' and user.is_active:
            if check_last_admin(user):
                return Response(
                    {'error': 'Cannot remove the last active admin.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Delete user (finds will CASCADE delete)
        user.delete()
        
        return Response(
            {'message': 'User successfully deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


# ============================================================================
# SPOT ENDPOINTS
# ============================================================================

class SpotViewSet(viewsets.ModelViewSet):
    """
    ViewSet for spot management.
    
    Admin endpoints (IsAdminRole required):
    - POST /api/spots/ - create spot
    - PATCH /api/spots/<id>/ - update spot
    - DELETE /api/spots/<id>/ - soft delete (set is_active=False)
    - GET /api/admin/spots/ - list all spots (via custom action)
    
    Public endpoints (authenticated):
    - GET /api/spots/ - list active spots with fuzzy coordinates
    - GET /api/spots/<id>/clue/ - get clue with fuzzy coordinates
    """
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'admin_list']:
            return [IsAdminRole()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """Return queryset based on action and permissions."""
        if self.action == 'admin_list':
            # Admin sees all spots (active and inactive)
            return Spot.objects.annotate(_find_count=Count('finds')).order_by('-created_at')
        else:
            # Public sees only active spots
            return Spot.objects.filter(is_active=True).annotate(_find_count=Count('finds')).order_by('-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return SpotCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return SpotUpdateSerializer
        elif self.action == 'admin_list':
            return SpotAdminListSerializer
        elif self.action == 'clue':
            return SpotClueSerializer
        elif self.action == 'list':
            return SpotPublicListSerializer
        else:
            return SpotAdminDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """
        POST /api/spots/
        
        Create a spot with QR code generation.
        
        Edge cases:
        - Coordinate validation (lat: -90 to 90, lng: -180 to 180)
        - Name cannot be blank or whitespace
        - fuzzy_radius_meters must be 5-100
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Add created_by
        spot = serializer.save(created_by=request.user)
        
        # Return full spot data including qr_code_url
        response_serializer = SpotAdminDetailSerializer(spot, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def partial_update(self, request, *args, **kwargs):
        """
        PATCH /api/spots/<id>/
        
        Update spot fields. QR code and unique_code never change.
        """
        spot = self.get_object()
        serializer = self.get_serializer(spot, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated spot
        response_serializer = SpotAdminDetailSerializer(spot, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/spots/<id>/
        
        Soft delete (set is_active=False).
        
        Edge cases:
        - If spot has finds, still allow but return warning
        - Never hard delete spots with finds (PROTECT at DB level)
        """
        spot = self.get_object()
        
        # Check if spot has finds
        find_count = spot.finds.count()
        
        # Soft delete
        spot.is_active = False
        spot.save()
        
        # Build response
        response_data = {'message': 'Spot deactivated.'}
        if find_count > 0:
            response_data['warning'] = f'Note: {find_count} users had already found this cache.'
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='admin-list', permission_classes=[IsAdminRole])
    def admin_list(self, request):
        """
        GET /api/admin/spots/
        
        List all spots (active and inactive) for admins.
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def clue(self, request, pk=None):
        """
        GET /api/spots/<id>/clue/
        
        Return clue and fuzzed coordinates.
        
        Edge cases:
        - If spot is inactive: 404 (don't reveal it exists)
        """
        try:
            spot = Spot.objects.get(pk=pk, is_active=True)
        except Spot.DoesNotExist:
            return Response(
                {'error': 'Spot not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(spot, context={'request': request})
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spot_updates_view(request):
    """
    GET /api/spots/updates/?since=<iso_timestamp>
    
    Polling endpoint for recent finds.
    
    Edge cases:
    - Missing or malformed since param: 400
    - Future timestamp: return empty list
    - Timestamps must be timezone-aware
    """
    since_param = request.query_params.get('since')
    
    if not since_param:
        return Response(
            {'error': 'Provide a valid ISO 8601 timestamp.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Parse timestamp
    try:
        since_datetime = parse_datetime(since_param)
        if since_datetime is None:
            raise ValueError("Invalid datetime format")
    except (ValueError, TypeError):
        return Response(
            {'error': 'Provide a valid ISO 8601 timestamp.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if timezone-aware
    if timezone.is_naive(since_datetime):
        return Response(
            {'error': 'Provide a valid ISO 8601 timestamp.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get finds after the timestamp
    finds = Find.objects.filter(
        found_at__gt=since_datetime,
        spot__is_active=True  # Only include finds for active spots
    ).select_related('spot', 'found_by').order_by('found_at')
    
    # Serialize
    serializer = FindUpdateSerializer(finds, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

