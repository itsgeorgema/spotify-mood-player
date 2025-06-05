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
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-6 bg-white rounded-lg shadow-md">
          <h2 className="text-xl font-semibold text-red-600 mb-4">Error</h2>
          <p className="text-gray-700 mb-4">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
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