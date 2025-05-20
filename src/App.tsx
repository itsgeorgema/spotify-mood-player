import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import PlayerPage from './pages/PlayerPage';
import LoginSuccess from './pages/LoginSuccess'; 
import { SpotifyDevice } from './types';
import { apiClient } from './api/client';
import './App.css';

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
      const response = await fetch('/api/check_auth', {
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

  const handleLogin = () => {
    console.log('Initiating Spotify login...');
    setMessage('Redirecting to Spotify login...');
    apiClient.initiateLogin();
  };

  const handleLogout = async () => {
    try {
      const response = await fetch('/api/logout', {
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