"""
Comprehensive tests for cache claiming and find endpoints.

Tests cover:
- All claim flow edge cases in exact priority order
- Rate limiting (20 attempts per user per hour)
- Code enumeration protection
- Brute-force prevention
- Spot finds listing
- User find history
- Polling endpoint capping (>7 days = max 100 entries)
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from core.models import User, Spot, Find


class ClaimCacheTests(APITestCase):
    """Tests for POST /api/spots/claim/"""
    
    def setUp(self):
        """Create user and spot."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='participant'
        )
        self.token = Token.objects.create(user=self.user)
        
        self.spot = Spot.objects.create(
            name='Test Cache',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=True
        )
        # Store the unique code for testing
        self.valid_code = self.spot.unique_code
        
        self.inactive_spot = Spot.objects.create(
            name='Inactive Cache',
            clue='Test clue',
            exact_location='POINT(-122.4194 37.7749)',
            is_active=False
        )
        self.inactive_code = self.inactive_spot.unique_code
        
        self.url = reverse('claim-cache')
    
    def test_claim_success(self):
        """Test successful cache claim."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        data = {'code': self.valid_code}
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['spot_id'], self.spot.id)
        self.assertEqual(response.data['spot_name'], 'Test Cache')
        self.assertEqual(response.data['total_finds'], 1)
        self.assertEqual(response.data['message'], 'Cache found!')
        self.assertIn('found_at', response.data)
        
        # Verify find was created
        self.assertTrue(Find.objects.filter(spot=self.spot, found_by=self.user).exists())
    
    def test_claim_missing_code(self):
        """Edge case 1: Missing or blank code field."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Missing code field
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Please provide a cache code.')
        
        # Blank code
        response = self.client.post(self.url, {'code': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Please provide a cache code.')
        
        # Whitespace only
        response = self.client.post(self.url, {'code': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Please provide a cache code.')
    
    def test_claim_invalid_characters(self):
        """Edge case 2: Code contains invalid characters."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Special characters
        response = self.client.post(self.url, {'code': 'ABC-12'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid code format.')
        
        # Spaces
        response = self.client.post(self.url, {'code': 'ABC 12'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid code format.')
        
        # Special symbols
        response = self.client.post(self.url, {'code': 'ABC@12'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid code format.')
    
    def test_claim_wrong_length(self):
        """Edge case 3: Code length is not 6 characters."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Too short
        response = self.client.post(self.url, {'code': 'ABC12'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Cache codes are 6 characters long.')
        
        # Too long
        response = self.client.post(self.url, {'code': 'ABC1234'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Cache codes are 6 characters long.')
    
    def test_claim_code_not_found(self):
        """Edge case 4: No spot matches the code."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Valid format but doesn't exist
        response = self.client.post(self.url, {'code': 'ZZZZZ9'})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'No cache found with that code.')
    
    def test_claim_inactive_spot(self):
        """Edge case 5: Spot exists but is inactive."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        response = self.client.post(self.url, {'code': self.inactive_code})
        
        # Should use same message as "not found" to prevent enumeration
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'No cache found with that code.')
    
    def test_claim_already_found(self):
        """Edge case 6: User already found this spot."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Create a find first
        Find.objects.create(spot=self.spot, found_by=self.user)
        
        # Try to claim again
        response = self.client.post(self.url, {'code': self.valid_code})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'You already found this cache!')
    
    def test_claim_case_insensitive(self):
        """Test that code lookup is case-insensitive."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Try with lowercase
        response = self.client.post(self.url, {'code': self.valid_code.lower()})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Create another user and spot
        user2 = User.objects.create_user(username='user2', password='pass')
        token2 = Token.objects.create(user=user2)
        spot2 = Spot.objects.create(
            name='Spot 2',
            clue='Clue',
            exact_location='POINT(0 0)',
            is_active=True
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token2.key}')
        
        # Try with mixed case
        mixed_case = spot2.unique_code[0:3].lower() + spot2.unique_code[3:].upper()
        response = self.client.post(self.url, {'code': mixed_case})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_claim_rate_limiting(self):
        """Test rate limiting: max 20 attempts per user per hour."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Mock ratelimit to simulate being rate limited
        with patch('django_ratelimit.decorators.is_ratelimited', return_value=True):
            response = self.client.post(self.url, {'code': 'ABC123'})
            
            # Should return 429 when rate limited
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn('too many', response.data['error'].lower())
    
    def test_claim_enumeration_protection(self):
        """Test that invalid codes and inactive spots use same error message."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Try a code that doesn't exist
        response1 = self.client.post(self.url, {'code': 'ZZZZZ9'})
        
        # Try an inactive spot's code
        response2 = self.client.post(self.url, {'code': self.inactive_code})
        
        # Both should have identical error messages
        self.assertEqual(response1.status_code, response2.status_code)
        self.assertEqual(response1.data['error'], response2.data['error'])
        self.assertEqual(response1.data['error'], 'No cache found with that code.')
    
    def test_claim_unauthenticated(self):
        """Test that unauthenticated users cannot claim."""
        response = self.client.post(self.url, {'code': self.valid_code})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_claim_increments_total_finds(self):
        """Test that total_finds increments correctly."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # First claim
        response = self.client.post(self.url, {'code': self.valid_code})
        self.assertEqual(response.data['total_finds'], 1)
        
        # Create another user and claim
        user2 = User.objects.create_user(username='user2', password='pass')
        token2 = Token.objects.create(user=user2)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token2.key}')
        response = self.client.post(self.url, {'code': self.valid_code})
        self.assertEqual(response.data['total_finds'], 2)


class SpotFindsListTests(APITestCase):
    """Tests for GET /api/spots/<id>/finds/"""
    
    def setUp(self):
        """Create users, spot, and finds."""
        self.user1 = User.objects.create_user(
            username='user1',
            password='pass',
            display_name='Display Name 1'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='pass'
            # No display_name
        )
        self.token = Token.objects.create(user=self.user1)
        
        self.spot = Spot.objects.create(
            name='Test Spot',
            clue='Test clue',
            exact_location='POINT(0 0)',
            is_active=True
        )
        
        # Create finds at different times
        now = timezone.now()
        self.find1 = Find.objects.create(spot=self.spot, found_by=self.user1)
        self.find1.found_at = now - timedelta(hours=2)
        self.find1.save()
        
        self.find2 = Find.objects.create(spot=self.spot, found_by=self.user2)
        self.find2.found_at = now - timedelta(hours=1)
        self.find2.save()
        
        self.spot_no_finds = Spot.objects.create(
            name='Empty Spot',
            clue='Test clue',
            exact_location='POINT(0 0)',
            is_active=True
        )
        
        self.inactive_spot = Spot.objects.create(
            name='Inactive Spot',
            clue='Test clue',
            exact_location='POINT(0 0)',
            is_active=False
        )
    
    def test_list_finds_success(self):
        """Test listing finds for a spot."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-finds', args=[self.spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Should be ordered by found_at ascending
        self.assertEqual(response.data[0]['username'], 'Display Name 1')  # display_name used
        self.assertEqual(response.data[1]['username'], 'user2')  # username used
        
        # Check fields present
        self.assertIn('username', response.data[0])
        self.assertIn('found_at', response.data[0])
    
    def test_list_finds_display_name_priority(self):
        """Test that display_name is returned when set, else username."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-finds', args=[self.spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User1 has display_name
        self.assertEqual(response.data[0]['username'], 'Display Name 1')
        
        # User2 doesn't have display_name
        self.assertEqual(response.data[1]['username'], 'user2')
    
    def test_list_finds_empty_spot(self):
        """Test spot with no finds returns empty array."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-finds', args=[self.spot_no_finds.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        self.assertEqual(response.data, [])
    
    def test_list_finds_inactive_spot(self):
        """Test inactive spot returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-finds', args=[self.inactive_spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_list_finds_ordered_by_found_at_asc(self):
        """Test finds are ordered by found_at ascending."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        url = reverse('spots-finds', args=[self.spot.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Earlier find should come first
        found_at_1 = response.data[0]['found_at']
        found_at_2 = response.data[1]['found_at']
        
        self.assertLess(found_at_1, found_at_2)


class UserFindsHistoryTests(APITestCase):
    """Tests for GET /api/users/me/finds/"""
    
    def setUp(self):
        """Create user, spots, and finds."""
        self.user = User.objects.create_user(
            username='testuser',
            password='pass'
        )
        self.token = Token.objects.create(user=self.user)
        
        self.spot1 = Spot.objects.create(
            name='Spot 1',
            clue='Clue 1',
            exact_location='POINT(0 0)',
            is_active=True
        )
        self.spot2 = Spot.objects.create(
            name='Spot 2',
            clue='Clue 2',
            exact_location='POINT(1 1)',
            is_active=True
        )
        
        # Create finds at different times
        now = timezone.now()
        self.find1 = Find.objects.create(spot=self.spot1, found_by=self.user)
        self.find1.found_at = now - timedelta(hours=2)
        self.find1.save()
        
        self.find2 = Find.objects.create(spot=self.spot2, found_by=self.user)
        self.find2.found_at = now - timedelta(hours=1)
        self.find2.save()
        
        self.url = reverse('user-finds')
    
    def test_user_finds_success(self):
        """Test getting current user's find history."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Check fields present
        self.assertIn('spot_id', response.data[0])
        self.assertIn('spot_name', response.data[0])
        self.assertIn('found_at', response.data[0])
    
    def test_user_finds_ordered_newest_first(self):
        """Test finds are ordered newest first."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Newer find (spot2) should come first
        self.assertEqual(response.data[0]['spot_name'], 'Spot 2')
        self.assertEqual(response.data[1]['spot_name'], 'Spot 1')
        
        # Verify ordering
        found_at_1 = response.data[0]['found_at']
        found_at_2 = response.data[1]['found_at']
        
        self.assertGreater(found_at_1, found_at_2)
    
    def test_user_finds_empty(self):
        """Test user with no finds returns empty array with 200."""
        user_no_finds = User.objects.create_user(
            username='novice',
            password='pass'
        )
        token = Token.objects.create(user=user_no_finds)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        self.assertEqual(response.data, [])
    
    def test_user_finds_only_own_finds(self):
        """Test user only sees their own finds."""
        # Create another user with finds
        other_user = User.objects.create_user(username='other', password='pass')
        other_spot = Spot.objects.create(
            name='Other Spot',
            clue='Clue',
            exact_location='POINT(2 2)',
            is_active=True
        )
        Find.objects.create(spot=other_spot, found_by=other_user)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see own 2 finds, not the other user's
        self.assertEqual(len(response.data), 2)
        
        spot_names = [f['spot_name'] for f in response.data]
        self.assertNotIn('Other Spot', spot_names)


class PollingEndpointCappingTests(APITestCase):
    """Tests for GET /api/spots/updates/ with >7 days capping."""
    
    def setUp(self):
        """Create user, spot, and many finds."""
        self.user = User.objects.create_user(
            username='testuser',
            password='pass'
        )
        self.token = Token.objects.create(user=self.user)
        
        self.spot = Spot.objects.create(
            name='Popular Spot',
            clue='Clue',
            exact_location='POINT(0 0)',
            is_active=True
        )
        
        # Create 150 finds over 10 days
        now = timezone.now()
        for i in range(150):
            user = User.objects.create_user(username=f'user{i}', password='pass')
            find = Find.objects.create(spot=self.spot, found_by=user)
            # Spread finds over 10 days
            find.found_at = now - timedelta(days=10) + timedelta(hours=i)
            find.save()
        
        self.url = reverse('spot-updates')
    
    def test_polling_recent_timestamp_no_cap(self):
        """Test polling with recent timestamp (< 7 days) returns all matches."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Query for last 3 days
        since = timezone.now() - timedelta(days=3)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return all finds in last 3 days (no cap)
        # We have 150 finds over 10 days, so roughly 45 in last 3 days
        self.assertGreater(len(response.data), 40)
    
    def test_polling_old_timestamp_capped_at_100(self):
        """Test polling with old timestamp (> 7 days) caps at 100 entries."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Query for last 10 days (more than 7)
        since = timezone.now() - timedelta(days=10)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100 even though we have 150 finds
        self.assertEqual(len(response.data), 100)
    
    def test_polling_exactly_7_days(self):
        """Test polling at exactly 7 days boundary."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Query for exactly 7 days ago
        since = timezone.now() - timedelta(days=7)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still return without capping (boundary case)
        # We have finds spread over time, should get many
        self.assertGreater(len(response.data), 0)
    
    def test_polling_8_days_capped(self):
        """Test polling 8 days ago definitely gets capped."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Query for 8 days ago (more than 7)
        since = timezone.now() - timedelta(days=8)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100
        self.assertEqual(len(response.data), 100)
    
    def test_polling_returns_oldest_first(self):
        """Test that capped results are oldest first (not truncated randomly)."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Query for old timestamp
        since = timezone.now() - timedelta(days=10)
        response = self.client.get(self.url, {'since': since.isoformat()})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 100)
        
        # Verify results are ordered by found_at
        if len(response.data) > 1:
            for i in range(len(response.data) - 1):
                found_at_1 = response.data[i]['found_at']
                found_at_2 = response.data[i + 1]['found_at']
                self.assertLessEqual(found_at_1, found_at_2)


class EdgeCasePriorityTests(APITestCase):
    """Test that claim edge cases are handled in exact priority order."""
    
    def setUp(self):
        """Create user and spot."""
        self.user = User.objects.create_user(
            username='testuser',
            password='pass'
        )
        self.token = Token.objects.create(user=self.user)
        self.url = reverse('claim-cache')
    
    def test_priority_1_missing_code_before_invalid_chars(self):
        """Test priority 1 (missing code) comes before priority 2 (invalid chars)."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Blank code should trigger priority 1, not validate format
        response = self.client.post(self.url, {'code': ''})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Please provide a cache code.')
    
    def test_priority_2_invalid_chars_before_wrong_length(self):
        """Test priority 2 (invalid chars) comes before priority 3 (wrong length)."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Invalid chars with wrong length - should trigger priority 2
        response = self.client.post(self.url, {'code': 'AB@'})  # 3 chars + special char
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid code format.')
    
    def test_priority_3_wrong_length_before_not_found(self):
        """Test priority 3 (wrong length) comes before priority 4 (not found)."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Valid chars but wrong length
        response = self.client.post(self.url, {'code': 'ABC12'})  # 5 chars
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Cache codes are 6 characters long.')
    
    def test_priority_4_and_5_use_same_message(self):
        """Test priority 4 (not found) and 5 (inactive) use same message."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Create an inactive spot
        inactive_spot = Spot.objects.create(
            name='Inactive',
            clue='Clue',
            exact_location='POINT(0 0)',
            is_active=False
        )
        
        # Try non-existent code
        response1 = self.client.post(self.url, {'code': 'ZZZZZ9'})
        
        # Try inactive spot code
        response2 = self.client.post(self.url, {'code': inactive_spot.unique_code})
        
        # Both should return 404 with identical message
        self.assertEqual(response1.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response2.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response1.data['error'], response2.data['error'])
        self.assertEqual(response1.data['error'], 'No cache found with that code.')
    
    def test_priority_6_already_found_after_spot_checks(self):
        """Test priority 6 (already found) comes after spot existence checks."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        # Create spot and find
        spot = Spot.objects.create(
            name='Test',
            clue='Clue',
            exact_location='POINT(0 0)',
            is_active=True
        )
        Find.objects.create(spot=spot, found_by=self.user)
        
        # Try to claim again
        response = self.client.post(self.url, {'code': spot.unique_code})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'You already found this cache!')
