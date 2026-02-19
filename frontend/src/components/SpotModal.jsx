import { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import axiosInstance from '../utils/axiosInstance';

export function SpotModal({ isOpen, onClose, spot, onSaved }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    clue: '',
    latitude: 37.7749,
    longitude: -122.4194,
    fuzzy_radius_meters: 10,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerRef = useRef(null);

  // Initialize or update form data when spot changes
  useEffect(() => {
    if (spot) {
      setFormData({
        name: spot.name || '',
        description: spot.description || '',
        clue: spot.clue || '',
        latitude: spot.exact_lat || 37.7749,
        longitude: spot.exact_lng || -122.4194,
        fuzzy_radius_meters: spot.fuzzy_radius_meters || 10,
      });
    } else {
      setFormData({
        name: '',
        description: '',
        clue: '',
        latitude: 37.7749,
        longitude: -122.4194,
        fuzzy_radius_meters: 10,
      });
    }
    setError('');
  }, [spot, isOpen]);

  // Initialize map
  useEffect(() => {
    if (!isOpen || mapInstanceRef.current) return;

    const lat = formData.latitude;
    const lng = formData.longitude;

    // Small delay to ensure the DOM is ready
    setTimeout(() => {
      if (!mapRef.current) return;

      const map = L.map(mapRef.current, {
        center: [lat, lng],
        zoom: 13,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      // Add marker at current position
      const marker = L.marker([lat, lng], {
        draggable: true,
      }).addTo(map);

      markerRef.current = marker;

      // Update coordinates when marker is dragged
      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        setFormData((prev) => ({
          ...prev,
          latitude: pos.lat,
          longitude: pos.lng,
        }));
      });

      // Update marker when clicking on map
      map.on('click', (e) => {
        marker.setLatLng(e.latlng);
        setFormData((prev) => ({
          ...prev,
          latitude: e.latlng.lat,
          longitude: e.latlng.lng,
        }));
      });

      mapInstanceRef.current = map;
    }, 100);

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markerRef.current = null;
      }
    };
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update marker position when coordinates change externally
  useEffect(() => {
    if (markerRef.current && mapInstanceRef.current) {
      markerRef.current.setLatLng([formData.latitude, formData.longitude]);
      mapInstanceRef.current.setView([formData.latitude, formData.longitude]);
    }
  }, [formData.latitude, formData.longitude]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        clue: formData.clue.trim(),
        exact_lat: parseFloat(formData.latitude),
        exact_lng: parseFloat(formData.longitude),
        fuzzy_radius_meters: parseInt(formData.fuzzy_radius_meters),
      };

      if (spot) {
        // Update existing spot
        await axiosInstance.patch(`/api/spots/${spot.id}/`, payload);
      } else {
        // Create new spot
        await axiosInstance.post('/api/spots/', payload);
      }

      onSaved();
    } catch (err) {
      console.error('Error saving spot:', err);
      const errorMessage =
        err.response?.data?.error ||
        err.response?.data?.message ||
        'Failed to save spot. Please check your inputs.';
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-2xl max-w-4xl w-full my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">
            {spot ? 'Edit Spot' : 'Add New Spot'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 rounded-full hover:bg-gray-100 transition"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Error message */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 text-sm font-medium">{error}</p>
            </div>
          )}

          {/* Map */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Location (Click or drag marker)
            </label>
            <div
              ref={mapRef}
              className="w-full h-64 rounded-lg border border-gray-300"
            ></div>
            <p className="mt-2 text-sm text-gray-600">
              Lat: {formData.latitude.toFixed(6)}, Lng:{' '}
              {formData.longitude.toFixed(6)}
            </p>
          </div>

          {/* Name */}
          <div>
            <label
              htmlFor="name"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Spot Name *
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="Golden Gate Cache"
            />
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="description"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Description
            </label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="A brief description of this cache..."
            />
          </div>

          {/* Clue */}
          <div>
            <label
              htmlFor="clue"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Clue *
            </label>
            <textarea
              id="clue"
              name="clue"
              value={formData.clue}
              onChange={handleChange}
              required
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="Look for a small container near the old oak tree..."
            />
          </div>

          {/* Fuzzy Radius */}
          <div>
            <label
              htmlFor="fuzzy_radius_meters"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Fuzzy Radius (meters) *
            </label>
            <input
              type="number"
              id="fuzzy_radius_meters"
              name="fuzzy_radius_meters"
              value={formData.fuzzy_radius_meters}
              onChange={handleChange}
              required
              min="5"
              max="100"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            <p className="mt-1 text-sm text-gray-600">
              Distance in meters to obscure exact location (5-100)
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-6 py-3 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-6 py-3 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white font-bold rounded-lg transition disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Saving...
                </span>
              ) : spot ? (
                'Update Spot'
              ) : (
                'Create Spot'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
