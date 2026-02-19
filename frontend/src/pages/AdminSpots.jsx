import { useState, useEffect } from 'react';
import axiosInstance from '../utils/axiosInstance';
import { AdminLayout } from '../layouts/AdminLayout';
import { SpotModal } from '../components/SpotModal';
import { useToast } from '../context/ToastContext';

export function AdminSpots() {
  const [spots, setSpots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSpot, setEditingSpot] = useState(null);
  const { showToast } = useToast();

  useEffect(() => {
    fetchSpots();
  }, []);

  const fetchSpots = async () => {
    try {
      setLoading(true);
      const response = await axiosInstance.get('/api/spots/');
      setSpots(response.data);
    } catch (err) {
      console.error('Error fetching spots:', err);
      setError('Failed to load spots');
    } finally {
      setLoading(false);
    }
  };

  const handleAddSpot = () => {
    setEditingSpot(null);
    setIsModalOpen(true);
  };

  const handleEditSpot = (spot) => {
    setEditingSpot(spot);
    setIsModalOpen(true);
  };

  const handleDeactivateSpot = async (spot) => {
    if (!confirm(`Are you sure you want to deactivate "${spot.name}"?`)) {
      return;
    }

    try {
      await axiosInstance.patch(`/api/spots/${spot.id}/`, {
        is_active: false,
      });
      showToast('Spot deactivated successfully', 'success');
      fetchSpots();
    } catch (err) {
      console.error('Error deactivating spot:', err);
      showToast('Failed to deactivate spot', 'error');
    }
  };

  const handleSpotSaved = () => {
    fetchSpots();
    setIsModalOpen(false);
    showToast(
      editingSpot ? 'Spot updated successfully' : 'Spot created successfully',
      'success'
    );
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <svg
              className="animate-spin h-12 w-12 text-primary-600 mx-auto mb-4"
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
            <p className="text-gray-600">Loading spots...</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  if (error) {
    return (
      <AdminLayout>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800 font-medium">{error}</p>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Spots Management</h1>
          <button
            onClick={handleAddSpot}
            className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-bold rounded-lg transition shadow-lg hover:shadow-xl"
          >
            + Add Spot
          </button>
        </div>

        {/* Spots table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Finds
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Code
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {spots.map((spot) => (
                  <tr key={spot.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {spot.name}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          spot.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {spot.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {spot.find_count || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono">
                        {spot.unique_code}
                      </code>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {formatDate(spot.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => handleEditSpot(spot)}
                        className="text-primary-600 hover:text-primary-900 mr-4"
                      >
                        Edit
                      </button>
                      {spot.is_active && (
                        <button
                          onClick={() => handleDeactivateSpot(spot)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Deactivate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {spots.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-600">No spots found. Create your first spot!</p>
            </div>
          )}
        </div>
      </div>

      {/* Add/Edit Spot Modal */}
      <SpotModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        spot={editingSpot}
        onSaved={handleSpotSaved}
      />
    </AdminLayout>
  );
}
