import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
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

  useEffect(() => {
    setTimeout(() => setAnimate(true), 10); // ensure after first paint
  }, []);

  if (isLoading) {
    return <MusicAnalysisLoading />;
  }

  if (isAuthenticated) {
    return <Navigate to="/player" replace />;
  }

  // Animation strings
  const fadeInUp = 'fadeInUp 0.8s cubic-bezier(0.4,0,0.2,1) forwards';
  const bounceSmooth = 'bounce-smooth 2.2s ease-in-out infinite';

  return (
    <div className={["app", "login-centered", animate ? "fade-in-up delay-1" : "fade-in-up-init"].join(" ")}>
      <div className="login-content">
        <h1
          className="login-title"
          style={{
            animation: !titleFloatDone && animate
              ? `${fadeInUp}, ${bounceSmooth}`
              : bounceSmooth,
            animationDelay: !titleFloatDone && animate ? '0.55s, 0s' : '0s',
          }}
          onAnimationEnd={(e) => {
            if (e.animationName.includes('fadeInUp')) setTitleFloatDone(true);
          }}
        >Mood Player</h1>
        <p className={["subtitle", animate ? "fade-in-up delay-5" : "fade-in-up-init"].join(" ")}>Your music, your mood</p>
        <p className={["tagline", animate ? "fade-in-up delay-6" : "fade-in-up-init"].join(" ")}>Let your feelings pick the soundtrack</p>
        <button
          className="spotify-button"
          style={{
            animation: !buttonFloatDone && animate
              ? `${fadeInUp}`
              : undefined,
            animationDelay: !buttonFloatDone && animate ? '0.7s' : '0s',
          }}
          onClick={handleLogin}
          onAnimationEnd={(e) => {
            if (e.animationName.includes('fadeInUp')) setButtonFloatDone(true);
          }}
        >
          <span className={animate ? "spotify-logo fade-in-up delay-9" : "spotify-logo fade-in-up-init"} />
          Connect with Spotify
        </button>
      </div>
    </div>
  );
}

export default LoginPage;