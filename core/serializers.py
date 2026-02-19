from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Count
from core.models import User, Spot, Find
from core.utils import validate_coordinates, create_point_from_coords, get_fuzzy_coordinates


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Check if user exists and is active
            try:
                user = User.objects.get(username=username)
                if not user.is_active:
                    raise serializers.ValidationError(
                        "Your account has been deactivated. Contact an admin.",
                        code='account_deactivated'
                    )
            except User.DoesNotExist:
                pass  # Will be caught by authenticate below
            
            # Authenticate user
            user = authenticate(username=username, password=password)
            
            if not user:
                raise serializers.ValidationError(
                    "Invalid username or password.",
                    code='invalid_credentials'
                )
            
            attrs['user'] = user
        else:
            raise serializers.ValidationError(
                "Must include username and password.",
                code='missing_fields'
            )
        
        return attrs


class UserInfoSerializer(serializers.ModelSerializer):
    """
    Serializer for user info returned after login or in /me endpoint.
    """
    find_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'display_name', 'find_count', 'date_joined']
        read_only_fields = fields
    
    def get_find_count(self, obj):
        """Return the number of finds for this user."""
        return obj.finds.count()


class LoginResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for login response with token.
    """
    token = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['token', 'id', 'username', 'role', 'display_name']
        read_only_fields = fields


class UserListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing users (admin endpoint).
    """
    find_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'display_name',
            'is_active', 'find_count', 'date_joined', 'last_login'
        ]
        read_only_fields = fields
    
    def get_find_count(self, obj):
        """Return the number of finds for this user."""
        # Use annotation if available (from queryset), otherwise count
        if hasattr(obj, '_find_count'):
            return obj._find_count
        return obj.finds.count()


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users (admin only).
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role', 'display_name']
    
    def validate_username(self, value):
        """Check if username already exists."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value
    
    def validate_password(self, value):
        """Validate password length."""
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters."
            )
        return value
    
    def validate_role(self, value):
        """Validate role is one of the allowed choices."""
        allowed_roles = ['admin', 'participant']
        if value not in allowed_roles:
            raise serializers.ValidationError(
                f"Invalid role. Must be one of: {', '.join(allowed_roles)}"
            )
        return value
    
    def create(self, validated_data):
        """Create user with hashed password."""
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_active = True  # All new accounts start active
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating users (admin only).
    Supports updating role, display_name, email, is_active, and password reset.
    """
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['role', 'display_name', 'email', 'is_active', 'password']
    
    def validate_password(self, value):
        """Validate password length if provided."""
        if value and len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters."
            )
        return value
    
    def validate_role(self, value):
        """Validate role is one of the allowed choices."""
        allowed_roles = ['admin', 'participant']
        if value not in allowed_roles:
            raise serializers.ValidationError(
                f"Invalid role. Must be one of: {', '.join(allowed_roles)}"
            )
        return value
    
    def update(self, instance, validated_data):
        """Update user, hash password if provided."""
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed user view (admin endpoint).
    """
    find_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'display_name',
            'is_active', 'find_count', 'date_joined', 'last_login',
            'is_staff', 'is_superuser'
        ]
        read_only_fields = fields
    
    def get_find_count(self, obj):
        """Return the number of finds for this user."""
        return obj.finds.count()


# ============================================================================
# SPOT SERIALIZERS
# ============================================================================

class SpotCreateSerializer(serializers.Serializer):
    """
    Serializer for creating spots (admin only).
    Accepts lat/lng and converts to PostGIS Point.
    """
    name = serializers.CharField(required=True, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    clue = serializers.CharField(required=True)
    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    fuzzy_radius_meters = serializers.IntegerField(
        required=False,
        default=10,
        min_value=5,
        max_value=100
    )
    
    def validate_name(self, value):
        """Ensure name is not blank or whitespace only."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be blank or whitespace only.")
        return value.strip()
    
    def validate(self, attrs):
        """Validate coordinates."""
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        
        is_valid, error_msg = validate_coordinates(latitude, longitude)
        if not is_valid:
            raise serializers.ValidationError(error_msg)
        
        return attrs
    
    def create(self, validated_data):
        """Create spot with PostGIS Point."""
        latitude = validated_data.pop('latitude')
        longitude = validated_data.pop('longitude')
        
        # Create PostGIS Point
        exact_location = create_point_from_coords(latitude, longitude)
        
        # Create spot
        spot = Spot.objects.create(
            exact_location=exact_location,
            **validated_data
        )
        
        return spot


class SpotUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating spots (admin only).
    """
    name = serializers.CharField(required=False, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    clue = serializers.CharField(required=False)
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    fuzzy_radius_meters = serializers.IntegerField(required=False, min_value=5, max_value=100)
    
    def validate_name(self, value):
        """Ensure name is not blank or whitespace only."""
        if value is not None and (not value or not value.strip()):
            raise serializers.ValidationError("Name cannot be blank or whitespace only.")
        return value.strip() if value else value
    
    def validate(self, attrs):
        """Validate coordinates if provided."""
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        
        # If one coordinate is provided, both must be provided
        if (latitude is not None) != (longitude is not None):
            raise serializers.ValidationError(
                "Both latitude and longitude must be provided together."
            )
        
        if latitude is not None and longitude is not None:
            is_valid, error_msg = validate_coordinates(latitude, longitude)
            if not is_valid:
                raise serializers.ValidationError(error_msg)
        
        return attrs
    
    def update(self, instance, validated_data):
        """Update spot fields."""
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        # Update coordinates if provided
        if latitude is not None and longitude is not None:
            instance.exact_location = create_point_from_coords(latitude, longitude)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class SpotAdminListSerializer(serializers.ModelSerializer):
    """
    Serializer for admin list view of all spots (active and inactive).
    """
    find_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Spot
        fields = [
            'id', 'name', 'is_active', 'find_count', 'created_by_username',
            'created_at', 'unique_code', 'qr_code_url'
        ]
        read_only_fields = fields
    
    def get_find_count(self, obj):
        """Return the number of finds for this spot."""
        if hasattr(obj, '_find_count'):
            return obj._find_count
        return obj.finds.count()
    
    def get_qr_code_url(self, obj):
        """Return the absolute URL for the QR code."""
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None


class SpotAdminDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for admin detail view with all fields.
    """
    find_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = Spot
        fields = [
            'id', 'name', 'description', 'clue', 'latitude', 'longitude',
            'fuzzy_radius_meters', 'unique_code', 'qr_code_url', 'is_active',
            'find_count', 'created_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_find_count(self, obj):
        """Return the number of finds for this spot."""
        return obj.finds.count()
    
    def get_qr_code_url(self, obj):
        """Return the absolute URL for the QR code."""
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None
    
    def get_latitude(self, obj):
        """Return latitude from exact_location."""
        return obj.exact_location.y
    
    def get_longitude(self, obj):
        """Return longitude from exact_location."""
        return obj.exact_location.x


class SpotPublicListSerializer(serializers.ModelSerializer):
    """
    Serializer for public list view - only active spots with fuzzed coordinates.
    Does NOT expose: exact_location, unique_code, clue, created_by.
    """
    find_count = serializers.SerializerMethodField()
    fuzzy_lat = serializers.SerializerMethodField()
    fuzzy_lng = serializers.SerializerMethodField()
    found_by_me = serializers.SerializerMethodField()
    
    class Meta:
        model = Spot
        fields = ['id', 'name', 'find_count', 'fuzzy_lat', 'fuzzy_lng', 'found_by_me']
        read_only_fields = fields
    
    def get_find_count(self, obj):
        """Return the number of finds for this spot."""
        if hasattr(obj, '_find_count'):
            return obj._find_count
        return obj.finds.count()
    
    def get_fuzzy_lat(self, obj):
        """Return fuzzed latitude."""
        fuzzy_lat, _ = get_fuzzy_coordinates(obj.exact_location, obj.fuzzy_radius_meters)
        return fuzzy_lat
    
    def get_fuzzy_lng(self, obj):
        """Return fuzzed longitude."""
        _, fuzzy_lng = get_fuzzy_coordinates(obj.exact_location, obj.fuzzy_radius_meters)
        return fuzzy_lng
    
    def get_found_by_me(self, obj):
        """Return True if current user has found this spot."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Find.objects.filter(spot=obj, found_by=request.user).exists()
        return False


class SpotClueSerializer(serializers.ModelSerializer):
    """
    Serializer for clue endpoint - returns clue and fuzzed coordinates.
    Does NOT expose exact_location or unique_code.
    """
    fuzzy_lat = serializers.SerializerMethodField()
    fuzzy_lng = serializers.SerializerMethodField()
    
    class Meta:
        model = Spot
        fields = ['id', 'name', 'clue', 'fuzzy_radius_meters', 'fuzzy_lat', 'fuzzy_lng']
        read_only_fields = fields
    
    def get_fuzzy_lat(self, obj):
        """Return fuzzed latitude."""
        fuzzy_lat, _ = get_fuzzy_coordinates(obj.exact_location, obj.fuzzy_radius_meters)
        return fuzzy_lat
    
    def get_fuzzy_lng(self, obj):
        """Return fuzzed longitude."""
        _, fuzzy_lng = get_fuzzy_coordinates(obj.exact_location, obj.fuzzy_radius_meters)
        return fuzzy_lng


class FindUpdateSerializer(serializers.Serializer):
    """
    Serializer for polling endpoint - recent finds.
    """
    spot_id = serializers.IntegerField(source='spot.id')
    spot_name = serializers.CharField(source='spot.name')
    found_by_username = serializers.CharField(source='found_by.username')
    found_at = serializers.DateTimeField()


class ClaimCacheSerializer(serializers.Serializer):
    """
    Serializer for claiming a cache by code.
    """
    code = serializers.CharField(required=True)
    
    def validate_code(self, value):
        """Validate code format."""
        # Check if code is provided and not blank
        if not value or not value.strip():
            raise serializers.ValidationError("Please provide a cache code.")
        
        value = value.strip().upper()
        
        # Check if code contains only alphanumeric characters
        if not value.isalnum():
            raise serializers.ValidationError("Invalid code format.")
        
        # Check if code is exactly 6 characters
        if len(value) != 6:
            raise serializers.ValidationError("Cache codes are 6 characters long.")
        
        return value


class ClaimCacheResponseSerializer(serializers.Serializer):
    """
    Serializer for successful cache claim response.
    """
    spot_id = serializers.IntegerField()
    spot_name = serializers.CharField()
    found_at = serializers.DateTimeField()
    total_finds = serializers.IntegerField()
    message = serializers.CharField()


class SpotFindSerializer(serializers.Serializer):
    """
    Serializer for listing finds for a specific spot.
    """
    username = serializers.SerializerMethodField()
    found_at = serializers.DateTimeField()
    
    def get_username(self, obj):
        """Return display_name if set, else username."""
        if obj.found_by.display_name:
            return obj.found_by.display_name
        return obj.found_by.username


class UserFindHistorySerializer(serializers.Serializer):
    """
    Serializer for user's find history.
    """
    spot_id = serializers.IntegerField(source='spot.id')
    spot_name = serializers.CharField(source='spot.name')
    found_at = serializers.DateTimeField()

