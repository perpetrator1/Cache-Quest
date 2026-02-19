import random
import string
import os
import qrcode
from io import BytesIO
from django.core.files import File
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction
from django.conf import settings


class User(AbstractUser):
    """
    Custom User model extending AbstractUser.
    No self-registration - accounts created by admins only.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('participant', 'Participant'),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='participant'
    )
    display_name = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return self.display_name or self.username
    
    def save(self, *args, **kwargs):
        # Automatically set role to 'admin' for superusers
        if self.is_superuser and not self.role:
            self.role = 'admin'
        elif self.is_superuser:
            self.role = 'admin'
        super().save(*args, **kwargs)


class Spot(models.Model):
    """
    Represents a geocaching spot with location and clue information.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    clue = models.TextField(
        help_text="What the user sees after clicking the spot"
    )
    exact_location = models.PointField(
        srid=4326,
        help_text="Exact GPS coordinates (SRID=4326)"
    )
    fuzzy_radius_meters = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(5), MaxValueValidator(100)],
        help_text="Fuzzy radius in meters (5-100)"
    )
    unique_code = models.CharField(
        max_length=6,
        unique=True,
        editable=False,
        help_text="Auto-generated 6-character alphanumeric code"
    )
    qr_code = models.ImageField(
        upload_to='qrcodes/',
        blank=True,
        null=True,
        help_text="QR code image for this spot"
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_spots'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.unique_code})"
    
    def _generate_unique_code(self):
        """Generate a unique 6-character alphanumeric code."""
        import random
        import string
        
        max_attempts = 100
        for _ in range(max_attempts):
            code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
            if not Spot.objects.filter(unique_code=code).exists():
                return code
        
        raise ValueError("Could not generate unique code after maximum attempts")
    
    def _generate_qr_code(self):
        """Generate QR code image for this spot's unique_code."""
        if not self.unique_code:
            return
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.unique_code)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Save to model field
        filename = f'{self.unique_code}.png'
        self.qr_code.save(filename, File(buffer), save=False)
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate unique_code and QR code if not set."""
        is_new = self.pk is None
        
        if not self.unique_code:
            self.unique_code = self._generate_unique_code()
        
        # Save first to get an ID
        super().save(*args, **kwargs)
        
        # Generate QR code if this is a new spot and QR doesn't exist
        if is_new and not self.qr_code:
            self._generate_qr_code()
            # Save again to update the qr_code field
            super().save(update_fields=['qr_code'])


class Find(models.Model):
    """
    Represents a user finding a spot.
    Each user can only find each spot once.
    """
    spot = models.ForeignKey(
        'Spot',
        on_delete=models.PROTECT,  # Prevent deletion of spots with finds
        related_name='finds'
    )
    found_by = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='finds'
    )
    found_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['spot', 'found_by']]
        ordering = ['-found_at']
        verbose_name_plural = 'finds'
    
    def __str__(self):
        return f"{self.found_by} found {self.spot.name} at {self.found_at}"
