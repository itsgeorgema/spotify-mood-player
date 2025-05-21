import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import PlayerPage from './pages/PlayerPage';
import LoginSuccess from './pages/LoginSuccess'; 
import { SpotifyDevice } from './types';
import { apiClient } from './api/client';
import './App.css';

// Helper function to determine the API endpoint base
const getApiEndpoint = (pathStartingWithApi: string) => {
  if (import.meta.env.DEV) {
    // In development, use relative paths for the Vite proxy.
    return pathStartingWithApi;
  } else if (import.meta.env.VITE_BACKEND_API_URL.substring(import.meta.env.VITE_BACKEND_API_URL.length-4)=='/api') {
    // In production, use the full backend URL from environment variables.
        return `${import.meta.env.VITE_BACKEND_API_URL}${pathStartingWithApi.substring(4)}`;
  }
  else{
    return `${import.meta.env.VITE_BACKEND_API_URL}${pathStartingWithApi}`;
  }
};


function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedMood, setSelectedMood] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('');
  const [devices, setDevices] = useState<SpotifyDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);

  const checkAuthStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(getApiEndpoint('/api/check_auth'), {
        credentials: 'include'
      });
      const data = await response.json();
      setIsAuthenticated(data.isAuthenticated);
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const response = await (fetch(getApiEndpoint('/api/devices'), {
        credentials: 'include'
      }));
      if (response.ok) {
        const data = await response.json();
        if(data.devices){
          setDevices(data.devices);
        }}
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      setDevices([]);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated){
      fetchDevices();
    }
    else{
      setDevices([]);
      setSelectedDeviceId(null);
    }
  }, [isAuthenticated, fetchDevices]);

  const handleLogin = () => {
    console.log('Initiating Spotify login...');
    setMessage('Redirecting to Spotify login...');
    apiClient.initiateLogin();
  };

  const handleLogout = async () => {
    try {
      const response = await fetch(getApiEndpoint('/api/logout'), {
        method: 'POST',
        credentials: 'include'
      });
      if (response.ok) {
        setIsAuthenticated(false);
        setSelectedMood(null);
      }
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const handleMoodSelect = async (mood: string) => {
    setSelectedMood(mood);
    // ... rest of your mood selection logic
  };

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  return (
  <Router>
    <Routes>
      <Route path="/callback" 
        element={
          <LoginSuccess 
            checkAuthStatus={checkAuthStatus}
          />
        } 
      />
      <Route path="/player" 
        element={
          <PlayerPage
            isAuthenticated={isAuthenticated}
            isLoading={isLoading}
            selectedMood={selectedMood}
            message={message}
            devices={devices}
            selectedDeviceId={selectedDeviceId}
            setSelectedDeviceId={setSelectedDeviceId}
            handleLogout={handleLogout}
            handleMoodSelect={handleMoodSelect}
          />
        } 
      />
      <Route path="/" 
        element={
          <LoginPage
            isAuthenticated={isAuthenticated}
            handleLogin={handleLogin}
            isLoading={isLoading}
          />
        } 
      />
    </Routes>
  </Router>
);}

export default App;