import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { MapPage } from './pages/MapPage';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminSpots } from './pages/AdminSpots';
import { AdminUsers } from './pages/AdminUsers';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<LoginPage />} />
          
          {/* Protected routes */}
          <Route
            path="/map"
            element={
              <ProtectedRoute>
                <MapPage />
              </ProtectedRoute>
            }
          />
          
          {/* Admin routes */}
          <Route
            path="/admin/dashboard"
            element={
              <ProtectedRoute adminOnly={true}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/spots"
            element={
              <ProtectedRoute adminOnly={true}>
                <AdminSpots />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute adminOnly={true}>
                <AdminUsers />
              </ProtectedRoute>
            }
          />
          
          {/* Admin default redirect */}
          <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
          
          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/map" replace />} />
          
          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/map" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App
