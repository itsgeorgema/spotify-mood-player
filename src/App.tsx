import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import PlayerPage from './pages/PlayerPage';
import LoginSuccess from './pages/LoginSuccess'; 
import MusicAnalysisLoading from './pages/MusicAnalysisLoading';
import Failure from './pages/Failure';
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

// Types
interface SpotifyDevice {
  id: string;
  name: string;
  is_active: boolean;
  is_private_session: boolean;
  is_restricted: boolean;
  type: string;
  volume_percent: number;
}

interface Message {
  type: 'success' | 'warning';
  text: string;
}

interface LoginProps {
  onLogin: () => void;
}

interface MoodSelectorProps {
  onMoodSelect: (mood: string) => void;
  selectedMood: string | null;
  onLogout: () => Promise<void>;
}

interface DeviceSelectorProps {
  devices: SpotifyDevice[];
  selectedDevice: SpotifyDevice | null;
  onDeviceSelect: (device: SpotifyDevice | null) => void;
  onPlay: (deviceId: string) => Promise<void>;
  isLoading: boolean;
}

interface MessageProps {
  type: 'success' | 'warning';
  children: React.ReactNode;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedMood, setSelectedMood] = useState<string | null>(null);
  const [message, setMessage] = useState<Message | null>(null);
  const [devices, setDevices] = useState<SpotifyDevice[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<SpotifyDevice | null>(null);

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
      setSelectedDevice(null);
    }
  }, [isAuthenticated, fetchDevices]);

  const handleLogin = () => {
    console.log('Initiating Spotify login...');
    setMessage({ type: 'warning', text: 'Redirecting to Spotify login...' });
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
        setDevices([]);
        setSelectedDevice(null);
        setMessage(null);
      }
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const handleMoodSelect = async (mood: string) => {
    if (!selectedDevice) {
        setMessage({ type: 'warning', text: 'Please select a playback device first.' });
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
            setMessage({ type: 'warning', text: 'Your music library is still being analyzed. Please wait a moment and try again.' });
            setSelectedMood(null);
            return;
        }

        if (!moodCheckResponse.ok) {
            throw new Error(moodData.error || 'Failed to check mood data');
        }

        // If no tracks for this mood, show message and return early
        if (!moodData.track_uris || moodData.track_uris.length === 0) {
            setMessage({ type: 'warning', text: `No ${mood} tracks found in your library. Try another mood.` });
            setSelectedMood(null);
            return;
        }

        // If we have tracks, proceed with playback
        setIsLoading(true);
        setMessage({ type: 'warning', text: `Loading ${mood} playlist...` });

        const playResponse = await fetch(getApiEndpoint('/api/play'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                track_uris: moodData.track_uris,
                device_id: selectedDevice.id
            })
        });

        if (!playResponse.ok) {
            const errorData = await playResponse.json();
            throw new Error(errorData.error || 'Failed to play tracks');
        }

        setMessage({ type: 'success', text: `Playing ${mood} music...` });

    } catch (error) {
        console.error('Error in handleMoodSelect:', error);
        setMessage({ type: 'warning', text: error instanceof Error ? error.message : 'Failed to play tracks. Please try again.' });
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
      <div className="app">
        {message && (
          <div className={`message ${message.type === 'warning' ? 'warning-message' : ''}`}>
            {message.text}
          </div>
        )}
        <Routes>
          <Route path="/callback" 
            element={
              <LoginSuccess 
                checkAuthStatus={checkAuthStatus}
              />
            } 
          />
          <Route path="/failure" element={<Failure handleLogout={handleLogout} />} />
          <Route path="/player" 
            element={
              <PlayerPage
                isAuthenticated={isAuthenticated}
                isLoading={isLoading}
                selectedMood={selectedMood}
                message={message?.text || ''}
                devices={devices}
                selectedDeviceId={selectedDevice?.id || ''}
                setSelectedDeviceId={(id: string) => setSelectedDevice(devices.find(d => d.id === id) || null)}
                handleLogout={handleLogout}
                handleMoodSelect={handleMoodSelect}
              />
            } 
          />
          <Route path="/" 
            element={
              isAuthenticated ? (
                <PlayerPage
                  isAuthenticated={isAuthenticated}
                  isLoading={isLoading}
                  selectedMood={selectedMood}
                  message={message?.text || ''}
                  devices={devices}
                  selectedDeviceId={selectedDevice?.id || ''}
                  setSelectedDeviceId={(id: string) => setSelectedDevice(devices.find(d => d.id === id) || null)}
                  handleLogout={handleLogout}
                  handleMoodSelect={handleMoodSelect}
                />
              ) : (
                <LoginPage
                  isAuthenticated={isAuthenticated}
                  handleLogin={handleLogin}
                  isLoading={isLoading}
                />
              )
            }
          />
          <Route path="/analyzing" element={<MusicAnalysisLoading />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;