import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MusicAnalysisLoading from './MusicAnalysisLoading';
import { getApiEndpoint } from '../App';

const LoginSuccess: React.FC<{ 
  checkAuthStatus: () => Promise<{ isAuthenticated: boolean; hasCategorizedSongs: boolean }>;
}> = ({ checkAuthStatus }) => {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleLoginSuccess = async () => {
      try {
        // Check authentication status first and get the result immediately
        const authData = await checkAuthStatus();
        
        // If user already has categorized songs, go directly to player
        if (authData.hasCategorizedSongs) {
          console.log('User has categorized songs, redirecting to player');
          navigate('/player', { replace: true });
          return;
        }
        
        // User doesn't have categorized songs, start analysis
        console.log('User needs analysis, starting...');
        setIsAnalyzing(true);
        setError(null);
        
        // Only trigger analysis once, right after login
        const response = await fetch(getApiEndpoint('/api/analyze'), {
          method: 'POST',
          credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
          navigate('/failure', { replace: true, state: { error: data.error || 'Failed to analyze your library. Please try again.' } });
          return;
        }
        
        if (!data.message || !data.message.toLowerCase().includes('analyzed')) {
          navigate('/failure', { replace: true, state: { error: 'Analysis did not complete successfully. Please try again.' } });
          return;
        }
        
        // Success: redirect to player
        navigate('/player', { replace: true });
      } catch (error) {
        console.error('Login verification or analysis failed:', error);
        navigate('/failure', { replace: true, state: { error: 'Login verification or analysis failed. Please try again.' } });
      }
    };
    
    handleLoginSuccess();
  }, [checkAuthStatus, navigate]);

  if (isAnalyzing) {
    return <MusicAnalysisLoading />;
  }

  return null;
};

export default LoginSuccess;