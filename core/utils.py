"""
Utility functions for geocaching operations.
"""
import math
import random
from django.contrib.gis.geos import Point


def get_fuzzy_coordinates(exact_location, radius_meters):
    """
    Generate fuzzed coordinates within the specified radius.
    
    Uses haversine-based offset formula for geographically accurate fuzzing
    that accounts for latitude distortion.
    
    Args:
        exact_location: PostGIS Point object with exact coordinates
        radius_meters: Maximum offset distance in meters
        
    Returns:
        tuple: (fuzzy_lat, fuzzy_lng) as floats
    """
    # Extract exact coordinates
    exact_lng = exact_location.x  # longitude
    exact_lat = exact_location.y  # latitude
    
    # Random distance within radius (uniform distribution in area)
    # Using sqrt to ensure uniform distribution in 2D space
    distance = radius_meters * math.sqrt(random.random())
    
    # Random angle
    angle = random.random() * 2 * math.pi
    
    # Earth's radius in meters
    earth_radius = 6371000
    
    # Calculate offset in degrees
    # Latitude offset (straightforward)
    lat_offset = (distance * math.cos(angle)) / earth_radius * (180 / math.pi)
    
    # Longitude offset (adjusted for latitude)
    lng_offset = (distance * math.sin(angle)) / (earth_radius * math.cos(exact_lat * math.pi / 180)) * (180 / math.pi)
    
    # Calculate fuzzed coordinates
    fuzzy_lat = exact_lat + lat_offset
    fuzzy_lng = exact_lng + lng_offset
    
    # Ensure coordinates are within valid ranges
    fuzzy_lat = max(-90, min(90, fuzzy_lat))
    fuzzy_lng = ((fuzzy_lng + 180) % 360) - 180  # Wrap longitude to -180 to 180
    
    return fuzzy_lat, fuzzy_lng


def validate_coordinates(latitude, longitude):
    """
    Validate latitude and longitude values.
    
    Args:
        latitude: Latitude value
        longitude: Longitude value
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return False, "Coordinates must be numeric values."
    
    if lat < -90 or lat > 90:
        return False, f"Latitude must be between -90 and 90. Got: {lat}"
    
    if lng < -180 or lng > 180:
        return False, f"Longitude must be between -180 and 180. Got: {lng}"
    
    return True, None


def create_point_from_coords(latitude, longitude):
    """
    Create a PostGIS Point from latitude and longitude.
    
    Args:
        latitude: Latitude value
        longitude: Longitude value
        
    Returns:
        Point: PostGIS Point object with SRID=4326
    """
    # Point(longitude, latitude) - note the order!
    return Point(float(longitude), float(latitude), srid=4326)
