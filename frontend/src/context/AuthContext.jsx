import { useState, useEffect } from 'react';
import axiosInstance from '../utils/axiosInstance';
import { AuthContext } from './authContext';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('auth_token'));
  const [loading, setLoading] = useState(true);

  // Check if user is admin
  const isAdmin = user?.role === 'admin';

  // Validate token on app load
  useEffect(() => {
    async function validateToken() {
      const storedToken = localStorage.getItem('auth_token');
      
      if (!storedToken) {
        setLoading(false);
        return;
      }

      try {
        const response = await axiosInstance.get('/api/auth/me/');
        setUser(response.data);
        setToken(storedToken);
      } catch (error) {
        // Token is invalid or expired
        console.error('Token validation failed:', error);
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    validateToken();
  }, []);

  // Login function
  const login = async (username, password) => {
    try {
      const response = await axiosInstance.post('/api/auth/login/', {
        username,
        password,
      });

      const { token: newToken, user: userData } = response.data;
      
      // Store token and user
      localStorage.setItem('auth_token', newToken);
      localStorage.setItem('user', JSON.stringify(userData));
      
      setToken(newToken);
      setUser(userData);

      return { success: true };
    } catch (error) {
      // Return specific error message from API
      const errorMessage = 
        error.response?.data?.error || 
        error.response?.data?.detail || 
        'Login failed. Please try again.';
      
      return { success: false, error: errorMessage };
    }
  };

  // Logout function
  const logout = async () => {
    try {
      await axiosInstance.post('/api/auth/logout/');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear state and localStorage regardless of API response
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      setToken(null);
      setUser(null);
    }
  };

  const value = {
    user,
    token,
    login,
    logout,
    isAdmin,
    loading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
