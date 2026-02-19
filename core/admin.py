from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.gis.admin import GISModelAdmin
from django.db.models import Count, ProtectedError
from django.contrib import messages
from .models import User, Spot, Find


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin with role, is_active, find_count, and last_login displayed.
    """
    list_display = [
        'username',
        'email',
        'role',
        'is_active',
        'find_count',
        'last_login',
        'is_staff',
        'is_superuser'
    ]
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'display_name']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {
            'fields': ('role', 'display_name')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Fields', {
            'fields': ('role', 'display_name')
        }),
    )
    
    def get_queryset(self, request):
        """Annotate queryset with find count."""
        qs = super().get_queryset(request)
        return qs.annotate(_find_count=Count('finds'))
    
    def find_count(self, obj):
        """Display the count of finds for each user."""
        return obj._find_count
    find_count.admin_order_field = '_find_count'
    find_count.short_description = 'Finds'


@admin.register(Spot)
class SpotAdmin(GISModelAdmin):
    """
    Spot admin with list_display, filters, search, and readonly fields.
    Handles ProtectedError when attempting to delete spots with finds.
    """
    list_display = [
        'name',
        'is_active',
        'find_count',
        'created_by',
        'created_at',
        'unique_code'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'unique_code']
    readonly_fields = ['unique_code', 'created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'description', 'clue', 'is_active')
        }),
        ('Location', {
            'fields': ('exact_location', 'fuzzy_radius_meters')
        }),
        ('Metadata', {
            'fields': ('unique_code', 'created_by', 'created_at', 'updated_at')
        }),
    ]
    
    def get_queryset(self, request):
        """Annotate queryset with find count."""
        qs = super().get_queryset(request)
        return qs.annotate(_find_count=Count('finds'))
    
    def find_count(self, obj):
        """Display the count of finds for each spot."""
        return obj._find_count
    find_count.admin_order_field = '_find_count'
    find_count.short_description = 'Finds'
    
    def delete_model(self, request, obj):
        """Handle ProtectedError when deleting a spot with finds."""
        try:
            super().delete_model(request, obj)
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete spot "{obj.name}" because it has existing finds. '
                'You must delete all finds for this spot first, or mark it as inactive.'
            )
    
    def delete_queryset(self, request, queryset):
        """Handle ProtectedError when bulk deleting spots with finds."""
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError:
            messages.error(
                request,
                'Cannot delete one or more spots because they have existing finds. '
                'You must delete all finds for these spots first, or mark them as inactive.'
            )


@admin.register(Find)
class FindAdmin(admin.ModelAdmin):
    """
    Find admin with list_display, filters, and readonly fields.
    """
    list_display = ['spot', 'found_by', 'found_at']
    list_filter = ['spot', 'found_at']
    search_fields = ['spot__name', 'found_by__username', 'found_by__display_name']
    readonly_fields = ['found_at']
    
    fieldsets = [
        (None, {
            'fields': ('spot', 'found_by', 'found_at')
        }),
    ]
