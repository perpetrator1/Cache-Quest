import { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useAuth } from '../hooks/useAuth';
import { useWindowSize } from '../hooks/useWindowSize';
import { useToast } from '../context/ToastContext';
import { useWebSocket } from '../hooks/useWebSocket';
import axiosInstance from '../utils/axiosInstance';
import { SpotMarker } from '../components/SpotMarker';
import { BottomSheet } from '../components/BottomSheet';
import { ClaimModal } from '../components/ClaimModal';
import { LogOut } from '../components/Icons';

export function MapPage() {
  const { user, logout } = useAuth();
  const { isMobile } = useWindowSize();
  const { showToast } = useToast();
  
  const [spots, setSpots] = useState([]);
  const [userFinds, setUserFinds] = useState(new Set());
  const [selectedSpot, setSelectedSpot] = useState(null);
  const [clueData, setClueData] = useState(null);
  const [isLoadingClue, setIsLoadingClue] = useState(false);
  const [error, setError] = useState(null);
  const [isClaimModalOpen, setIsClaimModalOpen] = useState(false);
  
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const circleRef = useRef(null);
  const popupRef = useRef(null);

  // WebSocket connection for real-time updates
  const token = localStorage.getItem('auth_token');
  const wsUrl = token ? `ws://localhost:8000/ws/cache/?token=${token}` : null;
  
  const handleWebSocketMessage = (data) => {
    if (data.type === 'cache.found') {
      // Show toast notification
      showToast(`📍 ${data.username} just found ${data.spot_name}!`, 'info', 4000);
      
      // Update the spot marker if it's visible
      if (data.spot_id) {
        setUserFinds((prev) => new Set([...prev, data.spot_id]));
        
        // Update spots list to increment find count
        setSpots((prevSpots) =>
          prevSpots.map((spot) =>
            spot.id === data.spot_id
              ? { ...spot, find_count: spot.find_count + 1 }
              : spot
          )
        );
      }
    }
  };

  useWebSocket(wsUrl, handleWebSocketMessage, !!token);

  // Initialize map
  useEffect(() => {
    if (mapInstanceRef.current) return; // Already initialized

    const map = L.map(mapRef.current, {
      center: [37.7749, -122.4194], // Default to San Francisco
      zoom: 13,
      zoomControl: true,
    });

    // Add OSM tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Fetch spots and user finds
  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch all spots
        const spotsResponse = await axiosInstance.get('/api/spots/');
        setSpots(spotsResponse.data);

        // Fetch user's finds
        const findsResponse = await axiosInstance.get('/api/users/me/finds/');
        const foundSpotIds = new Set(findsResponse.data.map(f => f.spot_id));
        setUserFinds(foundSpotIds);

        // Center map on first spot if available
        if (spotsResponse.data.length > 0 && mapInstanceRef.current) {
          const firstSpot = spotsResponse.data[0];
          mapInstanceRef.current.setView([firstSpot.fuzzy_lat, firstSpot.fuzzy_lng], 13);
        }
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('Failed to load cache locations');
      }
    }

    fetchData();
  }, []);

  // Handle marker click
  const handleMarkerClick = (spot) => {
    setSelectedSpot(spot);
    setClueData(null); // Reset clue data
    setError(null);
  };

  // Handle get clue
  const handleGetClue = async () => {
    if (!selectedSpot) return;

    setIsLoadingClue(true);
    setError(null);

    try {
      const response = await axiosInstance.get(`/api/spots/${selectedSpot.id}/clue/`);
      setClueData(response.data);

      // Draw circle on map
      if (mapInstanceRef.current && response.data.fuzzy_lat && response.data.fuzzy_lng) {
        // Remove existing circle
        if (circleRef.current) {
          circleRef.current.remove();
        }

        // Create new circle
        const circle = L.circle(
          [response.data.fuzzy_lat, response.data.fuzzy_lng],
          {
            radius: response.data.fuzzy_radius_meters,
            color: '#22c55e',
            fillColor: '#22c55e',
            fillOpacity: 0.2,
            weight: 2,
          }
        ).addTo(mapInstanceRef.current);

        circleRef.current = circle;

        // Pan to circle
        mapInstanceRef.current.setView(
          [response.data.fuzzy_lat, response.data.fuzzy_lng],
          Math.max(mapInstanceRef.current.getZoom(), 15)
        );
      }
    } catch (err) {
      console.error('Error fetching clue:', err);
      setError(err.response?.data?.error || 'Failed to load clue');
    } finally {
      setIsLoadingClue(false);
    }
  };

  // Handle close sheet/popup
  const handleClose = () => {
    setSelectedSpot(null);
    setClueData(null);
    setError(null);

    // Remove circle
    if (circleRef.current) {
      circleRef.current.remove();
      circleRef.current = null;
    }

    // Remove popup
    if (popupRef.current && mapInstanceRef.current) {
      mapInstanceRef.current.closePopup(popupRef.current);
      popupRef.current = null;
    }
  };

  // Handle claim success
  const handleClaimSuccess = () => {
    showToast('🎉 Cache found!', 'success');
    
    // Update local state to mark this spot as found
    if (selectedSpot) {
      setUserFinds((prev) => new Set([...prev, selectedSpot.id]));
      
      // Update spots list to increment find count
      setSpots((prevSpots) =>
        prevSpots.map((spot) =>
          spot.id === selectedSpot.id
            ? { ...spot, find_count: spot.find_count + 1 }
            : spot
        )
      );
    }
  };

  // Handle logout
  const handleLogout = async () => {
    await logout();
    // The AuthContext will clear localStorage and AuthProvider will redirect
  };

  // Render spot details content
  const renderSpotDetails = () => {
    if (!selectedSpot) return null;

    const alreadyFound = userFinds.has(selectedSpot.id);

    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-gray-900">{selectedSpot.name}</h2>
        
        <div className="flex items-center gap-3 text-sm text-gray-600 font-medium">
          <span className="bg-primary-100 text-primary-800 px-3 py-1 rounded-full font-bold">
            {selectedSpot.find_count} {selectedSpot.find_count === 1 ? 'find' : 'finds'}
          </span>
          {alreadyFound && (
            <span className="bg-gray-200 text-gray-700 px-3 py-1 rounded-full font-bold">
              ✓ Found
            </span>
          )}
        </div>

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800 text-sm font-medium">{error}</p>
          </div>
        )}

        {!clueData && !error && (
          <button
            onClick={handleGetClue}
            disabled={isLoadingClue}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-lg transition shadow-lg hover:shadow-xl disabled:cursor-not-allowed flex items-center justify-center"
            style={{ minHeight: '44px' }}
          >
            {isLoadingClue ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            
            {!alreadyFound && (
              <button
                onClick={() => setIsClaimModalOpen(true)}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition shadow-lg hover:shadow-xl flex items-center justify-center"
                style={{ minHeight: '44px' }}
              >
                🎯 Claim this cache
              </button>
            )}
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Loading...
              </>
            ) : (
              'Get Clue'
            )}
          </button>
        )}

        {clueData && (
          <div className="space-y-3">
            <div className="p-4 bg-primary-50 border-2 border-primary-200 rounded-lg">
              <p className="font-bold text-gray-900 text-base leading-relaxed">{clueData.clue}</p>
            </div>
            <p className="text-sm text-gray-600 font-medium">
              A circle has been drawn on the map showing the approximate location.
            </p>
          </div>
        )}
      </div>
    );
  };

  // Show desktop popup or mobile bottom sheet
  useEffect(() => {
    if (!selectedSpot || !mapInstanceRef.current) return;

    if (!isMobile) {
      // Desktop: use Leaflet popup
      const popupContent = document.createElement('div');
      popupContent.style.minWidth = '280px';
      
      const popup = L.popup({
        closeButton: true,
        autoClose: true,
        closeOnClick: false,
      })
        .setLatLng([selectedSpot.fuzzy_lat, selectedSpot.fuzzy_lng])
        .setContent(popupContent)
        .openOn(mapInstanceRef.current);

      popup.on('remove', handleClose);
      popupRef.current = popup;

      // We'll use a portal or render the content separately
      // For simplicity, we'll use the BottomSheet on mobile only
    }
  }, [selectedSpot, isMobile]);

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      {/* Map container */}
      <div ref={mapRef} className="absolute inset-0 z-0" />

      {/* Header bar */}
      <div className="absolute top-0 left-0 right-0 z-30 bg-white/90 backdrop-blur-sm shadow-md">
        <div className="flex items-center justify-between px-4 py-3 md:px-6">
          <h1 className="text-xl md:text-2xl font-bold text-gray-900">
            Cache Quest
          </h1>
          
          <div className="flex items-center gap-3">
            <span className="hidden md:inline text-sm font-medium text-gray-700">
              {user?.display_name || user?.username}
            </span>
            
            {/* Admin Panel button (only for admins) */}
            {user?.role === 'admin' && (
              <a
                href="/admin"
                className="flex items-center gap-2 px-3 py-2 bg-primary-100 hover:bg-primary-200 text-primary-700 font-medium rounded-lg transition"
                style={{ minHeight: '44px' }}
              >
                <span>⚙️</span>
                <span className="hidden md:inline">Admin Panel</span>
              </a>
            )}
            
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium rounded-lg transition"
              style={{ minHeight: '44px', minWidth: '44px' }}
              aria-label="Log out"
            >
              <LogOut />
              <span className="hidden md:inline">Log Out</span>
            </button>
          </div>
        </div>
      </div>

      {/* Render markers */}
      {spots.map((spot) => (
        <SpotMarker
          key={spot.id}
          map={mapInstanceRef.current}
          spot={spot}
          found={userFinds.has(spot.id)}
          onClick={handleMarkerClick}
        />
      ))}

      {/* Mobile: Bottom sheet */}
      {isMobile && (
        <BottomSheet isOpen={!!selectedSpot} onClose={handleClose}>
          {renderSpotDetails()}
        </BottomSheet>
      )}

      {/* Desktop: Modal overlay (simplified popup alternative) */}
      {!isMobile && selectedSpot && (
        <div className="absolute inset-0 z-40 flex items-center justify-center pointer-events-none">
          <div className="bg-white rounded-lg shadow-2xl p-6 max-w-md w-full mx-4 pointer-events-auto">
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 p-2 text-gray-500 hover:text-gray-700 rounded-full hover:bg-gray-100 transition"
              style={{ minWidth: '44px', minHeight: '44px' }}
              aria-label="Close"
            >
              ✕
            </button>
            {renderSpotDetails()}
          </div>
        </div>
      )}

      {/* Claim Modal */}
      <ClaimModal
        spot={selectedSpot}
        isOpen={isClaimModalOpen}
        onClose={() => setIsClaimModalOpen(false)}
        onSuccess={handleClaimSuccess}
      />
    </div>
  );
}
