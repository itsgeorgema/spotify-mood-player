// src/App.tsx
import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

interface SpotifyDevice {
  id: string | null;
  is_active: boolean;
  is_private_session: boolean;
  is_restricted: boolean;
  name: string;
  type: string;
  volume_percent: number | null;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true); // Start with loading true
  const [selectedMood, setSelectedMood] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('');
  const [devices, setDevices] = useState<SpotifyDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);

  const BACKEND_API_URL = import.meta.env.VITE_BACKEND_API_URL || 'http://localhost:5001/api';

  const checkAuthStatus = useCallback(async () => {
    console.log('Frontend: checkAuthStatus called');
    // setIsLoading(true); // isLoading is managed by the calling useEffect or initial state
    try {
      const response = await fetch(`${BACKEND_API_URL}/check_auth`, {
        method: 'GET',
        credentials: 'include', 
      });
      console.log('Frontend: /check_auth response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('Frontend: /check_auth data:', data);
        setIsAuthenticated(data.isAuthenticated);
      } else {
        console.log('Frontend: /check_auth failed, setting isAuthenticated to false');
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Frontend: Error checking auth status:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false); // Always set loading to false after the check completes
    }
  }, [BACKEND_API_URL]);

  useEffect(() => {
    // This effect runs once on component mount due to stable checkAuthStatus
    console.log('Frontend: Initial mount useEffect running');
    const queryParams = new URLSearchParams(window.location.search);
    const loginSuccess = queryParams.get('login_success') === 'true';

    if (loginSuccess) {
      console.log('Frontend: login_success=true found in URL.');
      // Clean the URL query parameters
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    // Regardless of loginSuccess, we need to check the actual auth status with the backend.
    // setIsLoading(true) is already set initially.
    checkAuthStatus();
  }, [checkAuthStatus]); // Runs on mount because checkAuthStatus is stable (due to useCallback)

  const fetchDevices = useCallback(async () => {
    if (!isAuthenticated) {
      console.log('Frontend: fetchDevices skipped, not authenticated.');
      return;
    }
    console.log('Frontend: fetchDevices called');
    try {
      const response = await fetch(`${BACKEND_API_URL}/devices`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        console.log('Frontend: /devices data:', data);
        setDevices(data.devices || []);
        const activeDevice = data.devices?.find((d: SpotifyDevice) => d.is_active);
        if (activeDevice) {
          setSelectedDeviceId(activeDevice.id);
        } else if (data.devices?.length > 0) {
          setSelectedDeviceId(data.devices[0].id);
        }
      } else {
        console.error('Frontend: Failed to fetch devices');
        setDevices([]);
      }
    } catch (error) {
      console.error('Frontend: Error fetching devices:', error);
      setDevices([]);
    }
  }, [BACKEND_API_URL, isAuthenticated]);

  useEffect(() => {
    console.log('Frontend: isAuthenticated changed to:', isAuthenticated);
    if (isAuthenticated) {
      fetchDevices();
    } else {
      // Clear sensitive data if not authenticated
      setDevices([]);
      setSelectedDeviceId(null);
      // setSelectedMood(null); // Optionally reset mood
      // setMessage(''); // Optionally clear messages
    }
  }, [isAuthenticated, fetchDevices]);


  const handleLogin = () => {
    console.log('Frontend: handleLogin called. Redirecting to backend login.');
    setMessage('Redirecting to Spotify for login...');
    window.location.href = `${BACKEND_API_URL}/login`;
  };

  const handleLogout = async () => {
    console.log('Frontend: handleLogout called.');
    try {
      const response = await fetch(`${BACKEND_API_URL}/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      if (response.ok) {
        setIsAuthenticated(false);
        setSelectedMood(null);
        setMessage('Logged out successfully.');
      } else {
        setMessage('Logout failed.');
      }
    } catch (error) {
      console.error('Frontend: Error logging out:', error);
      setMessage('Error logging out.');
    }
  };

  const handleMoodSelect = async (mood: string) => {
    console.log(`Frontend: handleMoodSelect called with mood: ${mood}`);
    if (!isAuthenticated) {
      setMessage('Please log in with Spotify first.');
      return;
    }
    if (!selectedDeviceId) {
        setMessage('No active Spotify device selected or found. Please open Spotify on a device.');
        fetchDevices();
        return;
    }

    setSelectedMood(mood);
    setMessage(`Fetching songs for ${mood} mood...`);

    try {
      const tracksResponse = await fetch(`${BACKEND_API_URL}/mood-tracks?mood=${mood}`, {
        credentials: 'include',
      });

      if (!tracksResponse.ok) {
        const errorData = await tracksResponse.json();
        throw new Error(errorData.error || `Failed to get tracks for ${mood}.`);
      }
      const { track_uris } = await tracksResponse.json();

      if (!track_uris || track_uris.length === 0) {
        setMessage(`No tracks found for ${mood}. Try another mood!`);
        return;
      }

      const playResponse = await fetch(`${BACKEND_API_URL}/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ track_uris, device_id: selectedDeviceId }),
      });

      if (!playResponse.ok) {
        const errorData = await playResponse.json();
        throw new Error(errorData.error || 'Failed to start playback.');
      }
      setMessage(`Now playing ${mood} tracks! Check your Spotify.`);

    } catch (error: any) {
      console.error('Frontend: Error handling mood select:', error);
      setMessage(`Error: ${error.message}. Make sure Spotify is active on a device.`);
      if (error.message.includes("User not authenticated")) {
        setIsAuthenticated(false);
      }
    }
  };

  if (isLoading) {
    return <div className="container">Loading application state...</div>;
  }

  const moods = ["happy", "sad", "energetic", "calm"];

  return (
    <div className="container">
      <header>
        <h1>Spotify Mood Player</h1>
        {!isAuthenticated ? (
          <button onClick={handleLogin} className="spotify-button login">
            Login with Spotify
          </button>
        ) : (
          <button onClick={handleLogout} className="spotify-button logout">
            Logout
          </button>
        )}
      </header>

      {isAuthenticated && (
        <main>
          <h2>Select Your Mood:</h2>
          <div className="mood-buttons">
            {moods.map((mood) => (
              <button
                key={mood}
                onClick={() => handleMoodSelect(mood)}
                className={`mood-button ${selectedMood === mood ? 'selected' : ''} mood-${mood}`}
              >
                {mood.charAt(0).toUpperCase() + mood.slice(1)}
              </button>
            ))}
          </div>

          {devices.length > 0 && (
            <div className="device-selector">
              <h3>Select Device:</h3>
              <select
                value={selectedDeviceId || ''}
                onChange={(e) => setSelectedDeviceId(e.target.value)}
              >
                {devices.map((device) => (
                  <option key={device.id || 'unknown_device'} value={device.id || ''}>
                    {device.name} ({device.type})
                  </option>
                ))}
              </select>
            </div>
          )}
           {devices.length === 0 && ( // Show this only if authenticated but no devices
            <p className="warning-message">No Spotify devices found. Please open Spotify on one of your devices and ensure it's active, then try refreshing or selecting a mood again.</p>
          )}
        </main>
      )}

      {message && <p className="message">{message}</p>}
      
      <footer>
        <p>Ensure Spotify is running on one of your devices.</p>
        <p>Spotify Premium may be required for certain playback controls.</p>
      </footer>
    </div>
  );
}

export default App;
