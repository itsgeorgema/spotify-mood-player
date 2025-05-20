import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

interface LoginSuccessProps {
  checkAuthStatus: () => Promise<void>;
}

function LoginSuccess({ checkAuthStatus }: LoginSuccessProps) {
  const [isProcessing, setIsProcessing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    const processLogin = async () => {
      const params = new URLSearchParams(location.search);
      const loginSuccess = params.get('login_success');
      
      if (loginSuccess === 'true') {
        try {
          await checkAuthStatus();
          setIsProcessing(false);
        } catch (error) {
          console.error('Failed to verify authentication:', error);
          setError('Authentication verification failed');
          setIsProcessing(false);
        }
      } else {
        setError('Login was not successful');
        setIsProcessing(false);
      }
    };

    processLogin();
  }, [location.search, checkAuthStatus]);

  if (isProcessing) {
    return <div>Finalizing login...</div>;
  }

  if (error) {
    return <Navigate to="/" replace />;
  }

  return <Navigate to="/player" replace />;
}

export default LoginSuccess;