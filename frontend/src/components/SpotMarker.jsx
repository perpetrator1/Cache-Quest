import { useEffect } from 'react';
import L from 'leaflet';

/**
 * Custom marker component using Leaflet divIcon
 * Renders as green pulsing dot (not found) or grey dot (found)
 */
export function SpotMarker({ map, spot, found, onClick }) {
  useEffect(() => {
    if (!map || !spot) return;

    // Create custom HTML for marker
    const markerHtml = found
      ? `<div class="spot-marker spot-marker-found"></div>`
      : `<div class="spot-marker spot-marker-active"></div>`;

    // Create divIcon
    const icon = L.divIcon({
      html: markerHtml,
      className: 'spot-marker-wrapper',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });

    // Create marker
    const marker = L.marker([spot.fuzzy_lat, spot.fuzzy_lng], { icon });

    // Add click handler
    marker.on('click', () => onClick(spot));

    // Add to map
    marker.addTo(map);

    // Cleanup
    return () => {
      marker.remove();
    };
  }, [map, spot, found, onClick]);

  return null;
}

// CSS for markers (to be added to index.css)
export const markerStyles = `
.spot-marker-wrapper {
  background: transparent;
  border: none;
}

.spot-marker {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 3px solid #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  cursor: pointer;
}

.spot-marker-active {
  background: #22c55e;
  animation: pulse 2s infinite;
}

.spot-marker-found {
  background: #9ca3af;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(34, 197, 94, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);
  }
}

/* Ensure markers are tappable on mobile */
.leaflet-marker-icon {
  cursor: pointer !important;
}
`;
