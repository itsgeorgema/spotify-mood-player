import React from 'react';
import { Navigate } from 'react-router-dom';
import { SpotifyDevice } from '../types';

interface PlayerPageProps {
  isAuthenticated: boolean;
  isLoading: boolean;
  selectedMood: string | null;
  message: string;
  devices: SpotifyDevice[];
  selectedDeviceId: string | null;
  setSelectedDeviceId: (id: string) => void;
  handleLogout: () => void;
  handleMoodSelect: (mood: string) => void;
}

function PlayerPage(props: PlayerPageProps) {
  const {
    isAuthenticated,
    isLoading,
    selectedMood,
    message,
    devices,
    selectedDeviceId,
    setSelectedDeviceId,
    handleLogout,
    handleMoodSelect
  } = props;

  if (isLoading) {
    return <div className="container">Loading player...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const moods = ["happy", "sad", "energetic", "calm"];

  return (
    <div className="container">
      <header>
        <h1>Spotify Mood Player</h1>
        <button onClick={handleLogout} className="spotify-button logout">
          Logout
        </button>
      </header>

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
        {devices.length === 0 && (
          <p className="warning-message">
            No Spotify devices found. Please open Spotify on one of your devices and ensure it's active.
          </p>
        )}
      </main>

      {message && <p className="message">{message}</p>}
      
      <footer>
        <p>Ensure Spotify is running on one of your devices.</p>
        <p>Spotify Premium may be required for certain playback controls.</p>
      </footer>
    </div>
  );
}

export default PlayerPage;