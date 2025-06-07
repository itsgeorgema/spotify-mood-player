import { Navigate } from 'react-router-dom';
import { SpotifyDevice } from '../types';
import MusicAnalysisLoading from './MusicAnalysisLoading';
import './PlayerPage.css';

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
    return <MusicAnalysisLoading />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const moods = [
    { id: 'happy', label: 'Happy' },
    { id: 'sad', label: 'Sad' },
    { id: 'mad', label: 'Mad' },
    { id: 'calm', label: 'Calm' },
    { id: 'romantic', label: 'Romantic' },
    { id: 'energetic', label: 'Energetic' },
    { id: 'focused', label: 'Focused' },
    { id: 'mysterious', label: 'Mysterious' }
  ];

  return (
    <div
      className="app float-in-delay-1"
    >
      <header className="player-header">
        <h1 className="login-title float-in-delay-2">Mood Player</h1>
        <p className="subtitle float-in-delay-3">Select your mood and device</p>
        <p className="tagline float-in-delay-4" style={{ color: '#b3b3b3' }}>Let your feelings pick the soundtrack</p>
      </header>
      <main
        className="float-in-delay-5"
      >
        <div className="mood-grid float-in-delay-6">
          {moods.map((mood, idx) => (
            <button
              key={mood.id}
              onClick={() => handleMoodSelect(mood.id)}
              className={`mood-button float-in-delay-${7 + idx} ${selectedMood === mood.id ? 'selected' : ''} mood-${mood.id}`}
            >
              <span className={`button-text float-in-delay-${7 + idx}`}>{mood.label}</span>
            </button>
          ))}
        </div>
        {devices.length > 0 && (
          <div className="device-selector float-in-delay-17" style={{ marginBottom: 24 }}>
            <h3 className="float-in-delay-18">Select Device:</h3>
            <select
              className="float-in-delay-19"
              value={selectedDeviceId || ''}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
            >
              <option value="">Select a device</option>
              {devices.map((device, i) => (
                <option key={device.id || 'unknown_device'} value={device.id || ''} className={`float-in-delay-${20 + i}`}>
                  {device.name} ({device.type})
                </option>
              ))}
            </select>
          </div>
        )}
        {devices.length === 0 && (
          <p className="warning-message float-in-delay-20">
            No Spotify devices found. Please open Spotify on one of your devices and reload the page.
          </p>
        )}
        <button onClick={handleLogout} className="spotify-button logout float-in-delay-21" style={{ marginTop: 24 }}>
          Logout
        </button>
        {message && <p className="message float-in-delay-22" style={{ marginTop: 18 }}>{message}</p>}
      </main>
      <footer className="float-in-delay-23" style={{ marginTop: 32, fontSize: '0.95rem', color: '#b3b3b3', textAlign: 'center' }}>
        <p className="float-in-delay-24">Ensure Spotify is running on one of your devices. If you don't see your device listed, try refreshing the page.</p>
        <p className="float-in-delay-25">Spotify Premium may be required for certain playback controls.</p>
      </footer>
    </div>
  );
}

export default PlayerPage;