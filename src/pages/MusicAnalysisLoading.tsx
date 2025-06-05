import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getApiEndpoint } from '../App';
import './MusicAnalysisLoading.css';

const MusicAnalysisLoading: React.FC = () => {
  return (
    <div className="loading-container">
      <div className="loading-modal">
        <div className="spinner"></div>
        <p>Analyzing your music library. This may take a few minutes...</p>
      </div>
    </div>
  );
};

export default MusicAnalysisLoading; 