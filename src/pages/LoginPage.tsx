import React from 'react';
import { Navigate } from 'react-router-dom';

interface LoginPageProps {
  isAuthenticated: boolean;
  handleLogin: () => void;
  isLoading: boolean;
}

function LoginPage({ isAuthenticated, handleLogin, isLoading }: LoginPageProps) {
  if (isLoading) {
    return <div className="container">Checking authentication...</div>;
  }

  if (isAuthenticated) {
    return <Navigate to="/player" replace />;
  }

  return (
    <div className="container login-page">
      <header>
        <h1>Welcome to Spotify Mood Player</h1>
      </header>
      <main>
        <p>Play music that matches your mood!</p>
        <button onClick={handleLogin} className="spotify-button login">
          Login with Spotify
        </button>
      </main>
    </div>
  );
}

export default LoginPage;