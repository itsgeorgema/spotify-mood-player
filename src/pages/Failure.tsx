import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './Failure.css';

interface FailureProps {
  handleLogout: () => Promise<void>;
}

const Failure: React.FC<FailureProps> = ({ handleLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();
  // Accept error message from location state or default
  const error = location.state?.error || 'Login or analysis failed. Please try again.';

  const handleLogoutClick = async () => {
    try {
      await handleLogout();
      navigate('/', { replace: true });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <div className="app failure-centered">
      <div className="failure-content">
        <h1 className="failure-title">Login or Analysis Failed</h1>
        <p className="failure-message">{error}</p>
        <button
          className="spotify-button"
          onClick={handleLogoutClick}
        >
          Return to Login
        </button>
      </div>
    </div>
  );
};

export default Failure; 