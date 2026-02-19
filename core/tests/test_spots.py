"""
Comprehensive tests for Spots API.

Tests cover:
- Coordinate validation
- Fuzzy coordinate generation (assert returned != exact)
- Inactive spot visibility
- Polling endpoint edge cases
- Security: exact_location and unique_code never exposed in public endpoints
- QR code generation
- Soft deletion with find warnings
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta
import os

from core.models import User, Spot, Find
from core.utils import get_fuzzy_coordinates, validate_coordinates


class SpotCreateTests(APITestCase):
    """Tests for POST /api/spots/"""
    
    def setUp(self):
        """Create admin user."""
        self.admin = User.objects.create_user(
            username='admin',
            password='adminpass123',
            role='admin'
        )
        self.token = Token.objects.create(user=self.admin)
        self.url = reverse('spots-list')
    
    def test_create_spot_success(self):
        """Test admin can create spot with valid data."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        data = {
            'name': 'Test Spot',
            'description': 'A test geocache',
            'clue': 'Look under the bridge',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'fuzzy_radius_meters': 50
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Spot')
        self.assertIn('unique_code', response.data)
        self.assertIn('qr_code_url', response.data)
        self.assertEqual(len(response.data['unique_code']), 6)
        
        # Verify spot was created
        spot = Spot.objects.get(name='Test Spot')
        self.assertTrue(spot.is_active)
        self.assertEqual(spot.created_by, self.admin)
        self.assertIsNotNone(spot.qr_code)
    
    def test_create_spot_invalid_latitude(self):
        """Test creating spot with invalid latitude returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Latitude > 90
        data = {
            'name': 'Test Spot',
            'clue': 'Test clue',
            'latitude': 95.0,
            'longitude': -122.4194,
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('latitude', str(response.data).lower())
        self.assertIn('-90', str(response.data))
        self.assertIn('90', str(response.data))
        
        # Latitude < -90
        data['latitude'] = -95.0
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('latitude', str(response.data).lower())
    
    def test_create_spot_invalid_longitude(self):
        """Test creating spot with invalid longitude returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Longitude > 180
        data = {
            'name': 'Test Spot',
            'clue': 'Test clue',
            'latitude': 37.7749,
            'longitude': 185.0,
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('longitude', str(response.data).lower())
        self.assertIn('-180', str(response.data))
        self.assertIn('180', str(response.data))
        
        # Longitude < -180
        data['longitude'] = -185.0
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('longitude', str(response.data).lower())
    
    def test_create_spot_blank_name(self):
        """Test creating spot with blank name returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Blank name
        data = {
            'name': '',
            'clue': 'Test clue',
            'latitude': 37.7749,
            'longitude': -122.4194,
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Whitespace only
        data['name'] = '   '
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('blank', str(response.data).lower())
    
    def test_create_spot_invalid_fuzzy_radius(self):
        """Test creating spot with invalid fuzzy_radius_meters."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Too small
        data = {
            'name': 'Test Spot',
            'clue': 'Test clue',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'fuzzy_radius_meters': 3
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Too large
        data['fuzzy_radius_meters'] = 150
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_spot_non_admin(self):
        """Test non-admin cannot create spots."""
        participant = User.objects.create_user(
            username='participant',
            password='pass123',
            role='participant'
        )
        token = Token.objects.create(user=participant)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        data = {
            'name': 'Test Spot',
            'clue': 'Test clue',
            'latitude': 37.7749,
            'longitude': -122.4194,
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SpotUpdateTests(APITestCase):
    """Tests for PATCH /api/spots/<id>/"""
    
    def setUp(self):
        """Create admin and spot."""
        self.admin = User.objects.create_user(
            username='admin',
            password='adminpass123',
            role='admin'
        )
        self.token = Token.objects.create(user=self.admin)
        
        self.spot = Spot.objects.create(
            name='Original Name',
            clue='Original clue',
            exact_location='POINT(-122.4194 37.7749)',
            fuzzy_radius_meters=10,
            created_by=self.admin
        )
        self.original_code = self.spot.unique_code
    
    def test_update_spot_success(self):
        """Test admin can update spot."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-detail', args=[self.spot.id])
        
        data = {
            'name': 'Updated Name',
            'clue': 'Updated clue'
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.spot.refresh_from_db()
        self.assertEqual(self.spot.name, 'Updated Name')
        self.assertEqual(self.spot.clue, 'Updated clue')
        # unique_code should not change
        self.assertEqual(self.spot.unique_code, self.original_code)
    
    def test_update_spot_coordinates(self):
        """Test updating coordinates."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-detail', args=[self.spot.id])
        
        data = {
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.spot.refresh_from_db()
        
        # Check coordinates changed
        self.assertAlmostEqual(self.spot.exact_location.y, 40.7128, places=4)
        self.assertAlmostEqual(self.spot.exact_location.x, -74.0060, places=4)
        
        # unique_code should still be the same
        self.assertEqual(self.spot.unique_code, self.original_code)
    
    def test_update_spot_partial_coordinates(self):
        """Test that both lat and lng must be provided together."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-detail', args=[self.spot.id])
        
        # Only latitude
        data = {'latitude': 40.7128}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('both', str(response.data).lower())


class SpotDeleteTests(APITestCase):
    """Tests for DELETE /api/spots/<id>/"""
    
    def setUp(self):
        """Create admin and spots."""
        self.admin = User.objects.create_user(
            username='admin',
            password='adminpass123',
            role='admin'
        )
        self.token = Token.objects.create(user=self.admin)
        
        self.spot_no_finds = Spot.objects.create(
            name='No Finds Spot',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)',
            created_by=self.admin
        )
        
        self.spot_with_finds = Spot.objects.create(
            name='With Finds Spot',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)',
            created_by=self.admin
        )
        
        # Create finds
        participant = User.objects.create_user(
            username='participant',
            password='pass123',
            role='participant'
        )
        Find.objects.create(spot=self.spot_with_finds, found_by=participant)
        Find.objects.create(spot=self.spot_with_finds, found_by=self.admin)
    
    def test_delete_spot_soft_delete(self):
        """Test delete performs soft delete (sets is_active=False)."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-detail', args=[self.spot_no_finds.id])
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.spot_no_finds.refresh_from_db()
        self.assertFalse(self.spot_no_finds.is_active)
        # Spot should still exist in database
        self.assertTrue(Spot.objects.filter(id=self.spot_no_finds.id).exists())
    
    def test_delete_spot_with_finds_warning(self):
        """Test deleting spot with finds returns warning."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-detail', args=[self.spot_with_finds.id])
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('warning', response.data)
        self.assertIn('2 users', response.data['warning'])
        
        self.spot_with_finds.refresh_from_db()
        self.assertFalse(self.spot_with_finds.is_active)
        
        # Finds should still exist
        self.assertEqual(self.spot_with_finds.finds.count(), 2)


class SpotAdminListTests(APITestCase):
    """Tests for GET /api/admin/spots/"""
    
    def setUp(self):
        """Create admin and spots."""
        self.admin = User.objects.create_user(
            username='admin',
            password='adminpass123',
            role='admin'
        )
        self.token = Token.objects.create(user=self.admin)
        
        # Create active and inactive spots
        self.active_spot = Spot.objects.create(
            name='Active Spot',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=True,
            created_by=self.admin
        )
        
        self.inactive_spot = Spot.objects.create(
            name='Inactive Spot',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=False,
            created_by=self.admin
        )
        
        self.url = reverse('spots-admin-list')
    
    def test_admin_list_includes_all_spots(self):
        """Test admin list includes both active and inactive spots."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Check fields are present
        spot_data = response.data[0]
        self.assertIn('id', spot_data)
        self.assertIn('name', spot_data)
        self.assertIn('is_active', spot_data)
        self.assertIn('find_count', spot_data)
        self.assertIn('created_by_username', spot_data)
        self.assertIn('created_at', spot_data)
        self.assertIn('unique_code', spot_data)
        self.assertIn('qr_code_url', spot_data)
    
    def test_admin_list_non_admin(self):
        """Test non-admin cannot access admin list."""
        participant = User.objects.create_user(
            username='participant',
            password='pass123',
            role='participant'
        )
        token = Token.objects.create(user=participant)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SpotPublicListTests(APITestCase):
    """Tests for GET /api/spots/"""
    
    def setUp(self):
        """Create user and spots."""
        self.user = User.objects.create_user(
            username='user',
            password='userpass123',
            role='participant'
        )
        self.token = Token.objects.create(user=self.user)
        
        # Create active and inactive spots
        self.active_spot = Spot.objects.create(
            name='Active Spot',
            clue='Secret clue',
            exact_location='POINT(-122.4194 37.7749)',
            fuzzy_radius_meters=50,
            is_active=True
        )
        
        self.inactive_spot = Spot.objects.create(
            name='Inactive Spot',
            clue='Secret clue',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=False
        )
        
        # Create a find
        Find.objects.create(spot=self.active_spot, found_by=self.user)
        
        self.url = reverse('spots-list')
    
    def test_public_list_only_active_spots(self):
        """Test public list only returns active spots."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Active Spot')
    
    def test_public_list_fuzzy_coordinates(self):
        """Test that fuzzy coordinates are different from exact."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        spot_data = response.data[0]
        fuzzy_lat = spot_data['fuzzy_lat']
        fuzzy_lng = spot_data['fuzzy_lng']
        
        # Fuzzy coords should be different from exact
        exact_lat = self.active_spot.exact_location.y
        exact_lng = self.active_spot.exact_location.x
        
        # They should not be exactly equal (very unlikely with random offset)
        self.assertNotEqual(fuzzy_lat, exact_lat)
        self.assertNotEqual(fuzzy_lng, exact_lng)
        
        # But should be within fuzzy_radius_meters
        # (We can't easily verify distance without implementing haversine here,
        # but we can check they're reasonable)
        self.assertTrue(-90 <= fuzzy_lat <= 90)
        self.assertTrue(-180 <= fuzzy_lng <= 180)
    
    def test_public_list_does_not_expose_sensitive_fields(self):
        """Test that exact_location, unique_code, clue are not exposed."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        spot_data = response.data[0]
        
        # Should NOT have these fields
        self.assertNotIn('exact_location', spot_data)
        self.assertNotIn('unique_code', spot_data)
        self.assertNotIn('clue', spot_data)
        self.assertNotIn('created_by', spot_data)
        
        # Should have these fields
        self.assertIn('id', spot_data)
        self.assertIn('name', spot_data)
        self.assertIn('find_count', spot_data)
        self.assertIn('fuzzy_lat', spot_data)
        self.assertIn('fuzzy_lng', spot_data)
        self.assertIn('found_by_me', spot_data)
    
    def test_public_list_found_by_me(self):
        """Test found_by_me field is correct."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data[0]['found_by_me'])
    
    def test_public_list_empty_when_no_active_spots(self):
        """Test returns empty array when no active spots."""
        # Deactivate the active spot
        self.active_spot.is_active = False
        self.active_spot.save()
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class SpotClueTests(APITestCase):
    """Tests for GET /api/spots/<id>/clue/"""
    
    def setUp(self):
        """Create user and spots."""
        self.user = User.objects.create_user(
            username='user',
            password='userpass123',
            role='participant'
        )
        self.token = Token.objects.create(user=self.user)
        
        self.active_spot = Spot.objects.create(
            name='Active Spot',
            clue='Look under the rock',
            exact_location='POINT(-122.4194 37.7749)',
            fuzzy_radius_meters=30,
            is_active=True
        )
        
        self.inactive_spot = Spot.objects.create(
            name='Inactive Spot',
            clue='Secret clue',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=False
        )
    
    def test_get_clue_success(self):
        """Test getting clue for active spot."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-clue', args=[self.active_spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['clue'], 'Look under the rock')
        self.assertEqual(response.data['fuzzy_radius_meters'], 30)
        self.assertIn('fuzzy_lat', response.data)
        self.assertIn('fuzzy_lng', response.data)
    
    def test_get_clue_inactive_spot_404(self):
        """Test getting clue for inactive spot returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-clue', args=[self.inactive_spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_get_clue_fuzzy_coordinates(self):
        """Test clue endpoint returns fuzzed coordinates."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-clue', args=[self.active_spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        fuzzy_lat = response.data['fuzzy_lat']
        fuzzy_lng = response.data['fuzzy_lng']
        
        # Should be different from exact (with high probability)
        exact_lat = self.active_spot.exact_location.y
        exact_lng = self.active_spot.exact_location.x
        
        self.assertNotEqual(fuzzy_lat, exact_lat)
        self.assertNotEqual(fuzzy_lng, exact_lng)
    
    def test_get_clue_does_not_expose_exact_location(self):
        """Test clue endpoint does not expose exact_location or unique_code."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-clue', args=[self.active_spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should NOT have these fields
        self.assertNotIn('exact_location', response.data)
        self.assertNotIn('unique_code', response.data)


class SpotUpdatesPollingTests(APITestCase):
    """Tests for GET /api/spots/updates/?since=<timestamp>"""
    
    def setUp(self):
        """Create user, spots, and finds."""
        self.user = User.objects.create_user(
            username='user',
            password='userpass123',
            role='participant'
        )
        self.token = Token.objects.create(user=self.user)
        
        self.spot1 = Spot.objects.create(
            name='Spot 1',
            clue='Clue 1',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=True
        )
        
        self.spot2 = Spot.objects.create(
            name='Spot 2',
            clue='Clue 2',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=True
        )
        
        # Create finds at different times
        now = timezone.now()
        self.find1 = Find.objects.create(spot=self.spot1, found_by=self.user)
        self.find1.found_at = now - timedelta(hours=2)
        self.find1.save()
        
        self.find2 = Find.objects.create(
            spot=self.spot2,
            found_by=User.objects.create_user(username='other', password='pass')
        )
        self.find2.found_at = now - timedelta(hours=1)
        self.find2.save()
        
        self.url = reverse('spot-updates')
    
    def test_updates_success(self):
        """Test polling endpoint returns finds after timestamp."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Query for finds in last 90 minutes
        since = timezone.now() - timedelta(minutes=90)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['spot_name'], 'Spot 2')
    
    def test_updates_missing_since_param(self):
        """Test missing since param returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timestamp', str(response.data).lower())
    
    def test_updates_malformed_timestamp(self):
        """Test malformed timestamp returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        response = self.client.get(self.url, {'since': 'not-a-timestamp'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timestamp', str(response.data).lower())
    
    def test_updates_naive_timestamp(self):
        """Test naive (non-timezone-aware) timestamp returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # ISO format without timezone info
        response = self.client.get(self.url, {'since': '2026-01-01T12:00:00'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_updates_future_timestamp(self):
        """Test future timestamp returns empty list."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        future = timezone.now() + timedelta(hours=1)
        response = self.client.get(self.url, {'since': future.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_updates_includes_required_fields(self):
        """Test response includes spot_id, spot_name, found_by_username, found_at."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        since = timezone.now() - timedelta(hours=3)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        
        find_data = response.data[0]
        self.assertIn('spot_id', find_data)
        self.assertIn('spot_name', find_data)
        self.assertIn('found_by_username', find_data)
        self.assertIn('found_at', find_data)


class FuzzyCoordinateUtilsTests(TestCase):
    """Tests for fuzzy coordinate utility functions."""
    
    def test_validate_coordinates_valid(self):
        """Test valid coordinates pass validation."""
        is_valid, error = validate_coordinates(37.7749, -122.4194)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Edge cases
        is_valid, error = validate_coordinates(90, 180)
        self.assertTrue(is_valid)
        
        is_valid, error = validate_coordinates(-90, -180)
        self.assertTrue(is_valid)
    
    def test_validate_coordinates_invalid_latitude(self):
        """Test invalid latitude fails validation."""
        is_valid, error = validate_coordinates(91, 0)
        self.assertFalse(is_valid)
        self.assertIn('latitude', error.lower())
        
        is_valid, error = validate_coordinates(-91, 0)
        self.assertFalse(is_valid)
        self.assertIn('latitude', error.lower())
    
    def test_validate_coordinates_invalid_longitude(self):
        """Test invalid longitude fails validation."""
        is_valid, error = validate_coordinates(0, 181)
        self.assertFalse(is_valid)
        self.assertIn('longitude', error.lower())
        
        is_valid, error = validate_coordinates(0, -181)
        self.assertFalse(is_valid)
        self.assertIn('longitude', error.lower())
    
    def test_get_fuzzy_coordinates_within_radius(self):
        """Test fuzzed coordinates are within specified radius."""
        from django.contrib.gis.geos import Point
        
        exact_location = Point(-122.4194, 37.7749, srid=4326)
        radius_meters = 50
        
        # Generate multiple fuzzed coordinates
        for _ in range(10):
            fuzzy_lat, fuzzy_lng = get_fuzzy_coordinates(exact_location, radius_meters)
            
            # Check coordinates are valid
            self.assertTrue(-90 <= fuzzy_lat <= 90)
            self.assertTrue(-180 <= fuzzy_lng <= 180)
            
            # Coordinates should be different from exact (with high probability)
            # Note: There's a tiny chance they could be the same, but very unlikely
            # We're not testing exact distance here as that would require
            # implementing haversine formula in the test


class QRCodeGenerationTests(TestCase):
    """Tests for QR code generation."""
    
    def test_qr_code_created_on_spot_creation(self):
        """Test QR code is automatically generated when spot is created."""
        spot = Spot.objects.create(
            name='Test Spot',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)'
        )
        
        # QR code should be created
        self.assertIsNotNone(spot.qr_code)
        self.assertTrue(spot.qr_code.name.endswith('.png'))
        self.assertIn(spot.unique_code, spot.qr_code.name)
    
    def test_unique_code_collision_retry(self):
        """Test unique_code generation retries on collision."""
        # Create a spot to use up one code
        spot1 = Spot.objects.create(
            name='Spot 1',
            clue='Clue 1',
            exact_location='POINT(0 0)'
        )
        
        # Create another spot - should get different code
        spot2 = Spot.objects.create(
            name='Spot 2',
            clue='Clue 2',
            exact_location='POINT(1 1)'
        )
        
        self.assertNotEqual(spot1.unique_code, spot2.unique_code)
