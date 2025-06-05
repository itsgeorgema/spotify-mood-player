import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MusicAnalysisLoading from './MusicAnalysisLoading';
import { getApiEndpoint } from '../App';

const LoginSuccess: React.FC<{ checkAuthStatus: () => Promise<void> }> = ({ checkAuthStatus }) => {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  useEffect(() => {
    const handleLoginSuccess = async () => {
      try {
        await checkAuthStatus();
        setIsAnalyzing(true);
        // Only trigger analysis once, right after login
        const response = await fetch(getApiEndpoint('/api/sentiment_analysis'), {
          method: 'POST',
          credentials: 'include'
        });
        if (!response.ok) {
          // Handle error, maybe show a message or redirect
          navigate('/');
          return;
        }
        // Success: redirect to player
        navigate('/player', { replace: true });
      } catch (error) {
        console.error('Login verification or analysis failed:', error);
        navigate('/');
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