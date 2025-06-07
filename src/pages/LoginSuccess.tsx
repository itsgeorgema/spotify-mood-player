import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MusicAnalysisLoading from './MusicAnalysisLoading';
import { getApiEndpoint } from '../App';

const LoginSuccess: React.FC<{ checkAuthStatus: () => Promise<void> }> = ({ checkAuthStatus }) => {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleLoginSuccess = async () => {
      try {
        await checkAuthStatus();
        setIsAnalyzing(true);
        setError(null);
        
        // Only trigger analysis once, right after login
        const response = await fetch(getApiEndpoint('/api/sentiment_analysis'), {
          method: 'POST',
          credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
          setError(data.error || 'Failed to analyze your library. Please try again.');
          return;
        }
        
        if (!data.message || !data.message.toLowerCase().includes('analyzed')) {
          setError('Analysis did not complete successfully. Please try again.');
          return;
        }
        
        // Success: redirect to player
        navigate('/player', { replace: true });
      } catch (error) {
        console.error('Login verification or analysis failed:', error);
        setError('Login verification or analysis failed. Please try again.');
      }
    };
    
    handleLoginSuccess();
  }, [checkAuthStatus, navigate]);

  if (error) {
    const handleReturnToLogin = async () => {
      // Call logout endpoint to clear authentication
      await fetch(getApiEndpoint('/api/logout'), {
        method: 'POST',
        credentials: 'include',
      });
      // Forcefully remove the session cookie on the client side
      document.cookie = 'session=; Max-Age=0; path=/; domain=' + window.location.hostname + ';';
      navigate('/', { replace: true });
    };
    return (
      <div className="app login-centered fade-in-up delay-1" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #1e1e1e, #2d2d2d)' }}>
        <div className="login-modal" style={{ background: 'rgba(24,24,24,0.97)', borderRadius: '24px', boxShadow: '0 12px 48px 0 rgba(0,0,0,0.45)', padding: '40px 32px', maxWidth: 420, width: '100%', textAlign: 'center' }}>
          <h2 className="login-title" style={{
            marginBottom: 16,
            fontSize: '2rem',
            fontWeight: 700,
            background: 'linear-gradient(135deg, #ff4d4f, #ff7875, #fff 100%)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            color: 'transparent',
            WebkitTextFillColor: 'transparent',
            textShadow: '0 0 16px #ff4d4f, 0 2px 8px rgba(255,77,79,0.08)',
          }}>Login or Analysis Failed</h2>
          <p className="subtitle" style={{ color: '#fff', marginBottom: 24, fontSize: '1.1rem' }}>{error}</p>
          <button
            onClick={handleReturnToLogin}
            className="spotify-button logout fade-in-up delay-2"
            style={{ marginTop: 16, width: '100%', fontSize: '1.1rem', padding: '14px 0', borderRadius: '16px', fontWeight: 600 }}
          >
            Return to Login
          </button>
        </div>
      </div>
    );
  }

  if (isAnalyzing) {
    return <MusicAnalysisLoading />;
  }

  return null;
};

export default LoginSuccess;