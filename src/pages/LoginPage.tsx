import React, { useEffect, useState } from 'react';
import { Navigate, useNavigate, useLocation } from 'react-router-dom';
import MusicAnalysisLoading from './MusicAnalysisLoading';
import './LoginPage.css';

interface LoginPageProps {
  isAuthenticated: boolean;
  handleLogin: () => void;
  isLoading: boolean;
}

function LoginPage({ isAuthenticated, handleLogin, isLoading }: LoginPageProps) {
  const [animate, setAnimate] = useState(false);
  const [titleFloatDone, setTitleFloatDone] = useState(false);
  const [buttonFloatDone, setButtonFloatDone] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const error = params.get('error');
    if (error === 'auth_failed' || error === 'no_code') {
      navigate('/failure', {
        replace: true,
        state: {
          error: error === 'auth_failed'
            ? 'Login failed. Please try again.'
            : 'No code provided by Spotify. Please try logging in again.'
        }
      });
    }
  }, [location, navigate]);

  useEffect(() => {
    setTimeout(() => setAnimate(true), 10); // ensure after first paint
  }, []);

  // If not authenticated after login attempt, redirect to failure
  useEffect(() => {
    if (!isLoading && !isAuthenticated && location.state && location.state.justTriedLogin) {
      navigate('/failure', {
        replace: true,
        state: {
          error: 'Login failed. No session was established. Please try again.'
        }
      });
    }
  }, [isLoading, isAuthenticated, location, navigate]);

  if (isLoading) {
    return <MusicAnalysisLoading />;
  }

  if (isAuthenticated) {
    return <Navigate to="/player" replace />;
  }

  // Animation strings
  const floatIn = 'float-in 0.7s cubic-bezier(0.4,0,0.2,1) forwards';
  const bounceSmooth = 'bounce-smooth 2.2s ease-in-out infinite';

  return (
    <div className={["app", "login-centered", animate ? "float-in-delay-1" : ""].join(" ")}>
      <div className="login-content float-in-delay-2">
        <h1
          className="login-title"
          style={{
            animation: animate
              ? 'float-in 0.7s cubic-bezier(0.4,0,0.2,1) 0.2s both, bounce-smooth 2.2s ease-in-out infinite'
              : undefined
          }}
          onAnimationEnd={(e) => {
            if (e.animationName.includes('float-in')) setTitleFloatDone(true);
          }}
        >Mood Player</h1>
        <p className={["subtitle", animate ? "float-in-delay-4" : ""].join(" ")}>Your music, your mood</p>
        <p className={["tagline", animate ? "float-in-delay-5" : ""].join(" ")}>Let your feelings pick the soundtrack</p>
        <button
          className="spotify-button float-in-delay-6"
          style={{
            animation: !buttonFloatDone && animate
              ? `${floatIn}`
              : undefined,
            animationDelay: !buttonFloatDone && animate ? '0.7s' : '0s',
          }}
          onClick={handleLogin}
          onAnimationEnd={(e) => {
            if (e.animationName.includes('float-in')) setButtonFloatDone(true);
          }}
        >
          <span className={animate ? "spotify-logo float-in-delay-7" : ""} />
          Connect with Spotify
        </button>
      </div>
    </div>
  );
}

export default LoginPage;