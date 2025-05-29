import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import PlayerPage from './pages/PlayerPage';
import LoginSuccess from './pages/LoginSuccess'; 
import MusicAnalysisLoading from './pages/MusicAnalysisLoading';
import { SpotifyDevice } from './types';
import { apiClient } from './api/client';
import './App.css';

export const getApiEndpoint = (pathStartingWithApi: string) => {
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
    if (!selectedDeviceId) {
        setMessage('Please select a playback device first.');
        return;
    }

    setSelectedMood(mood);

    try {
        // Only check session data, never reanalyze
        const moodCheckResponse = await fetch(getApiEndpoint('/api/mood-tracks?mood=' + mood.toLowerCase()), {
            credentials: 'include',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        const moodData = await moodCheckResponse.json();

        // Handle case where analysis is not done yet
        if (moodCheckResponse.status === 400 && moodData.error && moodData.error.includes('No analyzed tracks in session')) {
            setMessage('Your music library is still being analyzed. Please wait a moment and try again.');
            setSelectedMood(null);
            return;
        }

        if (!moodCheckResponse.ok) {
            throw new Error(moodData.error || 'Failed to check mood data');
        }

        // If no tracks for this mood, show message and return early
        if (!moodData.track_uris || moodData.track_uris.length === 0) {
            setMessage(`No ${mood} tracks found in your library. Try another mood.`);
            setSelectedMood(null);
            return;
        }

        // If we have tracks, proceed with playback
        setIsLoading(true);
        setMessage(`Loading ${mood} playlist...`);

        const playResponse = await fetch(getApiEndpoint('/api/play'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                track_uris: moodData.track_uris,
                device_id: selectedDeviceId
            })
        });

        if (!playResponse.ok) {
            const errorData = await playResponse.json();
            throw new Error(errorData.error || 'Failed to play tracks');
        }

        setMessage(`Playing ${mood} music...`);

    } catch (error) {
        console.error('Error in handleMoodSelect:', error);
        setMessage(error instanceof Error ? error.message : 'Failed to play tracks. Please try again.');
        setSelectedMood(null);
    } finally {
        setIsLoading(false);
    }
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
      <Route path="/analyzing" element={<MusicAnalysisLoading />} />
    </Routes>
  </Router>
);}

export default App;