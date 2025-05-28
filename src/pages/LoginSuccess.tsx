import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MusicAnalysisLoading from './MusicAnalysisLoading';

const LoginSuccess: React.FC<{ checkAuthStatus: () => Promise<void> }> = ({ checkAuthStatus }) => {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  useEffect(() => {
    const handleLoginSuccess = async () => {
      try {
        await checkAuthStatus();
        setIsAnalyzing(true);
        // The actual sentiment analysis will be triggered by MusicAnalysisLoading component
        navigate('/analyzing');
      } catch (error) {
        console.error('Login verification failed:', error);
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