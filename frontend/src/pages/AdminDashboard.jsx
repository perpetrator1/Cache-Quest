import { useState, useEffect } from 'react';
import axiosInstance from '../utils/axiosInstance';
import { AdminLayout } from '../layouts/AdminLayout';

export function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await axiosInstance.get('/api/admin/stats/');
      setStats(response.data);
    } catch (err) {
      console.error('Error fetching stats:', err);
      setError('Failed to load statistics');
    } finally {
      setLoading(false);
    }
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
            <p className="text-gray-600">Loading statistics...</p>
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
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>

        {/* Stats cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center gap-4">
              <div className="bg-blue-100 p-4 rounded-lg">
                <span className="text-3xl">📍</span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Total Spots</p>
                <p className="text-3xl font-bold text-gray-900">
                  {stats?.total_spots || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center gap-4">
              <div className="bg-green-100 p-4 rounded-lg">
                <span className="text-3xl">🎯</span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Total Finds</p>
                <p className="text-3xl font-bold text-gray-900">
                  {stats?.total_finds || 0}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Top users and spots */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Most Active Users */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">Most Active Users</h2>
            </div>
            <div className="p-6">
              {stats?.most_active_users?.length > 0 ? (
                <div className="space-y-3">
                  {stats.most_active_users.map((user, index) => (
                    <div
                      key={user.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-gray-400">
                          #{index + 1}
                        </span>
                        <div>
                          <p className="font-medium text-gray-900">
                            {user.display_name || user.username}
                          </p>
                          <p className="text-sm text-gray-600">@{user.username}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-primary-600">
                          {user.find_count}
                        </p>
                        <p className="text-xs text-gray-600">finds</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-600 text-center py-8">No finds yet</p>
              )}
            </div>
          </div>

          {/* Most Found Spots */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">Most Found Spots</h2>
            </div>
            <div className="p-6">
              {stats?.most_found_spots?.length > 0 ? (
                <div className="space-y-3">
                  {stats.most_found_spots.map((spot, index) => (
                    <div
                      key={spot.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-gray-400">
                          #{index + 1}
                        </span>
                        <p className="font-medium text-gray-900">{spot.name}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-green-600">
                          {spot.find_count}
                        </p>
                        <p className="text-xs text-gray-600">finds</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-600 text-center py-8">No finds yet</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
